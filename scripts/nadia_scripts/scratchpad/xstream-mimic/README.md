# xstream-mimic — production-shaped reproduction of the xstream 1.4.18 break

A self-contained Maven project that reproduces the BUMP xstream behavioural break
**with the adaptation in production code**, addressing the weakness of the real
`apache/logging-chainsaw` case (whose fix was test-only).

## Provenance

- **Break:** xstream 1.4.18 switched to a default-deny security model — `fromXML`
  on a non-allowlisted class throws `com.thoughtworks.xstream.security.ForbiddenClassException`.
- **BUMP anchor:** `apache/logging-chainsaw`, breaking commit
  `19e20b0d69cb6dadbc54313cb6c6e5f70670ac93`, failing test
  `LogPanelPreferenceModelTest#testLogPanelPreferenceModelSerialization`
  (`data/benchmark_test_failures/19e20b0d….json`).
- The test here (`PreferenceStoreTest`) is **derived from that failing test**:
  same shape (mutate a model, round-trip through XStream, assert properties).

## Why this is better than the chainsaw case

In chainsaw the maintainer added `allowTypes(...)` **only inside the failing
test**; ~10 production XStream usages were left unadapted (the project later
dropped xstream). Here the adaptation lives in the **production** class
`mimic/PreferenceStore.java` (`newXStream()` → `stream.allowTypes(...)`), and the
test contains no XStream security config at all. A green test therefore means
production code was adapted.

## Layout

| File | Role |
|---|---|
| `src/main/java/mimic/PreferenceModel.java` | Domain POJO (stand-in for `LogPanelPreferenceModel`) — production |
| `src/main/java/mimic/PreferenceStore.java` | XStream save/load + **the adaptation** — production |
| `src/test/java/mimic/PreferenceStoreTest.java` | Round-trip test derived from the BUMP failing test |

## Run the 3-state differential

```bash
bash run_differential.sh
```

Expected (verified 2026-07-06, Maven 3.9.11 / JDK 11):

| State | Config | Result |
|---|---|---|
| 1 | `1.4.17`, prod not adapted | **PASS** |
| 2 | `1.4.19`, prod not adapted | **FAIL** — `ForbiddenClassException: mimic.PreferenceModel` |
| 3 | `1.4.19`, prod adapted (`-Dmimic.adapt=true`) | **PASS** |

The adaptation is gated on `-Dmimic.adapt` only so one build can show both the
pre- and post-adaptation states; in a real client the `allowTypes(...)` call is
simply present.
