# What's in `output/`

Everything the pipeline produces, split by the stage that produced it. The filename tells you
what a file is and, more importantly, **whether it is a measurement**. That distinction matters
more than it sounds: a run that failed to measure anything produces files that look exactly like
a run that measured zero, and conflating the two corrupts the census.

## The folders

`paths.py` at the repo root owns this layout — call `out("file.jsonl")` rather than building a
path by hand. Routing is by filename, because several files are written by one script and read
by another, so the name is the contract both sides already agree on.

| folder | stage | the question it answers | written by |
|---|---|---|---|
| `01_discover/` | discover | *Who might have adapted to this break?* | `discover/rank_candidates.py`, `mine_advisories.py`, `find_adaptations.py`, `probe_population.py` |
| `02_mine/` | mine | *Which commits are they, exactly?* | `mine/bbc_e2e.py run` / `mine-commits` / `classify` |
| `03_screen/` | screen | *Which of those are real candidates?* | `screen/screen_compile_break.py`, `screen/screen_trigger.py` |
| `04_traversal/` | traversal | *Did the client actually cross the boundary?* | `traversal/find_crossing.py` (and the one-shots now in `archive/`) |
| `05_verify/` | verify | *Did the break actually reproduce?* | `agent/run_worklist.py`, `verify/02_verify_bbc.py` |
| `reports/` | — | human-readable summaries | several |

Most files are named `<break_id>_<kind>.jsonl`.

## Measurements — safe to cite

| suffix | one row per | written by |
|---|---|---|
| `_candidates.jsonl` | candidate that survived classify **and** traversal | `mine/bbc_e2e.py run` |
| `_ADAPTATIONS.jsonl` | commit touching the recovery API, classified by the VALUE it sets | `discover/find_adaptations.py` |
| `_UNDECIDED.jsonl` | traversal row the POM walk could not decide | `archive/extract_undecided.py` |
| `_UNDECIDED_MVNRECHECK.jsonl` | undecided row re-decided by `mvn dependency:tree` | `archive/resolve_undecided.py` |
| `_traversal_RECHECK.jsonl` | candidate re-run through traversal | `archive/retraverse.py` |
| `_SCREENED.jsonl` | candidate labelled behavioural vs compile break | `screen/screen_compile_break.py` |
| `_PRODONLY.jsonl` | candidates filtered to production adaptations | ad hoc |
| `_differential.jsonl` | one three-state verification run | `agent/run_worklist.py` |

`_candidates.jsonl` is written **after** the classify loop finishes, so its row count reflects
that run's env settings (`BBC_CLASSIFY_CAP`, `BBC_MAVEN_JAVA_ONLY`, `BBC_REQUIRE_TRAVERSAL`)
rather than a raw search total. For the full funnel, read `reports/CENSUS.md`.

`_UNDECIDED` means the version could not be resolved. That is **not** the same as "did not
cross" — one is a measurement, the other a failure to measure.

## Checkpoints — resume state, not results

| suffix | holds |
|---|---|
| `_mine_checkpoint.jsonl` | every mined row + which search terms are done |
| `_classify_checkpoint.jsonl` | every classify **decision**, including rejections |
| `candidate_ranking_progress_<tier>.jsonl` | one stage-2 verdict per library |

**Gitignored on purpose.** `BBC_RESUME` defaults to on, so a committed checkpoint would make a
fresh run silently resume someone else's stale search.

They are still the richest artifact for analysis — the classify checkpoint records *why* each
of the 200 rows was rejected, which the candidates file does not. `census.py` reads them where
a candidates file is too lossy.

## Quarantined — deliberately NOT measurements

| suffix | why |
|---|---|
| `_MVNRECHECK_THROTTLED.jsonl` | produced while Maven Central was returning 403. Maven cannot distinguish "cannot fetch the parent POM" from "this project is broken", so nearly every row failed in a way that mimics a real result. |

Kept rather than deleted because the contrast is instructive: the same 22 rows, same code, gave
1 measured negative under the throttle and 6 without it. `census.py` reads `*_MVNRECHECK.jsonl`
and ignores the throttled name, so it is inert in the ledger.

**If you produce another contaminated run, rename it rather than deleting it** — and rename it
*before* re-running, because `archive/resolve_undecided.py` resumes by `(repo, sha)` and would
otherwise skip every poisoned row as already done.

## Reports (`reports/`, Markdown)

| file | what |
|---|---|
| `CENSUS.md` | **the ledger.** Per-break funnel, undecided resolution, decidability audit. Regenerate with `python ledger/census.py > output/reports/CENSUS.md` |
| `ADAPTATIONS_<break_id>.md` | commits touching the recovery API, split raise / lower / knob. **Check this before mining a break — it may already exist.** |
| `CANDIDATE_RANKING_WIDE.md` | advisory ranking, `deserialize` tier |
| `CANDIDATE_RANKING_VALIDATE.md` | advisory ranking, `validate` tier |
| `MAJOR_SCREEN.md` | major-version boundaries: which remove public API |
| `ADVISORY_SHORTLIST.md` | early advisory triage |
| `MINING_FINDINGS.md`, `BUMP_SEMANTIC_SWEEP.md` | earlier exploratory passes |

Reports are generated, not hand-edited. If a number looks wrong, fix the script and regenerate —
otherwise the next regeneration silently reverts the correction.

## Supporting data (`01_discover/`)

| file | what |
|---|---|
| `advisory_candidates.json` | 932 advisory rows over 595 libraries, from the OSV feed |
| `candidate_ranking.json` | ranking verdicts, `deserialize` tier |
| `candidate_ranking_<tier>.json` | ranking verdicts, other tiers |
| `boundary_dates.json` | each boundary version resolved to its release month |
| `major_screen.json` | machine-readable form of `MAJOR_SCREEN.md` |
| `_jackson_codesearch_hits.json` | the 600 `/search/code` hits that found the AthenZ case. **Kept as evidence, not scratch** — code-search results drift with the index, so the "241 repos, 238 unseen by commit search" claim in that case file cannot be re-derived later. |
