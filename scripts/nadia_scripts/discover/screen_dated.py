#!/usr/bin/env python3
"""
Turn dated code-search rows into candidate verdicts: is this repo's adaptation a genuine
RECOVERY from the break, or noise that merely mentions the API?

Runs after discover/date_hits.py. Three filters, cheapest first, because each costs API
calls and the population is mostly noise:

  1. WINDOW   -- the adaptation must land in the crossing window. A call written in 2026
                 is a project born long past the boundary configuring a limit it never
                 hit; it cannot be a case however real the call looks.
  2. VALUE    -- what the client SETS decides. Raising a limit above the library's default
                 is a recovery: they hit the cap and lifted it. Setting exactly the default
                 is a knob -- config plumbing that changes no behaviour. Lowering it is
                 hardening, the opposite of a break response. This is the filter that does
                 most of the work, and it is why the knob defaults must be per-API.
  3. BUILD    -- Maven only, because that is what the differential verifier drives.

A repo surviving all three is a CANDIDATE, not a case: it still needs traversal (did it
actually cross 2.14 -> 2.15?) and then the 3-state differential.

Resumes by repo.
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

import argparse, json, os, sys
from collections import Counter
from pathlib import Path

import bbc_e2e as B
from find_adaptations import classify

HERE = Path(__file__).resolve().parent.parent


def added_lines(repo, sha, path, token):
    """Lines ADDED to `path` by `sha`. The removed side is not evidence of adaptation."""
    c = B._gh(f"{B.GH}/repos/{repo}/commits/{sha}", token)
    if not isinstance(c, dict):
        return []
    for f in c.get("files", []):
        if f.get("filename") == path:
            patch = f.get("patch") or ""
            return [l[1:] for l in patch.split("\n")
                    if l.startswith("+") and not l.startswith("+++")]
    return []


def is_maven(repo, token):
    """Does the repo build with Maven? Root pom.xml is the cheap, reliable signal."""
    r = B._gh(f"{B.GH}/repos/{repo}/contents/pom.xml", token)
    return isinstance(r, dict) and r.get("name") == "pom.xml"


def repo_meta(repo, token):
    r = B._gh(f"{B.GH}/repos/{repo}", token)
    if not isinstance(r, dict):
        return {}
    return {"stars": r.get("stargazers_count"), "fork": r.get("fork"),
            "archived": r.get("archived")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dated", required=True, help="JSONL from date_hits.py")
    ap.add_argument("--out", required=True)
    ap.add_argument("--knob", action="append", required=True, metavar="NAME=DEFAULT",
                    help="an adaptation API and the library's own default, repeatable")
    ap.add_argument("--window-start", required=True, help="YYYY-MM-DD, the boundary")
    ap.add_argument("--window-end", required=True,
                    help="YYYY-MM-DD; past this a client is born beyond the boundary")
    ap.add_argument("--library-class",
                    help="class holding the library's own default constants, e.g. "
                         "StreamReadConstraints; an argument that IS one is a knob")
    ap.add_argument("--group-id", help="library group id, to reject the library's own repos")
    ap.add_argument("--artifact-id", default="", help="library artifact id, same purpose")
    args = ap.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GH_TOKEN required")

    knobs = {}
    for k in args.knob:
        name, _, dflt = k.partition("=")
        knobs[name] = int(dflt)

    rows = [json.loads(l) for l in Path(args.dated).read_text(encoding="utf-8").splitlines()
            if l.strip()]
    dated = [r for r in rows if r.get("date")]
    in_window = [r for r in dated
                 if args.window_start <= r["date"] <= args.window_end]
    print(f"[screen] {len(rows)} rows, {len(dated)} dated, "
          f"{len(in_window)} inside {args.window_start}..{args.window_end}")

    outp = Path(args.out)
    done = set()
    if outp.exists():
        for line in outp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["repo"])
    todo = [r for r in in_window if r["repo"] not in done]
    print(f"[screen] {len(done)} already screened, {len(todo)} to go\n")

    with outp.open("a", encoding="utf-8") as fh:
        for i, r in enumerate(todo, 1):
            out = dict(r)
            # Filter 0, free: is this repo the LIBRARY rather than a client? FasterXML's
            # own repos date before the boundary because that is where the feature was
            # written -- the changed file is the API definition, not a use of it.
            if args.group_id and B._is_library_source(
                    r["repo"], [r["path"]], args.group_id, args.artifact_id):
                out["screen"] = "library_source"
                fh.write(json.dumps(out) + "\n"); fh.flush()
                print(f"  [{i}/{len(todo)}] {r['repo']:<42} {r['date']}  library_source")
                continue
            try:
                lines = added_lines(r["repo"], r["sha"], r["path"], token)
                verdicts = {}
                for name, dflt in knobs.items():
                    if any(name in l for l in lines):
                        v, val, ev = classify(lines, name, dflt,
                                             library_class=args.library_class)
                        verdicts[name] = {"verdict": v, "value": val, "evidence": ev}
                out["knobs"] = verdicts
                vs = {d["verdict"] for d in verdicts.values()}
                # ANY raise makes it a recovery: clients raise only the limit that broke
                # them, and leave the others at the library's value (AthenZ raised
                # maxStringLength alone). Requiring every knob to be raised would reject
                # exactly the best-diagnosed adaptations.
                if "raise" in vs:
                    out["screen"] = "raise"
                elif "needs_reading" in vs:
                    out["screen"] = "needs_reading"
                elif vs:
                    out["screen"] = "knob_at_default" if "knob_at_default" in vs else "lower"
                else:
                    out["screen"] = "no_call_in_diff"
                if out["screen"] in ("raise", "needs_reading"):
                    out["maven"] = is_maven(r["repo"], token)
                    out.update(repo_meta(r["repo"], token))
            except Exception as e:
                out["screen"] = "error"
                out["error"] = f"{type(e).__name__}: {e}"[:200]
            fh.write(json.dumps(out) + "\n")
            fh.flush()
            tag = out["screen"]
            extra = f" maven={out.get('maven')} stars={out.get('stars')}" if "maven" in out else ""
            print(f"  [{i}/{len(todo)}] {r['repo']:<42} {r['date']}  {tag}{extra}")

    allrows = [json.loads(l) for l in outp.read_text(encoding="utf-8").splitlines() if l.strip()]
    print("\n[screen] verdicts: " +
          ", ".join(f"{k}:{v}" for k, v in Counter(x["screen"] for x in allrows).most_common()))
    keep = [x for x in allrows if x["screen"] in ("raise", "needs_reading") and x.get("maven")]
    print(f"[screen] CANDIDATES (raise/needs_reading + maven): {len(keep)}")
    for x in sorted(keep, key=lambda z: -(z.get("stars") or 0)):
        print(f"    {x['repo']:<44} {x['date']}  {x['screen']:<14} "
              f"stars={x.get('stars')} fork={x.get('fork')}")


if __name__ == "__main__":
    main()
