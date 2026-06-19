"""
01_mine_candidates_bump.py
──────────────────────────
Phase 1 (BUMP-targeted variant of 01_mine_candidates.py).

Instead of mining GitHub for bumps of *any* known BBC-causing library, this
script restricts the candidate filter to the seven specific breaking updates
catalogued in the BUMP dataset, each matched on BOTH the dependency identity
AND the version range that BUMP confirmed as breaking:

  1. Mockito 5.x            org.mockito          4.x → 5.x
     BUMP PRs #483 #490 #499 #510 · client pholser/junit-quickcheck
  2. Logback Classic 1.4.x  ch.qos.logback       1.2.x/1.3.x → 1.4.x+
     BUMP PRs #345 #346 #349 #350 #353 #362 · client retest/recheck.cli
  3. SLF4J API 2.0.x        org.slf4j            1.x → 2.x
     BUMP PRs #540 #570 #571 #572 #583 #584 #588 · client searls/jasmine-maven-plugin
  4. Apache POI Scratchpad  org.apache.poi       4.x → 5.x  (poi-scratchpad)
     BUMP PRs #1281 #1361 · client dadoonet/fscrawler
  5. Jenkins GitHub API     org.jenkins-ci.plugins  1.117 → 1.303+  (github-api)
     BUMP PR #265 · client jenkinsci/github-checks-plugin
  6. Apache HttpClient      org.apache.httpcomponents  4.5.1 → 4.5.13  (httpclient)
     BUMP PR #334 · client lookfirst/sardine
  7. jsoup 1.15.x           org.jsoup            1.14.x → 1.15.x
     BUMP PR #303 · client SPARQL-Anything/sparql.anything

The mining machinery (repo search → recursive tree → pom-filtered commit
crawl → commit-detail screening) is identical to 01_mine_candidates.py and the
output records share the same schema, so the result still feeds 02_verify_bbc.py
unchanged. The only behavioural difference is the per-commit filter: a commit is
kept only when its single pom.xml dependency bump matches one of the seven BUMP
targets above (see match_bump_target / BUMP_TARGETS). Extra `bump_*` fields are
added to each record to record which target it matched.

By default the seven BUMP client projects are scanned first (guaranteed seeds),
so a quick run reproduces the canonical BUMP examples; the GitHub repo search
then widens the net to find OTHER client projects that performed the same bumps.

Usage:
    # reproduce the canonical BUMP examples only (fast):
    python 01_mine_candidates_bump.py --token <GH_TOKEN> --only-bump-clients

    # seed with the BUMP clients, then widen via search:
    python 01_mine_candidates_bump.py --token <GH_TOKEN> --max-repos 200 \
                                       --out output/bump_candidates.jsonl
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

from bbc_common import (
    HEADERS_BASE,
    gh,
    get_file_patch,
    is_single_dep_version_bump,
    parse_pom_diff,
)

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


# ── BUMP target definitions ───────────────────────────────────────────────────

def _pad(version: str, n: int = 3):
    """
    Parse a Maven version string into a fixed-length (major, minor, patch)
    tuple of ints, ignoring any qualifier. Handles the awkward Jenkins-plugin
    form too, e.g. '1.303-400.v35c2d8258028' → (1, 303, 0). Returns None when
    the version doesn't start with a number (e.g. a '${prop}' reference).
    """
    if not version:
        return None
    head = re.split(r"[-+]", version.strip(), 1)[0]   # drop '-qualifier'
    nums = []
    for part in head.split("."):
        m = re.match(r"\d+", part)
        if not m:
            break
        nums.append(int(m.group()))
    if not nums:
        return None
    nums = (nums + [0] * n)[:n]
    return tuple(nums)


# Each target matches on the exact groupId, an artifact-id guard, and a
# predicate over the parsed (old, new) version tuples. old/new are 3-tuples
# (major, minor, patch) as produced by _pad().
BUMP_TARGETS = [
    {
        "name": "Mockito 5.x",
        "group_id": "org.mockito",
        "artifact_ok": lambda a: a.startswith("mockito"),
        "matches": lambda o, n: o[0] == 4 and n[0] == 5,
        "bump_prs": "PR #483, #490, #499, #510",
        "client": "pholser/junit-quickcheck",
        "search_range": "4.x → 5.x",
    },
    {
        "name": "Logback Classic 1.4.x",
        "group_id": "ch.qos.logback",
        "artifact_ok": lambda a: a.startswith("logback"),
        "matches": lambda o, n: o[0] == 1 and o[1] in (2, 3) and n[0] == 1 and n[1] >= 4,
        "bump_prs": "PR #345, #346, #349, #350, #353, #362",
        "client": "retest/recheck.cli",
        "search_range": "1.2.x or 1.3.x → 1.4.x or higher",
    },
    {
        "name": "SLF4J API 2.0.x",
        "group_id": "org.slf4j",
        "artifact_ok": lambda a: a.startswith("slf4j"),
        "matches": lambda o, n: o[0] == 1 and n[0] == 2,
        "bump_prs": "PR #540, #570, #571, #572, #583, #584, #588",
        "client": "searls/jasmine-maven-plugin",
        "search_range": "1.x → 2.x",
    },
    {
        "name": "Apache POI Scratchpad 5.x",
        "group_id": "org.apache.poi",
        "artifact_ok": lambda a: a.startswith("poi"),
        "matches": lambda o, n: o[0] == 4 and n[0] == 5,
        "bump_prs": "PR #1281, #1361",
        "client": "dadoonet/fscrawler",
        "search_range": "4.x → 5.x",
    },
    {
        "name": "Jenkins GitHub API Plugin 1.303",
        "group_id": "org.jenkins-ci.plugins",
        "artifact_ok": lambda a: a == "github-api",
        "matches": lambda o, n: o[0] == 1 and 117 <= o[1] < 303 and n[0] == 1 and n[1] >= 303,
        "bump_prs": "PR #265",
        "client": "jenkinsci/github-checks-plugin",
        "search_range": "1.117 → 1.303+ (narrow Jenkins plugin versioning)",
    },
    {
        "name": "Apache HttpClient 4.5.13",
        "group_id": "org.apache.httpcomponents",
        "artifact_ok": lambda a: a == "httpclient",
        "matches": lambda o, n: o[:2] == (4, 5) and n[:2] == (4, 5) and o[2] < 13 <= n[2],
        "bump_prs": "PR #334",
        "client": "lookfirst/sardine",
        "search_range": "4.5.1 → 4.5.13 (patch-level)",
    },
    {
        "name": "jsoup 1.15.x",
        "group_id": "org.jsoup",
        "artifact_ok": lambda a: a == "jsoup",
        "matches": lambda o, n: o[:2] == (1, 14) and n[0] == 1 and n[1] >= 15,
        "bump_prs": "PR #303",
        "client": "SPARQL-Anything/sparql.anything",
        "search_range": "1.14.x → 1.15.x",
    },
]

# The canonical BUMP client projects, scanned first as guaranteed seeds.
BUMP_CLIENT_REPOS = [t["client"] for t in BUMP_TARGETS]


def match_bump_target(group_id: str, artifact_id: str, old_ver: str, new_ver: str):
    """
    Return the matching BUMP_TARGETS entry for a parsed dependency bump, or
    None. Requires the exact groupId, an artifact guard, and the confirmed
    BUMP version range (old → new) all to match.
    """
    if not group_id:
        return None
    g = group_id.strip().lower()
    a = (artifact_id or "").strip().lower()
    o, n = _pad(old_ver), _pad(new_ver)
    if not o or not n:
        return None
    for t in BUMP_TARGETS:
        if g != t["group_id"]:
            continue
        if not t["artifact_ok"](a):
            continue
        if t["matches"](o, n):
            return t
    return None


# ── GitHub crawl helpers (same behaviour as 01_mine_candidates.py) ─────────────

def get_repo(session, full_name: str):
    """Fetch a single repo's metadata (used for the explicit-seed repos)."""
    return gh(session, f"/repos/{full_name}")


def search_repos(session, query: str, max_repos: int):
    """Yield repo dicts from GitHub repo search (non-forks, ≥5 stars)."""
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


def search_code_repos(session, max_repos: int):
    """
    Discover repos to scan via GitHub CODE search over pom.xml files, one
    distinctive query per BUMP target (its groupId). This is far higher-yield
    than the generic repo search because every result is a repo whose pom.xml
    actually references one of the seven target libraries — so it stands a real
    chance of containing the bump we're looking for.

    Yields repo *full_names* (deduped). The code-search endpoint is rate-limited
    to ~10 requests/min, so we pace requests and cap pages per target.

    NOTE: code search only indexes the default branch and needs the dependency
    to appear literally in a pom.xml (groupId), which is exactly our case.
    """
    queries = []
    for t in BUMP_TARGETS:
        # e.g. '"org.mockito" filename:pom.xml' — quoted groupId keeps it precise.
        queries.append((t["name"], f'"{t["group_id"]}" in:file filename:pom.xml'))

    seen = set()
    emitted = 0
    per_target_pages = 5          # 5 pages × 50 = up to 250 repos/target
    for tname, q in queries:
        if emitted >= max_repos:
            break
        for page in range(1, per_target_pages + 1):
            if emitted >= max_repos:
                break
            data = gh(session, "/search/code", {
                "q": q, "per_page": 50, "page": page,
            })
            time.sleep(6.5)       # stay under code-search's ~10 req/min limit
            if data is None or not data.get("items"):
                break
            for item in data["items"]:
                repo = item.get("repository", {})
                full_name = repo.get("full_name")
                if not full_name or full_name.lower() in seen:
                    continue
                if repo.get("fork"):
                    continue
                seen.add(full_name.lower())
                yield full_name
                emitted += 1
                if emitted >= max_repos:
                    break
            if len(data["items"]) < 50:
                break


def scan_repo_tree(session, full_name: str, branch: str):
    """Single recursive tree call → (pom_paths, has_tests). See 01_mine_candidates."""
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
    """Yield commit SHAs (most recent first), filtered to commits touching `path`."""
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


# ── BUMP-targeted candidate screening ─────────────────────────────────────────

def build_bump_candidate(session, full_name: str, sha: str, detail: dict):
    """
    Like bbc_common.build_candidate, but the dependency filter is the BUMP
    target set (identity + confirmed version range) rather than the generic
    known-BBC library list. Returns a candidate record (with extra bump_*
    fields) or None.

    Filters:
      1. ≤ 8 files changed
      2. Exactly one pom.xml changed
      3. 1–5 .java files changed (adaptation signal, not a broad refactor)
      4. The pom.xml diff is a single same-dependency version bump
      5. That bump matches one of the seven BUMP targets (match_bump_target)
    """
    if not detail or "files" not in detail:
        return None

    files = detail["files"]
    filenames = [f["filename"] for f in files]

    if len(filenames) > 8:
        return None

    pom_files = [f for f in files if f["filename"].endswith("pom.xml")]
    if len(pom_files) != 1:
        return None

    java_files = [f for f in filenames if f.endswith(".java")]
    non_test_java = [f for f in java_files if "/test/" not in f.lower()]
    test_java = [f for f in java_files if "/test/" in f.lower()]

    # The adaptation signal must include production (non-test) code. A commit
    # whose only .java changes are under src/test/ is a test-suite tweak, not a
    # client adaptation to the breaking change, so it doesn't count. We also cap
    # on the non-test count: >5 changed production files is very likely a broad
    # refactor rather than a focused adaptation.
    if not non_test_java or len(non_test_java) > 5:
        return None

    diff_cache = {"text": None}
    pom_chunk = get_file_patch(session, full_name, sha, pom_files[0], diff_cache)
    if not is_single_dep_version_bump(pom_chunk):
        return None

    dep_info = parse_pom_diff(pom_chunk)
    if not dep_info:
        return None

    group_id, artifact_id, old_ver, new_ver = dep_info

    target = match_bump_target(group_id, artifact_id, old_ver, new_ver)
    if not target:
        return None

    commit_msg = detail.get("commit", {}).get("message", "").lower()
    smell_words = ["update", "upgrade", "bump", "migrat", "compati",
                   "fix", "break", "deprecat", "api"]
    has_smell = any(w in commit_msg for w in smell_words)

    return {
        "repo": full_name,
        "sha": sha,
        "commit_url": f"https://github.com/{full_name}/commit/{sha}",
        "commit_msg": detail["commit"]["message"][:300],
        "group_id": group_id,
        "artifact_id": artifact_id,
        "old_version": old_ver,
        "new_version": new_ver,
        "pom_file": pom_files[0]["filename"],
        "java_files_changed": java_files,
        "non_test_java_changed": non_test_java,
        "test_java_changed": test_java,
        "total_files_changed": len(filenames),
        "commit_msg_has_smell": has_smell,
        "date": detail["commit"]["committer"]["date"],
        "source": "bump-targeted",
        # BUMP-specific provenance
        "bump_target": target["name"],
        "bump_prs": target["bump_prs"],
        "bump_client": target["client"],
        "bump_search_range": target["search_range"],
        "is_bump_client_repo": full_name.lower() == target["client"].lower(),
    }


# ── repo iteration ─────────────────────────────────────────────────────────────

def iter_repos(session, args):
    """
    Yield repo dicts to scan: the explicit/seed BUMP client repos first
    (guaranteed coverage of the canonical examples), then — unless
    --only-bump-clients — the GitHub repo-search results.
    """
    seen = set()

    seed_names = list(BUMP_CLIENT_REPOS)
    if args.repos:
        seed_names += [r.strip() for r in args.repos.split(",") if r.strip()]

    for full_name in seed_names:
        key = full_name.lower()
        if key in seen:
            continue
        seen.add(key)
        repo = get_repo(session, full_name)
        if not repo:
            print(f"[seed] {full_name}  → skip (repo not found)", file=sys.stderr)
            continue
        yield repo

    if args.only_bump_clients:
        return

    if args.discover == "repo":
        # Generic repo search (low yield — kept for completeness).
        for repo in search_repos(session, args.query, args.max_repos):
            if repo["full_name"].lower() in seen:
                continue
            seen.add(repo["full_name"].lower())
            yield repo
        return

    # Default: code search over pom.xml for each target's groupId, then fetch
    # repo metadata for each hit. This is the path that actually finds the bumps.
    for full_name in search_code_repos(session, args.max_repos):
        if full_name.lower() in seen:
            continue
        seen.add(full_name.lower())
        repo = get_repo(session, full_name)
        if not repo:
            continue
        yield repo


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Mine GitHub for the seven BUMP-dataset breaking updates")
    ap.add_argument("--token", required=True, help="GitHub personal access token")
    ap.add_argument("--query", default="language:Java stars:>10 topic:maven",
                    help="GitHub repo search query (used to widen beyond the "
                         "BUMP client repos)")
    ap.add_argument("--repos", default=None,
                    help="Extra comma-separated owner/name repos to scan as "
                         "seeds, in addition to the seven BUMP client projects")
    ap.add_argument("--only-bump-clients", action="store_true",
                    help="Scan ONLY the seven BUMP client projects (skip search) "
                         "— fast reproduction of the canonical examples")
    ap.add_argument("--discover", choices=("code", "repo"), default="code",
                    help="How to find repos beyond the seeds: 'code' = GitHub "
                         "code search over pom.xml for each target's groupId "
                         "(high yield, default); 'repo' = generic repo search "
                         "with --query (low yield)")
    ap.add_argument("--target-candidates", type=int, default=50,
                    help="Stop once this many candidates have been found "
                         "(0 = no limit, scan everything)")
    ap.add_argument("--append", action="store_true",
                    help="Append to --out instead of overwriting (useful to "
                         "accumulate candidates across multiple runs)")
    ap.add_argument("--max-repos", type=int, default=2000,
                    help="Max discovered repos to scan (beyond the seeds)")
    ap.add_argument("--max-commits-per-repo", type=int, default=200,
                    help="Max commits to inspect per pom.xml path per repo")
    ap.add_argument("--max-commits-per-repo-total", type=int, default=300,
                    help="Hard cap on commit-detail fetches per repo")
    ap.add_argument("--max-poms-per-repo", type=int, default=5,
                    help="Max pom.xml paths to crawl per repo (shallowest first)")
    ap.add_argument("--out", default="output/bump_candidates.jsonl",
                    help="Output JSONL path (default: output/bump_candidates.jsonl "
                         "under the directory you run from, i.e. "
                         "nadia_scripts/output/ when run from nadia_scripts/)")
    args = ap.parse_args()

    session = requests.Session()
    session.headers.update({**HEADERS_BASE, "Authorization": f"Bearer {args.token}"})

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    target_n = args.target_candidates
    found = 0
    mode = "a" if args.append else "w"
    with out_path.open(mode) as fout:
        for repo in iter_repos(session, args):
            if target_n and found >= target_n:
                break
            full_name = repo["full_name"]
            tag = "client" if full_name.lower() in (c.lower() for c in BUMP_CLIENT_REPOS) else "repo"
            print(f"[{tag}] {full_name}  ★{repo.get('stargazers_count', '?')}")

            pom_paths, has_tests = scan_repo_tree(
                session, full_name, repo.get("default_branch", "main"))
            if not has_tests:
                print(f"  → skip (no src/test/)")
                continue
            if not pom_paths:
                print(f"  → skip (no pom.xml found)")
                continue

            # Dependency versions in multi-module Maven live in the root/parent
            # pom, so crawl shallowest poms first and cap the count.
            pom_paths.sort(key=lambda p: (p.count("/"), len(p)))
            if len(pom_paths) > args.max_poms_per_repo:
                print(f"  [info] {len(pom_paths)} poms, crawling shallowest "
                      f"{args.max_poms_per_repo}")
                pom_paths = pom_paths[:args.max_poms_per_repo]

            seen_shas = set()
            scanned = 0
            budget_hit = False
            for pom_path in pom_paths:
                if budget_hit or (target_n and found >= target_n):
                    break
                for sha in get_commits(session, full_name, args.max_commits_per_repo, path=pom_path):
                    if target_n and found >= target_n:
                        break
                    if sha in seen_shas:
                        continue
                    seen_shas.add(sha)

                    if scanned >= args.max_commits_per_repo_total:
                        print(f"  [info] hit per-repo budget "
                              f"({args.max_commits_per_repo_total} commits), moving on")
                        budget_hit = True
                        break

                    try:
                        detail = get_commit_detail(session, full_name, sha)
                        rec = build_bump_candidate(session, full_name, sha, detail)
                    except Exception as e:
                        print(f"  [warn] {sha[:8]}: {e}", file=sys.stderr)
                        continue

                    scanned += 1
                    if scanned % 25 == 0:
                        print(f"  … scanned {scanned} commits, {found} candidates so far")

                    if rec:
                        print(f"  ✓ CANDIDATE {sha[:8]}  [{rec['bump_target']}]  "
                              f"{rec['group_id']}:{rec['artifact_id']}  "
                              f"{rec['old_version']} → {rec['new_version']}")
                        fout.write(json.dumps(rec) + "\n")
                        fout.flush()
                        found += 1

                    time.sleep(0.15)   # stay well within secondary rate limits

    stop = "reached target" if (target_n and found >= target_n) else "exhausted repos"
    print(f"\nDone ({stop}). {found} BUMP-targeted candidates "
          f"{'appended to' if args.append else 'written to'} {out_path}")


if __name__ == "__main__":
    main()
