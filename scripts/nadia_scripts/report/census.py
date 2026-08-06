#!/usr/bin/env python
"""
census.py — build the per-break funnel table from the mining artifacts.

WHY THIS EXISTS
---------------
The project's headline result is a RARITY claim: production adaptations to behavioural
breaking changes are extremely uncommon. A rarity claim is a claim about a DENOMINATOR,
so the funnel — how many commits were examined to yield each verified case — is not
supporting material, it IS the result. This script computes it from the artifacts on
disk so the numbers in any writeup are reproducible rather than transcribed.

WHAT IT DOES NOT DO
-------------------
It does not pretend the corpora are mutually comparable. They are not, and the reasons
are recorded per break rather than smoothed over:

  * `<break>_candidates.jsonl` does not mean the same thing across runs. bbc_e2e.run()
    writes it AFTER the classify loop, so its contents depend on the env settings that
    run used — BBC_MAVEN_JAVA_ONLY and BBC_REQUIRE_TRAVERSAL in particular. For xstream
    (2026-08-06) it holds 11 traversal-confirmed survivors; for the 2026-07 corpora it
    holds every classified row including non-verifiable ones. Same filename, different
    stage.
  * Only xstream was mined on both the adaptation axis AND the bump axis (32 terms).
    Every other break used adaptation-signature terms only, so their mined totals are
    not comparable to xstream's.
  * CLASSIFY_CAP (default 200) bounds how many rows reach the traversal check. It binds
    for xstream and for nothing else, so xstream's "traversal-confirmed" is a count over
    a capped sample and the others are over their whole corpus.

Every emitted number carries the file it came from. A stage that was never run prints
"--", never 0: a zero is a finding and an absence is not, and conflating them would
manufacture evidence.
"""

import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
NADIA = HERE.parent
OUT = NADIA / "output"
CASES = NADIA / "verified_cases"
CATALOG = NADIA / "specs" / "bump_breaks_catalog.json"

MISSING = "--"

# The ONE break mined end-to-end under a single known configuration, so the only one
# whose full funnel is meaningful. Transcribed from
# _runlogs/deep_xstream_rerun_20260806.log (the run that produced
# xstream-1.4.17-to-1.4.19-forbiddenclass_candidates.jsonl on 2026-08-06), because the
# intermediate stages are not recoverable from the committed artifacts: the raw search
# rows live only in the mine checkpoint, which is gitignored on purpose (BBC_RESUME
# defaults to on, so a committed checkpoint would make a fresh run resume a stale
# search). Update these numbers only from a run log, never by hand.
DEEP_MINE_FUNNEL = """
## The one measured end-to-end funnel: xstream 1.4.17 -> 1.4.19

Only xstream was mined on BOTH axes (32 terms: adaptation signatures + version bumps)
under one configuration, so it is the only break whose funnel is comparable stage to
stage. Source: `_runlogs/deep_xstream_rerun_20260806.log`.

| stage | rows | what it removes |
|---|---:|---|
| raw commit-search hits | 2288 | — |
| distinct commits | 1221 | fork/mirror dedup collapsed 1067 duplicates of the same SHA |
| after 6-per-repo cap | 883 | across 525 repos |
| classified | 200 | `CLASSIFY_CAP`; this cap BINDS here and nowhere else |
| reached the traversal check | 48 | non-production and non-Maven rows dropped earlier |
| traversal-confirmed production | 11 | **the gate that removes nearly everything** |
| survived human reading | 9 | swiftmq removed a dependency; Synapse adapted to Java 21 |
| verified by 3-state differential | 4 | 3 not standalone-verifiable, 2 already known |

Read the last rows carefully. Mechanical gates took 2288 rows to 11. Human reading of
commit intent removed 2 of those 11 — a step no gate in the pipeline performs.
"""


def rows(path):
    if not path or not path.exists():
        return None
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def first_existing(break_id, *suffixes):
    """Resolve a stage to its most authoritative artifact, in the given precedence."""
    for suffix in suffixes:
        p = OUT / f"{break_id}_{suffix}"
        if p.exists():
            return p
    return None


def count(rs, pred, requires=None):
    """Count rows matching pred.

    `requires` names the field the stage writes. If NO row carries it, the stage never
    ran over this artifact and the answer is None (-> "--"), not 0. Without this check
    a corpus that was never traversal-checked reports "0 crossings", which reads as a
    measured negative and is the single most misleading error this table could make --
    the rarity claim rests on distinguishing a real zero from an absent measurement.
    """
    if rs is None:
        return None
    if requires is not None and not any(requires in r for r in rs):
        return None
    return sum(1 for r in rs if pred(r))


def parse_ver(s):
    import re
    nums = re.findall(r"\d+", s or "")
    return tuple(int(n) for n in nums[:4]) if nums else None


def ver_lt(a, b):
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) < b + (0,) * (n - len(b))


def below_boundary(rs, boundary):
    """How many rows sat BELOW the boundary at their parent commit.

    This is the eligibility signal, and it is what org-json cost us to learn. A break can
    only yield a witnessed crossing if some client was below the boundary and moved
    above it. If every mined client is already past the boundary, the break yields zero
    crossings BY CONSTRUCTION however many real adaptations exist -- which is exactly
    org-json (boundary 2013-10, earliest client 2016-08, 31 production adaptations, 0
    crossings measured over all 50 rows).

    Returns (n_below, n_with_a_resolvable_version). The second number matters: a corpus
    where nothing resolves tells you nothing either way.
    """
    b = parse_ver(boundary)
    if rs is None or not b:
        return None, None
    below = resolvable = 0
    for r in rs:
        v = parse_ver(r.get("version_at_parent") or r.get("version_at_commit"))
        if not v:
            continue
        resolvable += 1
        if ver_lt(v, b):
            below += 1
    return below, resolvable


def traversal_ok(r):
    return bool((r.get("traversal") or {}).get("traversal_confirmed"))


def prod_ok(r):
    return bool(r.get("is_production_adaptation"))


def load_cases():
    """Map break_id -> (verified, excluded-by-reason) from verified_cases/."""
    verified, excluded = Counter(), {}
    for p in CASES.glob("*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        bid = (d.get("discovery") or {}).get("break_id") or _infer_break(d)
        if d.get("status") == "verified_bbc":
            verified[bid] += 1
    for p in CASES.glob("excluded/*/*.json"):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        bid = (d.get("discovery") or {}).get("break_id") or _infer_break(d)
        excluded.setdefault(bid, Counter())[p.parent.name] += 1
    return verified, excluded


def _infer_break(d):
    lib = (d.get("library") or {}).get("artifact_id", "")
    return {"xstream": "xstream-1.4.17-to-1.4.19-forbiddenclass",
            "snakeyaml": "snakeyaml-1.x-to-2.0-safeconstructor",
            "poi": "poi-4.1.2-to-5.x"}.get(lib, lib or "?")


def main():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    bpath = OUT / "boundary_dates.json"
    bdates = json.loads(bpath.read_text(encoding="utf-8")) if bpath.exists() else {}
    verified, excluded = load_cases()
    table, provenance, notes = [], [], []

    for brk in catalog["breaks"]:
        bid = brk["break_id"]

        cand_p = first_existing(bid, "candidates.jsonl")
        # Prefer the artifact that actually carries traversal verdicts.
        trav_p = first_existing(bid,
                                "traversal_RECHECK_SCREENED.jsonl",
                                "traversal_RECHECK.jsonl",
                                "PRODONLY_SCREENED.jsonl",
                                "PRODONLY.jsonl",
                                "candidates_SCREENED.jsonl",
                                "candidates.jsonl")
        # The screen verdict lives on whichever SCREENED artifact is newest in the chain.
        scr_p = first_existing(bid,
                               "traversal_RECHECK_SCREENED.jsonl",
                               "candidates_SCREENED.jsonl",
                               "PRODONLY_SCREENED.jsonl")

        cand, trav, scr = rows(cand_p), rows(trav_p), rows(scr_p)

        # "rows examined" is the row count of the SAME artifact the other columns are
        # computed from. Using the candidates file here instead would make rows
        # internally incoherent -- snakeyaml's candidates file holds 6 rows while its
        # traversal artifact holds 44, so the table would have claimed 44 production
        # adaptations out of 6 candidates. The candidates count is kept in provenance.
        n_rows = len(trav) if trav is not None else None
        n_cand = len(cand) if cand is not None else None
        n_prod = count(trav, prod_ok, requires="is_production_adaptation")
        n_trav = count(trav, traversal_ok, requires="traversal")
        n_behav = (count(scr, lambda r: (r.get("compile_screen") or {}).get("verdict")
                         == "behavioural") if scr is not None else None)
        n_cmpl = (count(scr, lambda r: (r.get("compile_screen") or {}).get("verdict")
                        == "compile_break") if scr is not None else None)

        bd = bdates.get(bid) or {}
        boundary = (brk.get("verify") or {}).get("break_boundary")
        n_below, n_resolv = below_boundary(trav, boundary)

        v = verified.get(bid, 0)
        exc = excluded.get(bid) or Counter()

        table.append({
            "break": bid,
            "mined": n_rows, "candidates": n_cand, "prod": n_prod, "traversal": n_trav,
            "behavioural": n_behav, "compile_break": n_cmpl,
            "verified": v, "excluded": sum(exc.values()),
            "boundary": bd.get("boundary_resolved") or boundary,
            "boundary_date": bd.get("release_date"),
            "boundary_exact": bd.get("exact"),
            "below": n_below, "resolvable": n_resolv,
        })
        provenance.append({
            "break": bid,
            "candidates": f"{cand_p.name} ({n_cand} rows)" if cand_p else MISSING,
            "traversal_source": trav_p.name if trav_p else MISSING,
            "screen_source": scr_p.name if scr_p else MISSING,
        })
        if exc:
            notes.append(f"{bid}: excluded -> " +
                         ", ".join(f"{k} x{n}" for k, n in sorted(exc.items())))

    def cell(v):
        return MISSING if v is None else str(v)

    print("# BBC mining census\n")
    print("Generated by `report/census.py` from the artifacts in `output/` and "
          "`verified_cases/`.\n")
    print("**`--` means the stage was never run for that break. It does NOT mean "
          "zero.** A measured zero is a finding; an absent measurement is not, and the "
          "rarity claim depends entirely on telling them apart.\n")
    print("| break | rows examined | production | traversal-confirmed | behavioural | "
          "compile break | VERIFIED | excluded |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|")
    tot = Counter()
    for r in table:
        print(f"| `{r['break']}` | {cell(r['mined'])} | {cell(r['prod'])} | "
              f"{cell(r['traversal'])} | {cell(r['behavioural'])} | "
              f"{cell(r['compile_break'])} | **{r['verified']}** | {r['excluded']} |")
        for k in ("prod", "traversal"):
            if r[k]:
                tot[k] += r[k]
        tot["verified"] += r["verified"]
        tot["excluded"] += r["excluded"]
    print(f"| **total** | *not summable* | **{tot['prod']}** | "
          f"**{tot['traversal']}** | | | **{tot['verified']}** | **{tot['excluded']}** |")
    print("\n`rows examined` is deliberately NOT totalled: the corpora were produced by "
          "different pipeline configurations and the column does not mean the same "
          "thing in every row (see caveats).\n")

    # A break with production adaptations but no traversal measurement is not a
    # negative result -- it is unfinished work, and the table above would otherwise let
    # it sit there looking like one.
    leads = [r for r in table if r["prod"] and r["traversal"] is None]
    if leads:
        print("## Unchecked leads (production adaptations, traversal NEVER run)\n")
        print("These are the only cells in the table that represent work not done "
              "rather than a measured negative. Each is a corpus where production "
              "adaptations were found and then never checked for a boundary crossing.\n")
        print("| break | production adaptations awaiting a traversal check |")
        print("|---|---:|")
        for r in sorted(leads, key=lambda x: -x["prod"]):
            print(f"| `{r['break']}` | **{r['prod']}** |")
        print()

    print("## Boundary dates and mineability\n")
    print("A break can only yield a *witnessed* crossing if some client was below the "
          "boundary and moved above it. If the boundary predates the mineable client "
          "population, the break yields zero crossings **by construction**, however "
          "many genuine adaptations exist. That is not a finding about how clients "
          "behave — it is a property of the boundary's date, and it is knowable before "
          "spending a mine.\n")
    print("`below` counts corpus rows whose version at the parent commit sits below the "
          "boundary; `resolvable` is how many rows had a version that could be parsed "
          "at all. `below = 0` with a healthy `resolvable` means every mined client was "
          "born past the boundary.\n")
    print("**Limitation, and it is not a small one:** `below` reads the version DECLARED "
          "in the client's build file. It cannot see a version that arrives "
          "transitively. xstream is the proof — the break with four verified crossings "
          "in this dataset shows `resolvable = 0`, because its confirmed cases receive "
          "xstream through `axon-spring-boot-starter` and declare nothing themselves. "
          "So a low `below` is evidence only when `resolvable` covers most of the "
          "corpus, and it is never evidence against a MEASURED crossing. The "
          "`traversal` column is the ground truth; this table is a cheap pre-filter for "
          "breaks not yet mined.\n")
    print("| break | boundary | released | below | resolvable | traversal (measured) | "
          "mineable for crossings? |")
    print("|---|---|---|---:|---:|---:|---|")
    MIN_EVIDENCE = 5
    for r in sorted(table, key=lambda x: (x["boundary_date"] or "9999")):
        b = r["boundary"] or MISSING
        if r["boundary_exact"] is False:
            b += " *(approx)*"
        below, res, meas = r["below"], r["resolvable"], r["traversal"]
        if meas:
            verdict = f"**YES — {meas} measured**"
        elif below is None or not res:
            verdict = "unknown — no declared versions to read"
        elif below == 0 and res >= MIN_EVIDENCE:
            verdict = "**NO** — every mined client born past it"
        elif below == 0:
            verdict = f"probably not — but only {res} row(s) resolve, too few to say"
        else:
            verdict = "yes — clients below the boundary exist"
        print(f"| `{r['break']}` | {b} | {r['boundary_date'] or MISSING} | "
              f"{cell(below)} | {cell(res)} | {cell(meas)} | {verdict} |")
    print(f"\n`below = 0` is only called decisive when at least {MIN_EVIDENCE} rows "
          "resolve; below that the corpus is too thin to distinguish 'born past the "
          "boundary' from 'we could not tell'.\n")
    print("The rule this encodes, learned from org-json: **check the boundary's DATE "
          "before mining a break, not just that a boundary exists.**\n")

    print(DEEP_MINE_FUNNEL)

    print("\n## Column meanings\n")
    print("- **rows examined** — row count of the artifact the other columns are computed "
          "from (named in Provenance). NOT a raw search total: bbc_e2e writes its "
          "candidates file AFTER the classify loop, so its size depends on that run's "
          "env settings. For the one raw funnel, see the xstream block above.")
    print("- **production** — rows whose adaptation touches `src/main`.")
    print("- **traversal-confirmed** — the client crossed the break boundary in its own "
          "history. This is the gate that removes nearly everything.")
    print("- **behavioural / compile break** — `screen_compile_break.py` verdicts. Only "
          "meaningful for constructor-mediated breaks; POI and h2 return all-unknown "
          "because their breaks are a static config call and SQL semantics respectively.")
    print("- **VERIFIED** — a 3-state differential was actually run and passed.")

    print("\n## Provenance\n")
    print("| break | candidates file | traversal source | screen source |")
    print("|---|---|---|---|")
    for p in provenance:
        print(f"| `{p['break']}` | `{p['candidates']}` | `{p['traversal_source']}` | "
              f"`{p['screen_source']}` |")

    if notes:
        print("\n## Exclusions by reason\n")
        for n in notes:
            print(f"- {n}")


if __name__ == "__main__":
    main()
