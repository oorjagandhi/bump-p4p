#!/usr/bin/env python
"""
validate_worklists.py — check that every worklist row's `build_system` is true.

WHY THIS EXISTS
---------------
The verification harness is Maven. A row tagged `"build_system": "maven"` that is
actually Gradle gets dispatched, fails at setup with "version knob does not work", and
the failure reads like a fact about the client rather than a routing mistake.

That happened to The-Ant-Forge/TVRenamer on 2026-08-15: tagged maven, has no pom.xml at
any commit in its history, and it cost a full agent invocation before anyone opened the
repository. Running this check found a SECOND one nobody had hit yet
(PetteriM1/NukkitPetteriM1Edition), which is the argument for running it before a fan-out
rather than after a failure.

The tag comes from classify's `_detect_build_system`, which reads the build file at the
adaptation commit. It can be wrong when the API call fails, when the repo layout is
unusual, or when a row was hand-written.

Usage:
  python agent/validate_worklists.py            # check every worklist
  python agent/validate_worklists.py --fix      # rewrite wrong tags in place
Exit code is 1 when a mis-tag is found, so this can gate a fan-out in CI.
"""

import pathlib as _pl, sys as _sys
_NS_ROOT = _pl.Path(__file__).resolve().parent.parent
if str(_NS_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_NS_ROOT))

import argparse
import glob
import json
import os
import urllib.request

GH = "https://api.github.com"
BUILD_FILES = [("pom.xml", "maven"), ("build.gradle", "gradle"),
               ("build.gradle.kts", "gradle"), ("build.sbt", "sbt")]


def _exists(repo, path, ref, token):
    url = f"{GH}/repos/{repo}/contents/{path}" + (f"?ref={ref}" if ref else "")
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
    try:
        urllib.request.urlopen(req, timeout=20)
        return True
    except Exception:
        return False


def actual_build_system(repo, ref, token):
    """First build file that exists wins, in the same order classify uses."""
    for fname, system in BUILD_FILES:
        if _exists(repo, fname, ref, token):
            return system
    return "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true", help="rewrite wrong tags in place")
    args = ap.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GH_TOKEN required")

    agent_dir = _NS_ROOT / "agent"
    files = sorted(glob.glob(str(agent_dir / "worklist_*.json"))) + \
            sorted(glob.glob(str(agent_dir / "reverify_*.json")))

    checked, bad = 0, []
    for f in files:
        try:
            rows = json.loads(pathlib_read(f))
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        dirty = False
        for r in rows:
            repo, claim = r.get("repo"), r.get("build_system")
            if not repo or not claim:
                continue
            checked += 1
            real = actual_build_system(repo, r.get("adapt_sha"), token)
            if real != claim:
                bad.append((os.path.basename(f), repo, claim, real))
                if args.fix:
                    r["build_system"] = real
                    dirty = True
        if dirty:
            with open(f, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(rows, fh, indent=1, ensure_ascii=False)
                fh.write("\n")
            print(f"[fixed] {os.path.basename(f)}")

    print(f"\nchecked {checked} rows across {len(files)} worklists")
    if bad:
        print("MIS-TAGGED:")
        for src, repo, claim, real in bad:
            print(f"  {repo}  claims {claim}, is {real}   ({src})")
        print("\nA Maven-tagged Gradle row will fail at setup and the failure will look "
              "like a client fact. Fix the tag (or pass --fix) before fanning out.")
        raise SystemExit(1)
    print("all build_system tags correct")


def pathlib_read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


if __name__ == "__main__":
    main()
