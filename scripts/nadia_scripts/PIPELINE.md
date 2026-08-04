# BBC → external-production-adaptation pipeline

End-to-end workflow for finding, and verifying, real client **adaptations** to a
dependency's **behavioural breaking change (BBC)** — starting from BUMP, scaling
across the whole break catalog. Codifies the flow we validated by hand on
xstream/TVRenamer (`verified_cases/xstream-tvrenamer.json`).

Driver: `specs/bump_breaks_catalog.json` (9 BUMP-confirmed breaks, each with its
`characterization`, `mining`, and `verify` blocks). Entry point: `bbc_e2e.py`.

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
**baseline** version is overridden (`set_baseline_version.py`), because the repo is
already on the new version at both the parent-of-fix and the fix. A confirmed BBC:

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

| Break | signal | verify status |
|---|---|---|
| xstream 1.4.18 | clean | ✅ proven (TVRenamer) |
| poi 5.0 byte-cap | clean | 🟡 signature cases; parser-internal break (needs real build + crafted doc) |
| mockito 5 inline | medium | not yet attempted |
| slf4j/logback/httpclient/jsoup | weak | low priority (noisy commit search) |

## Files

- `bbc_e2e.py` — orchestrator (this pipeline)
- `bbc_pipeline.py` — original stages; `characterize` reused here
- `specs/bump_breaks_catalog.json` — the 9 breaks + characterization/mining/verify
- `specs/BUMP_BREAKS.md` — human-readable catalog
- `verified_cases/` — the output dataset (one JSON per case + README)
- `scratchpad/*-harness/` — generated differential harnesses
