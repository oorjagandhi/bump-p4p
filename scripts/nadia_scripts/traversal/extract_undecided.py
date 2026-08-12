#!/usr/bin/env python
"""
extract_undecided.py — pull the UNDECIDED traversal rows out of a classify checkpoint.

resolve_undecided.py takes a corpus of classify rows and re-decides the ones the POM
walk gave up on (`traversal.resolution == "unresolved"`). Those rows live inside the
classify checkpoint, wrapped in a decision envelope, so they were being extracted by
hand each time (fastjson, xstream). This does it in one place.

Usage:
  python extract_undecided.py <break_id>          # -> output/<break_id>_UNDECIDED.jsonl
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

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    break_id = sys.argv[1]
    src = HERE / "output" / f"{break_id}_classify_checkpoint.jsonl"
    if not src.exists():
        sys.exit(f"no classify checkpoint at {src}")
    rows, seen = [], set()
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue          # torn final line from a hard kill
        row = rec.get("row")
        if not row:
            continue
        if (row.get("traversal") or {}).get("resolution") != "unresolved":
            continue
        key = (row.get("repo"), row.get("sha"))
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)
    dst = HERE / "output" / f"{break_id}_UNDECIDED.jsonl"
    dst.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    print(f"[extract] {len(rows)} undecided row(s) -> {dst.relative_to(HERE)}")


if __name__ == "__main__":
    main()
