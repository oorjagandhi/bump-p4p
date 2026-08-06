# Verified BBC → adaptation cases

Curated, **rigorously verified** cases of a Behavioural Breaking Change (BBC) in a
dependency and the client **adaptation** made in response. One JSON file per case
(mirroring BUMP's own `data/benchmark_test_failures/` layout).

Each case is anchored in a BUMP-confirmed behavioural break and independently
verified with a **3-state differential** build+test, so every entry here is
evidence-backed, not inferred.

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
`test_gates.py` — BUMP recorded its bump commit, so its boundary crossing is
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

| case_id | library | transition | client | discovery | status |
|---|---|---|---|---|---|
| [xstream-logging-chainsaw](xstream-logging-chainsaw.json) | xstream | 1.4.17 → 1.4.19 (patch) | apache/logging-chainsaw | Phase 1 | ✅ verified_bbc (partial/test-only adaptation) |
| [xstream-mimic-production](xstream-mimic-production.json) | xstream | 1.4.17 → 1.4.19 (patch) | authored mimic (scratchpad/xstream-mimic) | Authored | ✅ verified_bbc (**production** adaptation) |
| [xstream-tvrenamer](xstream-tvrenamer.json) | xstream | 1.4.9 → 1.4.20 (crosses 1.4.18) | The-Ant-Forge/TVRenamer (Gradle) | Phase 2 | ✅ verified_bbc (real **external production** adaptation; full differential via Maven harness) |
| [xstream-axon-artshishkin](xstream-axon-artshishkin.json) | xstream | 1.4.17 → 1.4.19 (crosses 1.4.18) | artshishkin/…axon-microservices (**native Maven**) | Phase 2 (**pipeline-found**) | ✅ verified_bbc (real external **production** adaptation; Axon `XStreamConfig`, native Maven) |
| [xstream-spark](xstream-spark.json) | xstream | @1.4.18 (1.4.18 boundary) | igniterealtime/Spark (**native Maven**) | Phase 2 (**pipeline-found**) | 🟡 signature_confirmed (mature product, SPARK-2259; not standalone-verifiable — live-session coupling) |
| [poi-jadhavspeaks](poi-jadhavspeaks.json) | poi | 4.1.2 → 5.2.5 (5.0 byte-cap) | jadhavspeaks/file_compare_diffrent_ext | Phase 2 (**pipeline-found**) | 🟡 signature_confirmed (native-Maven Java; differential RAN, break didn't trip from .xlsx) |
| [poi-fmflatfile](poi-fmflatfile.json) | poi | @5.2.3 (5.0 byte-cap) | tpunder/fm-flatfile | Phase 2 (**pipeline-found**) | 🟡 signature_confirmed (real external **production** adaptation, Scala) |
| [poi-impactupgrade-nucleus-engine](poi-impactupgrade-nucleus-engine.json) | poi | 4.x → 5.x (major) | impactupgrade/nucleus-engine | Phase 2 | 🟡 signature_confirmed |
| [poi-kenzoknz-pdf-converter](poi-kenzoknz-pdf-converter.json) | poi | 4.x → 5.x (major) | kenzoknz/pdf-converter | Phase 2 | 🟡 signature_confirmed |
| [poi-usepa-data-gathering](poi-usepa-data-gathering.json) | poi | 4.x → 5.x (major) | USEPA/data_gathering | Phase 2 | 🟡 signature_confirmed |
| [poi-oboguev-rtss](poi-oboguev-rtss.json) | poi | 4.x → 5.x (major) | oboguev/RTSS | Phase 2 | 🟡 signature_confirmed |
