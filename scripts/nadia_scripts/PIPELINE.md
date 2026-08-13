# BBC → external-production-adaptation pipeline

**Stage mechanics reference for the COMMIT-SEARCH route.** For what the project is, the
current findings, and the screening rules that decide which libraries are worth mining at
all, start with [`README.md`](README.md) — this document assumes a target has already been
chosen and describes how the stages work.

> For the whole pipeline in one place — including the **code-search route**
> (`find_adaptations --via code-search` → `date_hits` → `screen_dated` → `find_crossing` →
> a hand-written harness), which is what produced the jackson-core cases and is not
> described here — see [`PIPELINE_END_TO_END.md`](PIPELINE_END_TO_END.md).

End-to-end workflow for finding, and verifying, real client **adaptations** to a
dependency's **behavioural breaking change (BBC)**. Codifies the flow validated by hand on
xstream/TVRenamer (`verified_cases/xstream-tvrenamer.json`).

Driver: `specs/bump_breaks_catalog.json`, each break carrying its `characterization`,
`mining`, and `verify` blocks. Entry point: `mine/bbc_e2e.py`.

Breaks now come from two sources, and the catalog records which via `provenance`:

- **BUMP** — breaks confirmed from the BUMP corpus, which carry a `characterization`
  block naming the failing test. `characterize` (stage 1) applies only to these.
- **EXTERNAL_ADVISORY_NOT_BUMP / EXTERNAL_CHANGELOG_NOT_BUMP** — breaks found by mining
  the OSV Maven feed and screening it (`discover/mine_advisories.py` → `discover/rank_candidates.py` → a
  shape check). These have no BUMP client, so `run` skips stage 1 for them. Their
  boundary is **pinned empirically** — old and new jars run side by side until the
  behaviour flips — before any mining is spent.

Two stages now run *before* this pipeline, and cost minutes rather than the day a mine
costs: `discover/rank_candidates.py` / `discover/screen_majors.py` reject boundaries that remove public API
(a compile break shadows the behavioural one), and a manual sources-jar diff confirms the
new restriction is active by default rather than relaxed or opt-in. See `README.md`.

## Scope

- **Language/build:** by default `run` keeps **native-Maven, Java production**
  candidates only, because those are the ones the verifier can exercise directly.
  Set `BBC_MAVEN_JAVA_ONLY=0` for exploratory mining that records Gradle/sbt or
  non-Java candidates without sending them to the differential.
- **Depth over breadth:** a handful of rigorously-verified cases is the goal. A
  clean `signature_confirmed` is a valid outcome when the break isn't cheaply
  reproducible (e.g. POI's parser-internal byte-cap).

## The stages

| # | Stage | Command | Kind |
|---|---|---|---|
| 1 | Characterize | `characterize <break_id>` | deterministic |
| 2 | Mine commits | `mine-commits <break_id>` | deterministic |
| 3 | Classify | `classify <repo> <sha> <break_id>` | deterministic |
| 4 | Generate test | (part of `gen-harness`) | **AI/human judgment** |
| 5 | Build + differential | `gen-harness … --reuse-pom` then `run_differential.sh` | deterministic |

`run <break_id>` chains 1→3 and prints the ranked candidates.

### 1. Characterize  *(deterministic)*
Pulls the exact failing test(s) + signal from BUMP's reproduction log for the
break's breaking commit. Handles ANSI/CR-dirty logs and three surefire formats
(inline, summary, Carrotsearch RandomizedTesting). This is the seed the generated
test is derived from.

### 2. Mine commits  *(deterministic)*
GitHub **commit search** (not code search) for either direct dependency bump
terms (`mining.direct_bump_search_terms`) or adaptation signatures
(`mining.commit_search_terms`). The default `BBC_SEARCH_MODE=balanced` tries both;
use `BBC_SEARCH_MODE=bump` when you want more candidates with an explicit version
crossing, or `BBC_SEARCH_MODE=adaptation` when you want likely fix commits first.
For direct bump hits, the miner also scans later commits on the repo's default
branch (`BBC_EXPAND_BUMP_SEEDS=1`, `BBC_BUMP_SEED_LIMIT`,
`BBC_FORWARD_SCAN_COMMITS`) so post-merge fixes can be handed to the traversal
verifier. `BBC_MAX_ROWS_PER_REPO` prevents one noisy repo from consuming the
classification cap. `BBC_TERM_LIMIT` caps terms per run and `BBC_SEARCH_PAGES`
controls GitHub result depth per term. `mining.signal_quality` flags how trustworthy the signature is:
**clean** (xstream, POI) vs **weak** (slf4j/logback/httpclient/jsoup —
behavioural changes with no distinctive API).

### 3. Classify  *(deterministic)*
For each candidate commit: split files into **production** (`src/main`, `.java`)
vs **test**; read the dependency version at the commit and its parent (transition);
detect the **build system**. Two precision filters, both learned from real false
positives:
- **`library_source`** — drops repos that ARE the library (`apache/poi` + forks):
  the changed file is the API *definition*, not a client *call*.
- **`is_maven` / `verifiable`** — only native-Maven production adaptations are put
  forward for the differential.
- **default traversal gate** — `run` keeps only candidates with a direct dependency
  bump that crosses the break boundary in the same commit as the adaptation or up
  to `BBC_MAX_TRAVERSAL_COMMITS` commits earlier (default: 200). Set
  `BBC_REQUIRE_TRAVERSAL=0` for exploratory mining without this gate.
  Confirmed traversal candidates are labelled `BUNDLED_BUMP_AND_ADAPTATION`
  when distance is 0, otherwise `POST_MERGE_FIX`.

### 4. Generate test  *(JUDGMENT — the AI/human seam)*
`gen-harness` emits a JUnit test **stub** whose header cites the break's BUMP
failing test (from `characterization.failing_tests`). An agent/human completes
`reproducesBbc()` so it exercises the client's **real production path** (its
`load()`/`parse()`/`deserialize()`), asserting the pre-break outcome — derived from,
but not a copy of, the BUMP failing test. All library config stays in production
code, never the test.

### 5. Build + differential  *(deterministic)*
`--reuse-pom` (native-Maven): reuses the repo's own `pom.xml` (no hand-written
dependency list), injects the test, and runs the 3-state differential. Only the
**baseline** version is overridden (by `set_baseline_version.py`, which `gen-harness`
writes into each harness directory — it is generated, not a top-level script), because
the repo is already on the new version at both the parent-of-fix and the fix.
A confirmed BBC:

```
1) parent code + baseline version  -> PASS
2) parent code + new version        -> FAIL  (the break signal)
3) adapted code + new version       -> PASS
```

## The two JUDGMENT seams (everything else is plumbing)

1. **`mining.commit_search_terms`** — the adaptation signature to search for
   (catalog). Pick one that can ONLY exist because of the upgrade.
2. **The generated test body** — how to drive the affected production path.

## Gotchas baked into the tooling

- **Java 17 + XStream/reflection:** needs `--add-opens` (`verify.jvm_add_opens`) or
  the JPMS masks the break before the library check runs.
- **`mvn clean` between states:** incremental compile reuses the prior state's
  `.class` files after a `git checkout` → false results.
- **GitHub paths are repo-relative** (no leading slash) → match `src/main/`, not
  `/src/main/`.
- **Confounded signatures:** xstream `allowTypes` co-occurs with proactive RCE
  hardening (ActiveMQ AMQ-6013) — prefer in-repo causal evidence (a comment naming
  the boundary) or a version transition that crosses the break boundary.

## Per-break readiness

**See [`output/CENSUS.md`](output/CENSUS.md)** — it is generated from the artifacts by
`ledger/census.py`, so unlike a table here it cannot drift out of date. It gives, per
break: rows examined, production adaptations, traversal-confirmed, behavioural vs compile
break, verified, and excluded — plus an undecided-resolution table and a decidability
audit.

Read `--` there as "this stage never ran", **not** as zero. A measured zero is a finding;
an absent measurement is not, and the whole rarity claim depends on telling them apart.

## Traversal outcomes are three-valued

`run` records a traversal rejection as one of three things, and collapsing them loses the
distinction the census depends on:

- **confirmed** — a boundary-crossing bump in the adaptation's ancestry
- **genuine negative** — versions resolved, no crossing; the client was born past the
  boundary
- **undecided** — the version is BOM- or parent-managed and the HTTP POM walk cannot
  resolve it. An *unknown*. Extract with `traversal/extract_undecided.py` and decide with
  `traversal/resolve_undecided.py`, which asks `mvn dependency:tree` directly.

The undecided share varies enormously by ecosystem: beanutils gave 19 undecided against 3
genuine negatives; kubernetes-client gave 22 against 0, because every fabric8 client takes
its version from a BOM. When that happens the Maven recheck is not a cleanup pass — it is
the entire traversal answer.

## Files

- `mine/bbc_e2e.py` — orchestrator (this pipeline)
  (Stage 1, `characterize`, was removed on 2026-08-13 along with `mine/bbc_pipeline.py`
  and `mine/bbc_common.py`: it read a BUMP reproduction log, and reproductionLogs/ went
  with the BUMP corpus on 2026-08-12. Its output is already in the catalog's
  characterization blocks. `run` now starts at mining.)
- `specs/bump_breaks_catalog.json` — the break catalog + characterization/mining/verify
- `specs/BUMP_BREAKS.md` — human-readable catalog of the BUMP-sourced breaks
- `verified_cases/` — the output dataset (one JSON per case + README)
- `output/README.md` — what every artifact in `output/` is, and which are measurements
- `scratchpad/*-harness/` — generated differential harnesses
