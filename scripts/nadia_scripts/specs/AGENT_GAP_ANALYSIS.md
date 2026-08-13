# What seven hand-verified cases showed the agent is missing

**Status:** design note, 2026-08-13. Companion to [`AGENT_DESIGN.md`](AGENT_DESIGN.md) (the
engineering spec) and [`AGENT_EXPLAINED.md`](AGENT_EXPLAINED.md) (the plain-language one).

**Why it exists.** Between them, the jackson-core 2.15 cases —
json-compare, datashare, couchbase, benchto, vespa, arangodb, and trino (in progress) —
were verified by writing a differential harness per client by hand. That produced a log of
everything that went wrong before each one ran. This note classifies those failures and
asks a single question: *if the agent had been driving, which of them would it have
survived?*

The answer is: about two of fifteen.

---

## 1. Where the agent stands today

It is **demonstrated, not deployed**. On 2026-08-04 the acceptance run against
`artshishkin` produced a complete differential — PASS → FAIL(+signal) → PASS,
`OUTCOME: verified_bbc`. That is real and it matters: the deterministic plumbing and the
LLM seam both work end to end.

But that case was already verified by hand on 2026-07-12. **No case in `verified_cases/`
was produced by the agent.** All 17 came from hand-written harnesses in
`scratchpad/*-harness/`. There is exactly one acceptance run log.

So the machinery is proven on a replay. What follows is what a replay never had to face.

---

## 2. The evidence: 15 failures across 7 clients

| # | client | failure | kind |
|---|---|---|---|
| 1 | datashare | `javac` from PATH was JDK 11 while Maven used `JAVA_HOME`=17 → *class file has wrong version 61.0, should be 55.0* | env |
| 2 | couchbase | `protostellar:1.0-SNAPSHOT` unpublished and not in the root `<modules>` | prereq |
| 3 | couchbase | `-pl core-io` still parses every module; `scala-implicits` has a command line pasted into its `artifactId` → reactor unparseable → had to switch to `-f` | build |
| 4 | couchbase | shade plugin *duplicate entry* — the previous state's shaded jar was re-shaded because `clean` was missing | build |
| 5 | couchbase | `test-utils:1.4.7-SNAPSHOT` missing → `build-classpath` failed | prereq |
| 6 | couchbase | root parent POM not installed → needed `install -N` | prereq |
| 7 | couchbase | driver emitted a 9.5 MB log (`MapperException` embeds the whole input) | driver |
| 8 | benchto | CRLF from a Windows clone → airbase checkstyle failed the build | env |
| 9 | benchto | driver used `Object` where `JsonNode` was needed → compile error | driver |
| 10 | benchto | enforcer `RequireUpperBoundDeps` rejected the deliberate baseline downgrade | build |
| 11 | benchto | the real pre-crossing baseline (2.13.3) **cannot run** — Spring 6.1 calls `DatatypeFeature`, added in jackson 2.14 | version |
| 12 | vespa | `bundle-plugin` is a build *extension* defining custom packaging → *Unknown packaging: container-plugin*, reactor unparseable | prereq |
| 13 | trino | Windows `MAX_PATH` → `git checkout` dies partway, no root `pom.xml` | env |
| 14 | trino | sparse **cone** checkout → Maven *child module … does not exist* | env |
| 15 | trino | `cp.txt` never generated → driver ran with no dependencies and **threw**, looking exactly like the break | build |

**Tally:** env/build/prereq **12**, driver (SEAM_A's job) **2**, version judgment **1**.

`SEAM_A` (write the driver) and `SEAM_B` (state 2 didn't fail) between them address rows 7
and 9. The other thirteen are outside the agent's model entirely.

**Row 15 deserves separate attention.** It did not fail loudly — it produced
`RESULT=THREW`, which is precisely what a confirmed break looks like. It was caught only
because the driver also printed *where jackson loaded from*, and the answer was `unknown`.
An agent without that check would have recorded a verified case that was really a missing
classpath.

---

## 3. Proposals

### P1 — SEAM_C: `diagnose_build_failure` *(the one that matters)*

Same shape as SEAM_B, different trigger. **Input:** the failing Maven invocation, the last
~40 lines of output, the POM, and what has already been tried. **Output:** one of

- a flag to add (`-Dmaven.javadoc.skip=true`, `-Dair.check.skip-enforcer=true`, `-Dgpg.skip=true`)
- a prerequisite to build first (`mvn -f <module>/pom.xml install`, `install -N` for a parent)
- a checkout/clone adjustment (`core.longpaths`, a sparse exclusion)
- `give_up` with a reason, which becomes an honest exclusion rather than a silent failure

Every one of rows 1–6, 8, 10, 12–15 is diagnosable from its error text in a single read.
This is the change that moves the agent from replay to production.

**Two invariants SEAM_C must not be allowed to break:**

1. **A flag applies to ALL THREE STATES or none.** Skipping a check only where it fires
   means the states were built under different rules, and the one-variable property that
   makes the differential meaningful is gone. (I nearly made this mistake with benchto's
   enforcer skip.)
2. **It may never touch a build file.** Overrides go on the command line, through the
   project's *own* properties. The moment the agent edits a POM, the artefact stops being
   the client's build.

### P2 — Mandatory provenance, asserted by the orchestrator

Today the generated driver prints whatever SEAM_A decides. Make two prints **required**,
and then *check* them deterministically:

- where the library jar was loaded from
- the setting actually in force (read back reflectively, e.g. `getMaxStringLength()`)

Then assert, outside the LLM:

- state 1 and state 2 report **different** library versions — else the version override
  silently did nothing
- state 3's setting differs from state 2's — else the adaptation is not in effect
- no state reports `unknown` for the jar location

A differential whose three states cannot be shown to be three different configurations is
**invalid regardless of pass/fail**. This is what row 15 was, and what the arangodb and
couchbase harnesses got right by accident of care.

### P3 — Version-knob discovery as a deterministic probe

The right `-D` property is not guessable from the client's POM. Real examples:
`jackson.version` (json-compare), `adb.jackson.version` (arangodb), `jackson2.version`
(vespa), `dep.jackson.version` (trino), and `jackson-bom.version` for benchto — which is
**Spring Boot's** property, not benchto's, because benchto declares no jackson version at all.

Probe rather than guess: for each candidate name, run `mvn dependency:list -D<name>=<X>`
and keep the one where the resolved version actually moves. Cheap, deterministic, and it is
how benchto's non-obvious answer was found.

### P4 — Baseline fallback with a recorded threat

If the recorded pre-crossing version will not run, walk forward to the newest version still
below the boundary that does, and write the substitution into the case file as a threat to
validity. That is exactly benchto 2.13.3 → 2.14.2, where the framework that *delivered* the
crossing could not run without the library it delivered.

### P5 — Entry-point selection from the adaptation diff, not the search hit

SEAM_A is currently pointed at one file. Two cases show that is wrong:

- **vespa** changed 9 files; the code-search hit was `JsonWriter`, whose factory builds
  *generators* — the read constraint there is never exercised. The demonstrable site was
  `JsonFeedReader`, changed in the same commit.
- **trino**'s hit was `JsonUtils`, whose `parseJson` was already safe via airlift's
  `ObjectMapperProvider`. The break lives at the six direct `JsonFactory` call sites the
  same commit migrated.

Give SEAM_A **every** changed call site and ask it to choose one that is (a) reachable
without a running server and (b) on the read/parse path the constraint governs.

---

## 4. Do the acceptance suite first

Building SEAM_C and testing it only against `artshishkin` teaches nothing — that case
needed none of this.

The seven jackson harnesses are ready-made hard fixtures with independently known answers:

| fixture | what it exercises |
|---|---|
| couchbase | shaded library + 3 missing prerequisites + a **bounded** payload window (must exceed 5 MB *and* stay under 20 MiB) |
| benchto | transitive version via a BOM two levels up + an unrunnable true baseline |
| vespa | custom build extension; reactor unparseable until bootstrapped; hit-file ≠ break-file |
| arangodb | the trigger is the client's **own test**; reflective adaptation the value screen could not read |
| datashare | JDK differing from the PATH default |
| trino | Windows MAX_PATH; sparse-checkout interacting with Maven's module list |

Wire these in as acceptance cases **before** extending the agent. Then "the agent verified
it" becomes a claim that can be checked, on cases where the answer is already known and the
path to it is genuinely hard.

---

## 5. What NOT to change

- **The oracle stays pass → fail → pass.** It is self-checking and it is why this is
  automatable at all. Nothing here weakens it.
- **`undecided` stays a third value.** Discovery-side, but the same principle: an unknown
  must never be recorded as a negative.
- **The hand-written harness stays the fallback.** It produced all 17 cases. The agent
  should be measured against it, not assumed to replace it.
- **`verify/02_verify_bbc.py` is not the model to extend.** Its own commit history records
  that it gives false negatives, and no case in the dataset used it. The
  `scratchpad/*-harness/` shape — build the project's own build, drive one production entry
  point, print provenance — is what has actually worked.
