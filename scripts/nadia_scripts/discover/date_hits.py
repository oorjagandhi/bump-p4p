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
so the introduction can be bisected in ~7 fetches instead.

EVERY MATCHING FILE IS DATED, AND THE REPO'S DATE IS THE EARLIEST. Dating one file per repo
was a systematic false-negative -- 47% of these repos match more than one file, and the file
chosen was the shortest path, which says nothing about when anything happened. See
pick_files for the apache/tika case that exposed it. The extra files are made affordable by
an exact prune rather than a sample: a file cannot contain the call before its own first
commit, so a path whose history begins after the best introduction found so far is skipped
without bisecting. Cost stays near ~8 calls plus ~1 per additional file.

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


def pick_files(paths):
    """EVERY production file in the repo that contains the call, not one of them.

    Production source is what a case needs -- an adaptation in src/test proves the project
    noticed the break, not that it had to change production code to keep working. So prod
    paths are preferred, and test paths used only if there are no prod ones.

    THIS USED TO RETURN A SINGLE FILE, the shortest prod path, and that was a systematic
    false-negative rather than a rounding error. 114 of the 241 repos in the jackson hit
    set (47%) contain the call in more than one file, and path length has nothing to do
    with time: a repo whose adaptation is old in one file but which later added the same
    call to a shorter-named file was dated by the LATER file and dropped out of the
    crossing window entirely.

    apache/tika is the demonstration. Its call appears in four files; the shortest prod
    path is tika-serialization/.../config/loader/TikaLoader.java, introduced 2025-12-17,
    so the repo was dated 2025 and screened out as three years past the boundary -- while
    a fork of it, sassoftware/tika, carries TIKA-4154 "parameterize max string length"
    dated 2023-10-14, in the window. The adaptation was in the corpus the whole time,
    attributed to the wrong file's date.

    The repo's date is now the EARLIEST introduction across its files, which is the date
    that actually answers "when did this project adapt".
    """
    prod = [p for p in paths if "src/main/" in p]
    return sorted(set(prod or paths), key=lambda p: (len(p), p))


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


def date_repo(repo, paths, identifier, token, max_files):
    """Earliest introduction of `identifier` across `paths`. Returns a row dict.

    Dating every file would multiply the API cost by the number of matching files, so the
    search is PRUNED, and the prune is exact rather than heuristic: a file cannot contain
    the call earlier than the first commit that touched the file at all. So each path's
    commit list is fetched first (one cheap call), paths are visited oldest-history-first,
    and a path whose whole history starts at or after the best introduction already found
    is skipped without bisecting -- it cannot beat it. On the jackson set this costs about
    one extra call per additional file rather than the ~8 a bisect takes.

    `max_files` bounds the worst case (one repo in the jackson set matches 52 files). When
    it truncates, the row says so rather than quietly reporting a possibly-late date.
    """
    row = {"repo": repo, "files_matched": len(paths)}
    considered = paths[:max_files]
    if len(paths) > max_files:
        row["files_truncated"] = len(paths) - max_files

    histories = []
    calls = 0
    for p in considered:
        commits = path_commits(repo, p, token)
        calls += 1
        if commits:
            # commits are newest-first, so the last one is where this path's history starts
            histories.append((commits[-1]["commit"]["author"]["date"][:10], p, commits))

    if not histories:
        row["error"] = "no commits at any matching path"
        row["calls"] = calls
        return row

    histories.sort()                        # oldest-starting path first
    best = None                             # (date, sha, message, path)
    per_file, bisected = [], 0
    for starts, p, commits in histories:
        if best and starts >= best[0]:
            per_file.append({"path": p, "skipped": f"history starts {starts}, not earlier than {best[0]}"})
            continue
        c, n = bisect_introduction(repo, p, identifier, commits, token)
        calls += n
        bisected += 1
        if not c:
            # present today but in no commit at this path: renamed into place
            per_file.append({"path": p, "error": "identifier in no commit at this path (rename?)"})
            continue
        d = (c["commit"]["author"]["date"] or "")[:10]
        per_file.append({"path": p, "date": d, "sha": c["sha"][:12]})
        if best is None or d < best[0]:
            best = (d, c["sha"][:12], (c["commit"]["message"] or "").split("\n")[0][:120], p,
                    len(commits))

    row["files_considered"] = len(considered)
    row["files_bisected"] = bisected
    row["per_file"] = per_file
    row["calls"] = calls
    if best:
        # canonical keys stay exactly as they were, so screen_dated.py and everything
        # downstream keep working -- they now just describe the EARLIEST file, not an
        # arbitrary one.
        row["date"], row["sha"], row["message"], row["path"], row["commits_at_path"] = best
        row["fetches"] = bisected
    else:
        row["path"] = considered[0]
        row["error"] = "identifier in no commit at any matching path (rename?)"
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hits", required=True, help="cached code-search hits JSON")
    ap.add_argument("--identifier", required=True, help="the adaptation API call")
    ap.add_argument("--out", required=True, help="JSONL, resumed by repo")
    ap.add_argument("--boundary-date", help="YYYY-MM-DD, for the in-window tally")
    ap.add_argument("--limit", type=int, help="stop after N new repos")
    ap.add_argument("--max-files", type=int, default=12,
                    help="cap on matching files dated per repo (default 12); truncation is "
                         "recorded in the row as files_truncated")
    args = ap.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GH_TOKEN required")

    hits = json.loads(Path(args.hits).read_text(encoding="utf-8"))
    by_repo = {}
    for row in hits:
        repo, path = (row[0], row[1]) if isinstance(row, list) else (row["repo"], row["path"])
        by_repo.setdefault(repo, []).append(path)

    # Resume skips repos already dated -- but ONLY those dated by the current, all-files
    # logic. A row without `files_considered` was written by the old one-file-per-repo
    # version, whose dates are unreliable for any repo matching more than one file (47% of
    # them). Those are re-dated rather than trusted, so upgrading needs no manual purge of
    # the output file and cannot silently keep a stale date.
    outp = Path(args.out)
    done, keep, stale = set(), [], 0
    if outp.exists():
        for line in outp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if "files_considered" in r or "files_matched" in r:
                    done.add(r["repo"])
                    keep.append(line)
                else:
                    stale += 1
    if stale:
        # The file is appended to, so leaving the stale rows in place would give those repos
        # two contradictory entries. Drop them -- after backing the original up, since this
        # rewrites a data file that took thousands of API calls to produce and the re-dating
        # run that replaces it can be interrupted.
        backup = outp.with_suffix(outp.suffix + ".single-file-era.bak")
        if not backup.exists():
            backup.write_text(outp.read_text(encoding="utf-8"), encoding="utf-8")
        outp.write_text("".join(l + "\n" for l in keep), encoding="utf-8")
        print(f"[dates] {stale} row(s) from the old single-file logic dropped and will be "
              f"re-dated; original saved to {backup.name}")
    todo = [r for r in sorted(by_repo) if r not in done]
    print(f"[dates] {len(by_repo)} repos, {len(done)} already dated, {len(todo)} to go")

    if args.limit:
        todo = todo[:args.limit]

    calls = 0
    with outp.open("a", encoding="utf-8") as fh:
        for i, repo in enumerate(todo, 1):
            paths = pick_files(by_repo[repo])
            try:
                row = date_repo(repo, paths, args.identifier, token, args.max_files)
                calls += row.pop("calls", 0)
            except Exception as e:                       # keep going; the row records why
                row = {"repo": repo, "path": paths[0] if paths else "",
                       "error": f"{type(e).__name__}: {e}"[:200]}
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
