# Behavioural breaking changes: finding real clients that broke and adapted

## What this is looking for

When a Java library ships a new version, some changes break clients at **compile** time —
a method is gone, the client no longer builds. Those are easy to find and not interesting
here.

This project hunts the other kind: a **behavioural breaking change (BBC)**, where the
client still compiles perfectly but behaves differently at run time. The upgrade is
silent until something fails in a test or in production.

A **case** is a real client repository where all of this is true:

1. it crossed the version boundary where the behaviour changed, and
2. it changed **production Java code** in response, and
3. we can prove it, by rebuilding the project three times: it passes before the
   upgrade, fails with the upgrade applied alone, and passes again with the client's fix.

Everything in this directory exists to find those, or to prove cheaply that a given
library cannot produce one.

## The finding so far

**They are rare.** Of the libraries mined to completion, one has produced verified cases
(xstream 1.4.17 → 1.4.19, deny-by-default type filtering). Several others produced a
measured zero, each for a different and now-understood reason.

`output/CENSUS.md` is the live ledger — per-break funnel, undecided-resolution table, and
a decidability audit. **Read it rather than any number quoted in prose**, here or
elsewhere, because it is regenerated from the artifacts:

```
python report/census.py > output/CENSUS.md
```

The census distinguishes a measured zero from an absent measurement. `--` means the stage
never ran; it does not mean zero. That distinction is the point of the whole ledger.

## Why most candidates die — the screening rules

These were each paid for with mining time. Apply them **before** spending a day on a
library, in this order:

| # | Rule | Failure it catches | Cost to check |
|---|---|---|---|
| 1 | The boundary must remove **no public API** | A compile break shadows the behavioural one — the client stops at javac and never reaches the change. Killed snakeyaml. | 2 jar downloads + javap (`discover/rank_candidates.py`, `discover/screen_majors.py`) |
| 2 | The new restriction must be **active by default** | *Relaxation*: the fix removes a restriction, so nothing breaks (mybatis 3.5.6). *Opt-in*: the restriction ships switched off (avro 1.11.3). | read the `-sources.jar` diff |
| 3 | The boundary must be **old enough that clients crossed it** | The client population is born past it, so no crossing can exist however many adaptations there are. Killed org-json (2013 boundary). | `report/boundary_dates.py` |
| 4 | The library must be used **directly**, not only transitively | Nobody writes code against it, so nobody has code to adapt. Killed json-smart (89% of mined commits changed no Java). | inspect a sample of mined commits |
| 5 | Prefer a restriction on the library's **primary API path** | Blast radius predicts yield. xstream's filter hits every `fromXML`; beanutils' hits only the property named `class`. | judgment, from the diff |

Rule 1 is automated. Rule 2 is the one that most often decides, and it is not visible to
javap — two libraries passed rule 1 and still turned out to be dead ends.

## The pipeline

```
  advisories / majors        discover/rank_candidates.py       is a case even possible?
          │                  discover/screen_majors.py         (rules 1 and 3)
          ▼
   shape check (manual)      sources-jar diff         is the restriction on by default?
          │                                           (rule 2)
          ▼
   catalog entry             specs/bump_breaks_catalog.json
          │                                           boundary pinned EMPIRICALLY first
          ▼
   mine ──► classify ──► traversal                    mine/bbc_e2e.py run <break_id>
          │
          ▼
   resolve undecided         traversal/resolve_undecided.py     ask Maven what the POM walk couldn't
          │
          ▼
   judgment (human/LLM)      read the diff            is this really THIS break?
          │
          ▼
   3-state differential      verify/02_verify_bbc.py         pass → fail → pass
```

### Mining, classifying, traversal — `mine/bbc_e2e.py run <break_id>`

Chains three stages, each checkpointed so a kill costs only the row in flight.

- **mine** — GitHub *commit* search on two axes: adaptation terms (the fix) and bump terms
  (the upgrade), plus a forward scan of commits after each bump. Collapses forks/mirrors.
- **classify** — per commit: does it change production Java, in a Maven project, with
  evidence linking it to the library, reachable from the default branch? Anything failing
  those is `not_verifiable`.
- **traversal** — did this client actually cross the boundary near this commit? Walks the
  build files. Three outcomes, and they are **not** the same thing:
  - confirmed — a boundary-crossing bump in the commit's ancestry
  - genuine negative — versions resolved, no crossing (client born past the boundary)
  - **undecided** — the version comes from a BOM or parent POM the HTTP walk can't read.
    This is an *unknown*, not a negative. Feed it to `traversal/resolve_undecided.py`.

### Verification — two paths

**`verify/02_verify_bbc.py`** runs the client's **own** test suite at three states: baseline
(parent commit), pom-only (parent code + just the version bump, via
`git show <sha> -- pom.xml | git apply`), and adapted (the full fix). A BBC is confirmed
only from tests that pass → fail → pass. Differential per-test, so a project with
pre-existing flaky failures is still usable — those never enter the baseline-pass set.

**`agent/`** handles clients that broke without having a test for it. Two LLM judgment
seams (`agent/seams.py`): `generate_test` writes a JUnit driver against the client's real
production path, and `diagnose_nontrip` adjusts the fixture when state 2 refuses to fail.
Everything around those two calls is deterministic. See `specs/AGENT_DESIGN.md` and
`specs/AGENT_EXPLAINED.md`.

## Scripts, by role

**Finding targets**
| script | does |
|---|---|
| `discover/mine_advisories.py` | pull candidate breaks from the OSV Maven feed |
| `discover/rank_candidates.py` | rank advisories by whether a case is *possible* (rules 1 + 3) |
| `discover/screen_majors.py` | same API check across curated major-version boundaries |
| `discover/mine_major_bumps.py` | discovery-first mining for top-library major releases |
| `discover/bump_semantic_sweep.py` | classify the BUMP corpus by kind of failure |

**Mining and classifying**
| script | does |
|---|---|
| `mine/bbc_e2e.py` | the main pipeline: `run`, `mine-commits`, `classify`, `gen-harness` |
| `mine/bbc_pipeline.py` | older stage-wise driver, kept for reference |
| `traversal/extract_undecided.py` | pull undecided traversal rows out of a classify checkpoint |
| `traversal/resolve_undecided.py` | decide them with `mvn dependency:tree` (endpoint comparison) |
| `traversal/resolve_version.py` | what version does a client's build actually resolve? |
| `traversal/retraverse.py` | re-run traversal over already-mined candidates |
| `traversal/audit_traversal.py` | record a traversal verdict into each verified case |

**Screening candidates**
| script | does |
|---|---|
| `screen/screen_compile_break.py` | separate behavioural breaks from compile breaks |
| `screen/screen_trigger.py` | does the client actually exercise the broken behaviour? |

**Verifying**
| script | does |
|---|---|
| `verify/02_verify_bbc.py` | the 3-state differential over the client's own tests |
| `agent/orchestrator.py` | the same 3 states with a generated test |
| `verify/test_gates.py` | regression fixtures for the decision gates |

**Reporting**
| script | does |
|---|---|
| `report/census.py` | build `output/CENSUS.md` from the artifacts |
| `report/boundary_dates.py` | resolve each boundary to its release date |
| `report/verify_numbers.py` | independently re-derive the numbers quoted in the report |
| `report/make_figures.py` | figures for the technical report |

## Where things live

Scripts sit in role folders — `discover/` (is a case possible?), `mine/`, `traversal/`,
`screen/`, `verify/`, `report/`, `agent/`. They still import each other by bare module name
and resolve data paths against **this** directory, which a small `sys.path` preamble at the
top of each file makes work: run them from anywhere, but keep that preamble if you move a
script again.

| path | holds |
|---|---|
| `specs/bump_breaks_catalog.json` | **the driver.** One entry per break: library, why it breaks, mining terms, verify config |
| `specs/top_maven_majors.json` | curated major-version boundaries |
| `specs/*.md` | agent design docs, BUMP break notes |
| `output/` | every artifact the pipeline produces — see `output/README.md` for naming |
| `verified_cases/` | confirmed cases, plus `excluded/` with a reason per rejection |
| `report/` | census, figures, the mid-year technical report |
| `agent/` | the LLM-seam verification path |
| `_runlogs/` | run logs (gitignored) |
| `scratchpad/` | generated harnesses and the jar cache (jars gitignored) |

## Running things

```bash
export GH_TOKEN=...                      # GitHub search + contents API

python discover/rank_candidates.py --tier validate --limit 120 --since 2019 \
       --out output/CANDIDATE_RANKING_VALIDATE.md
python discover/screen_majors.py

python mine/bbc_e2e.py run <break_id>         # mine + classify + traversal
python traversal/extract_undecided.py <break_id>
python traversal/resolve_undecided.py <break_id> --in output/<break_id>_UNDECIDED.jsonl

python report/boundary_dates.py
python report/census.py > output/CENSUS.md
```

Tiers for `discover/rank_candidates.py`: `deserialize`, `validate`, `limit`, `all`.

## Things that will bite you

- **Everything resumes.** `BBC_RESUME=1` is the default, and checkpoints are keyed by
  `(repo, sha)` or package. That is what makes a kill cheap — but it also means a **failed**
  row is remembered as done. To re-measure, move the output file aside first.
- **Maven Central answers 403 when it throttles you**, and a 403 is indistinguishable from
  a 404 to code that only checks "did I get a jar". A throttled run once produced 20 of 22
  rows of `mvn failed`, which read exactly like genuinely unresolvable projects. The guards
  now in place: `discover/rank_candidates.py` aborts after 5 consecutive 403s and labels them
  distinctly, and `discover/screen_majors.py` reports `UNAVAILABLE`/`UNREADABLE` as *non-verdicts*.
  Keep that principle — **a failure to measure must never be recorded as a measurement**.
  The quarantined `*_MVNRECHECK_THROTTLED.jsonl` is kept as an example of the failure mode.
- **Don't run two Central-heavy jobs at once.** A `mvn dependency:tree` sweep plus jar
  downloads is what earned the throttle.
- **GitHub secondary rate limits** cost a forced 60s sleep; the mine handles them, but they
  stretch wall-clock time considerably.
- **Disk.** `C:` runs near-full. `traversal/resolve_undecided.py` shallow-clones large repos one at a
  time and deletes each after use; leftovers appear as `%TEMP%/bbcres_*` when a run is
  killed.
- **Pin every boundary empirically before mining.** Run the old and new jars side by side
  and watch the behaviour flip. Reading a CVE description is not the same thing, and twice
  the empirical check has contradicted what the advisory implied.
