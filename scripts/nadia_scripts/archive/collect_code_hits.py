#!/usr/bin/env python3
"""
Collect a raw code-search hit set: every (repo, path) whose CURRENT content contains
the adaptation identifier. Dates nothing -- that is date_hits.py's job.

WHY THIS IS SEPARATE FROM find_adaptations.py --via code-search
---------------------------------------------------------------
find_adaptations' code-search path finds the same files but then dates them inline,
and it does so in two ways that are now known to be wrong:

  * ONE FILE PER REPO. Its `by_repo.setdefault(repo, path)` keeps whichever path the
    search happened to return first. That is the same defect fixed in date_hits.py on
    2026-08-13: 47% of repos in the jackson corpus matched more than one file, and
    dating by an arbitrary one ejected datahub, trino, tika, nifi and besu from the
    crossing window entirely. Whatever the arbitrary file's date says, it is not the
    repo's adaptation date.
  * LINEAR WALK. `introducing_commit` fetches content at each commit oldest-first --
    up to 100 fetches per file, where date_hits bisects in ~7.

Keeping collection and dating apart means the expensive, rate-limited search runs once
and its output can be re-dated as often as the dating logic improves. That is exactly
what happened to jackson: the hit set from the original run was re-dated twice without
re-searching.

Output format matches output/_jackson_codesearch_hits.json -- a flat JSON list of
[repo, path] pairs -- which is what date_hits.py --hits expects.
"""
import pathlib as _pl, sys as _sys
_NS_ROOT = _pl.Path(__file__).resolve().parent.parent
for _d in (_NS_ROOT, *(_NS_ROOT / _s for _s in
           ('discover', 'mine', 'traversal', 'screen', 'verify', 'archive', 'ledger', 'agent'))):
    if str(_d) not in _sys.path:
        _sys.path.insert(0, str(_d))

import argparse, json, os, sys

from find_adaptations import code_search_files, is_library_repo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--identifier", required=True, help="the adaptation API call")
    ap.add_argument("--group-id", default="", help="library groupId, to reject its own repos")
    ap.add_argument("--artifact-id", default="", help="library artifactId, same purpose")
    ap.add_argument("--extra-query", action="append", default=[],
                    help="additional raw code-search query, repeatable")
    ap.add_argument("--pages", type=int, default=10, help="pages per query (100 hits each)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GH_TOKEN required")

    # Two queries by default: the bare identifier, and the identifier narrowed by the
    # groupId. The narrowed one is not redundant -- code search caps at 1000 results per
    # query, so a popular identifier needs a second, differently-shaped query to reach
    # repos the first one truncated away.
    queries = [f'"{args.identifier}" language:java']
    if args.group_id:
        queries.append(f'"{args.identifier}" "{args.group_id}" language:java')
    queries += args.extra_query

    pairs, seen = [], set()
    for q in queries:
        got = code_search_files(q, token, pages=args.pages)
        added = 0
        for repo, path in got:
            if args.group_id and is_library_repo(repo, args.group_id, args.artifact_id):
                continue                      # the library's own repo/forks define the API
            if (repo, path) in seen:
                continue
            seen.add((repo, path))
            pairs.append([repo, path])
            added += 1
        print(f"[code] {q[:60]!r} -> {len(got)} hit(s), {added} new", flush=True)

    pathlib_out = _pl.Path(args.out)
    pathlib_out.parent.mkdir(parents=True, exist_ok=True)
    pathlib_out.write_text(json.dumps(pairs, indent=1), encoding="utf-8")

    repos = {r for r, _ in pairs}
    multi = len(pairs) - len(repos)
    print(f"\n[code] {len(pairs)} file hit(s) across {len(repos)} repo(s) "
          f"({multi} extra files beyond one-per-repo) -> {args.out}")
    print("[code] next: discover/date_hits.py --hits "
          f"{args.out} --identifier {args.identifier} --out <dated>.jsonl")


if __name__ == "__main__":
    main()
