#!/usr/bin/env python3
"""
Fan-out driver: turn the break catalog + mined candidate files into a WORK QUEUE the
verification agent can grind, and a results LEDGER.

Per break in bump_breaks_catalog.json, reads output/<break_id>_candidates.jsonl, applies the
deterministic filters (verifiable + production + maven; dedup by sha; skip repos already in
verified_cases/; skip library_source/test_only), and emits one work item per surviving
candidate with everything SEAM_A needs. Optionally runs orchestrator.verify_candidate for
candidates whose (break,repo) has a registered seam provider (the two proven acceptance cases).

Usage:
  python fanout.py                 # summarize the whole catalog's queue
  python fanout.py <break_id>      # worklist for one break -> agent/worklist_<break_id>.json
  python fanout.py --run           # also verify candidates that have a seam provider
"""
import os, sys, json, glob, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import orchestrator as O

NADIA = O.NADIA
OUT = os.path.join(NADIA, "output")
VERIFIED = os.path.join(NADIA, "verified_cases")
AGENT = os.path.join(NADIA, "agent")

def recorded_repos():
    repos = set()
    for f in glob.glob(os.path.join(VERIFIED, "*.json")):
        try:
            d = json.load(open(f, encoding="utf-8"))
            r = d.get("adaptation", {}).get("repo", "")
            if r: repos.add(r)
        except Exception:
            pass
    return repos

def candidates_for(break_id):
    """Yield deduped, filtered work items for a break_id from its *_candidates.jsonl."""
    # candidate files are named by transition, not always == break_id; match on prefix token
    key = break_id.split("-")[0]  # poi, xstream, json ...
    files = glob.glob(os.path.join(OUT, f"*{key}*_candidates.jsonl"))
    done = recorded_repos()
    seen = set()
    for f in files:
        for line in open(f, encoding="utf-8"):
            d = json.loads(line)
            if not (d.get("verifiable") and d.get("is_production_adaptation")): continue
            if d.get("library_source") or d.get("test_only"): continue
            if not d.get("is_maven"): continue
            sha = d.get("sha", "")[:12]
            if sha in seen: continue
            seen.add(sha)
            status = "already_recorded" if d.get("repo") in done else "queued"
            yield {
                "break_id": break_id, "repo": d.get("repo"), "adapt_sha": d.get("sha"),
                "parent_sha": d.get("parent"), "build_system": d.get("build_system"),
                "production_files": d.get("production_files", []),
                "message": (d.get("message", "") or "")[:100], "status": status,
            }

def main():
    args = sys.argv[1:]
    do_run = "--run" in args
    args = [a for a in args if a != "--run"]
    cat = json.load(open(O.CATALOG, encoding="utf-8"))
    break_ids = [args[0]] if args else [b["break_id"] for b in cat["breaks"]]

    grand = collections.Counter()
    per_break = {}
    for bid in break_ids:
        items = list(candidates_for(bid))
        q = [i for i in items if i["status"] == "queued"]
        rec = [i for i in items if i["status"] == "already_recorded"]
        per_break[bid] = {"queued": len(q), "already_recorded": len(rec)}
        grand["queued"] += len(q); grand["recorded"] += len(rec)
        if args:  # single-break mode: write the worklist
            path = os.path.join(AGENT, f"worklist_{bid}.json")
            json.dump(items, open(path, "w", encoding="utf-8"), indent=1)
            print(f"{bid}: {len(q)} queued, {len(rec)} already recorded -> {path}")
            for i in q:
                print(f"   [queue] {i['repo']}@{(i['adapt_sha'] or '')[:10]}  {i['message'][:60]}")

    if not args:
        print("=== catalog fan-out summary ===")
        print(f"{'break_id':40} queued  recorded")
        for bid, c in per_break.items():
            mark = "  <- has candidates" if (c["queued"] or c["already_recorded"]) else ""
            print(f"  {bid:40} {c['queued']:5}  {c['already_recorded']:7}{mark}")
        print(f"\nTOTAL queued (ready for the agent to verify): {grand['queued']}")
        print(f"TOTAL already recorded:                        {grand['recorded']}")

    if do_run:
        print("\n(--run: verify_candidate would execute here for candidates with a seam "
              "provider; SEAM_A/SEAM_B are agent turns — see acceptance_*.py for proven cases.)")

if __name__ == "__main__":
    main()
