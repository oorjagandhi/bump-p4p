#!/usr/bin/env python3
"""
audit_traversal.py — record a mechanical traversal verdict into each verified case.

Context: `status: verified_bbc` currently conflates two different claims —
  (a) TRAVERSAL   a real client crossed the break boundary, broke, and adapted
                  (the witnessed bump -> break -> fix pair)
  (b) MECHANISM   the behavioural break is real and a harness reproduces it via a
                  version swap, but the client was already past the boundary and was
                  responding to the library's BEHAVIOUR, not to its own bump

Only (a) supports a claim about how clients respond to breaking updates. snakeyaml-mongoose
was audited honestly as (b); the other cases were never asked the question.

This writes an additive `traversal_audit` block. It does NOT modify `status` — the
taxonomy decision stays with the author.

Usage:
  python audit_traversal.py --dry-run       # print verdicts, write nothing
  python audit_traversal.py                 # write traversal_audit into each case
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


import argparse
import datetime
import json
from pathlib import Path

import bbc_e2e as B

HERE = Path(__file__).resolve().parent.parent
CASES = HERE / "verified_cases"

# (case file, break_id, repo, adaptation sha)
TARGETS = [
    ("xstream-logging-chainsaw.json", "xstream-1.4.17-to-1.4.19-forbiddenclass",
     "apache/logging-chainsaw", "7ec771e2fbc0"),
    ("xstream-tvrenamer.json", "xstream-1.4.17-to-1.4.19-forbiddenclass",
     "The-Ant-Forge/TVRenamer", "b236f68e"),
    ("xstream-axon-artshishkin.json", "xstream-1.4.17-to-1.4.19-forbiddenclass",
     "artshishkin/art-kargopolov-cqrs-saga-axon-microservices", "b76d747f8d27"),
    ("xstream-axon-saga-einsteinarbert.json", "xstream-1.4.17-to-1.4.19-forbiddenclass",
     "einsteinarbert/axon-saga-example", "dddd794b5d0f"),
    ("xstream-chaintrade-amirsnw.json", "xstream-1.4.17-to-1.4.19-forbiddenclass",
     "amirsnw/chainrtrade-axon-CQRS-DDD", "d408d4cac768"),
    ("xstream-spark.json", "xstream-1.4.17-to-1.4.19-forbiddenclass",
     "igniterealtime/Spark", "aad38d68"),
    ("poi-jadhavspeaks.json", "poi-4.1.2-to-5.x",
     "jadhavspeaks/file_compare_diffrent_ext", "156a9624"),
]

NOTE = ("Mechanical re-check after fixing a bug that made verify_traversal return a "
        "false negative for EVERY candidate (_gh called .get() on GitHub's list "
        "responses; find_boundary_bump swallowed the AttributeError as 'no commits'). "
        "All traversal verdicts recorded before this date are void.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    token = B._token()
    today = datetime.date.today().isoformat()

    for fname, break_id, repo, sha in TARGETS:
        # TARGETS carries bare filenames; cases are nested per library since
        # the 2026-08 reorg, so resolve by search rather than by join.
        path = CASES / fname
        if not path.exists():
            path = next(iter(CASES.glob(f"*/{fname}")), path)
        if not path.exists():
            print(f"  SKIP {fname} (missing)")
            continue
        brk = B.get_break(break_id)
        t = B.verify_traversal(repo, sha, brk, token)
        confirmed = bool(t.get("traversal_confirmed"))
        verdict = "traversal_confirmed" if confirmed else "behaviour_response_only"
        print(f"  [{'GOLD' if confirmed else '----'}] {fname:<42} {verdict:<26} "
              f"{t.get('reason','')[:70]}")
        if args.dry_run:
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        d["traversal_audit"] = {
            "audited_date": today,
            "verdict": verdict,
            "crossed_break_boundary_in_repo": confirmed,
            "shape": t.get("shape"),
            "distance_commits": t.get("distance_commits"),
            "bump": t.get("bump"),
            "reason": t.get("reason"),
            "checked_repo": repo,
            "checked_sha": sha,
            "note": NOTE,
        }
        path.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"         -> wrote traversal_audit into {fname}")


if __name__ == "__main__":
    main()
