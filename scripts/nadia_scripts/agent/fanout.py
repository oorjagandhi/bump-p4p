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
import pathlib as _pl, sys as _sys
_NS_ROOT = _pl.Path(__file__).resolve().parent.parent
if str(_NS_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_NS_ROOT))

from paths import out, str_out

import os, sys, json, glob, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import orchestrator as O

NADIA = O.NADIA
OUT = os.path.join(NADIA, "output")
VERIFIED = os.path.join(NADIA, "verified_cases")
AGENT = os.path.join(NADIA, "agent")

# break_id -> the version where the break was INTRODUCED. Prefer verify.break_boundary
# (e.g. xstream 1.4.18, poi-ooxml 5.0.0, jsoup 1.15.0) over library.to_version, which is the
# BUMP target's upper bound and can be LATER than the break — using it would wrongly drop
# genuine cases pinned at the boundary (e.g. Spark @1.4.18 vs to_version 1.4.19).
def _boundary_version(b):
    return ((b.get("verify", {}) or {}).get("break_boundary")
            or (b.get("library", {}) or {}).get("to_version"))

BOUNDARY = {b["break_id"]: _boundary_version(b)
            for b in json.load(open(O.CATALOG, encoding="utf-8"))["breaks"]}


def _ver_tuple(s):
    """Loose numeric version tuple, e.g. '5.2.5' -> (5,2,5). None/garbage -> None.
    Only the leading dotted-numeric run is used ('2.0.206-beta' -> (2,0,206))."""
    if not s:
        return None
    parts = []
    for tok in str(s).split("."):
        num = ""
        for ch in tok:
            if ch.isdigit():
                num += ch
            else:
                break
        if num == "":
            break
        parts.append(int(num))
    return tuple(parts) or None


def _boundary_status(version_at_commit, to_version):
    """Classify a candidate against the break boundary.

    'below_boundary'  -> resolvable version PROVABLY older than the break's to_version:
                         the repo isn't even on the broken release, so it cannot be an
                         adaptation to THIS break. Safe deterministic drop.
    'on_or_past'      -> resolvable version >= to_version (e.g. jadhavspeaks @ 5.2.5).
    'unconfirmed'     -> version_at_commit not resolvable. KEPT — genuine adaptation
                         commits routinely show None here (property/transitive versions:
                         amirsnw, Spark, einstein all None), so None must NOT be dropped.
    """
    vc, tv = _ver_tuple(version_at_commit), _ver_tuple(to_version)
    if vc is None or tv is None:
        return "unconfirmed"
    return "below_boundary" if vc < tv else "on_or_past"


def recorded_repos():
    repos = set()
    # verified_cases/<library>/*.json since the 2026-08 reorg
    for f in glob.glob(os.path.join(VERIFIED, "*", "*.json")):
        if os.path.basename(os.path.dirname(f)) in (
                "excluded", "pending_differential", "drivers"):
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
            r = d.get("adaptation", {}).get("repo", "")
            if r: repos.add(r)
        except Exception:
            pass
    return repos

def candidates_for(break_id, dropped=None):
    """Yield deduped, filtered work items for a break_id from its *_candidates.jsonl.

    `dropped`, if a list, collects candidates rejected by the boundary check so callers
    can report them (never drop silently — a hidden drop reads as 'nothing there')."""
    exact = str_out(f"{break_id}_candidates.jsonl")
    files = [exact] if os.path.exists(exact) else []
    done = recorded_repos()
    to_version = BOUNDARY.get(break_id)
    seen = set()
    for f in files:
        for line_no, line in enumerate(open(f, encoding="utf-8"), 1):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except Exception:
                print(f"[fanout] skip invalid JSON: {os.path.basename(f)}:{line_no}", file=sys.stderr)
                continue
            if not d.get("repo") or not d.get("sha"):
                print(f"[fanout] skip malformed row missing repo/sha: {os.path.basename(f)}:{line_no}", file=sys.stderr)
                continue
            if not (d.get("verifiable") and d.get("is_production_adaptation")): continue
            if d.get("library_source") or d.get("test_only"): continue
            if not d.get("is_maven"): continue
            # An adaptation to a library's behavioural break has to live in code that USES
            # the library. If NOT ONE changed production file even mentions it, the version
            # move is incidental to whatever the commit is really doing. Measured 2026-08-16
            # on four candidates that had passed every other filter and reached traversal:
            # onap/so (218 files, Spring Boot 3 migration), kafka-ops/julie, and two
            # apache/linkis feature merges (53 and 141 files). All four: empty list.
            # The field is already computed by classify, so this costs nothing.
            #
            # Validated against the known answers before being switched on: every mined row
            # for a repo that produced a verified_bbc case has library_referenced_files >= 1
            # (8 rows across xstream, snakeyaml and the Axon pair). This filter drops none of
            # them. Re-run that check if the field's definition in classify ever changes.
            if not d.get("library_referenced_files"):
                if dropped is not None:
                    dropped.append({"repo": d.get("repo"), "sha": d.get("sha", "")[:12],
                                    "reason": "no changed production file references the library"})
                continue
            sha = d.get("sha", "")[:12]
            if sha in seen: continue
            seen.add(sha)
            # Boundary sanity: drop only candidates whose version is RESOLVABLE and
            # provably older than the break's to_version (e.g. poi 3.16 vs 4.1.2->5.x).
            # None stays — genuine cases are frequently None here (see _boundary_status).
            bstat = _boundary_status(d.get("version_at_commit"), to_version)
            if bstat == "below_boundary":
                if dropped is not None:
                    dropped.append({"repo": d.get("repo"), "sha": sha,
                                    "version_at_commit": d.get("version_at_commit"),
                                    "to_version": to_version})
                continue
            status = "already_recorded" if d.get("repo") in done else "queued"
            yield {
                "break_id": break_id, "repo": d.get("repo"), "adapt_sha": d.get("sha"),
                "parent_sha": d.get("parent"), "build_system": d.get("build_system"),
                "production_files": d.get("production_files", []),
                "message": (d.get("message", "") or "")[:100], "status": status,
                "boundary_status": bstat,
            }

def main():
    args = sys.argv[1:]
    do_run = "--run" in args
    args = [a for a in args if a != "--run"]
    cat = json.load(open(O.CATALOG, encoding="utf-8"))
    break_ids = [args[0]] if args else [b["break_id"] for b in cat["breaks"]]

    grand = collections.Counter()
    per_break = {}
    all_dropped = []
    for bid in break_ids:
        dropped = []
        items = list(candidates_for(bid, dropped=dropped))
        all_dropped += [dict(break_id=bid, **x) for x in dropped]
        q = [i for i in items if i["status"] == "queued"]
        rec = [i for i in items if i["status"] == "already_recorded"]
        per_break[bid] = {"queued": len(q), "already_recorded": len(rec),
                          "dropped_below_boundary": len(dropped)}
        grand["queued"] += len(q); grand["recorded"] += len(rec); grand["dropped"] += len(dropped)
        if args:  # single-break mode: write the worklist
            path = os.path.join(AGENT, f"worklist_{bid}.json")
            json.dump(items, open(path, "w", encoding="utf-8"), indent=1)
            print(f"{bid}: {len(q)} queued, {len(rec)} already recorded, "
                  f"{len(dropped)} dropped<boundary -> {path}")
            for i in q:
                print(f"   [queue] {i['repo']}@{(i['adapt_sha'] or '')[:10]}  {i['message'][:60]}")
            for x in dropped:
                print(f"   [drop ] {x['repo']} @ {x['version_at_commit']} < boundary {x['to_version']}")

    if not args:
        print("=== catalog fan-out summary ===")
        print(f"{'break_id':40} queued  recorded")
        for bid, c in per_break.items():
            mark = "  <- has candidates" if (c["queued"] or c["already_recorded"]) else ""
            print(f"  {bid:40} {c['queued']:5}  {c['already_recorded']:7}{mark}")
        print(f"\nTOTAL queued (ready for the agent to verify): {grand['queued']}")
        print(f"TOTAL already recorded:                        {grand['recorded']}")
        print(f"TOTAL dropped below break boundary:            {grand['dropped']}")
        for x in all_dropped:
            print(f"   [drop] {x['break_id']:32} {x['repo']} @ {x['version_at_commit']} "
                  f"< boundary {x['to_version']}")

    if do_run:
        print("\n(--run: verify_candidate would execute here for candidates with a seam "
              "provider; SEAM_A/SEAM_B are agent turns — see acceptance_*.py for proven cases.)")

if __name__ == "__main__":
    main()
