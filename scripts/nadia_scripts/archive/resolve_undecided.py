#!/usr/bin/env python
"""
resolve_undecided.py — decide the traversal rows the POM walk could not.

THE PROBLEM
-----------
verify_traversal resolves a transitively-supplied library version by walking POMs over
HTTP (resolve_version.py). That walk cannot see through a BOM or a parent POM it cannot
fetch, so it gives up and the row is recorded as:

    "no declared-version crossing, and the transitive version could not be resolved
     for N commit(s) (BOM/parent-managed or unavailable POM) — undecided,
     confirm with `mvn dependency:tree`"

Measured on the snakeyaml bump-axis corpus (2026-08-07), 27 of 30 traversal REJECTIONS
were this message and only 2 were a genuine "client born past the boundary". So ~90% of
rejections are UNDECIDED rather than negative, which makes every traversal-confirmed
count in the census a FLOOR rather than a measurement. This script closes that gap by
doing what the message says: asking Maven itself.

WHAT IT DOES
------------
For each undecided row: shallow-fetch the repo at two commits, run
`mvn dependency:tree -Dincludes=<g>:<a>` in the module that owns the build file, and
compare the two resolved versions against the boundary.

WHAT IT DOES NOT DO — read this before using the output
-------------------------------------------------------
This is an ENDPOINT comparison, not a per-commit bump search. It answers "did the
effective version cross the boundary somewhere inside the scanned window?" It does NOT
identify which commit did the bumping, so a confirmation here carries
`traversal_kind: "endpoint"` and NO bump_sha. That is weaker evidence than a
verify_traversal confirmation and must not be merged into the same column without saying
so. It is the difference between "this client crossed" and "this commit is the crossing".

Endpoint comparison is what makes the cost bearable: 2 Maven invocations per candidate
instead of 2 per scanned commit. Resolving every commit properly would be ~30x this.

Usage:
  python resolve_undecided.py <break_id> --in output/<corpus>.jsonl [--limit N]
"""

# Scripts live one level down (discover/, mine/, traversal/, screen/, verify/) since
# the 2026-08 reorganisation, but they still import each other by module name and
# resolve data paths (output/, specs/, verified_cases/) against nadia_scripts/.
# This puts that root on sys.path so both keep working from anywhere.
import pathlib as _pl, sys as _sys
_NS_ROOT = _pl.Path(__file__).resolve().parent.parent
for _d in (_NS_ROOT, *(_NS_ROOT / _s for _s in
           ('discover', 'mine', 'traversal', 'screen', 'verify', 'archive', 'ledger', 'agent'))):
    if str(_d) not in _sys.path:
        _sys.path.insert(0, str(_d))


import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import bbc_e2e as B
from paths import str_m2

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent.parent

MVN_TIMEOUT = int(os.environ.get("BBC_MVN_TIMEOUT", "420"))
# Resolved by paths.m2_repo() rather than derived here. This line used to build
# `<toolkit>/../.bbc_m2` itself, which is a THIRD location -- not ~/.m2, and not the
# repo-root .bbc_m2 the verified runs actually used. Nothing errors when that is wrong;
# Maven just re-downloads the world into an empty directory beside the populated one.
# Override with BBC_M2_REPO.
M2 = str_m2()
SETTINGS = os.environ.get("BBC_MVN_SETTINGS")  # optional -s file


def _rmtree(path):
    def onerr(func, p, _):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:
            pass
    shutil.rmtree(path, onerror=onerr)


def shallow_fetch(repo, sha, dest):
    """Fetch exactly one commit. Avoids cloning history we will never read."""
    dest.mkdir(parents=True, exist_ok=True)
    cmds = [
        ["git", "init", "-q"],
        ["git", "config", "core.longpaths", "true"],   # Windows MAX_PATH; see cspace
        ["git", "remote", "add", "origin", f"https://github.com/{repo}.git"],
        ["git", "fetch", "-q", "--depth", "1", "origin", sha],
        ["git", "checkout", "-q", "FETCH_HEAD"],
    ]
    for c in cmds:
        r = subprocess.run(c, cwd=dest, capture_output=True, text=True,
                           errors="replace", timeout=MVN_TIMEOUT)
        if r.returncode != 0 and c[1] not in ("config", "init"):
            return False, f"{c[1]}: {(r.stderr or '').strip()[:120]}"
    return True, None


def mvn_resolved_version(project_dir, buildfile, group_id, artifact_id):
    """Effective version of g:a per `mvn dependency:tree`, or (None, reason)."""
    module = (project_dir / buildfile).parent
    if not (module / "pom.xml").exists():
        # The module may not exist yet at the OLD commit (added later), or the path
        # guessed from the adaptation's source layout may be wrong. Fall back to the
        # repository root, which still yields the effective version for a single-module
        # project and for the aggregator's own dependency set.
        if (project_dir / "pom.xml").exists():
            module = project_dir
        else:
            return None, "no pom at module path or repo root"
    # Write the tree to a FILE rather than reading stdout. `-q` suppresses INFO, which is
    # the level dependency:tree prints at, so a quiet run yields an empty tree and looks
    # exactly like "the artifact is not a dependency" -- a false negative that would have
    # been indistinguishable from a real one. -DoutputFile is log-level independent.
    tree = module / "_bbc_tree.txt"
    cmd = ["mvn", "-B", "dependency:tree",
           f"-Dincludes={group_id}:{artifact_id}",
           f"-DoutputFile={tree.name}", "-DoutputType=text",
           f"-Dmaven.repo.local={M2}",
           "-Denforcer.skip=true", "-Dmaven.javadoc.skip=true"]
    if SETTINGS:
        cmd[1:1] = ["-s", SETTINGS]
    try:
        r = subprocess.run(cmd, cwd=module, capture_output=True, text=True,
                           errors="replace", timeout=MVN_TIMEOUT, shell=True)
    except subprocess.TimeoutExpired:
        return None, f"mvn timeout after {MVN_TIMEOUT}s"
    out = ""
    if tree.exists():
        out = tree.read_text(encoding="utf-8", errors="replace")
    out += (r.stdout or "")
    # dependency:tree prints e.g. "[INFO] +- org.yaml:snakeyaml:jar:1.33:compile"
    pat = re.compile(rf"{re.escape(group_id)}:{re.escape(artifact_id)}:[\w.-]+:([\w.\-+]+)")
    hits = pat.findall(out)
    if hits:
        return hits[0], None
    if r.returncode != 0:
        first = next((l for l in (r.stdout or "").splitlines()
                      if "ERROR" in l), "")
        return None, f"mvn failed rc={r.returncode} {first[:110]}"
    return None, "artifact absent from the resolved tree"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("break_id")
    ap.add_argument("--in", dest="infile", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--keep-clones", action="store_true")
    args = ap.parse_args()

    brk = B.get_break(args.break_id)
    lib = brk["library"]
    gid, aid = lib["group_id"], lib["artifact_id"]
    boundary = (brk.get("verify") or {}).get("break_boundary")
    token = B._token()
    print(f"[resolve] {gid}:{aid} boundary={boundary}")

    src = Path(args.infile)
    rows = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    # Rows the POM walk explicitly could not decide. Anything else is already answered.
    todo = [r for r in rows
            if (r.get("traversal") or {}).get("resolution") == "unresolved"]
    if args.limit:
        todo = todo[:args.limit]
    print(f"[resolve] {len(todo)} undecided row(s) of {len(rows)}\n")

    # Append each decision as it is made. Each row costs two shallow fetches and two
    # Maven runs -- minutes -- so accumulating in memory and writing at the end means a
    # kill throws away the whole pass. That happened on the xstream run at row 23 of 33.
    # This is the THIRD time the same mistake has cost a pass today (the commit search
    # and the classify loop were both fixed for it earlier), so it is fixed here the
    # same way rather than retried.
    dst = src.with_name(src.stem + "_MVNRECHECK.jsonl")
    done_keys = set()
    if dst.exists() and os.environ.get("BBC_RESUME", "1").lower() not in ("0", "false", "no"):
        for line in dst.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                prev = json.loads(line)
            except Exception:
                continue
            done_keys.add((prev.get("repo"), prev.get("sha")))
        if done_keys:
            print(f"[resolve] resuming: {len(done_keys)} row(s) already decided\n")
    fh = dst.open("a" if done_keys else "w", encoding="utf-8")

    tally = {"crossed": 0, "not_crossed": 0, "still_undecided": 0}
    out = []
    for i, r in enumerate(todo, 1):
        repo, sha = r["repo"], r["sha"]
        if (repo, sha) in done_keys:
            continue
        bfs = [f for f in (r.get("production_files") or [])]
        buildfile = "pom.xml"
        # Prefer the module pom nearest the adaptation, matching bbc_e2e's own choice.
        for f in bfs:
            if "/src/main/" in f:
                cand = f.split("/src/main/")[0] + "/pom.xml"
                buildfile = cand
                break

        parent = r.get("parent")
        if not parent:
            c = B._gh(f"{B.GH}/repos/{repo}/commits/{sha}", token)
            parent = (c.get("parents") or [{}])[0].get("sha") if isinstance(c, dict) else None
        if not parent:
            print(f"[{i}/{len(todo)}] {repo}@{sha[:8]}  no parent commit")
            tally["still_undecided"] += 1
            continue

        work = Path(tempfile.mkdtemp(prefix="bbcres_"))
        verdict, detail, vnew, vold = "still_undecided", None, None, None
        try:
            for label, csha in (("new", sha), ("old", parent)):
                d = work / label
                ok, err = shallow_fetch(repo, csha, d)
                if not ok:
                    detail = f"fetch {label}: {err}"
                    break
                v, why = mvn_resolved_version(d, buildfile, gid, aid)
                if v is None:
                    detail = f"{label}: {why}"
                    break
                if label == "new":
                    vnew = v
                else:
                    vold = v
            if vnew and vold:
                if B._crosses_boundary(vold, vnew, boundary):
                    verdict, detail = "crossed", f"{vold} -> {vnew}"
                else:
                    verdict, detail = "not_crossed", f"{vold} -> {vnew}"
        finally:
            if not args.keep_clones:
                _rmtree(work)

        tally[verdict] += 1
        r.setdefault("traversal", {})["mvn_recheck"] = {
            "verdict": verdict, "detail": detail,
            "resolved_old": vold, "resolved_new": vnew,
            "buildfile": buildfile,
            "method": "mvn dependency:tree, ENDPOINT comparison (adapt vs parent) — "
                      "establishes that a crossing occurred, NOT which commit made it",
            "traversal_kind": "endpoint",
        }
        mark = {"crossed": "CROSS", "not_crossed": " no  ",
                "still_undecided": "  ?  "}[verdict]
        print(f"[{i}/{len(todo)}] [{mark}] {repo}@{sha[:8]}  {detail}", flush=True)
        fh.write(json.dumps(r) + "\n")
        fh.flush()
        out.append(r)

    fh.close()
    print(f"\n[resolve] this run: {tally}")
    print(f"[resolve] saved -> {dst} (append-per-row; may also hold resumed rows)")


if __name__ == "__main__":
    main()
