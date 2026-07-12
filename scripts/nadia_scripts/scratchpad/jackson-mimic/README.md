# Jackson PTV mimic — verification harness

Reproduces `verified_cases/jackson-ptv-mimic.json` — an **authored mimic** of Jackson's
default-typing **default-deny** (`PolymorphicTypeValidator`), the Jackson analogue of the
xstream 1.4.18 `ForbiddenClassException` break.

## Result (verified 2026-07-08, Maven / JDK 17, jackson-databind 2.17.2)

| State | Production mapper (PaymentStore) | Result |
|---|---|---|
| 1 | `permissiveMapper()` — LaissezFaire default typing | **PASS** |
| 2 | `securedUnadaptedMapper()` — restrictive PTV, app pkg NOT allowlisted | **FAIL** — `InvalidTypeIdException` (PTV denied) |
| 3 | `adaptedMapper()` — restrictive PTV, app pkg allowlisted | **PASS** |

## Run

```bash
export JAVA_HOME=<jdk-17>
mvn test                                                   # all 3 states
mvn test -Dtest=PaymentStoreBbcTest#state2_secured_unadapted_breaks   # the break
```

## Why an authored mimic (not an external repo)

Jackson's default-typing security is **opt-in**, so it is NOT a clean silent behavioural
break like xstream:

- `enableDefaultTyping()` was deprecated in 2.10 and **removed in 2.12** → migrating to
  `activateDefaultTyping(PolymorphicTypeValidator)` is a **compile** break. The deny only
  appears once you adopt a restrictive PTV.
- A pure library-**version** differential with identical code therefore can't show it
  (old code won't compile on the new version). This mimic instead varies the **security
  posture** the upgrade forces you to choose: permissive → restrictive → allowlisted.

Every real external Jackson PTV adaptation found in mining was either **framework-coupled**
(Spring Security session serialization — `madgeek-arc/resource-catalogue`, Jackson 3 /
Spring Boot 4) or a **data-driven** allowlist-widening (`omprakash201194/kin-keeper`), so
none gave a clean standalone version-driven differential. Bump commits themselves ARE
visible for Jackson (e.g. `apache/spark@8eb8f747`, pom `2.9.10 → 2.10.0`), unlike the
transitive xstream/Axon cases.

## Files

- `src/main/java/mimic/PaymentStore.java` — the three mapper factories (state 3 = the adaptation)
- `src/main/java/mimic/Account.java`, `Balance.java` — domain types (polymorphic holder)
- `src/test/java/mimic/PaymentStoreBbcTest.java` — the 3-state differential
