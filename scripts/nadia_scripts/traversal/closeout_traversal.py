#!/usr/bin/env python
"""
closeout_traversal.py — decide the rows `resolve_undecided.py` still could not.

WHY A SECOND PASS EXISTS
------------------------
resolve_undecided.py runs `mvn dependency:tree` in ONE module: the one guessed from the
adaptation's changed file path (`<x>/src/main/...` -> `<x>/pom.xml`). In a multi-module
repo the module that changed is frequently NOT the module that declares the dependency, so
the goal reports "artifact absent from the resolved tree" — which reads like a measurement
("this project does not use the library") but is really an artefact of where we pointed
Maven. 11 of kubernetes-client's 16 unresolved rows have exactly that detail.

This pass re-runs the same question at the REACTOR ROOT. `dependency:tree` executes per
module across the whole reactor, so a root run sees every module's dependencies and
answers the question the module-scoped run could not.

WHAT IT DOES NOT FIX
--------------------
Rows that failed because Maven itself errored (bad parent POM, plugin failure, a JVM
crash) or because the git fetch failed. Those are recorded unchanged: a second run in the
same conditions produces the same error, and re-running to no purpose is how a pass gets
mistaken for new evidence.

Verdicts carry `traversal_kind: "endpoint-root"` — an ENDPOINT comparison, like the pass
before it. It establishes that a crossing occurred somewhere in the scanned window, NOT
which commit made it. That is weaker than a verify_traversal confirmation and must not be
merged into the same column without saying so.

Usage:
  python closeout_traversal.py <break_id>            # reads *_UNDECIDED_MVNRECHECK.jsonl
  python closeout_traversal.py <break_id> --limit 4
  python closeout_traversal.py <break_id> --timeout 900
"""

# Scripts live one level down (discover/, mine/, traversal/, screen/, verify/) since
# the 2026-08 reorganisation, but they still import each other by module name and
# resolve data paths (output/, specs/, verified_cases/) against nadia_scripts/.
# This puts that root on sys.path so both keep working from anywhere.
import pathlib as _pl, sys as _sys
_NS_ROOT = _pl.Path(__file__).resolve().parent.parent
for _d in (_NS_ROOT, *(_NS_ROOT / _s for _s in
           ('discover', 'mine', 'traversal', 'screen', 'verify'))):
    if str(_d) not in _sys.path:
        _sys.path.insert(0, str(_d))


import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import bbc_e2e as B
import resolve_undecided as RU

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent.parent
OUT = HERE / "output"

# Only these are worth a second attempt; see "WHAT IT DOES NOT FIX".
RETRYABLE = "absent from the resolved tree"


def root_resolved_version(project_dir, group_id, artifact_id, timeout):
    """Effective version of g:a anywhere in the reactor, run from the repo root."""
    if not (project_dir / "pom.xml").exists():
        return None, "no pom.xml at repo root"
    tree = project_dir / "_bbc_root_tree.txt"
    cmd = ["mvn", "-B", "dependency:tree",
           f"-Dincludes={group_id}:{artifact_id}",
           f"-DoutputFile={tree.name}", "-DoutputType=text",
           f"-Dmaven.repo.local={RU.M2}",
           "-Denforcer.skip=true", "-Dmaven.javadoc.skip=true",
           # a broken module must not abort the reactor before the module we need
           "--fail-never"]
    if RU.SETTINGS:
        cmd[1:1] = ["-s", RU.SETTINGS]
    try:
        r = subprocess.run(cmd, cwd=project_dir, capture_output=True, text=True,
                           errors="replace", timeout=timeout, shell=True)
    except subprocess.TimeoutExpired:
        return None, f"mvn timeout after {timeout}s at root"
    out = ""
    # -DoutputFile writes one file per module, so collect every one the reactor produced.
    for f in project_dir.rglob("_bbc_root_tree.txt"):
        try:
            out += f.read_text(encoding="utf-8", errors="replace") + "\n"
        except Exception:
            pass
    out += (r.stdout or "")
    hits = RU.re.findall(
        rf"{RU.re.escape(group_id)}:{RU.re.escape(artifact_id)}:[\w.-]+:([\w.\-+]+)", out)
    if hits:
        return hits[0], None
    return None, "artifact absent from the whole reactor"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("break_id")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--timeout", type=int, default=900)
    args = ap.parse_args()

    brk = B.get_break(args.break_id)
    lib = brk["library"]
    gid, aid = lib["group_id"], lib["artifact_id"]
    boundary = (brk.get("verify") or {}).get("break_boundary")
    print(f"[closeout] {gid}:{aid} boundary={boundary}")

    src = OUT / f"{args.break_id}_UNDECIDED_MVNRECHECK.jsonl"
    if not src.exists():
        sys.exit(f"no recheck output at {src}")
    rows = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]

    todo, skipped = [], []
    for r in rows:
        mr = (r.get("traversal") or {}).get("mvn_recheck") or {}
        if mr.get("verdict") != "still_undecided":
            continue
        (todo if RETRYABLE in (mr.get("detail") or "") else skipped).append(r)
    if args.limit:
        todo = todo[:args.limit]
    print(f"[closeout] {len(todo)} retryable at reactor root, "
          f"{len(skipped)} not retryable (mvn/git errors, unchanged)\n")

    dst = OUT / f"{args.break_id}_TRAVERSAL_CLOSEOUT.jsonl"
    done = set()
    if dst.exists() and os.environ.get("BBC_RESUME", "1").lower() not in ("0", "false", "no"):
        for line in dst.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    prev = json.loads(line)
                    done.add((prev.get("repo"), prev.get("sha")))
                except Exception:
                    pass
        if done:
            print(f"[closeout] resuming: {len(done)} row(s) already decided\n")
    fh = dst.open("a" if done else "w", encoding="utf-8")

    tally = {"crossed": 0, "not_crossed": 0, "still_undecided": 0}
    for i, r in enumerate(todo, 1):
        repo, sha, parent = r["repo"], r["sha"], r.get("parent")
        if (repo, sha) in done:
            continue
        work = Path(tempfile.mkdtemp(prefix="bbcclose_"))
        verdict, detail, vnew, vold = "still_undecided", None, None, None
        try:
            for label, csha in (("new", sha), ("old", parent)):
                if not csha:
                    detail = f"{label}: no commit sha"
                    break
                d = work / label
                ok, err = RU.shallow_fetch(repo, csha, d)
                if not ok:
                    detail = f"fetch {label}: {err}"
                    break
                v, why = root_resolved_version(d, gid, aid, args.timeout)
                if v is None:
                    detail = f"{label}: {why}"
                    break
                if label == "new":
                    vnew = v
                else:
                    vold = v
            if vnew and vold:
                crossed = B._crosses_boundary(vold, vnew, boundary)
                verdict = "crossed" if crossed else "not_crossed"
                detail = f"{vold} -> {vnew}"
        finally:
            RU._rmtree(work)

        tally[verdict] += 1
        r.setdefault("traversal", {}).setdefault("mvn_recheck", {})
        r["traversal"]["closeout"] = {
            "verdict": verdict, "detail": detail,
            "resolved_old": vold, "resolved_new": vnew,
            "method": "mvn dependency:tree at the REACTOR ROOT (--fail-never), ENDPOINT "
                      "comparison — establishes that a crossing occurred, NOT which commit "
                      "made it",
            "traversal_kind": "endpoint-root",
        }
        mark = {"crossed": "CROSS", "not_crossed": " no  ", "still_undecided": "  ?  "}[verdict]
        print(f"[{i}/{len(todo)}] [{mark}] {repo}@{sha[:8]}  {detail}", flush=True)
        fh.write(json.dumps(r) + "\n")
        fh.flush()
    fh.close()

    print(f"\n[closeout] this run: {tally}")
    print(f"[closeout] {len(skipped)} row(s) left untouched (not retryable)")
    print(f"[closeout] saved -> {dst}")


if __name__ == "__main__":
    main()
