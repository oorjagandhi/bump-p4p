# SEAM A — driver-test generation prompt

You are generating a JUnit test that reproduces a dependency's **behavioural breaking
change** by driving the CLIENT's real production path. It must slot into a 3-state
differential (baseline PASS → new-lib FAIL → adapted PASS).

## Inputs (filled by the orchestrator)
- BREAK: `{group:artifact}` `{from}`→`{to}`, boundary `{break_boundary}`
- SIGNAL: the exception/grep that state 2 must produce: `{signal}`
- BUMP failing test (for shape only, do NOT copy): `{characterization.failing_tests}`
- ADAPTATION DIFF: `{diff of adapt_sha}`
- ADAPTED PRODUCTION METHOD(S): `{production_files / the_call}`
- TEST FRAMEWORK ON CLASSPATH: `{junit4 | jupiter}` (detected from the repo's poms)

## FIRST: pick the test shape from the diff

Look at the ADAPTATION DIFF and decide which case you are in:

- **Shape A — pre-adaptation entry point EXISTS.** A production method that the test can call
  was already present at the parent and the diff only *modified* its body / added config to it
  (e.g. `ExcelParser.parse(...)` existed; the fix added `setByteArrayMaxOverride` inside it).
  The SAME test compiles and runs at both parent and adapted code.
  → Emit **one** `@Test` method `bbcCase()` driving that real method. The orchestrator supplies
  the differential by checking out parent vs adapted code and toggling the library version.

- **Shape B — BORN PAST THE BOUNDARY (no pre-adaptation entry point).** The adapted method
  itself was **added** in this diff (it appears as `+ public ... method()` in the ADAPTATION
  DIFF), so there is *no* callable pre-adaptation production method at the parent — the client
  was written after the break and adapts by adding explicit configuration (e.g. the fix ADDS
  `@Bean XStream xStream(){ ... allowTypesByWildcard(...) }`). A single method driving only the
  adapted, already-hardened path can NEVER fail, so it cannot produce state 2.
  → Emit **exactly two** `@Test` methods, both driving the SAME domain type:
    - `preAdaptation()` — reconstructs the library's **default pre-adaptation behaviour** using
      only API common to BOTH `{from}` and `{to}` (e.g. `new XStream()` — the default the
      framework used before the client added config). This is the method that TRIPS the break
      on `{to}` and produces the SIGNAL.
    - `adapted()` — calls the client's **real** production configured method (e.g.
      `new EventProcessingConfig().xStream()`). This passes on `{to}`.
    Differential mapping the harness will use:
    `preAdaptation@{from}` → PASS, `preAdaptation@{to}` → FAIL+SIGNAL, `adapted@{to}` → PASS.
    Use EXACTLY the method names `preAdaptation` and `adapted`.

## Hard rules (each learned from a real failure this session)
1. **Drive the client's REAL production method** for the adapted path (e.g.
   `new ExcelParser().parse(path)`, `new EventProcessingConfig().xStream()`), NOT a synthetic
   library call. The break must manifest through the app's own code.
2. **Use ONLY API present in BOTH `{from}` and `{to}`.** The adaptation-only API (e.g.
   `setByteArrayMaxOverride`, `allowTypesByWildcard`) lives in PRODUCTION code, never in the
   test — so the same test compiles at the baseline / against `{from}`.
3. **Match the test framework given in `TEST FRAMEWORK ON CLASSPATH` EXACTLY.** For
   `jupiter (JUnit5)` use `org.junit.jupiter.api.Test` + `org.junit.jupiter.api.Assertions.*`;
   for `junit4` use `org.junit.Test` + `org.junit.Assert.*`. A mismatch fails to compile or
   silently runs 0 tests. Do NOT override the given framework based on your own guess.
4. **Assert the pre-break outcome** (the value that survives / the object that loads), so the
   failing state's failure surfaces as the SIGNAL, and the passing states pass.
5. Class is `bbc.BbcTest` in `src/test/java/bbc/`. Deterministic inputs. One method for Shape A,
   exactly the two named methods for Shape B.
6. If a method needs a fixture (a document, a payload), BUILD it in the test using only common
   API — see SEAM B for how to size it so the break actually trips.

## Output
A single compilable `.java` file. No prose.
