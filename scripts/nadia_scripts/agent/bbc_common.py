"""Shared utilities for the BBC agent pipeline."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Iterable

import requests

GH_API = "https://api.github.com"
DEFAULT_MODEL = "claude-sonnet-4-6"

HEADERS_BASE = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

JAVA_PACKAGE_BY_GROUP = {
    "com.google.guava": ("com.google.common",),
    "org.apache.httpcomponents": ("org.apache.http",),
    "commons-io": ("org.apache.commons.io",),
    "org.apache.commons": ("org.apache.commons",),
    "com.thoughtworks.xstream": ("com.thoughtworks.xstream",),
    "org.apache.poi": ("org.apache.poi",),
    "org.mockito": ("org.mockito",),
    "org.springframework.security": ("org.springframework.security",),
    "org.springframework": ("org.springframework",),
    "com.fasterxml.jackson": ("com.fasterxml.jackson",),
    "org.apache.logging.log4j": ("org.apache.logging.log4j",),
    "ch.qos.logback": ("ch.qos.logback",),
    "org.slf4j": ("org.slf4j",),
    "org.junit": ("org.junit", "org.junit.jupiter"),
    "junit": ("org.junit", "junit"),
    "org.hibernate": ("org.hibernate",),
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def agent_dir() -> Path:
    return Path(__file__).resolve().parent


def default_output_dir() -> Path:
    return agent_dir() / "output"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL: {exc}") from exc
    return records


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")


def write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")


def github_session(token: str | None = None) -> requests.Session:
    token = token or os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    session = requests.Session()
    session.headers.update(HEADERS_BASE)
    if token:
        session.headers["Authorization"] = f"Bearer {token}"
    return session


def gh_get(
    session: requests.Session,
    path: str,
    *,
    accept: str | None = None,
    params: dict[str, Any] | None = None,
    raw: bool = False,
    retries: int = 8,
) -> Any:
    url = path if path.startswith("http") else GH_API + path
    headers = dict(session.headers)
    if accept:
        headers["Accept"] = accept

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            resp = session.get(url, headers=headers, params=params, timeout=45)
        except requests.RequestException as exc:
            last_error = exc
            wait = min(8 * (attempt + 1), 60)
            print(f"[github] network {type(exc).__name__}; retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue

        if resp.status_code == 200:
            return resp.text if raw else resp.json()
        if resp.status_code in (403, 429):
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - time.time(), 1) + 2
            print(f"[github] rate limited; sleeping {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)
            continue
        if resp.status_code in (500, 502, 503, 504):
            wait = min(8 * (attempt + 1), 60)
            print(f"[github] transient {resp.status_code}; retrying in {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        if resp.status_code in (404, 410, 422):
            return None
        resp.raise_for_status()

    raise RuntimeError(f"GitHub GET failed after retries: {url}; last_error={last_error}")


def coalesce(record: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return None


def candidate_repo(record: dict[str, Any]) -> str:
    value = coalesce(record, "repo", "repository", "full_name", "repo_full_name")
    if isinstance(value, dict):
        value = coalesce(value, "full_name", "name")
    if not value or "/" not in str(value):
        raise ValueError(f"candidate missing GitHub repo full_name: keys={sorted(record)}")
    return str(value)


def candidate_sha(record: dict[str, Any]) -> str:
    value = coalesce(record, "sha", "commit", "commit_sha", "bump_sha", "head_sha", "merge_commit_sha")
    if isinstance(value, dict):
        value = coalesce(value, "sha", "id")
    if not value:
        raise ValueError("candidate missing commit sha")
    return str(value)


def candidate_library(record: dict[str, Any]) -> dict[str, Any]:
    lib = record.get("library")
    if isinstance(lib, dict):
        return {
            "group_id": coalesce(lib, "group_id", "groupId", "group"),
            "artifact_id": coalesce(lib, "artifact_id", "artifactId", "artifact"),
            "old_version": coalesce(lib, "old_version", "from_version", "previous_version"),
            "new_version": coalesce(lib, "new_version", "to_version", "current_version"),
        }
    return {
        "group_id": coalesce(record, "group_id", "groupId", "dependency_group_id"),
        "artifact_id": coalesce(record, "artifact_id", "artifactId", "dependency_artifact_id"),
        "old_version": coalesce(record, "old_version", "from_version", "previous_version"),
        "new_version": coalesce(record, "new_version", "to_version", "current_version"),
    }


def java_packages_for(group_id: str | None, artifact_id: str | None = None) -> tuple[str, ...]:
    group = (group_id or "").strip()
    artifact = (artifact_id or "").strip()
    packages: list[str] = []
    for prefix, mapped in JAVA_PACKAGE_BY_GROUP.items():
        if group == prefix or group.startswith(prefix + "."):
            packages.extend(mapped)
            break
    if group and group not in {"commons-io", "junit"}:
        packages.append(group)
    if artifact.startswith("commons-") and "org.apache.commons" not in packages:
        packages.append("org.apache.commons")
    return tuple(dict.fromkeys(p for p in packages if p))


def split_diff_by_file(diff: str) -> dict[str, str]:
    chunks: dict[str, str] = {}
    current_file: str | None = None
    current_lines: list[str] = []
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


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object from model")
    return value


def truncate_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    head = max_chars // 2
    tail = max_chars - head
    return text[:head] + "\n\n[... diff truncated for token budget ...]\n\n" + text[-tail:], True
