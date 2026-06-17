"""
filter_existing_candidates.py
─────────────────────────────
One-off: re-apply the current screening rules to an ALREADY-mined
candidates JSONL, without re-crawling GitHub.

Applies the rules that are checkable from the stored record fields:
  1. total_files_changed <= 8
  2. at most 5 changed .java files
  3. The bumped dependency is a known BBC-causing library
     (bbc_common.is_known_bbc_dep)

Note: the property-style multi-dependency check in
is_single_dep_version_bump() needs the raw pom diff, which is not stored
in the record, so it cannot be re-applied here — re-run
01_mine_candidates.py for a fully clean dataset. In practice, the
multi-dep commits that slipped through recorded a single (often
non-allowlisted) dependency, so the allowlist filter removes most of
them anyway.

Usage:
    python filter_existing_candidates.py [--in output/candidates_commit.jsonl] \
                                         [--out output/candidates_commit.filtered.jsonl] \
                                         [--max-files 8]
"""

import argparse
import json
import sys
from pathlib import Path

from bbc_common import is_known_bbc_dep

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Filter an existing candidates JSONL")
    ap.add_argument("--in",  dest="inp", default="output/candidates_commit.jsonl")
    ap.add_argument("--out", default="output/candidates_commit.filtered.jsonl")
    ap.add_argument("--max-files", type=int, default=8)
    ap.add_argument("--max-java", type=int, default=5)
    args = ap.parse_args()

    in_path = Path(args.inp)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    kept = dropped_files = dropped_java = dropped_dep = total = 0
    with in_path.open(encoding="utf-8") as fin, out_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            total += 1
            rec = json.loads(line)

            if rec.get("total_files_changed", 0) > args.max_files:
                dropped_files += 1
                continue

            if len(rec.get("java_files_changed", [])) > args.max_java:
                dropped_java += 1
                continue

            if not is_known_bbc_dep(rec.get("group_id"), rec.get("artifact_id")):
                dropped_dep += 1
                continue

            fout.write(json.dumps(rec) + "\n")
            kept += 1

    print(f"Read {total} records from {in_path}")
    print(f"  dropped (>{args.max_files} files):      {dropped_files}")
    print(f"  dropped (>{args.max_java} java files): {dropped_java}")
    print(f"  dropped (dep not in allowlist):  {dropped_dep}")
    print(f"  kept:                            {kept}")
    print(f"Wrote {kept} records to {out_path}")


if __name__ == "__main__":
    main()
