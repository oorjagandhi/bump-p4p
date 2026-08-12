# The BBC-verification agent, in plain terms

A companion to `AGENT_DESIGN.md`. That document is the engineering spec — stage tables,
I/O contracts, prompt rules. This one explains **what the agent is, why it exists, and
what it contributes to the research**, for a reader who has not touched the code.

---

## 1. The research question

We study **behavioural breaking changes** (BBCs): a library upgrade where the client's
code still *compiles*, the API signature is unchanged, but the program now *behaves*
differently at runtime. A stricter default limit rejects an input it used to accept. A
security tightening refuses to deserialise a class it used to allow. Nothing turns red
at compile time; something turns red at run time, or worse, silently changes meaning.

What we actually want to document is not the break itself but the **human response** to
it — the *adaptation*. When a real project hit this wall, what did the developers change
in their own production code to keep working? That is the artefact of interest: a real
commit, in a real repository, that adjusts application code because a dependency's
behaviour changed underneath it.

So each dataset entry is a triple:

> **break** (library X, version A → B, this behaviour changed)
> **client** (a real project that upgraded across that boundary)
> **adaptation** (the commit where they changed their own code to cope)

---

## 2. The challenge the agent addresses

Finding candidate adaptations is comparatively easy — mining commit messages and
dependency histories gets us a list. **Proving one is real is the bottleneck.**

A commit message saying "fix XStream security exception after upgrade" is a *claim*. It
might be the adaptation we're looking for. It might also be an unrelated refactor, a
test-only change, a coincidence of wording, or a fix for something else entirely. Taking
the message at face value would give us a large dataset of unverified anecdotes — which
is precisely the weakness that would sink the work under review.

Establishing one case by hand means: clone the repo at two commits, find the right JDK,
resolve the dependency version at each point, write a test that drives the client's real
production code, run it three times under three configurations, and read the results.
That is roughly a **half-day of skilled work per candidate**, and it fails often — the
repo won't build, the JDK is missing, the test framework is mismatched, the fixture
doesn't trip the limit. We have candidate lists in the hundreds. The arithmetic doesn't
work.

**The challenge, stated plainly: manual verification is the rate limiter on dataset size,
and unverified evidence is not worth collecting.** The agent exists to break that
trade-off — to make verification cheap enough to run at scale *without* lowering the
standard of proof.

---

## 3. The key idea: the differential is a self-checking oracle

This is what makes automation trustworthy, and it is the heart of the design.

We do not ask the agent "is this a real adaptation?" and believe its answer. We make it
run an experiment whose outcome it cannot fake. For a single test, driving the client's
own production code, we run **three states**:

| # | library version | client code | expected |
|---|---|---|---|
| 1 | **old** (pre-break) | **pre-adaptation** (the parent commit) | **PASS** |
| 2 | **new** (post-break) | **pre-adaptation** (the parent commit) | **FAIL**, with the break's exact signature |
| 3 | **new** (post-break) | **adapted** (the fix commit) | **PASS** |

Read it as a story. State 1 says: *before the upgrade, this code worked.* State 2 says:
*the upgrade alone — changing nothing but the library version — broke it, and broke it
with precisely the expected error.* State 3 says: *the developers' own change is what
repaired it.*

Only all three together establish causation. State 2 in particular must match the
break's specific signature (a regex on the exception — `signal_grep`); a compile error, a
JVM mismatch, or an out-of-memory failure is **not** the break, and does not count. So an
agent that hallucinates a plausible-looking case produces a run that doesn't line up, and
the case is rejected. In the design's phrase: **the LLM proposes, the differential
disposes.**

This is why the work is automatable at all. The expensive judgment is checkable by a
cheap deterministic test.

---

## 4. What the agent actually does

Per candidate, eight steps. Six are ordinary deterministic code — git, Maven, file
parsing — reusing the mining and classification machinery already validated in
`mine/bbc_e2e.py`. Only two require judgment, and those are the ones handed to the model. We
call them **seams**: narrow, well-defined points where an LLM is inserted into an
otherwise mechanical pipeline.

```
  1. resolve the candidate (repo, adaptation commit, its parent)      deterministic
  2. clone both commits, detect the build system                      deterministic
  3. pick the right JDK                                               deterministic
  4. resolve the dependency version on each side                      deterministic
  5. WRITE A TEST that drives the adapted production method    ◄──── SEAM A (LLM)
  6. run the three states                                             deterministic
  7. check the results, match the signature on state 2                deterministic
  8. classify the outcome and write the case file                     deterministic
     └─ if state 2 unexpectedly passed:  DIAGNOSE WHY          ◄──── SEAM B (LLM)
```

### Seam A — writing the driver test

The hard part is not "write a JUnit test". It is writing one that must compile and run
**identically against both the old and new library**, while driving the client's *own*
code rather than calling the library directly. The break has to manifest through the
application's real execution path, or we've demonstrated something about the library, not
about the client.

The prompt (`agent/prompts/seam_a_testgen.md`) encodes the rules, each of which comes
from a specific failure we hit by hand:

- **Use only API that exists in both versions.** The new API the adaptation introduced
  belongs in the production code, never in the test — otherwise the test won't compile at
  the baseline and state 1 is impossible.
- **Call the client's real method**, not a synthetic library call.
- **Match the test framework actually on the classpath.** A JUnit 4 test on a
  Jupiter-only classpath doesn't error loudly — it silently runs zero tests and reports
  success. We lost real time to this twice.

It also handles a subtler case we discovered mid-project: clients **born past the
boundary**, which never had a pre-adaptation state because they were written after the
break and adapted by *adding* configuration. There is no old code to run as state 2, so
the test reconstructs the library's pre-adaptation default behaviour instead.

### Seam B — diagnosing a non-trip

Sometimes state 2 passes when it should fail. The break didn't trigger. This is usually
not a wrong hypothesis but a **fixture that's too weak**, and the diagnoses are specific
and recurring: the input is under the limit; identical strings get de-duplicated so the
document never reaches the threshold; a *different* guard fires first (compressible
content hits the zip-bomb check before the size cap); the code path streams instead of
buffering.

The agent adjusts the **fixture** and retries, bounded to three attempts. It is never
permitted to adjust the assertion — weakening the check to force a green result is
exactly the corruption the oracle exists to prevent. If it still doesn't trip, the case is
downgraded honestly rather than retried forever.

---

## 5. Honest outcomes — including the ones that aren't wins

The agent classifies into four mutually exclusive outcomes, and **`verified_bbc` is not
the only acceptable one**:

| outcome | meaning |
|---|---|
| `verified_bbc` | All three states lined up. Full causal proof. |
| `signature_confirmed` | A real production adaptation with causal evidence, but not standalone-reproducible — the break needs a live framework session, the exception is swallowed, or the fixture wouldn't trip after retries. |
| `failed` | Environment problem: repo won't build, JDK unavailable, dependency won't resolve. Says nothing about the case. |
| `skip` | Not applicable: test-only change, or the repo *is* the library. |

`signature_confirmed` matters. Some adaptations are genuine but entangled with a
framework — the break happens inside a running Spark job or an XMPP session, and no
standalone test can reach it. Recording those honestly, with the reason, is more valuable
than either discarding them or promoting them past what the evidence supports. It also
leaves a review queue: a human can pick up the genuinely hard ones.

This is a **research-integrity property, not a limitation**. The agent is built so that
the easy way to make a number go up is unavailable to it.

Note on where these land (2026-08-04): `signature_confirmed` remains a valid agent
*outcome*, but it is no longer a *case*. `verified_cases/` now holds only entries that
satisfy all five inclusion rules in its README; a `signature_confirmed` result is filed
under `verified_cases/excluded/` with the reason. The distinction matters because the two
were previously stored side by side under one `status` field, so a count of the folder
mixed "proved by differential" with "looks right but never run". Five POI entries sat in
that state — POI's byte cap is enforced inside its document parsing, so a standalone
repro needs a crafted document and the repo's own build, which is exactly the
`signature_confirmed` condition.

---

## 6. What this buys the research

1. **Throughput.** Verification goes from half a day of expert attention per candidate to
   an unattended run, so the candidate lists we already have become processable.
2. **Consistency.** Every case is established the same way, with the same oracle. No
   drift between the first case and the fiftieth, and no "I remember checking that".
3. **Auditability.** Each case file records all three states with their raw surefire
   lines, plus the version transition and provenance. A reviewer can re-run any case
   rather than trusting a summary.
4. **A negative result worth reporting.** Running the same honest procedure across many
   libraries tells us how *rare* verifiable behavioural breaks actually are — which
   libraries produce them and which never do. That rarity finding is itself a
   contribution, and it only holds if the procedure was uniform.
5. **A reusable method.** The oracle plus the two seams is a general recipe for verifying
   dependency-induced behavioural breaks — not specific to the libraries we happened to
   study.

The honest framing of yield: the agent's job is to process many candidates quickly and
classify them truthfully. It is *not* to turn every candidate into a verified case, and a
design that promised that would be the untrustworthy one.

---

## 7. Where it stands today

*Status as of 2026-08-04. The figures below replace an earlier count of "16 case files —
9 verified_bbc, 6 signature_confirmed"; see "What changed" at the end of this section.*

**Working:**
- Deterministic plumbing — `agent/orchestrator.py` implements the state machine: clone,
  JDK selection, the three-state runner, signature matching, outcome classification.
- Both seam prompts are written and refined against real failures
  (`agent/prompts/seam_a_testgen.md`, `seam_b_diagnose.md`).
- The seam implementations exist in `agent/seams.py`, including deterministic input
  gathering (adaptation diff, adapted production code, test-framework detection).
- The LLM seams are proven in the **Claude-as-seam** configuration — the model answering
  the seam directly, with the deterministic harness around it. Every authored driver in
  the dataset was produced this way.
- **Candidate screening is now six deterministic gates**, not one: production adaptation,
  content evidence (the diff really touches the library), default-branch reachability,
  boundary traversal (direct **and transitive**), compile-vs-behavioural break, and
  trigger (does the client's data reach the changed behaviour). Each rejects a class of
  candidate that previously reached the oracle and wasted a run.
- **`test_gates.py`** holds regression fixtures for the two most error-prone gates, with
  BOTH polarities. This exists because gates fail silently: a gate stuck on "no" is
  indistinguishable from one reporting a genuine negative, and two did exactly that.
- **`agent/acceptance_artshishkin.py` passes**, reproducing the recorded 3-state result
  exactly (PASS / FAIL+signature / PASS, matching test counts).

**Not yet working:**
- The **headless** configuration (`seams.py` calling the Anthropic SDK unattended) needs a
  credential in the environment. The SDK is installed; `ANTHROPIC_API_KEY` is not set.
  Until then the agent runs with an interactive model at the seams, not autonomously.
- `agent/fanout.py` mis-buckets candidates when spreading work across a break's candidate
  list, so the fan-out layer is not trustworthy for a full unattended sweep. Single-case
  autonomy is testable now; fan-out is not.
- `verify.version_property` is still carried as a TODO in the orchestrator rather than
  resolved from the catalog per break.

**The dataset today:** 3 cases in `verified_cases/`, each with a recorded 3-state
differential — `xstream-tvrenamer` (direct crossing), `xstream-axon-artshishkin` and
`xstream-axon-saga-einsteinarbert` (both transitive). Everything else lives in
`verified_cases/excluded/`, sorted by which inclusion rule it fails: `authored_mimics/`,
`mechanism_only/`, `no_boundary_crossing/`. A case must satisfy all five rules in that
folder's README — verified by differential, production code, real external repo, a client
adaptation rather than a mechanism demo, and a boundary crossing in the client's own
history.

**The acceptance test** for autonomy is deliberately conservative: re-verify a case we
already established by hand and require the agent to reproduce it unaided. The current
bar is `acceptance_artshishkin.py`. The two older scripts
(`acceptance_jadhavspeaks.py`, `acceptance_amirsnw.py`) target cases that are now in
`excluded/no_boundary_crossing/` — both clients were born past their boundary — so they no
longer validate against anything that counts. In all three, SEAM_A output is FROZEN into
the script; they validate the deterministic half given a known-good seam result. The
autonomy test is to replace that constant with a live `seams.generate_test(...)` call and
require the same verdict.

**What changed on 2026-08-04, and why the numbers moved:**
- `verify_traversal` had **never confirmed a candidate**: `_gh()` called `.get()` on
  GitHub's list responses and `find_boundary_bump` swallowed the resulting error as "no
  commits". Every traversal verdict recorded before that date is void.
- Traversal now resolves the version the build **actually gets**, so crossings that arrive
  through a framework are visible. Two Axon cases previously filed as non-crossings turned
  out to be genuine transitive crossings.
- The inclusion rules were made explicit and applied, which moved most former entries into
  `excluded/`. The count fell from 16 files to 3 cases. The earlier number was not wrong
  arithmetic — it summed four different kinds of evidence under one status field.
- `verify/02_verify_bbc.py` (verify against the client's OWN test suite) was fixed and run on the
  traversal-confirmed pairs. It returned `no_bc` for two hand-verified cases: **false
  negatives**. The cause is structural — BUMP's corpus exists because a test failed, but
  externally mined adaptations reached production precisely because no test caught them.
  Operating rule: that tool may PROMOTE a case, never REJECT one.

---

## 8. One-paragraph summary

Behavioural breaking changes are dependency upgrades that compile fine and misbehave at
run time; the artefacts we want are the real commits where developers adapted their code
to them. Confirming that any given commit truly is such an adaptation took about half a
day of expert work, which capped the dataset far below a useful size — and unverified
cases would not be worth collecting. The agent automates that confirmation around a
three-state differential that acts as a self-checking oracle: the code passes on the old
library, fails on the new one with the break's exact signature, and passes again after
the developers' fix. Everything mechanical is ordinary deterministic code; the model is
inserted at exactly two points requiring judgment — writing a test that runs against both
library versions, and diagnosing a fixture that fails to trigger the break. Because the
differential must line up on a real run, the agent cannot manufacture a verified case,
and cases it cannot fully prove are recorded honestly as `signature_confirmed` rather
than promoted. The result is verification at a scale the research needs, without
weakening the standard of evidence it rests on.
