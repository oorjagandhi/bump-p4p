# XStream 1.4.18 break — plain-English summary

This file explains, simply, the whole XStream case: what the break is, how we
verified real-world adaptations to it, and what we found.

---

## 1. What broke (the library change)

XStream is a Java library that turns objects into XML/JSON and back
(`toXML` / `fromXML`). It is the **default serializer inside Axon Framework**, so
many Spring-Boot/Axon apps use it without ever naming it.

In **version 1.4.18**, XStream flipped its security model to **default-deny**:

- **Before 1.4.18:** `fromXML` would happily rebuild *any* class.
- **From 1.4.18 on:** `fromXML` only rebuilds classes you have explicitly
  **allow-listed**. Everything else throws
  `com.thoughtworks.xstream.security.ForbiddenClassException`.

This is a **behavioural** break, not a compile break. The code still compiles
against the new version — it just throws at **runtime** when it deserializes a
class that isn't on the allowlist (typically the app's *own* domain types).

**The fix apps make:** allow-list their own packages, e.g.
`xStream.allowTypesByWildcard(new String[]{ "com.myapp.**" });`

---

## 2. How we verified each case (the 3-state differential)

For a case to count as a **confirmed** break-and-adaptation, we build and run one
tiny round-trip test in **three states**, changing only the library version and/or
the fix:

| State | Library version | Code | Expected |
|---|---|---|---|
| 1. baseline | **1.4.17** (old) | plain XStream, no allowlist | **PASS** |
| 2. new lib, old code | **1.4.19** (new) | plain XStream, no allowlist | **FAIL** — `ForbiddenClassException` |
| 3. adapted | **1.4.19** (new) | the app's real allowlist fix | **PASS** |

If all three behave as above, the break is real *and* the app's fix is what
resolves it. The test itself is always the same shape: **make a domain object →
round-trip it through XStream → assert a field survived.**

---

## 3. The surprising part: there is usually no "bump commit"

In the Axon apps, **nobody ever upgraded XStream on purpose.** XStream is pulled
in **transitively** by `axon-spring-boot-starter`, which was pinned once when the
project was created. Maven quietly resolves that to a **post-1.4.18** version.

So the app runs on the "broken" version from day one — there is **no commit that
bumps XStream**. The only XStream-related commit in the repo is the **fix**. The
developer just hit the runtime `ForbiddenClassException` and added an allowlist.

Because the version change is implicit in the dependency tree (not a diff), our
harness **recreates the transition synthetically** — it adds one explicit XStream
dependency so we can pin 1.4.17 vs 1.4.19 and isolate exactly two variables: the
library version and the fix.

(Each case file has a `bump_provenance` block documenting this. One case,
`artshishkin`, later made the dependency explicit — but pinned it to the *same*
version it already had, so still not a real bump.)

---

## 4. What we did in this run

We took the 12 "verifiable production" XStream candidates from
`output/xstream-1.4.17-to-1.4.19-forbiddenclass_candidates.jsonl`, de-duplicated
them (several were the same commit mirrored across forks), and worked the ones
not already verified.

**Two new confirmed cases** (both native-Maven Axon/CQRS apps, same mechanism):

- **amirsnw/chainrtrade-axon-CQRS-DDD** (`d408d4ca`) — broke on `ProductRestModel`,
  fixed by an `@Bean XStream` allow-listing `com.chaintrade.core.**`. JDK 17.
- **einsteinarbert/axon-saga-example** (`dddd794b`) — broke on `CreateOrderCommand`,
  fixed by `XStreamAutoConfiguration` allow-listing
  `com.progressivecoder.ecommerce.**`. JDK 11.

**One assessed but not differential-verifiable:**

- **drools JBPM-7999** (`ce38e409`, the same commit mirrored across 7 forks =
  one real case) — the fix is **not** an allowlist; it's a **classloader** change
  deep inside the KIE build framework. Reproducing it needs the whole KIE
  build+marshalling stack, so it can't be isolated in a small test. Marked
  `signature_confirmed` (real and upgrade-triggered, but not standalone-verifiable).

---

## 5. All XStream cases so far

| Case | App | How it was verified | Status |
|---|---|---|---|
| xstream-logging-chainsaw | apache/logging-chainsaw | 3-state (fix was test-only) | ✅ verified |
| xstream-mimic-production | authored mimic | 3-state (production fix) | ✅ verified |
| xstream-tvrenamer | The-Ant-Forge/TVRenamer | 3-state (Gradle via Maven harness) | ✅ verified |
| xstream-axon-artshishkin | artshishkin/…axon-microservices | 3-state (native Maven, JDK 11) | ✅ verified |
| **xstream-chaintrade-amirsnw** | **amirsnw/chainrtrade-axon-CQRS-DDD** | **3-state (native Maven, JDK 17)** | ✅ **verified (new)** |
| **xstream-axon-saga-einsteinarbert** | **einsteinarbert/axon-saga-example** | **3-state (native Maven, JDK 11)** | ✅ **verified (new)** |
| xstream-spark | igniterealtime/Spark | live-session coupling — can't isolate | 🟡 signature only |
| drools JBPM-7999 | kiegroup/drools (×7 forks) | classloader fix, framework-coupled | 🟡 signature only |

**Bottom line:** 6 XStream cases fully confirmed by the 3-state differential
(2 new this run), plus 2 that are real but too deeply coupled to isolate. Every
confirmed case shows the same story: a post-1.4.18 XStream arriving **transitively**
(no bump commit), breaking the app's own types at runtime, and fixed with an
allowlist.
