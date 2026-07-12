#!/usr/bin/env python3
"""Classify mined dependency bump candidates as BBC adaptations.

Reads ``agent/output/candidates.jsonl`` by default, fetches each commit's full
diff from GitHub, asks Claude for a strict structured classification, and writes
verifiable candidates to ``agent/output/classified.jsonl``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from anthropic import Anthropic
except ImportError:  # pragma: no cover - exercised in environments without deps
    Anthropic = None  # type: ignore[assignment]

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from bbc_common import (  # noqa: E402
    DEFAULT_MODEL,
    candidate_library,
    candidate_repo,
    candidate_sha,
    default_output_dir,
    ensure_dir,
    extract_json_object,
    gh_get,
    github_session,
    java_packages_for,
    read_jsonl,
    split_diff_by_file,
    truncate_text,
    write_jsonl,
)

REQUIRED_KEYS = {
    "is_adaptation",
    "confidence",
    "reasoning",
    "adaptation_type",
    "adaptation_location",
    "library_directly_called",
    "library_directly_called_evidence",
    "bbc_type",
    "expected_exception",
    "red_flags",
    "should_verify",
    "skip_reason",
}

VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_ADAPTATION_TYPES = {
    "null_guard",
    "api_replacement",
    "precondition_fix",
    "type_cast",
    "exception_handling",
    "allowlist",
    "limit_override",
    "import_change",
    "new_config_bean",
    "other",
}
VALID_LOCATIONS = {"production_source", "test_only", "both"}
VALID_BBC_TYPES = {
    "RuntimeException",
    "TestAssertion",
    "CheckedException",
    "ProgramAssertion",
    "ResourceError",
    "unclear",
}


def load_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def commit_metadata(session, repo: str, sha: str) -> dict[str, Any]:
    data = gh_get(session, f"/repos/{repo}/commits/{sha}")
    if not data:
        raise RuntimeError(f"commit not found: {repo}@{sha}")
    return data


def full_diff(session, repo: str, sha: str) -> str:
    text = gh_get(
        session,
        f"/repos/{repo}/commits/{sha}",
        accept="application/vnd.github.diff",
        raw=True,
    )
    if text is None:
        raise RuntimeError(f"diff not found: {repo}@{sha}")
    return str(text)


def changed_line_text(chunk: str) -> str:
    lines = []
    for line in chunk.splitlines():
        if line.startswith(("+++", "---", "diff --git", "@@")):
            continue
        if line.startswith(("+", "-")):
            lines.append(line[1:])
    return "\n".join(lines)


def has_library_reference(chunk: str, packages: tuple[str, ...]) -> bool:
    text = changed_line_text(chunk)
    for pkg in packages:
        escaped = re.escape(pkg)
        if re.search(rf"\bimport\s+{escaped}(?:\.|\b)", text):
            return True
        if re.search(rf"\b{escaped}\.", text):
            return True
    return False


def file_status_from_chunk(chunk: str) -> str:
    if "\nnew file mode " in chunk:
        return "added"
    if "\ndeleted file mode " in chunk:
        return "removed"
    return "modified"


def deterministic_summary(record: dict[str, Any], commit: dict[str, Any], diff: str) -> dict[str, Any]:
    lib = candidate_library(record)
    packages = java_packages_for(lib.get("group_id"), lib.get("artifact_id"))
    files = commit.get("files") or []
    chunks = split_diff_by_file(diff)

    java_files: list[dict[str, Any]] = []
    pom_files: list[dict[str, Any]] = []
    prod_count = 0
    test_count = 0
    lib_refs = []
    added_java = 0
    modified_java = 0

    for file_entry in files:
        filename = file_entry.get("filename") or ""
        status = file_entry.get("status") or file_status_from_chunk(chunks.get(filename, ""))
        patch = file_entry.get("patch") or chunks.get(filename, "")
        if filename.endswith(".java"):
            is_test = bool(re.search(r"(^|/)src/test/|(^|/)test/", filename.replace("\\", "/"), re.I))
            has_ref = has_library_reference(patch, packages)
            if is_test:
                test_count += 1
            else:
                prod_count += 1
            if status == "added":
                added_java += 1
            elif status == "modified":
                modified_java += 1
            item = {
                "filename": filename,
                "status": status,
                "is_test": is_test,
                "library_referenced": has_ref,
                "additions": file_entry.get("additions"),
                "deletions": file_entry.get("deletions"),
            }
            java_files.append(item)
            if has_ref:
                lib_refs.append(filename)
        elif filename.endswith("pom.xml"):
            patch = patch or ""
            pom_files.append(
                {
                    "filename": filename,
                    "status": status,
                    "dependency_blocks_added": len(re.findall(r"^\+\s*<dependency>", patch, re.M)),
                    "version_lines_added": len(re.findall(r"^\+\s*<[\w.\-]*version>", patch, re.M)),
                    "version_lines_removed": len(re.findall(r"^-\s*<[\w.\-]*version>", patch, re.M)),
                    "mentions_scope_test": bool(re.search(r"<scope>\s*test\s*</scope>", patch, re.I)),
                }
            )

    message = ((commit.get("commit") or {}).get("message") or record.get("commit_message") or "").strip()
    msg_lower = message.lower()
    featureish_message = bool(re.search(r"\b(add|feature|refactor|cleanup|format|style)\b", msg_lower))
    fixish_message = bool(re.search(r"\b(fix|bug|update|upgrade|bump|compat|migration|migrate)\b", msg_lower))

    red_flags: list[str] = []
    if java_files and not lib_refs:
        red_flags.append("changed Java files do not import or directly reference the bumped library package")
    if java_files and added_java == len(java_files) and modified_java == 0:
        red_flags.append("only new Java files were added")
    if any(p["dependency_blocks_added"] for p in pom_files):
        red_flags.append("pom.xml appears to add new dependency blocks")
    if featureish_message and not fixish_message:
        red_flags.append("commit message looks feature/refactor oriented")
    if len(files) > 20:
        red_flags.append("large commit with many changed files")

    return {
        "repo": candidate_repo(record),
        "sha": candidate_sha(record),
        "commit_message": message,
        "library": lib,
        "java_packages_expected": packages,
        "java_files": java_files,
        "pom_files": pom_files,
        "production_java_file_count": prod_count,
        "test_java_file_count": test_count,
        "library_referenced_files": lib_refs,
        "library_referenced": bool(lib_refs),
        "deterministic_red_flags": red_flags,
        "changed_file_count": len(files),
        "diff_stats": {
            "additions": commit.get("stats", {}).get("additions"),
            "deletions": commit.get("stats", {}).get("deletions"),
            "total": commit.get("stats", {}).get("total"),
        },
    }


def render_prompt(template: str, record: dict[str, Any], summary: dict[str, Any], diff: str) -> str:
    candidate_json = json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True)
    summary_json = json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True)
    return (
        template.replace("{{CANDIDATE_JSON}}", candidate_json)
        .replace("{{DIFF_SUMMARY_JSON}}", summary_json)
        .replace("{{DIFF_TEXT}}", diff)
    )


def call_claude(client: Any, model: str, prompt: str, max_tokens: int) -> dict[str, Any]:
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    parts = []
    for block in message.content:
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return extract_json_object("\n".join(parts))


def normalize_classification(value: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    out = dict(value)

    missing = REQUIRED_KEYS - set(out)
    if missing:
        errors.append(f"missing keys: {sorted(missing)}")

    out["is_adaptation"] = bool(out.get("is_adaptation"))
    out["library_directly_called"] = bool(out.get("library_directly_called"))
    out["should_verify"] = bool(out.get("should_verify"))

    if out.get("confidence") not in VALID_CONFIDENCE:
        errors.append(f"invalid confidence: {out.get('confidence')!r}")
        out["confidence"] = "low"
    if out.get("adaptation_type") not in VALID_ADAPTATION_TYPES:
        errors.append(f"invalid adaptation_type: {out.get('adaptation_type')!r}")
        out["adaptation_type"] = "other"
    if out.get("adaptation_location") not in VALID_LOCATIONS:
        errors.append(f"invalid adaptation_location: {out.get('adaptation_location')!r}")
        out["adaptation_location"] = "test_only"
    if out.get("bbc_type") not in VALID_BBC_TYPES:
        errors.append(f"invalid bbc_type: {out.get('bbc_type')!r}")
        out["bbc_type"] = "unclear"
    if not isinstance(out.get("red_flags"), list):
        errors.append("red_flags must be a list")
        out["red_flags"] = [str(out.get("red_flags"))] if out.get("red_flags") else []
    if out.get("expected_exception") in ("", "null"):
        out["expected_exception"] = None
    if out.get("skip_reason") in ("", "null"):
        out["skip_reason"] = None

    return out, errors


def enforce_strict_gates(classification: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    out = dict(classification)
    red_flags = list(out.get("red_flags") or [])
    for flag in summary.get("deterministic_red_flags") or []:
        if flag not in red_flags:
            red_flags.append(flag)

    hard_reject = False
    hard_reasons: list[str] = []
    java_files = summary.get("java_files") or []

    if java_files and not summary.get("library_referenced"):
        hard_reject = True
        hard_reasons.append("no changed Java file directly references the bumped library Java package")
    if java_files and all(f.get("status") == "added" for f in java_files):
        hard_reject = True
        hard_reasons.append("only new Java files were added")
    if any(p.get("dependency_blocks_added") for p in summary.get("pom_files") or []):
        hard_reject = True
        hard_reasons.append("pom.xml adds dependency blocks, not just a version bump")
    if not out.get("library_directly_called"):
        hard_reject = True
        hard_reasons.append("model did not identify a direct library API call")

    if hard_reject:
        out["is_adaptation"] = False
        out["should_verify"] = False
        out["confidence"] = "low"
        out["skip_reason"] = "; ".join(hard_reasons)

    out["red_flags"] = red_flags
    return out


def classify_one(
    *,
    record: dict[str, Any],
    session,
    client: Any,
    model: str,
    prompt_template: str,
    max_diff_chars: int,
    max_tokens: int,
) -> dict[str, Any]:
    repo = candidate_repo(record)
    sha = candidate_sha(record)
    commit = commit_metadata(session, repo, sha)
    diff = full_diff(session, repo, sha)
    diff, was_truncated = truncate_text(diff, max_diff_chars)
    summary = deterministic_summary(record, commit, diff)
    summary["diff_truncated"] = was_truncated

    prompt = render_prompt(prompt_template, record, summary, diff)
    raw = call_claude(client, model, prompt, max_tokens)
    classification, errors = normalize_classification(raw)
    if errors:
        classification.setdefault("red_flags", [])
        classification["red_flags"].extend(f"classifier_json_validation: {err}" for err in errors)
        classification["should_verify"] = False
        classification["is_adaptation"] = False
        classification["skip_reason"] = "invalid classifier JSON shape"

    classification = enforce_strict_gates(classification, summary)
    enriched = dict(record)
    enriched["classification"] = classification
    enriched["diff_summary"] = summary
    enriched["case_id"] = make_case_id(enriched)
    return enriched


def make_case_id(record: dict[str, Any]) -> str:
    lib = candidate_library(record)
    repo = candidate_repo(record).split("/")[-1]
    group = str(lib.get("group_id") or "library").split(".")[-1]
    artifact = str(lib.get("artifact_id") or group)
    sha = candidate_sha(record)[:8]
    raw = f"{artifact}-{repo}-{sha}".lower()
    return re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-")


def should_keep(record: dict[str, Any], include_skipped: bool) -> bool:
    cls = record.get("classification") or {}
    return include_skipped or bool(cls.get("should_verify"))


def parse_args() -> argparse.Namespace:
    out_dir = default_output_dir()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=out_dir / "candidates.jsonl")
    parser.add_argument("--output", type=Path, default=out_dir / "classified.jsonl")
    parser.add_argument("--prompt", type=Path, default=Path(__file__).with_name("prompts") / "classify_adaptation.txt")
    parser.add_argument("--github-token", default=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
    parser.add_argument("--anthropic-api-key", default=os.environ.get("ANTHROPIC_API_KEY"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-diff-chars", type=int, default=120_000)
    parser.add_argument("--max-tokens", type=int, default=1600)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--include-skipped", action="store_true", help="write rejected classifications too")
    parser.add_argument("--library-filter", help="substring matched against groupId:artifactId")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if Anthropic is None:
        print("anthropic package is not installed. Install it with: pip install anthropic", file=sys.stderr)
        return 2
    if not args.anthropic_api_key:
        print("ANTHROPIC_API_KEY is required for classification", file=sys.stderr)
        return 2

    records = read_jsonl(args.input)
    if args.library_filter:
        needle = args.library_filter.lower()
        records = [
            r
            for r in records
            if needle
            in f"{candidate_library(r).get('group_id')}:{candidate_library(r).get('artifact_id')}".lower()
        ]
    if args.limit is not None:
        records = records[: args.limit]

    ensure_dir(args.output.parent)
    prompt_template = load_prompt(args.prompt)
    session = github_session(args.github_token)
    client = Anthropic(api_key=args.anthropic_api_key)

    kept: list[dict[str, Any]] = []
    summary = Counter()
    failures = 0

    print(f"[classify] input={args.input} candidates={len(records)} output={args.output}")
    for idx, record in enumerate(records, 1):
        try:
            repo = candidate_repo(record)
            sha = candidate_sha(record)
            lib = candidate_library(record)
            dep = f"{lib.get('group_id')}:{lib.get('artifact_id')}"
            print(f"[classify] {idx}/{len(records)} {repo}@{sha[:8]} {dep}")
            enriched = classify_one(
                record=record,
                session=session,
                client=client,
                model=args.model,
                prompt_template=prompt_template,
                max_diff_chars=args.max_diff_chars,
                max_tokens=args.max_tokens,
            )
            cls = enriched["classification"]
            decision = "verify" if cls.get("should_verify") else "skip"
            summary[decision] += 1
            summary[f"confidence:{cls.get('confidence')}"] += 1
            summary[f"type:{cls.get('adaptation_type')}"] += 1
            print(
                f"  -> {decision} confidence={cls.get('confidence')} "
                f"type={cls.get('adaptation_type')} reason={cls.get('skip_reason') or cls.get('reasoning')}"
            )
            if should_keep(enriched, args.include_skipped):
                kept.append(enriched)
        except Exception as exc:  # keep mining runs alive across bad candidates
            failures += 1
            summary["failed"] += 1
            print(f"  !! failed: {type(exc).__name__}: {exc}", file=sys.stderr)

    write_jsonl(args.output, kept)
    print("[classify] summary")
    print(f"  input: {len(records)}")
    print(f"  written: {len(kept)}")
    print(f"  failures: {failures}")
    for key, value in sorted(summary.items()):
        print(f"  {key}: {value}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
