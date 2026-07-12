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

## Hard rules (each learned from a real failure this session)
1. **Drive the client's REAL production method** (e.g. `new ExcelParser().parse(path)`,
   `new XStreamConfig().xStream()`, `EventProcessingConfig.xStream()`), NOT a synthetic
   library call. The break must manifest through the app's own code.
2. **Use ONLY API present in BOTH `{from}` and `{to}`.** The adaptation-only API (e.g.
   `setByteArrayMaxOverride`, `allowTypes`) lives in PRODUCTION code, never in the test —
   so the same test compiles at the baseline.
3. **Match the test framework actually on the classpath.** JUnit4 (`org.junit.Test`) vs
   JUnit5 (`org.junit.jupiter.api.Test`). A mismatch silently runs 0 tests (surefire on the
   JUnit Platform won't discover a JUnit4 test without the vintage engine).
4. **Assert the pre-break outcome** (the value that survives / the object that loads), so
   state 2's failure surfaces as the SIGNAL, and states 1 & 3 pass.
5. Keep it one test method, `bbc.BbcTest` in `src/test/java/bbc/`. Deterministic inputs.
6. If the adapted method needs a fixture (a document, a payload), BUILD it in the test using
   only common API — see SEAM B for how to size it so the break actually trips.

## Output
A single compilable `.java` file. No prose.
