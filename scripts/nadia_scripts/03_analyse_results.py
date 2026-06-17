"""
03_analyse_results.py
─────────────────────
Phase 3: Summarise the verified BBC dataset.

Produces:
  - summary.json        — aggregate statistics
  - bbc_table.csv       — one row per confirmed BBC
  - effect_taxonomy.txt — breakdown matching the paper's taxonomy

Usage:
    python 03_analyse_results.py \
        --verified ../output/verified_bbcs.jsonl \
        --out-dir  ../output/analysis
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def load_jsonl(path):
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def semver_level(old: str, new: str) -> str:
    """Classify the version bump as Major / Minor / Patch / Other."""
    def parse(v):
        # strip common prefixes
        v = re.sub(r"^[vV]", "", v)
        parts = re.split(r"[.\-]", v)
        nums = []
        for p in parts:
            try:
                nums.append(int(p))
            except ValueError:
                break
        return nums

    o, n = parse(old), parse(new)
    # pad
    while len(o) < 3: o.append(0)
    while len(n) < 3: n.append(0)

    if n[0] != o[0]:
        return "Major"
    if n[1] != o[1]:
        return "Minor"
    if n[2] != o[2]:
        return "Patch"
    return "Other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verified", required=True)
    ap.add_argument("--out-dir",  default="../output/analysis")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_records  = load_jsonl(args.verified)
    confirmed    = [r for r in all_records
                    if r.get("verification", {}).get("status") == "confirmed_bbc"]
    syntactic    = [r for r in all_records
                    if r.get("verification", {}).get("status") == "syntactic_bc"]
    no_bc        = [r for r in all_records
                    if r.get("verification", {}).get("status") == "no_bc"]
    incomplete   = [r for r in all_records
                    if r.get("verification", {}).get("status") == "bbc_adaptation_incomplete"]

    print(f"Total candidates verified : {len(all_records)}")
    print(f"  confirmed_bbc           : {len(confirmed)}")
    print(f"  syntactic_bc (excluded) : {len(syntactic)}")
    print(f"  no_bc (excluded)        : {len(no_bc)}")
    print(f"  adaptation_incomplete   : {len(incomplete)}")
    print()

    # ── Semantic version level breakdown ──────────────────────────────────────
    semver_counter = Counter()
    for r in confirmed:
        level = semver_level(r.get("old_version","0"), r.get("new_version","0"))
        semver_counter[level] += 1

    print("Semantic version level of BBC-introducing updates:")
    for lvl in ["Major", "Minor", "Patch", "Other"]:
        n = semver_counter[lvl]
        pct = 100 * n / max(len(confirmed), 1)
        print(f"  {lvl:<8}  {n:4d}  ({pct:.1f}%)")
    print()

    # ── Taxonomy of Effect ────────────────────────────────────────────────────
    effect_counter = Counter()
    for r in confirmed:
        eff = r.get("verification", {}).get("bc_effect_category", "Unknown")
        effect_counter[eff] += 1

    # Broad categories
    test_failures = sum(effect_counter[k] for k in
                        ["TestAssertion", "ProgramAssertion"])
    test_errors   = sum(effect_counter[k] for k in
                        ["RuntimeException", "CheckedException", "Error", "ResourceError"])

    print("Taxonomy of Effect:")
    print(f"  Test Failures  : {test_failures}  ({100*test_failures/max(len(confirmed),1):.1f}%)")
    for k in ["TestAssertion", "ProgramAssertion"]:
        n = effect_counter[k]
        print(f"    {k:<22} {n:4d}  ({100*n/max(test_failures,1):.1f}% of failures)")
    print(f"  Test Errors    : {test_errors}  ({100*test_errors/max(len(confirmed),1):.1f}%)")
    for k in ["RuntimeException", "CheckedException", "Error", "ResourceError"]:
        n = effect_counter[k]
        print(f"    {k:<22} {n:4d}  ({100*n/max(test_errors,1):.1f}% of errors)")
    print()

    # ── Exception types encountered ───────────────────────────────────────────
    exc_counter = Counter()
    for r in confirmed:
        for exc in r.get("verification", {}).get("exception_types", []):
            exc_counter[exc] += 1

    print("Top exception types across confirmed BBCs:")
    for exc, cnt in exc_counter.most_common(10):
        print(f"  {exc:<55} {cnt}")
    print()

    # ── Adaptation signals ────────────────────────────────────────────────────
    non_test_adaptations = sum(
        1 for r in confirmed if r.get("non_test_java_changed")
    )
    test_only_adaptations = sum(
        1 for r in confirmed
        if r.get("test_java_changed") and not r.get("non_test_java_changed")
    )
    print("Adaptation type:")
    print(f"  Src + (possibly) test changes : {non_test_adaptations}")
    print(f"  Test-only changes             : {test_only_adaptations}")
    print()

    # ── Top adapted artifacts ─────────────────────────────────────────────────
    artifact_counter = Counter()
    for r in confirmed:
        key = f"{r.get('group_id','?')}:{r.get('artifact_id','?')}"
        artifact_counter[key] += 1

    print("Most-frequent BBC-causing artifacts:")
    for art, cnt in artifact_counter.most_common(10):
        print(f"  {art:<60} {cnt}")
    print()

    # ── Write CSV ─────────────────────────────────────────────────────────────
    csv_path = out_dir / "bbc_table.csv"
    fieldnames = [
        "repo", "sha", "commit_url", "group_id", "artifact_id",
        "old_version", "new_version", "semver_level",
        "bc_effect_category", "exception_types",
        "non_test_java_changed", "test_java_changed",
        "commit_msg_has_smell", "date",
        "baseline_tests", "pom_only_tests", "adapted_tests",
    ]
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in confirmed:
            v = r.get("verification", {})
            row = {
                **r,
                "semver_level":        semver_level(r.get("old_version","0"),
                                                     r.get("new_version","0")),
                "bc_effect_category":  v.get("bc_effect_category",""),
                "exception_types":     "; ".join(v.get("exception_types",[])),
                "baseline_tests":      json.dumps(v.get("baseline_tests",{})),
                "pom_only_tests":      json.dumps(v.get("pom_only_tests",{})),
                "adapted_tests":       json.dumps(v.get("adapted_tests",{})),
                "non_test_java_changed": "; ".join(r.get("non_test_java_changed",[])),
                "test_java_changed":     "; ".join(r.get("test_java_changed",[])),
            }
            w.writerow(row)

    print(f"CSV written to {csv_path}")

    # ── Write summary JSON ────────────────────────────────────────────────────
    summary = {
        "total_verified":    len(all_records),
        "confirmed_bbc":     len(confirmed),
        "syntactic_bc":      len(syntactic),
        "no_bc":             len(no_bc),
        "incomplete":        len(incomplete),
        "semver_breakdown":  dict(semver_counter),
        "effect_taxonomy": {
            "test_failures": test_failures,
            "test_errors":   test_errors,
            "by_category":   dict(effect_counter),
        },
        "top_exceptions":    dict(exc_counter.most_common(20)),
        "top_artifacts":     dict(artifact_counter.most_common(20)),
    }
    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"Summary written to {summary_path}")


if __name__ == "__main__":
    main()