# BBC-verification agent — design spec

An autonomous agent that, given a **break** (from `bump_breaks_catalog.json`) and a
**candidate client repo+commit**, runs the whole verification I currently do by hand:
clone → build → generate a driver test → run the 3-state differential → classify → emit a
`verified_cases/*.json`. Built on the Claude Agent SDK (headless loop with bash/git/maven).

Grounded in the manual runs this session: xstream (artshishkin/amirsnw/einstein), POI
(jadhavspeaks), and the failure modes hit along the way (dedup, zip-bomb, class-load coupling).

---

## 1. Why this is automatable: the differential is a self-checking ORACLE

A case is `verified_bbc` **iff** all three hold, on the SAME test:

```
1) baseline (old lib, pre-adaptation code)  -> PASS
2) new lib  (new lib, pre-adaptation code)  -> FAIL, with the break's signal_grep matching
3) adapted  (new lib, adapted code)         -> PASS
```

The agent cannot fake a "verified" result: state 2 must reproduce the *specific* exception
(`verify.signal_grep`), and states 1 & 3 must pass. This oracle is what makes autonomous
verification trustworthy for research — the LLM proposes, the differential disposes.

---

## 2. Pipeline (mostly deterministic; two LLM seams)

Reuses the existing `mine/bbc_e2e.py` stages. Per `(break, candidate)`:

| # | stage | kind | reuse |
|---|---|---|---|
| 1 | resolve candidate (repo, adapt_sha, parent_sha) | deterministic | `mine-commits`+`classify` |
| 2 | clone @ adapt_sha and parent_sha; detect build system | deterministic | git; `_detect_build_system` |
| 3 | pick JDK (from `verify.java` / repo `java.version`) | deterministic | JDK table |
| 4 | resolve dep version at commit/parent → real transition or synthetic baseline | deterministic | `dep_version` |
| 5 | **locate the adapted production method + write a driver test** | **LLM seam A** | — |
| 6 | run the 3-state differential (`mvn clean test`, `argLine` heap, `-D` version overrides) | deterministic | reuse-pom harness |
| 7 | read results; match `signal_grep` on state 2 | deterministic | surefire reports |
| 8a | if states line up → emit `verified_bbc` JSON | deterministic | case template |
| 8b | **if state 2 did NOT fail → diagnose & retry the fixture** | **LLM seam B** | bounded loop |
| 8c | if uncallable/coupled → emit `signature_confirmed`, stop | deterministic | — |

### LLM seam A — test generation
Input: the adaptation diff, the adapted production method, the break's
`characterization.failing_tests` + `signal`. Output: a JUnit test that drives the **real
production path** (e.g. `ExcelParser.parse(path)`, `XStreamConfig.xStream()`), asserting the
pre-break outcome — derived from, not copied from, the BUMP failing test. **Rules the prompt
must enforce** (all learned this session):
- Use ONLY API present in BOTH versions (no adaptation-only API in the test — that lives in
  production code), so it compiles at the baseline.
- Drive the client's real method, not a synthetic library call.
- Detect the test framework actually on the classpath (JUnit4 vs Jupiter) — mismatches
  silently run 0 tests (the einstein/jadhav lesson).

### LLM seam B — non-trip diagnosis
When state 2 unexpectedly PASSes, the break didn't trip. The agent inspects and adjusts the
FIXTURE (not the assertion). Known diagnoses to encode as first-class hints:
- **input too small / under a cap** (POI byte-cap needs >100MB uncompressed part).
- **dedup collapses the fixture** (identical strings → one SST entry; use DISTINCT values).
- **wrong guard tripped first** (repetitive content hits POI's zip-bomb `MIN_INFLATE_RATIO`;
  use INCOMPRESSIBLE content).
- **streaming avoids the allocation** (read via a path that buffers the whole part).
Bounded to N retries (e.g. 3); if still no trip, downgrade to `signature_confirmed` with the
reason, don't loop forever.

---

## 3. Outcome classification (honest, mutually exclusive)

| outcome | condition |
|---|---|
| `verified_bbc` | 1 PASS, 2 FAIL+signal, 3 PASS |
| `signature_confirmed` | real production adaptation + causal evidence, but not standalone-runnable: **class-load/framework coupling** (Spark's live XMPP session), exception swallowed, or fixture non-trip after N retries |
| `failed` | build won't resolve / repo not buildable / JDK unavailable |
| `skip` | not a production adaptation, test-only, or `library_source` (the repo IS the library) |

The agent MUST record the reason and never promote a coupled/uncertain case to
`verified_bbc`. `signature_confirmed` is a valid, expected outcome (contra "verify everything").

---

## 4. Environment handling (from the C:/JDK/heap gotchas)

> **This section is the weak point, and it is now measured.** Of 15 failures logged while
> verifying the seven jackson-core cases by hand, **12 were environment, build or missing
> prerequisites** — the static list below covers only some of them. The two LLM seams
> addressed 2. See [`AGENT_GAP_ANALYSIS.md`](AGENT_GAP_ANALYSIS.md), which proposes a third
> seam (`diagnose_build_failure`) plus mandatory provenance assertions, and argues for
> building the acceptance suite before extending the agent.

- **JDK table**: map `verify.java` → an installed JDK path (11 = Eclipse Adoptium; 17 =
  `C:/Program Files/Java/jdk-17`; 21 available). Fail the case cleanly if the needed JDK is absent.
- **Heap**: pass `-DargLine=-Xmx3g` when the fixture is large (POI). Detectable from seam-B size.
- **`mvn clean` between states** — required; incremental compile reuses stale `.class` after a
  `git checkout` and gives false results (PIPELINE.md gotcha).
- **Disk (C: constrained)**: clone `--filter=blob:none`, delete large fixtures (`deleteOnExit`),
  clean worktrees after each candidate.
- **JDK-17 + reflection libs**: apply `verify.jvm_add_opens` (xstream needs it).

---

## 5. I/O contracts

- **Input**: a catalog break (`bump_breaks_catalog.json`) + a candidate row
  (`output/<break_id>_candidates.jsonl`, already produced by mine+classify).
- **Output**: `verified_cases/<case_id>.json` (existing schema, incl. `in_repo_version_transition`,
  `bump_provenance`, `verification.states`) + a preserved harness in `scratchpad/<case_id>-harness/`.
- **Idempotent**: skip candidates already recorded; re-runnable.

---

## 6. Agent SDK shape

Headless Claude agent, tools: `bash` (git/mvn/jdk), `read`/`write`/`edit` (test + pom),
`grep`/`glob`. One agent instance per candidate (fresh worktree) for isolation; a driver
script fans out over `(break × candidates)`. The two LLM seams are agent turns; everything
else is deterministic tool calls the agent orchestrates. Budget guardrails: max tool calls
and max fixture-retries per candidate; on exceed → `signature_confirmed`/`failed` with reason.

Loop skeleton lives in `scripts/nadia_scripts/agent/` (orchestrator + prompts).

---

## 7. Guardrails / honesty (research credibility)

1. **Never** emit `verified_bbc` without all three oracle conditions met on a real run.
2. State-2 failure must match `signal_grep` — a *different* failure (compile error, JVM
   mismatch, OOM) is NOT the break; treat as `failed`/retry, not verified.
3. Record every state's raw surefire line in the case file (auditable).
4. Prefer `signature_confirmed` over a forced/edited pass — no touching the assertion to make
   it green.
5. Keep the human-in-the-loop escape: emit a review queue for `signature_confirmed`/`failed`
   with the diagnosis, so a person can pick up genuinely-hard cases (Spark-class coupling).

---

## 8. Yield expectations (set with supervisors)

Throughput ↑, but yield is gated by break quality: framework-coupled adaptations stay
`signature_confirmed`. Realistic split per break ≈ clean-standalone → verified; coupled →
signature. Dataset ≈ Σ_breaks (verifiable adaptations). The agent's job is to process the
many candidates per break fast and classify honestly — not to make every candidate verified.

---

## 9. Build order

1. **Orchestrator skeleton** — wire stages 1–4, 6–8 (deterministic) around the existing
   `mine/bbc_e2e.py`; stub seams A/B as agent-callable steps.
2. **Seam A prompt** — driver-test generation with the compile/framework rules above.
3. **Seam B prompt** — non-trip diagnosis with the encoded fixture hints.
4. **Dry-run** on a KNOWN-good candidate (re-verify jadhavspeaks / amirsnw end-to-end
   autonomously) as the acceptance test — the agent should reproduce what we did by hand.
5. Fan out over the 12-break catalog's candidate files.
