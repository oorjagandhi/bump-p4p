#!/usr/bin/env python3
"""
Mine GitHub PRs for strict Java/Maven dependency-update adaptation candidates.

Goal:
Find merged GitHub PRs where:
  1. A pom.xml file has exactly one logical dependency version update.
  2. The pom.xml change is only one version-line replacement:
       - <version>old</version>
       + <version>new</version>
     or one dependency/version property replacement:
       - <mockito.version>old</mockito.version>
       + <mockito.version>new</mockito.version>
  3. At least one production Java file changes.
  4. No test files change.

This is designed to find cleaner candidate client adaptations:
  one-line pom.xml dependency update + main Java code changes.

Usage:
  python mine_strict_source_adaptations.py

Optional:
  python mine_strict_source_adaptations.py --max-pages 3 --output strict_source_adaptations
  python mine_strict_source_adaptations.py --queries-file queries.txt --max-pages 5

Token:
  Option 1:
    $env:GITHUB_TOKEN="your_token_here"

  Option 2:
    Put token in github_token.txt in the same folder as this script.
    Do NOT commit github_token.txt.

Outputs:
  strict_source_adaptations.csv
  strict_source_adaptations.jsonl
"""

import argparse
import csv
import json
import os
from pathlib import Path
import re
import time
from dataclasses import dataclass, asdict
from typing import Dict, Iterable, List, Optional, Tuple

import requests


GITHUB_API = "https://api.github.com"


DEFAULT_SEARCH_QUERIES = [
    '"pom.xml" "fix" "dependency" is:pr is:merged',
    '"pom.xml" "upgrade" "dependency" is:pr is:merged',
    '"pom.xml" "bump" "dependency" is:pr is:merged',
    '"pom.xml" "compatibility" "dependency" is:pr is:merged',
    '"pom.xml" "migration" "dependency" is:pr is:merged',
    '"pom.xml" "breaking" "dependency" is:pr is:merged',

    # Dependency-specific examples
    '"mockito-core" "fix" is:pr is:merged',
    '"kotlin-stdlib" "fix" is:pr is:merged',
    '"javaparser-core" "fix" is:pr is:merged',
    '"hsqldb" "fix" is:pr is:merged',
    '"jackson-databind" "fix" is:pr is:merged',
    '"guava" "fix" is:pr is:merged',
    '"logback-classic" "fix" is:pr is:merged',
]


ANY_JAVA_RE = re.compile(r".*\.java$", re.IGNORECASE)


@dataclass
class DependencyUpdate:
    pom_file: str
    group_id: Optional[str]
    artifact_id: Optional[str]
    old_version: str
    new_version: str
    update_type: str
    update_kind: str
    patch_context: str


@dataclass
class CandidatePR:
    repo: str
    pr_number: int
    pr_url: str
    title: str
    author: str
    created_at: str
    closed_at: Optional[str]
    merged_at: Optional[str]
    query: str
    changed_files_count: int
    pom_files_changed: str
    java_files_changed: str
    main_java_files_changed: str
    dependency_updates: str
    dependency_count: int
    adaptation_status: str
    adaptation_strength: str
    evidence: str


def get_github_token() -> Optional[str]:
    """
    Get GitHub token from:
      1. GITHUB_TOKEN environment variable, or
      2. github_token.txt in same folder as this script.
    """
    token = os.environ.get("GITHUB_TOKEN")

    if token:
        return token.strip()

    token_file = Path(__file__).parent / "github_token.txt"
    if token_file.exists():
        return token_file.read_text(encoding="utf-8").strip()

    return None


def get_headers() -> Dict[str, str]:
    token = get_github_token()

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "strict-source-adaptation-miner",
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    return headers


def request_json(url: str, params: Optional[Dict] = None, retries: int = 3):
    headers = get_headers()

    for attempt in range(retries):
        response = requests.get(url, headers=headers, params=params, timeout=40)

        if response.status_code in (403, 429):
            remaining = response.headers.get("X-RateLimit-Remaining")
            reset = response.headers.get("X-RateLimit-Reset")

            if remaining == "0" and reset:
                sleep_for = max(int(reset) - int(time.time()) + 5, 10)
                print(f"[rate limit] sleeping for {sleep_for}s")
                time.sleep(sleep_for)
                continue

            print(f"[warning] {response.status_code}: {response.text[:300]}")
            time.sleep(20 * (attempt + 1))
            continue

        if response.status_code >= 500:
            print(f"[server error] {response.status_code}, retrying...")
            time.sleep(10 * (attempt + 1))
            continue

        response.raise_for_status()
        return response.json(), response.headers

    raise RuntimeError(f"Failed after retries: {url}")


def search_prs(query: str, max_pages: int = 2) -> Iterable[Dict]:
    """
    Search merged PRs using GitHub issue search.
    GitHub PRs are returned through the issues search endpoint.
    """
    for page in range(1, max_pages + 1):
        print(f"  search page {page}: {query}")

        data, _headers = request_json(
            f"{GITHUB_API}/search/issues",
            params={
                "q": query,
                "per_page": 100,
                "page": page,
                "sort": "updated",
                "order": "desc",
            },
        )

        items = data.get("items", [])
        if not items:
            break

        for item in items:
            if "pull_request" in item:
                yield item

        time.sleep(2)


def parse_repo_from_repository_url(repository_url: str) -> str:
    return repository_url.replace(f"{GITHUB_API}/repos/", "")


def get_pr(repo: str, pr_number: int) -> Dict:
    data, _headers = request_json(f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}")
    return data


def get_pr_files(repo: str, pr_number: int) -> List[Dict]:
    files: List[Dict] = []
    page = 1

    while True:
        data, _headers = request_json(
            f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/files",
            params={"per_page": 100, "page": page},
        )

        if not data:
            break

        files.extend(data)

        if len(data) < 100:
            break

        page += 1
        time.sleep(1)

    return files


def short_patch_context(patch: str, max_len: int = 1200) -> str:
    patch = patch or ""
    patch = patch.strip()

    if len(patch) <= max_len:
        return patch

    return patch[:max_len] + "\n...[truncated]..."


def version_update_type(old: str, new: str) -> str:
    """
    Basic SemVer-ish classifier:
      major: 1.x.x -> 2.x.x
      minor: 1.2.x -> 1.3.x
      patch: 1.2.3 -> 1.2.4
    """
    old_nums = re.findall(r"\d+", old)
    new_nums = re.findall(r"\d+", new)

    if len(old_nums) < 3 or len(new_nums) < 3:
        return "unknown"

    old_major, old_minor, old_patch = map(int, old_nums[:3])
    new_major, new_minor, new_patch = map(int, new_nums[:3])

    if new_major != old_major:
        return "major"
    if new_minor != old_minor:
        return "minor"
    if new_patch != old_patch:
        return "patch"

    return "other"


def extract_nearby_tag(text: str, tag: str) -> Optional[str]:
    pattern = rf"<{tag}>\s*([^<]+)\s*</{tag}>"
    match = re.search(pattern, text)

    if match:
        return match.group(1).strip()

    return None


def is_version_like(value: str) -> bool:
    """
    Avoid treating random property changes as dependency versions.
    """
    value = value.strip()
    return bool(re.search(r"\d+\.\d+", value))


def extract_dependency_updates_from_pom_patch(filename: str, patch: str) -> List[DependencyUpdate]:
    """
    Extract likely dependency version updates from pom.xml patch.

    Handles direct dependency version changes:
      - <version>1.0.0</version>
      + <version>1.1.0</version>

    Handles property version changes:
      - <mockito.version>4.11.0</mockito.version>
      + <mockito.version>5.1.1</mockito.version>

    This is heuristic and should be manually validated.
    """
    if not patch:
        return []

    updates: List[DependencyUpdate] = []
    lines = patch.splitlines()

    for i in range(len(lines) - 1):
        old_line = lines[i]
        new_line = lines[i + 1]

        if not old_line.startswith("-") or not new_line.startswith("+"):
            continue

        if old_line.startswith("---") or new_line.startswith("+++"):
            continue

        old_content = old_line[1:].strip()
        new_content = new_line[1:].strip()

        # Case 1: direct <version> change
        old_ver_match = re.match(r"<version>\s*([^<]+)\s*</version>", old_content)
        new_ver_match = re.match(r"<version>\s*([^<]+)\s*</version>", new_content)

        if old_ver_match and new_ver_match:
            old_version = old_ver_match.group(1).strip()
            new_version = new_ver_match.group(1).strip()

            if old_version == new_version:
                continue

            if not is_version_like(old_version) or not is_version_like(new_version):
                continue

            context_start = max(0, i - 20)
            context_end = min(len(lines), i + 20)
            context = "\n".join(lines[context_start:context_end])

            group_id = extract_nearby_tag(context, "groupId")
            artifact_id = extract_nearby_tag(context, "artifactId")

            updates.append(DependencyUpdate(
                pom_file=filename,
                group_id=group_id,
                artifact_id=artifact_id,
                old_version=old_version,
                new_version=new_version,
                update_type=version_update_type(old_version, new_version),
                update_kind="direct_dependency_version",
                patch_context=short_patch_context(context),
            ))

            continue

        # Case 2: dependency property change
        old_prop_match = re.match(r"<([^>/\s]+)>\s*([^<]+)\s*</\1>", old_content)
        new_prop_match = re.match(r"<([^>/\s]+)>\s*([^<]+)\s*</\1>", new_content)

        if old_prop_match and new_prop_match:
            old_tag = old_prop_match.group(1).strip()
            old_version = old_prop_match.group(2).strip()
            new_tag = new_prop_match.group(1).strip()
            new_version = new_prop_match.group(2).strip()

            if old_tag != new_tag:
                continue

            if old_version == new_version:
                continue

            if old_tag.lower() in {"version", "modelversion"}:
                continue

            if not is_version_like(old_version) or not is_version_like(new_version):
                continue

            tag_lower = old_tag.lower()

            # Keep only dependency-ish property names.
            if not any(keyword in tag_lower for keyword in [
                "version",
                "mockito",
                "kotlin",
                "junit",
                "guava",
                "jackson",
                "logback",
                "slf4j",
                "hsqldb",
                "javaparser",
                "bytebuddy",
                "byte-buddy",
                "assertj",
                "hamcrest",
            ]):
                continue

            context_start = max(0, i - 20)
            context_end = min(len(lines), i + 20)
            context = "\n".join(lines[context_start:context_end])

            updates.append(DependencyUpdate(
                pom_file=filename,
                group_id=None,
                artifact_id=old_tag,
                old_version=old_version,
                new_version=new_version,
                update_type=version_update_type(old_version, new_version),
                update_kind="property_version",
                patch_context=short_patch_context(context),
            ))

    return updates


def is_test_file(filename: str) -> bool:
    """
    Exclude if ANY changed file is clearly test-related.

    This catches:
      - src/test
      - test resources
      - integration tests
      - files named *Test.java, *Tests.java, *IT.java, *Spec.java
    """
    path = filename.replace("\\", "/").lower()
    name = path.split("/")[-1]

    return (
        "/src/test/" in path
        or "/test/" in path
        or "/tests/" in path
        or "/it/" in path
        or "/integration-test/" in path
        or "/src/it/" in path
        or "testresources" in path
        or "test-resources" in path
        or name.endswith("test.java")
        or name.endswith("tests.java")
        or name.endswith("itest.java")
        or name.endswith("it.java")
        or name.endswith("spec.java")
    )


def classify_java_files(java_files: List[str]) -> Tuple[List[str], List[str], List[str]]:
    main_files = []
    test_files = []
    other_files = []

    for file in java_files:
        normalized = file.replace("\\", "/")

        if is_test_file(normalized):
            test_files.append(file)
        elif "/src/main/java/" in normalized or normalized.startswith("src/main/java/"):
            main_files.append(file)
        else:
            other_files.append(file)

    return test_files, main_files, other_files


def count_meaningful_pom_changed_lines(pom_files: List[Dict]) -> int:
    """
    Count meaningful changed lines in pom.xml patches.

    A one-line version update normally appears as two diff lines:
      - <version>old</version>
      + <version>new</version>

    So exactly one logical changed line means exactly 2 meaningful diff lines.
    """
    count = 0

    for pom_file in pom_files:
        patch = pom_file.get("patch", "") or ""

        for line in patch.splitlines():
            if line.startswith("---") or line.startswith("+++"):
                continue

            if not (line.startswith("-") or line.startswith("+")):
                continue

            content = line[1:].strip()

            if not content:
                continue

            if content.startswith("<!--") or content.startswith("-->"):
                continue

            count += 1

    return count


def has_only_one_logical_pom_change(
    pom_files: List[Dict],
    dependency_updates: List[DependencyUpdate]
) -> bool:
    """
    Keep only PRs where pom.xml has exactly one logical dependency version update.

    Requirements:
      - exactly one detected dependency update
      - exactly two meaningful changed pom lines:
          one '-' old version line
          one '+' new version line
    """
    return (
        len(dependency_updates) == 1
        and count_meaningful_pom_changed_lines(pom_files) == 2
    )


def classify_candidate(
    title: str,
    body: str,
    dependency_updates: List[DependencyUpdate],
    java_files: List[str],
    changed_files_count: int
) -> Tuple[str, str, str]:
    """
    Classify strict source adaptation candidates.
    """
    text = f"{title}\n{body}".lower()
    test_files, main_files, other_files = classify_java_files(java_files)

    repair_words = [
        "fix",
        "fixes",
        "fixed",
        "upgrade",
        "update",
        "dependency update",
        "bump",
        "breaking",
        "compatibility",
        "migration",
        "dependabot",
        "renovate",
    ]

    has_repair_language = any(word in text for word in repair_words)

    if len(dependency_updates) == 1 and main_files and has_repair_language:
        return (
            "STRICT_SOURCE_ADAPTATION_CANDIDATE",
            "HIGH",
            "Exactly one logical pom.xml dependency version update, no test files changed, and production Java files changed with update/repair language."
        )

    if len(dependency_updates) == 1 and main_files:
        return (
            "STRICT_POSSIBLE_SOURCE_ADAPTATION",
            "MEDIUM",
            "Exactly one logical pom.xml dependency version update, no test files changed, and production Java files changed."
        )

    return (
        "UNKNOWN",
        "LOW",
        "Matched basic filters, but relationship between dependency update and Java changes is unclear."
    )


def process_pr(item: Dict, query: str) -> Optional[CandidatePR]:
    repo = parse_repo_from_repository_url(item["repository_url"])
    pr_number = item["number"]

    try:
        pr = get_pr(repo, pr_number)
    except Exception as exc:
        print(f"    [skip] failed to fetch PR {repo}#{pr_number}: {exc}")
        return None

    if not pr.get("merged_at"):
        return None

    try:
        files = get_pr_files(repo, pr_number)
    except Exception as exc:
        print(f"    [skip] failed to fetch files {repo}#{pr_number}: {exc}")
        return None

    changed_filenames = [f.get("filename", "") for f in files]

    pom_files = [
        f for f in files
        if f.get("filename", "").endswith("pom.xml")
    ]

    java_files = [
        f.get("filename", "")
        for f in files
        if ANY_JAVA_RE.match(f.get("filename", ""))
    ]

    if not pom_files:
        return None

    if not java_files:
        return None

    # Strict rule: exclude PR if any test-related file changed.
    test_files_changed = [name for name in changed_filenames if is_test_file(name)]
    if test_files_changed:
        return None

    test_java_files, main_java_files, other_java_files = classify_java_files(java_files)

    # Strict rule: require production Java source changes.
    if not main_java_files:
        return None

    dependency_updates: List[DependencyUpdate] = []

    for pom_file in pom_files:
        filename = pom_file.get("filename", "")
        patch = pom_file.get("patch", "")
        dependency_updates.extend(
            extract_dependency_updates_from_pom_patch(filename, patch)
        )

    if not dependency_updates:
        return None

    # Strict rule: exactly one logical pom.xml dependency update.
    if not has_only_one_logical_pom_change(pom_files, dependency_updates):
        return None

    title = pr.get("title") or item.get("title", "")
    body = pr.get("body") or ""

    status, strength, evidence = classify_candidate(
        title=title,
        body=body,
        dependency_updates=dependency_updates,
        java_files=java_files,
        changed_files_count=len(files),
    )

    dep_updates_json = json.dumps(
        [asdict(update) for update in dependency_updates],
        ensure_ascii=False
    )

    return CandidatePR(
        repo=repo,
        pr_number=pr_number,
        pr_url=pr.get("html_url", item.get("html_url", "")),
        title=title,
        author=(pr.get("user") or {}).get("login", ""),
        created_at=pr.get("created_at", ""),
        closed_at=pr.get("closed_at"),
        merged_at=pr.get("merged_at"),
        query=query,
        changed_files_count=len(files),
        pom_files_changed=";".join([f.get("filename", "") for f in pom_files]),
        java_files_changed=";".join(java_files),
        main_java_files_changed=";".join(main_java_files),
        dependency_updates=dep_updates_json,
        dependency_count=len(dependency_updates),
        adaptation_status=status,
        adaptation_strength=strength,
        evidence=evidence,
    )


def write_outputs(candidates: List[CandidatePR], output_prefix: str) -> None:
    csv_path = f"{output_prefix}.csv"
    jsonl_path = f"{output_prefix}.jsonl"

    fieldnames = list(asdict(candidates[0]).keys()) if candidates else [
        "repo",
        "pr_number",
        "pr_url",
        "title",
        "author",
        "created_at",
        "closed_at",
        "merged_at",
        "query",
        "changed_files_count",
        "pom_files_changed",
        "java_files_changed",
        "main_java_files_changed",
        "dependency_updates",
        "dependency_count",
        "adaptation_status",
        "adaptation_strength",
        "evidence",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for candidate in candidates:
            writer.writerow(asdict(candidate))

    with open(jsonl_path, "w", encoding="utf-8") as f:
        for candidate in candidates:
            f.write(json.dumps(asdict(candidate), ensure_ascii=False) + "\n")

    print(f"\nWrote {len(candidates)} candidates:")
    print(f"  {csv_path}")
    print(f"  {jsonl_path}")


def load_queries_from_file(path: Optional[str]) -> List[str]:
    if not path:
        return DEFAULT_SEARCH_QUERIES

    with open(path, "r", encoding="utf-8") as f:
        queries = [
            line.strip()
            for line in f
            if line.strip() and not line.strip().startswith("#")
        ]

    return queries


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--queries-file",
        help="Text file with one GitHub search query per line."
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=2,
        help="Search pages per query, 100 results per page."
    )
    parser.add_argument(
        "--output",
        default="strict_source_adaptations",
        help="Output prefix for CSV/JSONL."
    )
    parser.add_argument(
        "--sleep",
        type=float,
        default=1.0,
        help="Sleep between PR processing requests."
    )

    args = parser.parse_args()

    if not get_github_token():
        print("Warning: no GitHub token found. You will hit low GitHub API rate limits.")

    queries = load_queries_from_file(args.queries_file)

    seen_prs = set()
    candidates: List[CandidatePR] = []

    print(f"Running {len(queries)} search queries...")
    print(f"Max pages per query: {args.max_pages}")

    for query in queries:
        print(f"\nQUERY: {query}")

        for item in search_prs(query, max_pages=args.max_pages):
            repo = parse_repo_from_repository_url(item["repository_url"])
            key = (repo, item["number"])

            if key in seen_prs:
                continue

            seen_prs.add(key)

            print(f"  checking {repo}#{item['number']} — {item.get('title', '')[:80]}")

            candidate = process_pr(item, query=query)

            if candidate:
                print(f"    KEEP: {candidate.adaptation_status} | {candidate.pr_url}")
                candidates.append(candidate)

                # Write incrementally so progress is not lost if the script stops.
                write_outputs(candidates, args.output)
            else:
                print("    skip")

            time.sleep(args.sleep)

    write_outputs(candidates, args.output)

    print("\nSUMMARY")
    counts: Dict[str, int] = {}

    for candidate in candidates:
        counts[candidate.adaptation_status] = counts.get(candidate.adaptation_status, 0) + 1

    for status, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {status:<40} {count}")

    print("\nNext step: manually inspect candidates and confirm whether Java changes relate to the dependency update.")


if __name__ == "__main__":
    main()