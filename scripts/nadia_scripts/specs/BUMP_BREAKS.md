# BUMP-confirmed behavioural breaks — study catalog

The set of behavioural breaking changes (BBCs) selected from **BUMP**
(chains-project/breaking-updates) for this study. Each row is a real BUMP
`TEST_FAILURE` reproduction, so the exact failing test + exception can be pulled
from BUMP and re-derived in our own differential.

Machine-readable version, with per-`to_version` breaking-commit SHAs:
[`bump_breaks_catalog.json`](bump_breaks_catalog.json).

SHAs were verified against `data/benchmark_test_failures/` on 2026-07-06; that data was
deleted on 2026-08-12, so the SHAs here are now the record rather than a derivation. All entries
`failureCategory=TEST_FAILURE`, reproduced on Java 11. Failing tests + signals
characterized from the repro logs on 2026-07-06 (see `characterization` in the JSON).

## The breaks

| Library | From → To | Boundary | Search boundary | Why it breaks behaviour | Client (BUMP project) |
|---|---|---|---|---|---|
| `org.mockito:mockito-core` | 4.11 → 5.1.1 / 5.2.0 / 5.3.1 / 5.4.0 | major | 4.x → 5.x | Default mock-maker switched to inline + stricter argument matching at 5.0; verification captures different args | junit-quickcheck + gax-java |
| `ch.qos.logback:logback-classic` | 1.2.11 → 1.4.0 / 1.4.1–1.4.6 | minor | 1.2.x → 1.4.x | Output/config behaviour change at the 1.4.0 Jakarta/Java-11 cutover | recheck.cli *(also html2pop3)* |
| `org.slf4j:slf4j-api` | 1.7.32 → 2.0.0 / 2.0.1–2.0.6 | major | 1.x → 2.x | Logging output / binding behaviour changed across the 1→2 rewrite | jasmine-maven-plugin *(also recheck)* |
| `org.apache.poi:poi-ooxml` | 4.1.2 → 5.2.0, 5.2.2 | major | 4.x → 5.x | POITextExtractor interface→class; IOUtils.toByteArray signature change at 5.0 → extraction returns null | fscrawler |
| `org.apache.poi:poi` | 4.1.2 → 5.0.0 | major | 4.x → 5.x | Same POI 5.0 change (POITextExtractor / IOUtils) | fscrawler |
| `org.apache.poi:poi-scratchpad` | 4.1.2 → 5.0.0 | major | 4.x → 5.x | Same POI 5.0 change (IOUtils.toByteArray) | fscrawler |
| `org.apache.httpcomponents:httpclient` | 4.5.1 → 4.5.13 | patch | within 4.5.x | Behavioural change within the 4.5.x patch line | sardine |
| `org.jsoup:jsoup` | 1.14.2 → 1.15.3 | minor | 1.14.x → 1.15.x | Parsing / output behaviour change at 1.15.0 (trailing whitespace) | sparql.anything |
| `com.thoughtworks.xstream:xstream` | 1.4.17 → 1.4.19 | patch | within 1.4.x | Security framework → default-deny: unregistered classes rejected on deserialization (ForbiddenClassException) | logging-chainsaw ✅ *verified* |

## Characterized failing tests (from repro logs)

| Break | Failing test(s) | Signal |
|---|---|---|
| mockito | `CompositeGeneratorTest#shrinkingChoosesAComponentCapableOfShrinkingTheValue` (junit-quickcheck); `OpencensusTracerTest#testLongRunningExample`, `OpencensusTracerFactoryTest#testImplicitParentSpan` (gax-java) | `AssertionError: expected:<[3, 6]> but was:<[]>` |
| logback | `SystemInUtilTest#should_repeatedly_ask_yes_or_no_when_input_is_invalid` (recheck.cli) | `AssertionError` — console/log output changed |
| slf4j | `JasmineResultLoggerTest#shouldLogDetails`, `#shouldLogHeader` (jasmine) | `AssertionError [Expected …]` — logged message format changed |
| poi-ooxml | `TikaDocParserTest#testExtractFromDocx`, `#testDocxWithEmbeddedBadPDF` (fscrawler) | **`ClassNotFoundException: org.apache.poi.poifs.crypt.agile.AgileEncryptionInfoBuilder`** |
| poi | `TikaDocParserTest#testExtractFromDocx / #testExtractFromDoc / #testDocxWithEmbeddedBadPDF` (fscrawler) | POI 5 extraction failure |
| poi-scratchpad | `TikaDocParserTest#testExtractFromDoc` (fscrawler) | POI 5 legacy `.doc` extraction failure |
| httpclient | `SardineExceptionTest#testMessage` (sardine) | `ComparisonFailure` — reason-phrase formatting changed |
| jsoup | `HTMLMicrodataTest#testMicrodata1`, `HTMLMicrodataRemoteTest#testMicrodata1` (sparql.anything) | `AssertionError` (assertIsomorphic on RDF triples) |
| xstream | `LogPanelPreferenceModelTest#testLogPanelPreferenceModelSerialization` (logging-chainsaw) | `ForbiddenClassException: LogPanelPreferenceModel` |

> **⚠️ POI correction:** the *actual* BUMP fscrawler failure is a
> `ClassNotFoundException` for `AgileEncryptionInfoBuilder` (POI 5 relocated/split its
> crypt classes) in `TikaDocParserTest`, **not** the `IOUtils.setByteArrayMaxOverride`
> byte-cap described in the "why it breaks" column. The byte-cap story is the
> *external adaptation signature* we mined in Phase 2 (the `verified_cases/poi-*`
> files) — a separate thread from this exact test's cause. Keep them distinct.

## How to use a row

1. Pick the client's `breaking_commit` for the wanted `to_version` from
   [`bump_breaks_catalog.json`](bump_breaks_catalog.json).
2. Read the failing test + assertion/exception from the entry's own `characterization`
   block. It used to be extracted from `reproductionLogs/successfulReproductionLogs/<sha>.log`
   by `bbc_pipeline.py characterize`; those logs were deleted 2026-08-12 and that script on
   2026-08-13. Restore from upstream chains-project/bump only if you need the raw log.
3. Write a per-break spec (see [`xstream-1.4.19-forbiddenclass.json`](xstream-1.4.19-forbiddenclass.json),
   [`jsoup-1.15-whitespace.json`](jsoup-1.15-whitespace.json)) capturing root cause,
   `affected_usage_regex`, and mimic.
4. Mine / verify (see `../verified_cases/README.md`).

## Status

- **xstream** — ✅ fully `verified_bbc` (see `../verified_cases/xstream-logging-chainsaw.json`).
- **poi** — 🟡 4 external adaptations `signature_confirmed` (differential pending).
- **jsoup** — spec written; pipeline found `novadata/adblock-parser` as an external candidate.
- **mockito, logback, slf4j, httpclient** — catalogued here, not yet characterized.
