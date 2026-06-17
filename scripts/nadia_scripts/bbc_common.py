"""
bbc_common.py
─────────────
Shared GitHub + pom.xml-diff screening logic used by the mining script:
  - 01_mine_candidates.py (crawl repo commit history)

Produces candidates in a schema that feeds 02_verify_bbc.py.

Key fix vs the original (commit-scan-only) version:
  parse_pom_diff() now requires the groupId/artifactId on the removed
  <version> line to match the groupId/artifactId on the added <version>
  line. Without this, a commit that REMOVES dependency X and ADDS
  dependency Y (a library swap, e.g. Hamcrest -> AssertJ) passes the
  "exactly one version line removed + one added" check and gets
  misreported as a version bump of a single dependency. That's how a
  library swap ended up as a false-positive "confirmed_bbc" before.
"""

import re
import sys
import time

GH_API = "https://api.github.com"
HEADERS_BASE = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

# Libraries with well-documented behavioural breaking changes (BBCs) in the
# literature. We only keep candidate bumps of these dependencies, since they
# are known to have introduced BBCs that forced client adaptations. A bump is
# kept if its groupId equals one of these prefixes or sits under it (prefix + ".").
KNOWN_BBC_GROUP_PREFIXES = (
    "com.google.guava",            # Guava
    "junit",                       # JUnit 3/4 (junit:junit)
    "org.junit",                   # JUnit 5 (org.junit.jupiter, org.junit.*)
    "org.apache.logging.log4j",    # Log4j 2.x
    "log4j",                       # Log4j 1.x (log4j:log4j)
    "org.springframework",         # Spring Framework
    "com.fasterxml.jackson",       # Jackson
    "org.mockito",                 # Mockito
    "commons-io",                  # Apache Commons IO
    "commons-lang",                # Apache Commons Lang (1.x/2.x groupId)
    "org.apache.commons",          # Apache Commons (commons-lang3, etc.)
    "org.apache.httpcomponents",   # HttpClient 4 -> 5
    "com.squareup.okhttp3",        # OkHttp
    "org.hibernate",               # Hibernate (query API, session handling)
    "ch.qos.logback",              # Logback (appender handling)
    "org.mockserver",              # MockServer
)


def is_known_bbc_dep(group_id, artifact_id=None) -> bool:
    """True if the dependency belongs to a known BBC-causing library family."""
    if not group_id:
        return False
    g = group_id.strip().lower()
    return any(g == p or g.startswith(p + ".") for p in KNOWN_BBC_GROUP_PREFIXES)


def gh(session, path, params=None, raw=False):
    """GET from GitHub API with automatic rate-limit back-off."""
    url = path if path.startswith("http") else GH_API + path
    for attempt in range(6):
        r = session.get(url, params=params, timeout=30)
        if r.status_code == 200:
            return r if raw else r.json()
        if r.status_code in (403, 429):
            reset = int(r.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - time.time(), 1) + 2
            print(f"  [rate-limit] sleeping {wait:.0f}s …", file=sys.stderr)
            time.sleep(wait)
            continue
        if r.status_code in (404, 422):
            # 404: path/resource doesn't exist; 422: GitHub search cap reached
            return None
        r.raise_for_status()
    raise RuntimeError(f"Failed after retries: {url}")


def split_diff_by_file(diff: str):
    """Returns a dict filename -> diff_chunk from a unified diff string."""
    chunks = {}
    current_file = None
    current_lines = []
    for line in diff.splitlines(keepends=True):
        if line.startswith("diff --git "):
            if current_file:
                chunks[current_file] = "".join(current_lines)
            parts = line.split(" b/", 1)
            current_file = parts[1].strip() if len(parts) == 2 else None
            current_lines = [line]
        else:
            current_lines.append(line)
    if current_file:
        chunks[current_file] = "".join(current_lines)
    return chunks


def get_file_patch(session, full_name: str, sha: str, file_entry: dict, diff_cache: dict) -> str:
    """
    Return the diff chunk for one file in a commit. Uses the inline
    `patch` field that GitHub already includes in the commit-detail
    response (no extra request) — only falls back to fetching the full
    unified diff for commits large enough that GitHub omits inline
    patches. `diff_cache` is a shared {} the caller reuses across files in
    the same commit so the fallback fetch happens at most once per commit.
    """
    if "patch" in file_entry:
        return file_entry["patch"]

    if diff_cache.get("text") is None:
        url = f"{GH_API}/repos/{full_name}/commits/{sha}"
        r = session.get(url, headers={**HEADERS_BASE, "Accept": "application/vnd.github.diff"},
                         timeout=30)
        diff_cache["text"] = r.text if r.status_code == 200 else ""

    return split_diff_by_file(diff_cache["text"]).get(file_entry["filename"], "")


def is_single_dep_version_bump(pom_chunk: str) -> bool:
    """
    True when exactly ONE dependency version changes (one removal + one
    addition) and it sits inside a <dependency> block (not <parent>,
    <plugin>, <pluginManagement>, <build>).

    The count below matches BOTH direct <version> tags and property-style
    version tags (e.g. <org.springframework.version>), so a commit that
    bumps one dependency via <version> and another via a <properties>
    entry is correctly seen as a MULTI-dependency change and rejected.
    Without this, a property-style bump is invisible to a plain `<version>`
    regex and the commit slips through as a false single-dep bump.
    """
    version_changes = re.findall(r"^[+-]\s*<[\w.\-]*version>", pom_chunk, re.M)
    if len(version_changes) != 2:
        return False

    lines = pom_chunk.splitlines()
    forbidden = re.compile(r"<(parent|plugin|pluginManagement|build)>", re.I)
    dep_tag = re.compile(r"<dependency>", re.I)

    for i, line in enumerate(lines):
        if re.search(r"^[+-]\s*<version>", line):
            window = "\n".join(lines[max(0, i - 30):i])
            if forbidden.search(window):
                return False
            if not dep_tag.search(window):
                return False
    return True


def parse_pom_diff(diff_chunk: str):
    """
    Extract the dependency identity and old/new <version> from a pom.xml
    diff chunk. Returns (groupId, artifactId, old_version, new_version) or
    None.

    Requires the groupId/artifactId immediately above the removed version
    line to match the groupId/artifactId above the added version line —
    this is what distinguishes a real version bump of dependency X from a
    library *swap* (X removed, Y added) that happens to touch exactly one
    <version> line on each side.
    """
    lines = diff_chunk.splitlines()
    group_re = re.compile(r"<groupId>([^<]+)</groupId>")
    artifact_re = re.compile(r"<artifactId>([^<]+)</artifactId>")
    version_re = re.compile(r"^([+-])\s*<version>([^<]+)</version>")

    def nearest_context(i: int, sign: str):
        """Walk upward from line i looking for the groupId/artifactId this
        version line belongs to, ignoring lines added/removed on the
        opposite side of the diff."""
        other_sign = "-" if sign == "+" else "+"
        group_id = artifact_id = None
        for line in reversed(lines[max(0, i - 30):i]):
            if line.startswith(other_sign):
                continue
            if group_id is None:
                m = group_re.search(line)
                if m:
                    group_id = m.group(1).strip()
            if artifact_id is None:
                m = artifact_re.search(line)
                if m:
                    artifact_id = m.group(1).strip()
            if group_id and artifact_id:
                break
        return group_id, artifact_id

    old_version = new_version = None
    old_dep = new_dep = (None, None)

    for i, line in enumerate(lines):
        m = version_re.match(line)
        if not m:
            continue
        sign, ver = m.group(1), m.group(2).strip()
        if sign == "-":
            old_version = ver
            old_dep = nearest_context(i, sign)
        else:
            new_version = ver
            new_dep = nearest_context(i, sign)

    if not (old_version and new_version and old_version != new_version):
        return None

    # Same dependency identity required on both sides, otherwise this is a
    # library swap, not a version bump.
    if old_dep[1] and new_dep[1] and old_dep[1] != new_dep[1]:
        return None
    if old_dep[0] and new_dep[0] and old_dep[0] != new_dep[0]:
        return None

    group_id = new_dep[0] or old_dep[0]
    artifact_id = new_dep[1] or old_dep[1]
    return group_id, artifact_id, old_version, new_version


def build_candidate(session, full_name: str, sha: str, detail: dict, source: str = "commit-scan"):
    """
    Apply the BBC screening filters to a single commit's detail payload
    (as returned by GET /repos/{full}/commits/{sha}) and return a
    candidate record, or None if it doesn't pass.

    Filters:
      1. No more than 8 files changed (keep the adaptation focused)
      2. Exactly one pom.xml changed
      3. Between 1 and 5 .java files changed (adaptation signal; >5 is
         very likely a broad refactor, not a BBC adaptation)
      4. The pom.xml diff is a single same-dependency version bump
         (see parse_pom_diff / is_single_dep_version_bump)
      5. The bumped dependency is a known BBC-causing library
         (see KNOWN_BBC_GROUP_PREFIXES / is_known_bbc_dep)
    Repo-level filters (stars, fork, has tests) are the caller's job,
    since they're cheaper to check once per repo than per commit.
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
    if not java_files:
        return None

    # More than 5 changed Java files is very likely a broad refactor rather
    # than a focused adaptation to a single breaking change.
    if len(java_files) > 5:
        return None

    diff_cache = {"text": None}
    pom_chunk = get_file_patch(session, full_name, sha, pom_files[0], diff_cache)
    if not is_single_dep_version_bump(pom_chunk):
        return None

    dep_info = parse_pom_diff(pom_chunk)
    if not dep_info:
        return None

    group_id, artifact_id, old_ver, new_ver = dep_info

    # Restrict to libraries known in the literature to introduce BBCs.
    if not is_known_bbc_dep(group_id, artifact_id):
        return None
    non_test_java = [f for f in java_files if "/test/" not in f.lower()]
    test_java = [f for f in java_files if "/test/" in f.lower()]

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
        "source": source,
    }
