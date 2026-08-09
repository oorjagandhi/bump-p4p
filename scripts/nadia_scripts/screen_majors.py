#!/usr/bin/env python
"""
screen_majors.py — which major boundaries are even ELIGIBLE to yield a BBC case.

WHY
---
A BBC case requires a client that COMPILES unchanged across the boundary and fails at run
time. A major release that removes public API breaks the client at javac instead, so the
behavioural change is never reached. That is the snakeyaml trap, measured three times over
on that library's traversal-confirmed candidates -- each one turned out to be a signature
fix, not a behavioural adaptation.

The trap is the DEFAULT case for major releases, not the exception: removing API is much of
what "major" means. So the screen has to run BEFORE mining, not after. This is the same
javap diff rank_candidates.py applies to advisory boundaries, pointed at the curated major
boundaries in specs/top_maven_majors.json.

WHAT A PASS MEANS -- AND DOES NOT MEAN
--------------------------------------
MINEABLE here means only "no public API removed, so crossing clients reach run time". It
does NOT mean the boundary changes behaviour at all. Two further failure modes were
measured on 2026-08-09 and neither is visible to javap:

    RELAXATION  the boundary REMOVES a restriction (mybatis 3.5.6 deletes its gadget
                blacklist for a log.warn). More permissive -> nothing to adapt to.
    OPT-IN      the boundary ADDS a restriction but leaves it off by default (avro 1.11.3
                defaults every limit to Integer.MAX_VALUE-8). Unreachable unless the client
                switches it on.

So a MINEABLE verdict is a shortlist for the SHAPE screen -- read the sources-jar diff and
confirm the new restriction is ACTIVE BY DEFAULT -- not a green light to mine.

Usage:
  python screen_majors.py                 # every library in the seed catalog
  python screen_majors.py --only poi-5
  python screen_majors.py --out output/MAJOR_SCREEN.md
"""

import argparse
import json
import sys
from pathlib import Path

import rank_candidates as R

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
SEED = HERE / "specs" / "top_maven_majors.json"


def screen(lib):
    """(verdict, removed_sigs, removed_classes, samples) for one seed entry."""
    g, a = lib["group_id"], lib["artifact_id"]
    old, new = lib["prev_major"], lib["boundary"]
    old_jar = R.download_jar(g, a, old)
    new_jar = R.download_jar(g, a, new)
    if not old_jar or not new_jar:
        # Central returns 403 when it is rate-limiting, which download_jar cannot tell
        # apart from a genuine 404. Report it as UNAVAILABLE rather than a verdict --
        # recording a throttle as a measurement is how a contaminated pass enters the
        # record, which already happened once to the kubernetes-client recheck.
        missing = " ".join(v for v, j in ((old, old_jar), (new, new_jar)) if not j)
        return "UNAVAILABLE", None, None, [f"no jar for {missing}"]
    removed, gone_classes, samples = R.api_removals(old_jar, new_jar)
    verdict = "REJECT" if (removed or gone_classes) else "MINEABLE"
    return verdict, removed, gone_classes, samples


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="screen a single library id from the seed catalog")
    ap.add_argument("--out", default="output/MAJOR_SCREEN.md")
    args = ap.parse_args()

    libs = json.loads(SEED.read_text(encoding="utf-8"))["libraries"]
    if args.only:
        libs = [l for l in libs if l["id"] == args.only]
        if not libs:
            sys.exit(f"no seed entry with id {args.only!r}")

    rows = []
    for lib in libs:
        verdict, removed, gone, samples = screen(lib)
        rows.append({"id": lib["id"], "ga": f"{lib['group_id']}:{lib['artifact_id']}",
                     "old": lib["prev_major"], "new": lib["boundary"],
                     "released": lib.get("released"), "verdict": verdict,
                     "removed_signatures": removed, "removed_classes": gone,
                     "samples": samples[:2]})
        shown = "--" if removed is None else removed
        print(f"{lib['id']:24} {lib['prev_major']:>8} -> {lib['boundary']:<8} "
              f"removed sigs={shown!s:<6} {verdict}", flush=True)

    mineable = [r for r in rows if r["verdict"] == "MINEABLE"]
    blocked = [r for r in rows if r["verdict"] == "REJECT"]
    unavailable = [r for r in rows if r["verdict"] == "UNAVAILABLE"]

    lines = ["# Major-boundary screen — which majors can reach run time", "",
             "A client crossing a boundary that removed public API fails at javac and never "
             "reaches the behavioural change. This screens that out before any mining is "
             "spent, using the same javap diff `rank_candidates.py` applies to advisories.",
             "",
             "**MINEABLE means only that clients compile across the boundary.** It does not "
             "mean behaviour changed. Confirm the restriction is ACTIVE BY DEFAULT from the "
             "sources-jar diff before mining — see the relaxation (mybatis) and opt-in "
             "(avro) failure modes.", "",
             f"Screened {len(rows)}: **{len(mineable)} mineable**, {len(blocked)} reject, "
             f"{len(unavailable)} unavailable.", "",
             "| library | transition | released | removed sigs | removed classes | verdict |",
             "|---|---|---|---:|---:|---|"]
    for r in rows:
        rs = "—" if r["removed_signatures"] is None else r["removed_signatures"]
        rc = "—" if r["removed_classes"] is None else r["removed_classes"]
        lines.append(f"| `{r['ga']}` | {r['old']} → {r['new']} | {r['released'] or '—'} "
                     f"| {rs} | {rc} | **{r['verdict']}** |")
    if unavailable:
        lines += ["", "## Unavailable", "",
                  "Central did not serve a jar. A 403 from rate-limiting is indistinguishable "
                  "from a 404 here, so these are NOT verdicts — re-run them.", ""]
        for r in unavailable:
            lines.append(f"- `{r['ga']}` {r['old']} → {r['new']}: {r['samples'][0]}")
    if blocked:
        lines += ["", "## Rejected: the boundary removes public API", "",
                  "| library | removed sigs | example |", "|---|---:|---|"]
        for r in sorted(blocked, key=lambda x: -x["removed_signatures"]):
            eg = (r["samples"] or ["—"])[0]
            lines.append(f"| `{r['ga']}` | {r['removed_signatures']} | `{eg}` |")

    dest = HERE / args.out
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (HERE / "output" / "major_screen.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\n[screen] mineable={len(mineable)} reject={len(blocked)} "
          f"unavailable={len(unavailable)}")
    print(f"[screen] saved -> {dest}")


if __name__ == "__main__":
    main()
