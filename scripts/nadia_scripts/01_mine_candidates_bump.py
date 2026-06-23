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

Candidate model — a (bump_sha, adapt_sha) pair that 02_verify_bbc can confirm:
  • bump_sha  — the commit that changes the dependency version (plain <version>
                or a <properties> bump like <mockito.version>).
  • adapt_sha — the commit whose checkout contains BOTH the bump and the client
                adaptation. Found in priority order:
                  1. same commit: bump_sha itself changes production .java
                     → adapt_sha == bump_sha (02 behaves exactly as before).
                  2. same PR: the PR containing the bump has production .java
                     somewhere (multi-commit migration, or dependabot bump +
                     maintainer fix) → adapt_sha = the PR's MERGE commit, which
                     holds both bump and fix.
A pure pom-only bump with no production adaptation anywhere (a plain dependabot
merge) is dropped — 02 could never confirm it as a BBC. --adaptation-scope=auto
(default) tries commit then PR; =commit restricts to the same-commit case.
Each record carries adaptation_scope ("commit"|"pr") and pr_number/pr_title/url.

Recall over precision: this is the candidate-GENERATION stage — it does not try
to confirm a candidate is a genuine BBC; 02_verify_bbc.py does that (e.g. by
building/running tests). So mining keeps plausible candidates and leaves the
hard call to verification.

Library-reference signal: whether ≥1 production adaptation file actually
references the bumped library's Java package (e.g. org.mockito, or
org.apache.http for HttpClient, org.kohsuke.github for the Jenkins github-api
plugin — note these last two differ from the Maven groupId) is RECORDED on every
record (library_referenced / library_reference_files) as a ranking signal, but
by default is NOT used to drop candidates. Pass --require-library-reference to
filter on it at mining time when you want higher precision / fewer candidates.

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
    GH_API,
    HEADERS_BASE,
    KNOWN_BBC_GROUP_PREFIXES,
    gh,
    get_file_patch,
    is_single_dep_version_bump,
    parse_pom_diff,
)

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

# Funnel diagnostics: where do candidates die? Incremented through screening so
# a run can show, e.g., "lots of bumps detected but all rejected for no
# production java" vs "no bumps detected at all".
from collections import Counter
STATS = Counter()


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
    head = re.split(r"[-+]", version.strip(), maxsplit=1)[0]   # drop '-qualifier'
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

# Java import-package prefixes that indicate code actually USES each target
# library. Used to confirm an adaptation really touches the bumped library
# (not just unrelated code in the same PR). NOTE two deliberate mismatches
# between the Maven groupId and the Java package:
#   - HttpClient 4.x classes live in org.apache.http (not org.apache.httpcomponents)
#   - the Jenkins github-api plugin bundles the kohsuke library, so clients
#     import org.kohsuke.github (not org.jenkins-ci.plugins)
TARGET_LIBRARY_PACKAGES = {
    "Mockito 5.x": ("org.mockito",),
    "Logback Classic 1.4.x": ("ch.qos.logback",),
    "SLF4J API 2.0.x": ("org.slf4j",),
    "Apache POI Scratchpad 5.x": ("org.apache.poi",),
    "Jenkins GitHub API Plugin 1.303": ("org.kohsuke.github",),
    "Apache HttpClient 4.5.13": ("org.apache.http",),
    "jsoup 1.15.x": ("org.jsoup",),
}


# ── broad "known-bbc" tier ─────────────────────────────────────────────────────
# A second, wider tier built from bbc_common.KNOWN_BBC_GROUP_PREFIXES. The 7
# BUMP targets above are the precise tier (exact confirmed version ranges); this
# tier widens the net toward a larger research dataset by accepting bumps of any
# known-BBC library family that cross a MAJOR-OR-MINOR boundary (patch-only bumps
# are skipped — they're rarely breaking). It reuses the same per-candidate rigor
# (single-dep bump, production adaptation, library-reference check), so the extra
# breadth doesn't cost precision; it just lowers the version-range confidence,
# which is why every record carries a `tier` field ("bump" vs "known-bbc").
#
# Java packages differ from the Maven groupId for several families (Guava lives
# in com.google.common; Commons-IO in org.apache.commons.io; OkHttp in okhttp3;
# Log4j 1.x in org.apache.log4j; HttpClient 5 in org.apache.hc), so we map them
# explicitly for the library-reference check.
_GENERIC_PACKAGES = {
    "com.google.guava": ("com.google.common",),
    "junit": ("org.junit", "junit.framework"),
    "org.junit": ("org.junit",),
    "org.apache.logging.log4j": ("org.apache.logging.log4j",),
    "log4j": ("org.apache.log4j",),
    "org.springframework": ("org.springframework",),
    "com.fasterxml.jackson": ("com.fasterxml.jackson",),
    "org.mockito": ("org.mockito",),
    "commons-io": ("org.apache.commons.io",),
    "commons-lang": ("org.apache.commons.lang",),
    "org.apache.commons": ("org.apache.commons",),
    "org.apache.httpcomponents": ("org.apache.http", "org.apache.hc"),
    "com.squareup.okhttp3": ("okhttp3",),
    "org.hibernate": ("org.hibernate",),
    "ch.qos.logback": ("ch.qos.logback",),
    "org.mockserver": ("org.mockserver",),
    # widened families with package != groupId
    "com.google.code.gson": ("com.google.gson",),
    "joda-time": ("org.joda.time",),
    "com.squareup.retrofit2": ("retrofit2",),
    "com.squareup.okhttp": ("com.squareup.okhttp", "okhttp3"),
    "org.yaml": ("org.yaml.snakeyaml",),
}


def _major_or_minor_increase(o, n):
    """True when the major OR minor version increased (patch-only/downgrade skipped)."""
    return (n[0] > o[0]) or (n[0] == o[0] and n[1] > o[1])


GENERIC_BBC_TARGETS = [
    {
        "name": f"{prefix} (known-bbc)",
        "group_id": prefix,
        "group_prefix": True,                 # match the whole groupId family
        "artifact_ok": (lambda a: True),
        "matches": _major_or_minor_increase,
        "tier": "known-bbc",
        "bump_prs": "",
        "client": "",
        "search_range": "major or minor increase",
    }
    for prefix in KNOWN_BBC_GROUP_PREFIXES
]
for _t in GENERIC_BBC_TARGETS:
    TARGET_LIBRARY_PACKAGES.setdefault(
        _t["name"], _GENERIC_PACKAGES.get(_t["group_id"], (_t["group_id"],)))


def active_targets(target_set: str):
    """Return the list of target dicts to use, precise (bump) tier first."""
    ts = []
    if target_set in ("bump", "both"):
        ts += BUMP_TARGETS
    if target_set in ("known-bbc", "both"):
        ts += GENERIC_BBC_TARGETS
    return ts


def _group_matches(g: str, target: dict) -> bool:
    gid = target["group_id"]
    if target.get("group_prefix"):
        return g == gid or g.startswith(gid + ".")
    return g == gid


def match_target(group_id, artifact_id, old_ver, new_ver, targets):
    """
    Return the first matching target dict for a parsed dependency bump, or None.
    `targets` is the active list (precise BUMP tier first, then the broad
    known-bbc tier), so a bump that fits an exact BUMP range is attributed to
    that precise target rather than the looser family entry.
    """
    if not group_id:
        return None
    g = group_id.strip().lower()
    a = (artifact_id or "").strip().lower()
    o, n = _pad(old_ver), _pad(new_ver)
    if not o or not n:
        return None
    for t in targets:
        if not _group_matches(g, t):
            continue
        if not t["artifact_ok"](a):
            continue
        if t["matches"](o, n):
            return t
    return None


# ── property-style bump support ────────────────────────────────────────────────
# Many bumps (especially dependabot) change a <properties> entry like
# <mockito.version>4.11.0</mockito.version> rather than a <version> inside a
# <dependency>. bbc_common.parse_pom_diff only reads plain <version> tags, so
# those bumps are invisible to it. We detect a single property-version change
# here and attribute it to a target by a keyword in the property name.

# Property-name keyword per target (the property name carries the library hint).
_PROP_KEYWORDS = {
    "Mockito 5.x": "mockito",
    "Logback Classic 1.4.x": "logback",
    "SLF4J API 2.0.x": "slf4j",
    "Apache POI Scratchpad 5.x": "poi",
    "Jenkins GitHub API Plugin 1.303": "github",
    "Apache HttpClient 4.5.13": "httpclient",
    "jsoup 1.15.x": "jsoup",
}
_GENERIC_KEYWORDS = {
    "com.google.guava": "guava",
    "junit": "junit",
    "org.junit": "junit",
    "org.apache.logging.log4j": "log4j",
    "log4j": "log4j",
    "org.springframework": "spring",
    "com.fasterxml.jackson": "jackson",
    "org.mockito": "mockito",
    "commons-io": "commons-io",
    "commons-lang": "commons-lang",
    "org.apache.commons": "commons",
    "org.apache.httpcomponents": "httpclient",
    "com.squareup.okhttp3": "okhttp",
    "org.hibernate": "hibernate",
    "ch.qos.logback": "logback",
    "org.mockserver": "mockserver",
    # widened families
    "org.slf4j": "slf4j",
    "org.apache.poi": "poi",
    "org.jsoup": "jsoup",
    "org.assertj": "assertj",
    "org.hamcrest": "hamcrest",
    "org.testng": "testng",
    "com.google.code.gson": "gson",
    "org.yaml": "snakeyaml",
    "io.netty": "netty",
    "joda-time": "joda",
    "org.json": "json",
    "com.squareup.retrofit2": "retrofit",
    "com.squareup.okhttp": "okhttp",
    "org.apache.kafka": "kafka",
    "org.eclipse.jetty": "jetty",
    "org.elasticsearch": "elasticsearch",
    "org.apache.lucene": "lucene",
}


def _target_keyword(t):
    if t["name"] in _PROP_KEYWORDS:
        return _PROP_KEYWORDS[t["name"]]
    return _GENERIC_KEYWORDS.get(t["group_id"], t["group_id"].split(".")[-1])


def parse_property_bump(pom_chunk: str):
    """
    Detect a single <…version>OLD→NEW</…version> property change in a pom diff
    (e.g. <mockito.version>). Returns (property_name, old, new) or None. Only
    fires when exactly one property-version is removed and one added with the
    same name and a different value.
    """
    removed, added = [], []
    for raw in pom_chunk.splitlines():
        m = re.match(r"^([+-])\s*<([\w.\-]+)>\s*([\w.\-]+)\s*</\2>\s*$", raw)
        if not m:
            continue
        sign, name, val = m.group(1), m.group(2), m.group(3)
        if "version" not in name.lower():
            continue
        (removed if sign == "-" else added).append((name, val))
    if (len(removed) == 1 and len(added) == 1
            and removed[0][0] == added[0][0] and removed[0][1] != added[0][1]):
        return removed[0][0], removed[0][1], added[0][1]
    return None


def match_property_target(prop_name, old_ver, new_ver, targets):
    """Match a property-style bump to a target by a keyword in the property name."""
    pn = (prop_name or "").lower()
    o, n = _pad(old_ver), _pad(new_ver)
    if not o or not n:
        return None
    for t in targets:
        kw = _target_keyword(t)
        if kw and kw in pn and t["matches"](o, n):
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


def search_code_repos(session, max_repos: int, targets):
    """
    Discover repos to scan via GitHub CODE search over pom.xml files, one
    distinctive query per active target groupId (deduped). This is far
    higher-yield than the generic repo search because every result is a repo
    whose pom.xml actually references a target library — so it stands a real
    chance of containing the bump we're looking for.

    Yields repo *full_names* (deduped). The code-search endpoint is rate-limited
    to ~10 requests/min, so we pace requests and cap pages per target.

    NOTE: code search only indexes the default branch and needs the dependency
    to appear literally in a pom.xml (groupId), which is exactly our case.
    """
    # GitHub code search hard-caps at 1000 results PER QUERY, no matter how many
    # pages you ask for. A single '"<gid>" filename:pom.xml' query therefore can
    # never surface more than 1000 repos for a big family. To get past that
    # ceiling we partition each family's search by pom.xml file-SIZE bands: the
    # bands are disjoint, so their 1000-result windows cover DIFFERENT repos and
    # multiply the reachable set. (size: is one of the few qualifiers GitHub
    # code search supports alongside filename:.)
    # Bands start at 1500 bytes: pom.xml files smaller than that are almost
    # always trivial toy/homework projects (no real dependency-upgrade history),
    # and including them floods discovery with ★0 repos that burn the per-repo
    # budget for nothing. Three disjoint bands above that still partition the
    # result space to beat the 1000-per-query cap.
    SIZE_BANDS = ["size:1500..4000", "size:4000..10000", "size:>10000"]
    queries, seen_groups = [], set()
    for t in targets:
        gid = t["group_id"]
        if gid in seen_groups:
            continue
        seen_groups.add(gid)
        # e.g. '"org.mockito" filename:pom.xml size:<1500' — quoted groupId keeps
        # it precise; the size band partitions the result space.
        for band in SIZE_BANDS:
            queries.append((gid, f'"{gid}" in:file filename:pom.xml {band}'))

    seen = set()
    emitted = 0
    per_target_pages = 10         # 10 pages × 100 = up to 1000 repos/query (the cap)
    for tname, q in queries:
        if emitted >= max_repos:
            break
        for page in range(1, per_target_pages + 1):
            if emitted >= max_repos:
                break
            data = gh(session, "/search/code", {
                "q": q, "per_page": 100, "page": page,
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
            if len(data["items"]) < 100:
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
    """
    Yield (sha, message) for commits (most recent first), filtered to commits
    touching `path`. The message comes free in the list response, so callers
    can cheaply pre-filter (looks_like_bump) and skip the expensive per-commit
    detail fetch for commits that clearly aren't dependency bumps.
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
            yield c["sha"], c.get("commit", {}).get("message", "")
            collected += 1
        if len(items) < 100:
            break
        page += 1
        time.sleep(0.2)


def get_commit_detail(session, full_name: str, sha: str):
    return gh(session, f"/repos/{full_name}/commits/{sha}")


# Cheap, message-only pre-screen so we only spend a commit-detail API call on
# commits that plausibly are a dependency bump. Without this, a single big repo
# can burn the whole hourly REST quota (5000 calls) fetching details for every
# pom-touching commit — most of which are unrelated build/pom edits — and the
# crawl covers only ~15 repos/hour and finds nothing.
_BUMP_VERB_TOKENS = ("bump", "upgrade", "upgrading", "update", "updating",
                     "dependabot", "renovate", "dependenc", "migrat", "version")
# Distinctive artifact/groupId tokens for the seven targets.
_BUMP_ARTIFACT_TOKENS = ("mockito", "logback", "slf4j", "poi-scratchpad",
                         "org.apache.poi", "jsoup", "httpclient", "github-api")


def looks_like_bump(message: str) -> bool:
    """True if a commit message plausibly describes a dependency bump."""
    if not message:
        return False
    m = message.lower()
    return (any(t in m for t in _BUMP_VERB_TOKENS)
            or any(t in m for t in _BUMP_ARTIFACT_TOKENS))


# ── BUMP-targeted candidate screening ─────────────────────────────────────────

def screen_bump_commit(session, full_name, sha, detail, targets):
    """
    Decide whether a commit is a target *version bump*, independent of whether
    the client adaptation is in this same commit. This is the first half of the
    relaxed (PR-aware) screening: it only looks at the pom.

    Returns (group_id, artifact_id, old_ver, new_ver, target, pom_file) or
    None. Requires exactly one changed pom.xml whose diff is a single
    same-dependency version bump matching one of the active `targets`.
    """
    if not detail or "files" not in detail:
        return None

    files = detail["files"]
    pom_files = [f for f in files if f["filename"].endswith("pom.xml")]
    if len(pom_files) != 1:
        return None

    STATS["pom_commits"] += 1
    diff_cache = {"text": None}
    pom_chunk = get_file_patch(session, full_name, sha, pom_files[0], diff_cache)
    if not is_single_dep_version_bump(pom_chunk):
        STATS["reject_not_single_version_change"] += 1
        return None

    dep_info = parse_pom_diff(pom_chunk)
    if dep_info:
        group_id, artifact_id, old_ver, new_ver = dep_info
        target = match_target(group_id, artifact_id, old_ver, new_ver, targets)
    else:
        # Fall back to a <properties> bump (e.g. <mockito.version>) — invisible
        # to the plain-<version> parser but very common (dependabot, pinned
        # versions). Attribute it to a target via a keyword in the property name.
        prop = parse_property_bump(pom_chunk)
        if not prop:
            STATS["reject_unparsed_version_change"] += 1
            return None
        prop_name, old_ver, new_ver = prop
        target = match_property_target(prop_name, old_ver, new_ver, targets)
        # No real groupId on a property line; use the target's and the prop name.
        group_id = target["group_id"] if target else None
        artifact_id = prop_name

    if not target:
        STATS["reject_not_a_target"] += 1
        return None

    STATS["bump_target_matched"] += 1
    return group_id, artifact_id, old_ver, new_ver, target, pom_files[0]["filename"]


def get_pr_for_commit(session, full_name: str, sha: str):
    """
    Return the PR that contains `sha` (first / lowest-numbered), or None.
    Uses the commit→PRs association endpoint; for a squash- or merge-commit
    this resolves the bump commit back to its pull request so we can look at
    the WHOLE PR for the client adaptation, not just this one commit.
    """
    pulls = gh(session, f"/repos/{full_name}/commits/{sha}/pulls")
    if not pulls:
        return None
    return sorted(pulls, key=lambda p: p.get("number", 0))[0]


def get_pr_files(session, full_name: str, number: int, max_files: int = 300):
    """Return the list of file dicts changed across an entire PR (paged)."""
    files, page = [], 1
    while len(files) < max_files:
        items = gh(session, f"/repos/{full_name}/pulls/{number}/files",
                   {"per_page": 100, "page": page})
        if not items:
            break
        files.extend(items)
        if len(items) < 100:
            break
        page += 1
        time.sleep(0.15)
    return files


def get_file_content(session, full_name: str, path: str, ref: str) -> str:
    """Return raw file content at a given ref, or '' on failure."""
    if not ref:
        return ""
    try:
        r = session.get(f"{GH_API}/repos/{full_name}/contents/{path}",
                        params={"ref": ref},
                        headers={**HEADERS_BASE, "Accept": "application/vnd.github.raw"},
                        timeout=30)
        return r.text if r.status_code == 200 else ""
    except Exception:
        return ""


def file_references_library(session, full_name, file_dict, ref, packages):
    """
    True if a changed .java file actually references the bumped library — first
    cheaply via its diff patch (already in hand), then, only if that misses,
    via the file's full content at `ref` (catches references whose import line
    sits outside a diff hunk, e.g. static-import / method-rename migrations).
    """
    patch = file_dict.get("patch", "") or ""
    if any(pkg in patch for pkg in packages):
        return True
    content = get_file_content(session, full_name, file_dict["filename"], ref)
    return any(pkg in content for pkg in packages)


def assemble_candidate(session, full_name, bump_sha, detail, bump, args):
    """
    Second half of screening: given a confirmed bump commit, locate the client
    adaptation and emit a (bump_sha, adapt_sha) candidate that 02_verify_bbc can
    confirm. The adaptation is found in priority order:

      1. SAME COMMIT — the bump commit itself changes production .java.
         adapt_sha = bump_sha, scope "commit". (02 applies the pom diff, then
         checks out this commit; identical to its original behaviour.)
      2. SAME PR — the PR containing the bump has production .java somewhere
         (a multi-commit migration, or dependabot bump + a maintainer fix).
         adapt_sha = the PR's MERGE commit, which contains BOTH bump and fix.

    A pure pom-only bump with no production adaptation anywhere (e.g. a plain
    dependabot merge) yields None — 02 could never confirm it as a BBC.
    Returns a candidate record or None.
    """
    group_id, artifact_id, old_ver, new_ver, target, pom_file = bump

    # Case 1: adaptation in the bump commit itself.
    commit_java = {f["filename"]: f for f in detail["files"]
                   if f["filename"].endswith(".java")}
    commit_nontest = [f for f in commit_java if "/test/" not in f.lower()]

    adaptation_scope = "commit"
    adapt_sha = bump_sha
    pr_number = pr_title = pr_url = None
    pr_total_files = None
    java_by_name = commit_java
    ref_sha = bump_sha

    if commit_nontest:
        adaptation_scope = "commit"
    elif args.adaptation_scope == "commit":
        # Same-commit-only mode: no production java in the bump commit → skip.
        STATS["reject_no_production_java"] += 1
        return None
    else:
        # Case 2: look at the PR that contains the bump; use its merge commit as
        # adapt_sha (it has both the bump and the fix).
        pr = get_pr_for_commit(session, full_name, bump_sha)
        merge_sha = (pr or {}).get("merge_commit_sha")
        if not pr or not merge_sha:
            STATS["reject_no_production_java"] += 1
            return None
        pr_files = get_pr_files(session, full_name, pr.get("number"))
        # A real breaking-change adaptation PR is FOCUSED. A sprawling PR (big
        # refactor / "restructuring merge") that merely contains the bump and
        # incidentally touches the library is a false pairing — reject it on
        # total PR size so we don't attribute a huge unrelated merge as the
        # adaptation.
        if len(pr_files) > args.max_pr_files:
            STATS["reject_pr_too_large"] += 1
            return None
        pr_total_files = len(pr_files)
        pr_java = {f["filename"]: f for f in pr_files
                   if f["filename"].endswith(".java")}
        if not [f for f in pr_java if "/test/" not in f.lower()]:
            STATS["reject_no_production_java"] += 1
            return None
        adaptation_scope = "pr"
        adapt_sha = merge_sha
        ref_sha = merge_sha
        java_by_name = pr_java
        pr_number = pr.get("number")
        pr_title = (pr.get("title") or "")[:200]
        pr_url = pr.get("html_url")

    java_files = list(java_by_name)
    non_test_java = [f for f in java_files if "/test/" not in f.lower()]
    test_java = [f for f in java_files if "/test/" in f.lower()]

    # Cap the adaptation size so a PR/commit that bumps a dep AND does a big
    # unrelated refactor isn't mistaken for a focused adaptation.
    if len(non_test_java) > args.max_adaptation_files:
        STATS["reject_too_many_adapt_files"] += 1
        return None

    # Record (and optionally require) that the adaptation actually USES the
    # bumped library — strong evidence it's a real breaking-change adaptation.
    packages = TARGET_LIBRARY_PACKAGES.get(target["name"], ())
    reference_files = [
        f for f in non_test_java
        if file_references_library(session, full_name, java_by_name[f], ref_sha, packages)
    ]
    library_referenced = bool(reference_files)
    if args.require_library_reference and not library_referenced:
        STATS["reject_no_library_ref"] += 1
        return None

    STATS["candidate"] += 1
    STATS[f"candidate_via_{adaptation_scope}"] += 1

    commit_msg = detail.get("commit", {}).get("message", "")
    smell_words = ["update", "upgrade", "bump", "migrat", "compati",
                   "fix", "break", "deprecat", "api"]
    has_smell = any(w in commit_msg.lower() for w in smell_words)

    return {
        "repo": full_name,
        "sha": bump_sha,                         # back-compat: == bump_sha
        "bump_sha": bump_sha,
        "adapt_sha": adapt_sha,
        "commit_url": f"https://github.com/{full_name}/commit/{bump_sha}",
        "commit_msg": commit_msg[:300],
        "group_id": group_id,
        "artifact_id": artifact_id,
        "old_version": old_ver,
        "new_version": new_ver,
        "pom_file": pom_file,
        "java_files_changed": java_files,
        "non_test_java_changed": non_test_java,
        "test_java_changed": test_java,
        "total_files_changed": len(detail["files"]),
        "commit_msg_has_smell": has_smell,
        "date": detail["commit"]["committer"]["date"],
        "source": "bump-targeted",
        "tier": target.get("tier", "bump"),     # "bump" (precise) or "known-bbc" (broad)
        # where the adaptation came from: "commit" (bump_sha) or "pr" (merge sha)
        "adaptation_scope": adaptation_scope,
        "pr_number": pr_number,
        "pr_title": pr_title,
        "pr_url": pr_url,
        "pr_total_files": pr_total_files,
        # evidence the adaptation actually uses the bumped library
        "library_referenced": library_referenced,
        "library_reference_packages": list(packages),
        "library_reference_files": reference_files,
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

    # Default: code search over pom.xml for each active target's groupId, then
    # fetch repo metadata for each hit. This is the path that finds the bumps.
    for full_name in search_code_repos(session, args.max_repos, args._active_targets):
        if full_name.lower() in seen:
            continue
        seen.add(full_name.lower())
        repo = get_repo(session, full_name)
        if not repo:
            continue
        # Stars gate: code search has no star qualifier and its result objects
        # carry no star count, so it floods with ★0 toy/homework repos. get_repo
        # already fetched full metadata, so we can filter here for free — and
        # skipping a low-star repo now avoids its whole tree+commit crawl. Seeds
        # (yielded above) are never subject to this gate.
        stars = repo.get("stargazers_count", 0)
        if stars < args.min_stars:
            print(f"[repo] {full_name}  ★{stars}  → skip (<{args.min_stars} stars)")
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
    ap.add_argument("--min-stars", type=int, default=5,
                    help="Minimum stars for a code-search-discovered repo "
                         "(default 5, matching the BUMP/Libraries.io selection "
                         "criterion). Filters out toy/homework projects that "
                         "code search surfaces in bulk. Seed repos are exempt.")
    ap.add_argument("--only-bump-clients", action="store_true",
                    help="Scan ONLY the seven BUMP client projects (skip search) "
                         "— fast reproduction of the canonical examples")
    ap.add_argument("--discover", choices=("code", "repo"), default="code",
                    help="How to find repos beyond the seeds: 'code' = GitHub "
                         "code search over pom.xml for each target's groupId "
                         "(high yield, default); 'repo' = generic repo search "
                         "with --query (low yield)")
    ap.add_argument("--target-set", choices=("bump", "known-bbc", "both"),
                    default="bump",
                    help="Which libraries to mine: 'bump' = the 7 precise BUMP "
                         "targets with exact version ranges (default); "
                         "'known-bbc' = the broad bbc_common library families "
                         "(major-or-minor bumps only); 'both' = both tiers, for "
                         "scaling the dataset toward hundreds/1000 samples. "
                         "Each record is tagged with its tier.")
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
    ap.add_argument("--max-commits-per-repo-total", type=int, default=80,
                    help="Hard cap on commit-DETAIL fetches per repo (only "
                         "bump-like commits, post message pre-screen, count "
                         "against this). Keeps one big repo from burning the "
                         "REST quota so the crawl covers more repos.")
    ap.add_argument("--max-poms-per-repo", type=int, default=5,
                    help="Max pom.xml paths to crawl per repo (shallowest first)")
    ap.add_argument("--adaptation-scope", choices=("auto", "commit"), default="auto",
                    help="How to locate the adaptation for the (bump_sha, "
                         "adapt_sha) pair: 'auto' (default) = use the bump "
                         "commit if it already changes production java, else "
                         "the PR's merge commit (covers multi-commit PRs and "
                         "dependabot bump + maintainer fix); 'commit' = "
                         "same-commit only (adapt_sha == bump_sha).")
    ap.add_argument("--max-adaptation-files", type=int, default=10,
                    help="Max non-test .java files in the adaptation set before "
                         "it's treated as a broad refactor and rejected")
    ap.add_argument("--max-pr-files", type=int, default=25,
                    help="When the adaptation is taken from a PR, reject the "
                         "pairing if the PR changed more than this many files "
                         "total — a focused breaking-change adaptation is small; "
                         "a big restructuring PR that merely contains the bump "
                         "is a false pairing.")
    ap.add_argument("--require-library-reference",
                    action=argparse.BooleanOptionalAction, default=False,
                    help="Mining favours recall: the library-reference signal "
                         "(does a production adaptation file import the bumped "
                         "library's package?) is always RECORDED on each record "
                         "but, by default, NOT used to drop candidates — "
                         "02_verify_bbc.py is what decides if a candidate is a "
                         "real BBC. Pass --require-library-reference to filter "
                         "at mining time (higher precision, lower recall).")
    ap.add_argument("--out", default="output/bump_candidates.jsonl",
                    help="Output JSONL path (default: output/bump_candidates.jsonl "
                         "under the directory you run from, i.e. "
                         "nadia_scripts/output/ when run from nadia_scripts/)")
    args = ap.parse_args()

    session = requests.Session()
    session.headers.update({**HEADERS_BASE, "Authorization": f"Bearer {args.token}"})

    # Resolve the active target list once (precise BUMP tier first) and stash it
    # for iter_repos' code-search discovery and the per-commit screening.
    args._active_targets = active_targets(args.target_set)
    print(f"[config] target-set={args.target_set} "
          f"({len(args._active_targets)} target families)", file=sys.stderr)

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
            inspected = 0          # commit messages looked at (cheap)
            detailed = 0           # commit details fetched (1 API call each)
            budget_hit = False
            for pom_path in pom_paths:
                if budget_hit or (target_n and found >= target_n):
                    break
                for sha, msg in get_commits(session, full_name, args.max_commits_per_repo, path=pom_path):
                    if target_n and found >= target_n:
                        break
                    if sha in seen_shas:
                        continue
                    seen_shas.add(sha)
                    inspected += 1

                    # Cheap message-only pre-screen: skip commits that don't look
                    # like a dependency bump without spending a detail API call.
                    if not looks_like_bump(msg):
                        continue

                    if detailed >= args.max_commits_per_repo_total:
                        print(f"  [info] hit per-repo detail budget "
                              f"({args.max_commits_per_repo_total} fetches), moving on")
                        budget_hit = True
                        break

                    try:
                        detail = get_commit_detail(session, full_name, sha)
                        # Stage 1: is this commit a target version bump?
                        bump = screen_bump_commit(session, full_name, sha, detail,
                                                  args._active_targets)
                        # Stage 2: find the adaptation (same commit or whole PR).
                        rec = (assemble_candidate(session, full_name, sha, detail, bump, args)
                               if bump else None)
                    except Exception as e:
                        print(f"  [warn] {sha[:8]}: {e}", file=sys.stderr)
                        continue

                    detailed += 1
                    if detailed % 20 == 0:
                        print(f"  … {inspected} commits inspected, {detailed} bump-like "
                              f"details fetched, {found} candidates so far")

                    if rec:
                        where = (f"PR #{rec['pr_number']}" if rec['adaptation_scope'] == "pr"
                                 else "same commit")
                        print(f"  ✓ CANDIDATE {sha[:8]}  [{rec['bump_target']}]  "
                              f"{rec['group_id']}:{rec['artifact_id']}  "
                              f"{rec['old_version']} → {rec['new_version']}  "
                              f"(adaptation in {where})")
                        fout.write(json.dumps(rec) + "\n")
                        fout.flush()
                        found += 1

                    time.sleep(0.15)   # stay well within secondary rate limits

            print(f"  [repo done] {inspected} commits inspected, "
                  f"{detailed} details fetched, {found} candidates total")
            print(f"  [funnel] {_funnel_str()}")

    stop = "reached target" if (target_n and found >= target_n) else "exhausted repos"
    print(f"\nDone ({stop}). {found} BUMP-targeted candidates "
          f"{'appended to' if args.append else 'written to'} {out_path}")
    print(f"[funnel total] {_funnel_str()}")


def _funnel_str():
    """Compact one-line view of the screening funnel for diagnostics."""
    keys = ["pom_commits", "reject_not_single_version_change",
            "reject_unparsed_version_change", "reject_not_a_target",
            "bump_target_matched", "reject_no_production_java",
            "reject_too_many_adapt_files", "reject_no_library_ref",
            "candidate", "candidate_via_pr", "candidate_via_commit"]
    return "  ".join(f"{k}={STATS.get(k, 0)}" for k in keys if STATS.get(k, 0))


if __name__ == "__main__":
    main()
