# xstream 1.4.18 — native-Maven production adaptation candidates

Found by `bbc_e2e.py run xstream-1.4.17-to-1.4.19-forbiddenclass` on 2026-07-07
(GitHub commit search: 113 commits across 107 repos → these are the native-Maven,
production (`src/main`) adaptations, marked `*` in the run output).

**Important:** 8 of the 12 rows are the SAME drools commit `ce38e409` (JBPM-7999)
mirrored across forks — so there are really **~5 distinct adaptations**. (The
`library_source` filter only strips *xstream* forks, so *drools* forks slip through.)

## Distinct adaptations

| Repo | Commit | Production file | Notes |
|---|---|---|---|
| igniterealtime/Spark | `aad38d68` (also merge `c26602bf`) | `core/.../status/CustomMessages.java` | **Mature product, SPARK-2259.** Recorded → `verified_cases/xstream-spark.json` (signature_confirmed; not standalone-verifiable — live XMPP session coupling) |
| artshishkin/art-kargopolov-cqrs-saga-axon-microservices | `b76d747f` | `core/.../config/XStreamConfig.java` | Axon + Spring config bean (framework-coupled) |
| einsteinarbert/axon-saga-example | `dddd794b` | `.../config/XStreamAutoConfiguration.java` | Axon example (framework-coupled) |
| amirsnw/chainrtrade-axon-CQRS-DDD | `d408d4ca` | `core/.../model/ProductRestModel.java` | Axon; "package migration" — possibly confounded |
| drools (kiegroup) | `ce38e409` (JBPM-7999) | `kie-ci/.../KieURLClassLoader.java`, `MavenClassLoaderResolver.java` | Real drools fix; appears 8× across forks (RicBatista, Shkr00007, gitgabrio, 1000853727, KangweiZhu, kiegroup/drools-archive, gridgentoo, …) |

## All 12 raw `*` rows (as printed)

```
* amirsnw/chainrtrade-axon-CQRS-DDD@d408d4ca   core/src/main/java/com/chaintrade/core/model/ProductRestModel.java
* igniterealtime/Spark@c26602bf                core/src/main/java/org/jivesoftware/spark/ui/status/CustomMessages.java
* igniterealtime/Spark@aad38d68                core/src/main/java/org/jivesoftware/spark/ui/status/CustomMessages.java
* einsteinarbert/axon-saga-example@dddd794b    order-service/.../config/XStreamAutoConfiguration.java
* RicBatista/drools@ce38e409                   kie-ci/src/main/java/org/kie/scanner/KieURLClassLoader.java
* artshishkin/art-kargopolov-cqrs-saga-axon-microservices@b76d747f  core/.../config/XStreamConfig.java
* Shkr00007/drool-bpm@ce38e409                 kie-ci/.../KieURLClassLoader.java   (drools fork)
* gitgabrio/efesto-langchain4j-poc@ce38e409    kie-ci/.../KieURLClassLoader.java   (drools fork)
* 1000853727/drools@ce38e409                   kie-ci/.../KieURLClassLoader.java   (drools fork)
* KangweiZhu/incubator-kie-drools@ce38e409     kie-ci/.../KieURLClassLoader.java   (drools fork)
* kiegroup/drools-archive@ce38e409             kie-ci/.../KieURLClassLoader.java   (drools fork)
* gridgentoo/drools@ce38e409                   kie-ci/.../KieURLClassLoader.java   (drools fork)
```

## Non-Maven / demoted (also found, not verifiable under Maven-only scope)
- `bonitasoft/bonita-engine` (gradle) — `HttpAPIServletCall.java`
- several `apache/poi` etc. flagged LIB-SOURCE (the xstream *forks* were filtered; these were from the earlier POI run)
