# Verified BBC → adaptation cases

Curated, **rigorously verified** cases of a Behavioural Breaking Change (BBC) in a
dependency and the client **adaptation** made in response. One JSON file per case
(mirroring BUMP's own `data/benchmark_test_failures/` layout).

Each case is anchored in a BUMP-confirmed behavioural break and independently
verified with a **3-state differential** build+test, so every entry here is
evidence-backed, not inferred.

## Layout

Cases are nested **one folder per library** (since 2026-08):

```
verified_cases/
  xstream/                  7 cases + XSTREAM_SUMMARY.md
  snakeyaml/                2 cases (the 1.32 code-point limit)
  excluded/<reason>/        rejected candidates, one folder per reason
  pending_differential/     found but not yet run
  drivers/                  generated test drivers
```

**The folder is the authority on what counts as verified, not the `status` field.**
Six files under `excluded/` still read `status: verified_bbc` — they were verified and
then excluded as authored mimics, mechanism-only, or no-boundary-crossing, and their
status was never rewritten. Anything globbing `**/*.json` and filtering on status will
count them and overstate the verified total. `report/census.py`, `mine/bbc_e2e.py summarize()`
and `agent/fanout.py` all glob `*/*.json` and skip `excluded`, `pending_differential`
and `drivers` by name.

## What belongs in this folder

A file here is a **client production adaptation to a behavioural break, verified by a
3-state differential**. All four conditions, no exceptions:

1. `status: verified_bbc` — a differential was actually run, not inferred
2. the adaptation is in **production code** (`src/main`), not tests
3. it is a **real external client repo**, not an authored mimic
4. it is a **client adaptation**, not merely a demonstration that the library break exists
5. the client **crossed the break boundary in its own history** — a direct or
   transitive dependency bump took the resolved library version from below the
   boundary to at/above it

Rule 5 is what makes a case evidence of *adaptation to a breaking update* rather than
*a latent bug the client happened to hit*. A client born at or above the boundary never
experienced a transition: the restrictive behaviour was there from its first commit, so
its fix is a response to the library's behaviour, not to a change in it. Both are real
engineering, but only the first supports a claim about how clients respond when a
dependency breaks them.

Removed 2026-08-04 for failing these:

| removed | why |
|---|---|
| `poi-fmflatfile`, `poi-impactupgrade-nucleus-engine`, `poi-kenzoknz-pdf-converter`, `poi-oboguev-rtss`, `poi-usepa-data-gathering`, `xstream-spark` | `signature_confirmed` — causally real, but no differential was ever run (rule 1). POI's byte cap is enforced inside its document parsing, so a standalone repro needs a crafted document and the repo's own build. |
| `xstream-logging-chainsaw` | the adaptation touches only `src/test/java/.../LogPanelPreferenceModelTest.java` (rule 2). The break manifested and was fixed, but production code was never forced to change, so it is not evidence that this break forces production adaptation. |

Moved to `excluded/`, kept because they are still evidence of something — just not of a
client adapting:

- `excluded/authored_mimics/` — `xstream-mimic-production`, `jackson-ptv-mimic`: we wrote
  the client. They demonstrate the mechanism, prove nothing about real-world behaviour.
- `excluded/mechanism_only/` — `snakeyaml-mongoose`, `jackson-streamreadconstraints`: the
  harness proves the library's behaviour changed, but the clients did not cross the
  boundary in-repo (see each file's audit block). Adaptation to a break's *behaviour*,
  not to a version transition they made.
- `excluded/compile_break/` — the client crossed the boundary and adapted production
  code, but the break it adapted to is **syntactic**, not behavioural:
    - `snakeyaml-adityajoy-dashboard` — `adityajoy-1902/Dashboard-V-2@8c39d993`, snakeyaml
      1.29 → 2.0. Verified 2026-08-06 by a 3-state `mvn compile` differential: parent code
      compiles at 1.29, **fails javac** at 2.0 (`Class` cannot be converted to
      `LoaderOptions`), and compiles again after the fix. 2.0 kept an arity-1 `Constructor`
      but narrowed it from `Constructor(Class)` to `Constructor(LoaderOptions)`, so the old
      call never reaches runtime. A syntactic BC is out of scope by definition — this
      dataset is about breaks that survive compilation.

- `excluded/no_boundary_crossing/` — fully verified production adaptations in real
  external repos that fail rule 5:
    - `xstream-axon-saga-einsteinarbert` — `axon-spring-boot-starter 4.6.1` set in the
      first commit and never bumped; xstream 1.4.19 from the repo's birth.
    - `xstream-chaintrade-amirsnw` — recorded `crossed_boundary: false`; the transitive
      chain is BOM-managed and does not resolve from Maven Central alone, so the
      automated gate reports it as undecided rather than negative.
    - `poi-jadhavspeaks` — no crossing on either poi or poi-ooxml; born at/above 5.0.0.
  These are the clearest evidence for the rarity finding: the adaptation is real and
  the break is real, but the client never lived through the transition.

Note on `xstream-logging-chainsaw`: it remains a valid **traversal** fixture in
`verify/test_gates.py` — BUMP recorded its bump commit, so its boundary crossing is
independently confirmed. Valid crossing, test-only adaptation, not a case.


## How a case is verified (the A→D recipe)

- **A. Characterize** — from BUMP: `data/benchmark_test_failures/<sha>.json` +
  `reproductionLogs/successfulReproductionLogs/<sha>.log` give the exact failing
  test and exception.
- **B. Find the adaptation** — the commit where the client actually adapted its
  code (often the BUMP project itself, in a commit *separate* from the unmerged
  dependabot breaking commit).
- **C. Verify (3-state differential)** — build + run the failing test in three
  states; a case is a confirmed BBC only if:
  1. `baseline` (old lib, old code) → **PASS**
  2. `new_lib_old_code` (new lib, pre-adaptation code) → **FAIL** with the break
  3. `adapted` (new lib + the adaptation) → **PASS**
- **D. Record the adaptation** — the diff and a summary of what the client did.

## Schema (per case file)

| field | meaning |
|---|---|
| `case_id`, `status`, `verified_date`, `verified_by` | provenance |
| `library` | groupId/artifactId, `from_version`→`to_version`, boundary type, scope |
| `bump_source` | the BUMP entry: project, breaking commit, PR, repro-log path, Java version |
| `behavioral_break` | failing test, exception, affected class, why it breaks |
| `adaptation` | repo, commit, files changed, whether it's in test code, summary, diff |
| `verification` | the 3-state differential results and conclusion |

## Status levels

- **`verified_bbc`** — the 3-state differential was actually run: baseline PASS →
  new-lib+old-code FAIL with the break → adapted PASS. Fully evidence-backed.
- **`authored_mimic`** (`case_type`) — a self-contained project we authored to
  reproduce a real BUMP break, used when no clean *external* adaptation exists (e.g.
  xstream production adaptations are confounded with proactive RCE hardening). Still
  held to the full 3-state differential; the failing test is derived from the BUMP
  failing test. See [xstream-mimic-production](xstream-mimic-production.json).
- **`signature_confirmed`** — the client calls a *causally-clean* adaptation API
  (one that can only exist because of the upgrade, e.g. POI's
  `IOUtils.setByteArrayMaxOverride`), so the adaptation is provably upgrade-triggered,
  but the break has **not yet** been reproduced in that repo (differential pending).

## Discovery phases

- **Phase 1 — BUMP self-adaptation:** check whether the BUMP client project itself
  adapted, in a commit separate from the (usually unmerged) dependabot break.
- **Phase 2 — external signature mining:** GitHub code-search for the break's
  *adaptation signature*, then confirm the version-transition link. Pick signatures
  that can ONLY exist because of the upgrade (POI `setByteArrayMaxOverride` = clean;
  xstream `allowTypes` = confounded with general security hardening, high false-positive).

## Cases

Seven cases. Every other file that used to be listed here is now under `excluded/`,
sorted by which rule it fails — see the tables above.

| case_id | transition | client | discovery | recovery attributable to production change? |
|---|---|---|---|---|
| [xstream-marklogic-contentpump](xstream-marklogic-contentpump.json) | 1.4.16 → 1.4.18 | marklogic/marklogic-contentpump | 32-term mine (bump axis) | ✅ **yes** — invariant driver across all 3 states |
| [xstream-collectionspace-services](xstream-collectionspace-services.json) | 1.4.10 → 1.4.19 | collectionspace/services | 32-term mine (bump axis) | ✅ **yes** — invariant driver; classpath confirmed |
| [xstream-voyanttools-trombone](xstream-voyanttools-trombone.json) | 1.4.16 → 1.4.18 | voyanttools/trombone | 32-term mine (bump axis) | ✅ **yes** — invariant driver; baseline reconstructed |
| [xstream-openmrs-core](xstream-openmrs-core.json) | 1.4.17 → 1.4.20 | openmrs/openmrs-core | 32-term mine (bump axis) | ⚠️ **no** — state 4 shows this test recovers test-side; production mechanism confirmed separately by the commit's own new tests |
| [xstream-axon-artshishkin](xstream-axon-artshishkin.json) | 1.4.16 → 1.4.19 (transitive, via Axon) | artshishkin/…axon-microservices | 3-query mine | ✅ yes |
| [xstream-axon-saga-einsteinarbert](xstream-axon-saga-einsteinarbert.json) | 1.4.10 → 1.4.19 (transitive, via Axon) | einsteinarbert/axon-saga-example | 3-query mine | ✅ yes |
| [xstream-tvrenamer](xstream-tvrenamer.json) | 1.4.9 → 1.4.20 | The-Ant-Forge/TVRenamer (Gradle) | Phase 2 signature search | ✅ yes |

Two further exclusion categories were opened by the 2026-08-07 batch:

- `excluded/wrong_cause/` — `xstream-synapse-repository-services`: every mechanical gate
  passed (production, native Maven, real repo, confirmed crossing one commit away), but
  the commit message says the cause is **Java 21**, not the xstream upgrade, and the
  parent was *already* whitelisting. **Traversal confirmation is necessary but not
  sufficient** — it proves the client crossed the boundary near the adaptation, never
  that the crossing caused it. Deliberately not differentiated: a Java 21 toolchain
  would likely have produced a green PASS/FAIL/PASS attributing a JDK break to xstream.
- `excluded/not_standalone_verifiable/` — `xstream-openfire-fastpath-plugin`: causally
  clean (the commit message names the upgrade) but the break site is a private method
  reached only through a live Openfire server, and its exception is swallowed by a
  `catch (Exception e) { Log.error(...) }`. It cannot fail a test even in principle.
  Same disposition as `xstream-spark`.

**Two cheap pre-differential checks, learned the hard way:** before building anything,
read the commit message for an explicitly stated non-library cause (JDK migrations are
the common one), and check whether the *parent* already contains adaptation-signature
calls — a client already carrying the fix cannot be adapting to that break. Mechanical
gates took 2288 mined rows down to 11 candidates; human reading removed 2 more.

The last column is worth keeping. A 3-state differential can go green because the client
changed its *test* rather than its production code, and only a fourth state — adapted
production code against the PARENT's test — distinguishes the two. `xstream-openmrs-core`
is the case that made this visible; it is a real production adaptation to a real break,
but its differential does not by itself prove the production change is what recovers.
Run state 4 whenever the adaptation commit touches test files.

Authored drivers live in [`drivers/`](drivers/). A driver is not an authored mimic: the
client, the break and the fix are all real and external, and the driver only calls
existing production methods. It is used when the repo has no test covering the broken
path, and it must be byte-identical across all three states.
