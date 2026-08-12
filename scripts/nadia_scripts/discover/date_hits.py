#!/usr/bin/env python3
"""
Date every repo in a cached code-search hit set: when did this file first contain the
adaptation call?

Code search answers "which files contain the identifier TODAY". That is the half that
commit search gets wrong -- commit search is recency-biased and cannot index some
repositories at all -- but it carries no dates, and a case is only interesting if the
adaptation lands NEAR the boundary. This walks each file's own history to date it.

WHY BINARY SEARCH. find_adaptations.introducing_commit walks a path's commits oldest-first,
fetching content at each until the identifier appears: up to 100 content fetches per file.
Across 241 repos that is ~24k calls against a 5,000/hr limit. Since the identifier is
present today and was introduced once, "contains it" is monotonic along the path's history,
so the introduction can be bisected in ~7 fetches instead. Cost drops to ~8 calls a repo.

THE CAVEAT that buys: if a call was added, removed, and re-added, monotonicity is false and
the bisection lands on *a* transition rather than the earliest. That is fine for triage --
it still dates the file into or out of the crossing window -- but any repo that becomes a
candidate should be re-checked with the linear walk before it is written up as a case.

Resumes by repo, so a kill costs one repo.
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

import argparse, json, os, sys, time
from collections import Counter
from pathlib import Path

import bbc_e2e as B

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / "output"


def pick_file(paths):
    """One file per repo: production source first, then the shortest path.

    Production source is what a case needs -- an adaptation in src/test proves the project
    noticed the break, not that it had to change production code to keep working.
    """
    prod = [p for p in paths if "src/main/" in p]
    return sorted(prod or paths, key=lambda p: (len(p), p))[0]


def path_commits(repo, path, token):
    """Every commit touching `path`, oldest last (the API's own order), fully paginated."""
    out, page = [], 1
    while True:
        batch = B._gh(f"{B.GH}/repos/{repo}/commits", token,
                      path=path, per_page=100, page=page)
        if not isinstance(batch, list) or not batch:
            break
        out += batch
        if len(batch) < 100 or page >= 10:      # 10 pages = 1000 commits, enough
            break
        page += 1
    return out


def bisect_introduction(repo, path, identifier, commits, token):
    """Oldest commit (of `commits`, newest-first) whose content contains `identifier`.

    Returns (commit, n_fetches). Assumes monotonicity -- see the module docstring.
    """
    old_to_new = list(reversed(commits))
    lo, hi, best, fetches = 0, len(old_to_new) - 1, None, 0
    while lo <= hi:
        mid = (lo + hi) // 2
        text = B._gh_file(repo, path, old_to_new[mid]["sha"], token)
        fetches += 1
        if text and identifier in text:
            best = old_to_new[mid]
            hi = mid - 1                        # an earlier one may also contain it
        else:
            lo = mid + 1
    return best, fetches


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hits", required=True, help="cached code-search hits JSON")
    ap.add_argument("--identifier", required=True, help="the adaptation API call")
    ap.add_argument("--out", required=True, help="JSONL, resumed by repo")
    ap.add_argument("--boundary-date", help="YYYY-MM-DD, for the in-window tally")
    ap.add_argument("--limit", type=int, help="stop after N new repos")
    args = ap.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GH_TOKEN required")

    hits = json.loads(Path(args.hits).read_text(encoding="utf-8"))
    by_repo = {}
    for row in hits:
        repo, path = (row[0], row[1]) if isinstance(row, list) else (row["repo"], row["path"])
        by_repo.setdefault(repo, []).append(path)

    outp = Path(args.out)
    done = set()
    if outp.exists():
        for line in outp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                done.add(json.loads(line)["repo"])
    todo = [r for r in sorted(by_repo) if r not in done]
    print(f"[dates] {len(by_repo)} repos, {len(done)} already dated, {len(todo)} to go")

    if args.limit:
        todo = todo[:args.limit]

    calls = 0
    with outp.open("a", encoding="utf-8") as fh:
        for i, repo in enumerate(todo, 1):
            path = pick_file(by_repo[repo])
            row = {"repo": repo, "path": path}
            try:
                commits = path_commits(repo, path, token)
                calls += 1
                if not commits:
                    row["error"] = "no commits at path"
                else:
                    c, n = bisect_introduction(repo, path, args.identifier, commits, token)
                    calls += n
                    row["commits_at_path"] = len(commits)
                    row["fetches"] = n
                    if c:
                        row["sha"] = c["sha"][:12]
                        row["date"] = (c["commit"]["author"]["date"] or "")[:10]
                        row["message"] = (c["commit"]["message"] or "").split("\n")[0][:120]
                    else:
                        # present today but absent from every commit at this path: the file
                        # was renamed into place, and this path's history predates the call
                        row["error"] = "identifier in no commit at this path (rename?)"
            except Exception as e:                       # keep going; the row records why
                row["error"] = f"{type(e).__name__}: {e}"[:200]
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            print(f"  [{i}/{len(todo)}] {repo:<44} {row.get('date') or row.get('error','')[:44]}")

    rows = [json.loads(l) for l in outp.read_text(encoding="utf-8").splitlines() if l.strip()]
    dated = [r for r in rows if r.get("date")]
    print(f"\n[dates] {len(dated)} dated / {len(rows)} rows ({calls} API calls this run)")
    years = Counter(r["date"][:4] for r in dated)
    print("[dates] by year: " + ", ".join(f"{y}:{n}" for y, n in sorted(years.items())))
    if args.boundary_date:
        after = [r for r in dated if r["date"] >= args.boundary_date]
        print(f"[dates] on/after the {args.boundary_date} boundary: {len(after)}/{len(dated)}")


if __name__ == "__main__":
    main()
