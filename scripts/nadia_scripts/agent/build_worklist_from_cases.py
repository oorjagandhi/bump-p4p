#!/usr/bin/env python3
"""
Build an agent worklist from ALREADY-VERIFIED case files, to re-verify them with the agent.

WHY THIS EXISTS. fanout.py builds worklists from the mined candidate corpus and marks
anything already in verified_cases/ as `already_recorded`, which is right for finding NEW
cases and wrong for the other thing you want the agent to do: reproduce known answers.

Re-verification is the only measurement of the agent that is unambiguous. On a fresh
candidate a `failed` outcome is indistinguishable between "the agent could not express this
build" and "this client is genuinely not a case" — the snakeyaml corpus needed all five of
its failures diagnosed by hand before anyone could tell which was which. Against a case
already verified by other means, a disagreement is just a disagreement, and it points at
the agent.

Usage:
  python build_worklist_from_cases.py <break_id> <case-dir-glob> [-o worklist.json]
  python build_worklist_from_cases.py xstream-1.4.17-to-1.4.19-forbiddenclass "xstream/*.json"
"""
from __future__ import annotations
import argparse, glob, json, os, re, sys, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import orchestrator as O

CASES = os.path.join(O.NADIA, "verified_cases")


def github_parent(repo: str, sha: str) -> str | None:
    """First parent of `sha`, for cases whose file never recorded one."""
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not tok:
        return None
    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/commits/{sha}",
        headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"})
    try:
        parents = json.load(urllib.request.urlopen(req)).get("parents", [])
        return parents[0]["sha"] if parents else None
    except Exception as e:
        print(f"  ! could not fetch parent for {repo}@{sha}: {e}", file=sys.stderr)
        return None


def clean_paths(entries) -> list:
    """Source paths out of a files_changed list.

    These lists are written for humans and carry annotations —
    "services/id/service/pom.xml (xstream 1.4.10 -> 1.4.19)" — so the raw strings are not
    paths. SEAM_A passes them to `git show -- <paths>`, where an annotated one silently
    matches nothing. Keep the leading token, keep only .java (a pom diff tells SEAM_A
    nothing about the production call it has to drive).
    """
    out = []
    for e in entries or []:
        path = re.split(r"\s*\(", str(e).strip())[0].strip()
        if path.endswith(".java"):
            out.append(path)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("break_id")
    ap.add_argument("pattern", help="glob under verified_cases/, e.g. 'xstream/*.json'")
    ap.add_argument("-o", "--out")
    args = ap.parse_args()

    brk = O.load_break(args.break_id)
    boundary = brk.get("verify", {}).get("break_boundary") or brk["library"]["to_version"]

    items, skipped = [], []
    for f in sorted(glob.glob(os.path.join(CASES, args.pattern))):
        case = json.load(open(f, encoding="utf-8"))
        name = os.path.basename(f)
        adapt = case.get("adaptation", {}) or {}
        trav = case.get("traversal", {}) or {}
        trans = case.get("in_repo_version_transition", {}) or {}
        lib = case.get("library", {}) or {}

        repo, sha = adapt.get("repo"), adapt.get("commit")
        if not repo or not sha:
            skipped.append((name, "no adaptation.repo/commit"))
            continue

        parent = adapt.get("parent") or adapt.get("parent_commit") or github_parent(repo, sha)
        if not parent:
            skipped.append((name, "no parent recorded and none fetchable"))
            continue

        prod = clean_paths(adapt.get("production_files_changed") or adapt.get("files_changed")
                           or adapt.get("production_files"))

        # The module the driver has to live in, or it cannot see the classes it drives.
        # Prefer the recorded build file; fall back to the source path, because several
        # cases record no buildfile at all and would otherwise be filed at the root —
        # openmrs (api/src/main/...) and artshishkin (core/src/main/...) are both
        # multi-module, and a driver written to the reactor root compiles against nothing.
        buildfile = trav.get("buildfile") or ""
        if buildfile not in ("", "pom.xml"):
            module = os.path.dirname(buildfile)
        elif prod and "/src/" in prod[0]:
            module = prod[0].split("/src/")[0]      # "" when src/ is at the repo root
        else:
            module = ""

        items.append({
            "break_id": args.break_id,
            "repo": repo,
            "adapt_sha": sha,
            "parent_sha": parent,
            "build_system": "maven",
            "module": module,
            "production_files": prod,
            "message": (adapt.get("message") or "")[:100],
            "crossing": {
                "boundary": boundary,
                "from": trav.get("from") or lib.get("baseline_used") or lib.get("from_version"),
                "to": trav.get("to") or lib.get("at_version") or lib.get("to_version"),
                "sha": trans.get("bump_sha") or trans.get("bump_commit"),
            },
            "status": "reverify",
            "known_outcome": case.get("status"),      # the answer we are checking against
            "case_file": os.path.relpath(f, O.NADIA),
        })

    out = args.out or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   f"reverify_{args.break_id}.json")
    json.dump(items, open(out, "w", encoding="utf-8", newline="\n"), indent=1)
    print(f"{len(items)} case(s) -> {out}")
    for i in items:
        print(f"  {i['repo']:56} {i['crossing']['from']}->{i['crossing']['to']} "
              f"module={i['module'] or '(root)':18} files={len(i['production_files'])}")
    for name, why in skipped:
        print(f"  [skip] {name}: {why}")


if __name__ == "__main__":
    main()
