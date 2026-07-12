# TVRenamer xstream BBC — verification harness

Reproduces the **real** `The-Ant-Forge/TVRenamer` xstream 1.4.18 default-deny break
and its **production** adaptation, via a 3-state differential over the repo's
untouched production source. This is what promoted `verified_cases/xstream-tvrenamer.json`
from `signature_confirmed` to `verified_bbc`.

## What's here

| File | Role |
|---|---|
| `pom.xml` | Maven harness (the repo ships a Gradle 8 + SWT + launch4j build and no wrapper; Gradle isn't installed here). Compiles the real `src/main/java`, parameterises the xstream version, and runs only the authored test. |
| `PreferencesBbcTest.java` | Authored test (not in the repo), derived from the BUMP failing test `LogPanelPreferenceModelTest#testLogPanelPreferenceModelSerialization`. Calls the **production** `UserPreferencesPersistence.retrieve()` on a realistic preferences XML. |
| `run_differential.sh` | Clones the repo, applies the two files, runs the 3 states. |

## Result (verified 2026-07-06, Maven 3.9.11 / JDK 17)

| State | Config | Result |
|---|---|---|
| 1 | parent `16803ddb` + xstream **1.4.17** | **PASS** |
| 2 | parent `16803ddb` + xstream **1.4.20** | **FAIL** — `ForbiddenClassException: org.tvrenamer.model.UserPreferences` |
| 3 | adapted `b236f68e` + xstream **1.4.20** | **PASS** |

Baseline passes, the same code breaks only under the new library, and the
client's production `allowTypes` adaptation resolves it → confirmed BBC.

## Two things that made this non-trivial (documented so they aren't rediscovered)

1. **Java 17 module access.** XStream's reflection needs `--add-opens` for
   `java.base/{util,lang,lang.reflect,text,io}` and `java.desktop/java.beans`
   (see `pom.xml` `argLine`). Without them the JPMS blocks access *before* the
   xstream security check runs, masking the real break.
2. **PropertyChangeSupport confound.** `UserPreferences` holds a non-transient
   `java.beans.PropertyChangeSupport pcs`. Serializing a live instance drags that
   type into the graph, where it fails under *both* xstream versions (JDK-serialization
   fragility at 1.4.17, a *second* ForbiddenClass at 1.4.20 — TVRenamer's fix
   allowlists the domain types but not `PropertyChangeSupport`). To isolate the
   target break cleanly, the test deserializes a realistic preferences XML with no
   `<pcs>` element (XStream bypasses the constructor, so `pcs` stays null).
3. **`mvn clean` is mandatory** between states — incremental compilation skips the
   recompile after a `git checkout` and silently reuses the prior state's classes.

## Run it

```bash
bash run_differential.sh
```
