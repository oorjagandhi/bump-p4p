"""
01_mine_candidates.py
──────────────────────
Phase 1: Mine GitHub for BBC candidate commits by crawling each repo's
commit history.

A candidate commit satisfies ALL of these:
  1. Exactly one pom.xml is changed (single dependency bump)
  2. At least one .java file is also changed in the same commit
     (client adaptation to the breaking change)
  3. The pom.xml diff shows exactly ONE <version> tag change under a
     <dependency> block (not a <parent> or <plugin> bump), with the same
     groupId/artifactId on both sides (rules out library swaps — see
     bbc_common.parse_pom_diff)
  4. The repo has a test suite (src/test/ exists)
  5. The repo has ≥ 5 stars and is not a fork

Output: candidates.jsonl — one JSON record per candidate commit, in a
schema that feeds 02_verify_bbc.py.

Performance fix vs the previous version: commit listing is now filtered
server-side to the repo's actual pom.xml path(s) (found via one tree call
per repo), so full commit detail is only fetched for commits that touched
a pom.xml — not for every one of --max-commits-per-repo commits. That
per-commit-detail-call-regardless-of-relevance pattern was what burned
through the GitHub rate limit before enough repos could be scanned.

Usage:
    python 01_mine_candidates.py --token <GH_TOKEN> [--query "language:Java stars:>10"] \
                                  [--max-repos 200] [--out ../output/candidates.jsonl]
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

from bbc_common import HEADERS_BASE, gh, build_candidate

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


# ── helpers ───────────────────────────────────────────────────────────────────

def search_repos(session, query: str, max_repos: int):
    """Yield repo dicts from GitHub repo search."""
    page, collected = 1, 0
    while collected < max_repos:
        data = gh(session, "/search/repositories", {
            "q": query, "sort": "updated", "order": "desc",
            "per_page": 30, "page": page,
        })
        if data is None or not data.get("items"):
            break
        for repo in data["items"]:
            if collected >= max_repos:
                break
            if repo.get("fork"):
                continue
            if repo.get("stargazers_count", 0) < 5:
                continue
            yield repo
            collected += 1
        if len(data["items"]) < 30:
            break
        page += 1
        time.sleep(0.5)


def scan_repo_tree(session, full_name: str, branch: str):
    """
    Single recursive tree call that returns BOTH the repo's pom.xml paths
    and whether it has any src/test/ directory. Folding the test check in
    here (instead of a separate root-only /contents/src/test call) is more
    correct for multi-module Maven projects — whose tests live in
    <module>/src/test/, not a root src/test/ — and saves one API call per
    repo. The tree is also what lets us filter the commit list server-side
    instead of crawling every commit.

    Returns (pom_paths, has_tests).
    """
    data = gh(session, f"/repos/{full_name}/git/trees/{branch}", {"recursive": "1"})
    if not data or "tree" not in data:
        return [], False
    if data.get("truncated"):
        print(f"  [warn] tree truncated for {full_name}, pom/test list may be incomplete",
              file=sys.stderr)

    pom_paths = []
    has_tests = False
    for item in data["tree"]:
        path = item["path"]
        if item.get("type") == "blob" and path.endswith("pom.xml"):
            pom_paths.append(path)
        if "src/test/" in path or path.endswith("src/test"):
            has_tests = True
    return pom_paths, has_tests


def get_commits(session, full_name: str, max_commits: int, path: str = None):
    """
    Yield commit SHAs for a repo (most recent first), filtered to commits
    that touched `path` when given — this is what keeps the crawl cheap.
    """
    page, collected = 1, 0
    params_base = {"per_page": 100}
    if path:
        params_base["path"] = path
    while collected < max_commits:
        items = gh(session, f"/repos/{full_name}/commits", {**params_base, "page": page})
        if not items:
            break
        for c in items:
            yield c["sha"]
            collected += 1
        if len(items) < 100:
            break
        page += 1
        time.sleep(0.2)


def get_commit_detail(session, full_name: str, sha: str):
    return gh(session, f"/repos/{full_name}/commits/{sha}")


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Mine GitHub for BBC candidate commits")
    ap.add_argument("--token",     required=True,  help="GitHub personal access token")
    ap.add_argument("--query",     default="language:Java stars:>10 topic:maven",
                    help="GitHub repo search query")
    ap.add_argument("--max-repos", type=int, default=100,
                    help="Max repos to scan")
    ap.add_argument("--max-commits-per-repo", type=int, default=80,
                    help="Max commits to inspect per pom.xml path per repo")
    ap.add_argument("--max-commits-per-repo-total", type=int, default=150,
                    help="Hard cap on commit-detail fetches per repo, across "
                         "all its poms — stops one mega-repo hogging the run")
    ap.add_argument("--max-poms-per-repo", type=int, default=5,
                    help="Max pom.xml paths to crawl per repo (shallowest "
                         "first — multi-module projects keep dependency "
                         "versions in the root/parent pom, not leaf modules)")
    ap.add_argument("--out",       default="../output/candidates.jsonl")
    args = ap.parse_args()

    session = requests.Session()
    session.headers.update({**HEADERS_BASE, "Authorization": f"Bearer {args.token}"})

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    found = 0
    with out_path.open("w") as fout:
        for repo in search_repos(session, args.query, args.max_repos):
            full_name = repo["full_name"]
            print(f"[repo] {full_name}  ★{repo['stargazers_count']}")

            pom_paths, has_tests = scan_repo_tree(
                session, full_name, repo.get("default_branch", "main"))
            if not has_tests:
                print(f"  → skip (no src/test/)")
                continue
            if not pom_paths:
                print(f"  → skip (no pom.xml found)")
                continue

            # Dependency versions in multi-module Maven live in the root/
            # parent pom, so crawl shallowest poms first and cap the count —
            # otherwise a 40-module repo triggers 40 full commit crawls.
            pom_paths.sort(key=lambda p: (p.count("/"), len(p)))
            if len(pom_paths) > args.max_poms_per_repo:
                print(f"  [info] {len(pom_paths)} poms, crawling shallowest "
                      f"{args.max_poms_per_repo}")
                pom_paths = pom_paths[:args.max_poms_per_repo]

            seen_shas = set()
            scanned = 0
            budget_hit = False
            for pom_path in pom_paths:
                if budget_hit:
                    break
                for sha in get_commits(session, full_name, args.max_commits_per_repo, path=pom_path):
                    if sha in seen_shas:
                        continue
                    seen_shas.add(sha)

                    # Cap total commit-detail fetches per repo so one very
                    # active mega-repo can't consume the whole run / rate limit.
                    if scanned >= args.max_commits_per_repo_total:
                        print(f"  [info] hit per-repo budget "
                              f"({args.max_commits_per_repo_total} commits), moving on")
                        budget_hit = True
                        break

                    try:
                        detail = get_commit_detail(session, full_name, sha)
                        rec = build_candidate(session, full_name, sha, detail)
                    except Exception as e:
                        print(f"  [warn] {sha[:8]}: {e}", file=sys.stderr)
                        continue

                    scanned += 1
                    if scanned % 25 == 0:
                        print(f"  … scanned {scanned} commits, {found} candidates so far")

                    if rec:
                        print(f"  ✓ CANDIDATE {sha[:8]}  "
                              f"{rec['group_id']}:{rec['artifact_id']}  "
                              f"{rec['old_version']} → {rec['new_version']}")
                        fout.write(json.dumps(rec) + "\n")
                        fout.flush()
                        found += 1

                    time.sleep(0.15)   # stay well within secondary rate limits

    print(f"\nDone. {found} candidates written to {out_path}")


if __name__ == "__main__":
    main()
