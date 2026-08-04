#!/usr/bin/env python3
"""
retraverse.py — re-run verify_traversal over ALREADY-MINED candidates.

Why: verify_traversal was returning a false negative for EVERY candidate — _gh()
called .get() on GitHub's list responses (JSON arrays), and find_boundary_bump
swallowed the AttributeError as "no commits". Both fixed in bbc_e2e.py; every
traversal verdict recorded before that fix is meaningless and must be redone.

This re-checks saved candidates without re-mining (mining is the expensive part
and its results are unaffected by the bug).

Usage:
  python retraverse.py <break_id> [--in <jsonl>] [--limit N] [--evidence message+content]
"""

import argparse
import json
import sys
from pathlib import Path

import bbc_e2e as B

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("break_id")
    ap.add_argument("--in", dest="infile", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--evidence", default=None,
                    help="only re-check rows with this evidence tier")
    args = ap.parse_args()

    brk = B.get_break(args.break_id)
    token = B._token()
    src = Path(args.infile or
               HERE / "output" / f"{args.break_id}_traversal_candidates.jsonl")
    rows = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.evidence:
        rows = [r for r in rows if r.get("evidence") == args.evidence]
    if args.limit:
        rows = rows[:args.limit]
    print(f"[retraverse] {len(rows)} candidate(s) from {src.name}\n", flush=True)

    gold, other = [], []
    for i, c in enumerate(rows, 1):
        t = B.verify_traversal(c["repo"], c["sha"], brk, token)
        c["traversal"] = t
        c["shape"] = t.get("shape") if t.get("traversal_confirmed") else None
        ok = t.get("traversal_confirmed")
        (gold if ok else other).append(c)
        mark = "GOLD" if ok else "----"
        print(f"[{i}/{len(rows)}] [{mark}] {c['repo']}@{c['sha'][:8]} "
              f"({c.get('build_system')})  {t.get('reason','')[:90]}", flush=True)

    out = HERE / "output" / f"{args.break_id}_traversal_RECHECK.jsonl"
    with out.open("w", encoding="utf-8") as fh:
        for c in gold + other:
            fh.write(json.dumps(c) + "\n")
    print(f"\n[retraverse] GOLD: {len(gold)} / {len(rows)}")
    for c in gold:
        b = c["traversal"]["bump"]
        pf = (c.get("production_files") or ["?"])[0]
        print(f"  GOLD  {c['repo']}@{c['sha'][:8]}  {b['from']}->{b['to']}  "
              f"{c['shape']}  {pf}")
    print(f"[retraverse] saved -> {out.relative_to(HERE)}")


if __name__ == "__main__":
    main()
