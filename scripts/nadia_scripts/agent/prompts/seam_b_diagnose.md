# SEAM B — non-trip diagnosis prompt

State 2 (new library + pre-adaptation code) was expected to FAIL with the break's signal,
but it PASSED. The break did not trip. Diagnose WHY and return an adjusted **fixture** (not
an adjusted assertion — never weaken the assertion to force a result).

## Inputs
- SIGNAL wanted on state 2: `{signal}` (e.g. `RecordFormatException ... maximum length`)
- Current test source + the fixture it builds
- State 2 surefire output (it passed)
- Attempt `{n}` of `{max_retries}`

## Diagnosis checklist (encoded from real non-trips)
1. **Input too small / under a cap.** Limits have thresholds (POI byte-cap = 100,000,000
   bytes uncompressed). Size the fixture ABOVE the default but BELOW the production override
   (e.g. between 100MB and the 200MB override) so state 2 fails and state 3 passes.
2. **Dedup / normalization collapses the fixture.** Identical values get de-duplicated
   (XSSF shared strings → one entry). Use DISTINCT values so the fixture keeps its size.
3. **A DIFFERENT guard trips first.** Highly-compressible content hits POI's zip-bomb guard
   (`MIN_INFLATE_RATIO`, "Zip bomb detected") BEFORE the byte cap. Use INCOMPRESSIBLE
   (random) content so the target guard is the one that fires.
4. **A streaming path avoids the allocation.** Some readers stream instead of buffering the
   whole part; route through the path that buffers it into a single `byte[]` (e.g. read from
   an `InputStream` so the zip entry is materialized).
5. **Wrong version actually resolved.** Confirm the `-D` override changed the resolved
   version (transitive pins can ignore a property unless an explicit depth-1 dep exists).
6. **Environment coupling, not a fixture problem.** If reaching the break needs a live
   session / framework bootstrap (class-load NPE before the lib call), this is NOT fixable
   here — signal `GIVE_UP: coupling` so the orchestrator records `signature_confirmed`.

## Output
Either an adjusted `.java` fixture (compilable, same rules as SEAM A), or the literal token
`GIVE_UP: <reason>` if the break is not standalone-reproducible.
