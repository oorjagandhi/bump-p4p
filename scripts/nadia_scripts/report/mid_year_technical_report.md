# Mining Client Adaptations to Behavioural Breaking Changes in Java Dependencies

## 1. Introduction

Java projects rely heavily on third-party Maven dependencies. Updating these dependencies is
important for security and maintenance, but updates can also break client projects. Some breaks are
syntactic, where an API is removed or renamed and the client no longer compiles. This project
focuses on behavioural breaking changes.

A behavioural breaking change occurs when the client still compiles against the new dependency
version, but the dependency behaves differently at runtime. This may cause a previously passing test
to fail because the output changes, a new exception is thrown, configuration defaults change, or the
dependency becomes stricter about inputs. The aim of this project is to understand not only where
these breaks occur, but how client projects adapt their code, tests, or configuration in response.

The central research question is:

> What types of code-level adaptations do client projects make in response to semantic breaking
> changes in Java dependencies?

This report summarises the current mining approach, the main findings from BUMP, the XStream case
study, and the revised strategy for finding more adaptations.

## 2. BUMP Filtering Findings

**[Figure 1: `figures/fig1_funnel.png` — Filtering BUMP failures for behavioural-break candidates.]**

The first stage of the project used BUMP to identify dependency updates that may represent
behavioural breaking changes. BUMP contains 571 reproducible breaking-update benchmarks, but not all
of these are relevant to this work. Since the project focuses on behavioural rather than syntactic
breaks, the first step was to script a filter over the BUMP metadata and separate benchmarks by
their recorded failure category.

The script inspected the failure-category field for each benchmark and filtered the corpus into
three broad groups: compile errors, test failures, and other failures. As shown in Figure 1, the 571
BUMP benchmarks split into **235 compile errors**, **188 test failures**, and **148 other failures**
(the "other" group being enforcer, dependency-lock, werror, and dependency-resolution failures).
Compile errors were excluded from the main behavioural analysis because they indicate that the
client no longer compiles against the new dependency version. These are more likely to reflect
syntactic or API-level incompatibilities, such as removed methods, changed signatures, or missing
classes.

The key category for this project is the **188 test failures**. These are stronger behavioural-break
candidates because the client project still compiles, but the test suite fails at runtime. To
understand what kind of runtime failure each benchmark represented, a second script executed the
BUMP reproduction commands for the test-failure cases and inspected the resulting test output. This
allowed the cases to be separated into **158 runtime errors** and **30 assertion failures**.
Assertion failures are especially strong behavioural signals because the test ran to completion but
observed a different result from the expected one. Runtime errors can also indicate behavioural
change, where the new dependency version throws an exception in a situation that previously passed.

The 158 runtime-error cases were then further classified using the reproduced failure output. This
produced **34 syntactic** cases (`NoSuchMethodError`, `AbstractMethodError`, `InvalidClassException`),
**14 semantic** and **6 possible-semantic** cases, and **104 other/unclassified** cases — dominated
by 69 missing-class failures (`ClassNotFoundException` / `NoClassDefFoundError`), 21 binding/init
failures (SLF4J-style provider initialisation), and 11 JVM-version failures
(`UnsupportedClassVersionError`), plus a handful of miscellaneous cases. The semantic and
possible-semantic cases are the most relevant to this project because they indicate dependency
updates where the client code still compiles, but behaviour changes at runtime.

Overall, the BUMP analysis shows that behavioural breaking changes are a relatively small subset of
dependency-update failures — around 20 of the 188 test failures (~11%), or roughly eight distinct
breaks after de-duplication. Most failures are either compile errors or other infrastructure/runtime
issues. However, the scripted filtering and reproduction process identified a focused set of
assertion, semantic, and possible-semantic test failures that can be used as seeds for adaptation
mining.

## 3. The Main Limitation: BUMP Finds Breaks, Not Adaptations

The biggest issue we found with using BUMP is that most failed dependency-update pull requests were
never merged. This matters because the research target is the code-level adaptation that allows the
client to behave as expected with the new dependency behaviour. If a dependency-update PR failed CI
and was abandoned, then there may be no adaptation commit to mine.

To check this, our script checked whether the 188 TEST_FAILURE updates were merged into their
projects' default branches. Only **18 of the 188** were merged. Manual inspection showed that many
BUMP cases were automated dependency-update PRs, such as through Dependabot, that failed CI and were
closed or left unresolved.

This creates an important methodological limitation:

> BUMP is rich in dependency-update breaks, but sparse in client adaptations.

As a result, BUMP is best used as a seed source. It helps identify dependency updates that can cause
behavioural breaking changes, but the search for actual adaptations needs to expand beyond the
original BUMP repositories.

## 4. Behavioural Breaks Identified from BUMP

After filtering the BUMP test failures, we created a script to filter the 188 benchmarks labelled as
test failures down to a small set of dependency updates whose failure signatures appear behavioural
rather than syntactic. These include Mockito 4.x to 5.x, Logback 1.2.x to 1.4.x, SLF4J 1.x to 2.x,
Apache POI 4.x to 5.x, HttpClient 4.5.1 to 4.5.13, jsoup 1.14.x to 1.15.x, and XStream 1.4.17 to
1.4.19. The draft catalogue describes these as seven distinct breaks, with XStream being the
strongest and most fully worked case.

Not all of these are equally useful for adaptation mining. Mockito, for example, is usually
test-scoped, so adaptations often happen inside test files. Logging libraries can be difficult to
isolate because behaviour depends heavily on configuration and the test environment. The most
productive case so far has been XStream, because the break has a clear runtime signal and a
distinctive adaptation pattern.

## 5. Mining External Client Adaptations

Because BUMP rarely contains the fix, the pipeline treats each confirmed behavioural break as a query
seed and searches external GitHub repositories for other projects that crossed the same dependency
boundary and adapted to it. This pipeline is implemented in `mine/bbc_e2e.py`.

### Characterising the Break

The first stage characterises the behavioural break using the original BUMP failure. Rather than
relying only on the dependency version update, the pipeline extracts the specific failing test and
the runtime signal that defines the break. This signal may be an exception type, an assertion
message, or other test output showing how the dependency update changed behaviour.

For example, in the XStream case, the relevant signal is `ForbiddenClassException`. This exception
occurs when XStream's newer default-deny security model rejects deserialisation of a class that has
not been explicitly allow-listed. This signal is important because it is used both to search for
likely adaptation commits and later to confirm that a reproduced failure has the same shape as the
original behavioural break. It is the "load-bearing" signal for the later mining and
differential-verification stages.

### Mining Commit Messages

The second stage searches GitHub commit messages rather than source code. This is important because
code search often returns projects that simply use a relevant API, even if they never experienced the
breaking change. For example, searching for `allowTypesByWildcard` in code may find projects that
were always configured correctly. In contrast, commit messages are more likely to capture the moment
where a developer reacted to a failure, such as "Fix XStream security exception" or "resolve
ForbiddenClassException."

For each behavioural break, the query combines a library keyword with a set of break-specific terms.
In the XStream case, examples include `xstream ForbiddenClassException`, `xstream allowTypes`, and
`xstream allowTypesByWildcard`. Choosing these search terms is one of the judgement seams in the
pipeline, because the terms must be specific enough to avoid unrelated usage but broad enough to catch
different ways developers describe the same fix.

### Classifying Candidate Commits

Each mined commit is then classified to determine whether it is a plausible client adaptation. The
classifier inspects the changed files, identifies the build system, and reads the dependency version
at both the commit and its parent. This stage is designed to remove false positives that appeared
during early mining.

First, changed files are separated into production and test locations. Changes under `src/main` are
treated as production adaptations and provide the strongest evidence. Changes under `src/test`, or
files named like tests, are retained but flagged separately, because test-only adaptations can create
a circularity: the test is both the oracle used to detect the break and the artifact being changed to
fix it.

Second, the pipeline filters out library-source matches. Search terms for a library API can return
the library's own repository or forks of it. For example, searching for an Apache POI API may return
commits inside `apache/poi`, where the changed file defines the library API rather than adapting to it
as a client. These are rejected because they are not client adaptations.

Third, the pipeline reads dependency versions carefully from Maven POM files. This is not always
straightforward, because versions may be declared using Maven properties, inherited from parent POMs,
or scoped to different modules in a multi-module project. The version reader therefore resolves
property placeholders, checks the dependency block for the relevant artifact, and looks in the module
POM nearest to the changed source file before falling back to the root POM. If a version is managed by
a parent or BOM and cannot be read directly, the pipeline returns an unconfirmed result rather than
guessing. This prevents unsupported conclusions about whether a project crossed the behavioural
boundary.

Only Maven projects are treated as fully verifiable in the current pipeline, because the generated
differential harness is Maven-based. Gradle and other build systems may still be noted, but they are
not promoted to the strongest verification category.

The pipeline also keeps candidates focused rather than sprawling. A candidate commit is expected to
change at most eight files in total, exactly one `pom.xml` (whose diff is a single same-dependency
version bump), and between one and five `.java` files; a change touching more than five Java files is
almost always a broad refactor in which the adaptation cannot be isolated.

### Verifying Boundary Traversal

A candidate adaptation commit does not prove that the client actually experienced the behavioural
breaking change. A project may use `allowTypesByWildcard`, for example, without ever having upgraded
across the XStream security boundary. Therefore, the pipeline includes a boundary-traversal check.

This stage searches backwards through the relevant build-file history from the adaptation commit and
looks for a direct dependency version bump that crosses the behavioural boundary. For a break boundary
`b`, a project is considered to have crossed the boundary only if:

```
old version < b ≤ new version
```

This check is important because it distinguishes genuine adaptations from projects that merely use the
same API. It also handles transitive cases conservatively. If the project receives the dependency only
transitively and no direct version can be read, the case is not counted as a witnessed direct
adaptation. Instead, it is labelled separately as transitive or born on the new version. When a
crossing bump is found, the pipeline also checks that the bump precedes the fix and occurs within a
bounded commit window, so the result represents a plausible bump-to-fix sequence rather than unrelated
co-occurrence.

### Causal Confirmation with a Three-State Differential

The strongest candidates are then validated using a three-state differential test. This is the key
step for showing that the relationship is causal rather than incidental.

The idea is to run **one single test** — always the same test — three times, changing only two things
between runs: the dependency version, and whether the client code is the original ("before the fix")
or the adapted version ("after the fix"). The test itself never changes. It performs one realistic
operation on the client's own production code — for XStream, it builds one of the app's domain objects,
round-trips it through the client's real serialisation path, and asserts that a field survived the
round-trip. Whether that test **passes** or **fails** is what we read off in each state:

- **PASS** means the test method ran to completion and its assertion held — the operation behaved as it
  did before the library changed (the object serialised and came back intact, the value survived).
- **FAIL** means the test did *not* complete normally. For a behavioural break this is almost always a
  runtime *error*: the library threw the characterised exception (for XStream,
  `ForbiddenClassException`) part-way through the operation, so the assertion was never reached. The
  harness confirms a failure is the *right* failure by grepping the test output for the specific signal
  string, so an unrelated build or environment error is not mistaken for the break.

| State | Dependency version | Client code | What we run | Expected result |
|---|---|---|---|---|
| 1. baseline | old (e.g. 1.4.17) | original (parent commit) | the one test | **PASS** — the operation still works on the old library |
| 2. new lib, old code | new (e.g. 1.4.19) | original (parent commit) | the same test | **FAIL** — the new library throws the characterised signal on the unchanged code |
| 3. adapted | new (e.g. 1.4.19) | adapted (fix commit) | the same test | **PASS** — the client's real fix makes the operation work again |

Reading the three states together is what makes the result causal. State 1 establishes that the test
is a fair baseline: the operation genuinely worked before the update. State 2 is the crucial one — the
*only* thing changed from state 1 is the library version, and that alone is enough to break the test
with the exact signal, which proves the **update caused the failure**. State 3 changes the version
*and* swaps in the client's real adaptation, and the test passes again, which proves the **adaptation
is what fixes it**. A case is confirmed only if all three states behave exactly as in the table; if
state 2 fails to reproduce the signal, or state 3 does not recover, the case is downgraded rather than
counted.

The harness is generated in a way that keeps the build as close as possible to the original client
project. Where possible, it reuses the repository's own Maven POM and overrides only the dependency
version being tested. For multi-module projects, the harness builds the relevant module and its
dependencies. This avoids the need to manually reconstruct the client's dependency tree and reduces
the risk of introducing artificial build differences. In practice the runner checks out the parent
commit for states 1 and 2 (the "before the fix" code) and the adaptation commit for state 3 (the
"after the fix" code), toggling only the dependency version between runs, and then inspects the test
reports for the expected runtime signal.

### Generating the Test with Claude as an Agent

The one part of the differential that cannot be produced by deterministic rules is the **body of the
test** — deciding *which* production method to call and *how* to build a realistic input that actually
exercises the affected code path. This is a judgement task, so the pipeline delegates it to Claude
acting as an agent. In the codebase this is the stage labelled "SEAM A", and it is wired to the
Anthropic API (`agent/seams.py`, using the `claude-opus-4-8` model with extended thinking enabled).

Before Claude is called, the pipeline deterministically gathers the context the model needs and puts
it into a structured prompt:

- the **break description** — the library, the old and new versions, the boundary, and the exact
  runtime signal that state 2 must produce (e.g. `ForbiddenClassException`);
- the **adaptation diff** — the real change the client made in the fix commit;
- the **adapted production code** — the actual source of the method(s) the fix touched, so the model
  drives the client's real entry point rather than inventing one;
- the **detected test framework** — whether the module is on JUnit 4 or JUnit 5, since Spring Boot
  projects often pull in JUnit 5 transitively and a mismatch would fail to compile.

Claude is then asked to return a single compilable JUnit test class (`bbc.BbcTest`) that drives the
client's real production path. The prompt enforces the rules that make the test valid for the
differential: it must call the client's genuine production method rather than the library API in
isolation, and it must use **only APIs that exist in both the old and new versions**, so the same
unchanged test compiles and runs in all three states. Any version-specific configuration (such as the
allow-list call) is expected to live in the production code, never in the test — otherwise the test
could not compile against the baseline.

The agent is also given a **self-correction loop**, labelled "SEAM B". After generating the test, the
harness runs state 2 and checks whether the break actually tripped. If state 2 unexpectedly *passes* —
meaning the input was not severe enough to trigger the library's changed behaviour — the failing
output is fed back to Claude, which adjusts the test fixture (for example, constructing a more
representative object) and tries again, up to a small fixed number of attempts. If after those
attempts the break still cannot be made to trip in isolation, the model is expected to reply with an
explicit "give up" token, and the case is recorded as *signature-confirmed* (real, but not reducible
to a standalone test) rather than being forced or faked. This keeps the automation honest: Claude
supplies the judgement, but the deterministic three-state check is still the thing that decides whether
a case counts.

### Excluding Test-Scoped Libraries from Production Adaptation Mining

The current verification method is designed for production adaptations. This creates a structural
limitation for libraries that are themselves test dependencies, such as Mockito. In these cases, the
behavioural break and the adaptation usually occur inside the test files. That means the file used to
detect the break is also the file that must be changed to fix it. The oracle and the adaptation
collapse into the same artifact.

For this reason, test-scoped libraries can still be recorded as genuine behavioural breaks, but they
are set aside from the strongest production-adaptation mining pipeline. Their fixes are better
classified as test-level adaptations rather than production adaptations. This maintains a clear
distinction between client production-code changes and changes made only to the test oracle.

## 6. Case Study: XStream Security Tightening

### What broke, and what the adaptation is

The clearest case so far is XStream's move to a stricter deserialisation security model at version
1.4.18. XStream is a Java library that turns objects into XML/JSON and back (`toXML` / `fromXML`), and
it is the default serialiser inside the Axon framework, so many Spring-Boot/Axon apps use it without
ever naming it directly.

- **Before 1.4.18:** `fromXML` would rebuild *any* class.
- **From 1.4.18 onward:** `fromXML` only rebuilds classes that have been explicitly allow-listed.
  Everything else throws `com.thoughtworks.xstream.security.ForbiddenClassException`.

This is a behavioural breaking change, not a compile break. The client still compiles against the new
version, but the same runtime operation now fails — typically on the application's *own* domain types,
which were never registered because they never needed to be before.

Crucially, the adaptation is **not** a syntactic migration where the client replaces a removed API.
No method disappeared. Instead, the client must **add configuration to satisfy the dependency's
stricter runtime behaviour** — it allow-lists the types it deserialises. This is exactly the kind of
code-level adaptation the research question targets: a semantic break is resolved by *adding a
permission call*, not by rewriting a call site.

Two verified cases show the same adaptation in two concrete forms:

**(a) A direct call on the production XStream instance** — in `The-Ant-Forge/TVRenamer`, the
production class `UserPreferencesPersistence` deserialises the app's `UserPreferences` object. The fix
adds, on the shared XStream instance, an explicit allow-list of the app's own types:

```java
// XStream 1.4.18+ requires explicit security permissions
xstream.allowTypes(new Class[] { UserPreferences.class });
xstream.allowTypesByWildcard(new String[] { "org.tvrenamer.model.**" });
```

The maintainer's own comment attributes the change directly to the XStream security boundary, so this
is a reaction to the break rather than proactive hardening.

**(b) A new Spring configuration bean** — in the Axon apps (e.g. `einsteinarbert/axon-saga-example`),
the developer creates a new `@Configuration` that produces the XStream bean Axon will use and
allow-lists the application's domain package:

```java
xstream.allowTypesByWildcard(new String[] { "com.progressivecoder.ecommerce.**" });
```

In both forms the pattern is identical: the client explicitly re-permits its own package so that
XStream's default-deny model will rebuild those types. The adaptation is an added allow-list, applied
either inline on an existing XStream instance or inside a newly created configuration class.

### How the version transition reaches the client

The XStream mining run produced several adaptation patterns, and how the client *reached* the breaking
version turned out to be as interesting as the fix itself.

- **Direct bump and fix in the same commit** — `apache/logging-chainsaw` bumped 1.4.17 → 1.4.19 and
  added the allow-list together. Notably, its fix was applied only in the failing test, leaving the
  production usages unadapted, so it is a *partial* adaptation.
- **Direct bump, then a separate fix** — `The-Ant-Forge/TVRenamer` bumped XStream (1.4.9 → 1.4.20),
  crossing the boundary, and added the production allow-list 15 commits later in
  `UserPreferencesPersistence.java`. This is the clearest bump-then-adapt pair.
- **Transitive bump crossing the boundary** — an Axon microservices project never named XStream in any
  POM. It bumped the Axon Spring Boot starter, and the newer starter resolved a post-1.4.18 XStream, so
  the transitive dependency crossed the boundary within the repo's own history. The production fix
  added a custom `XStreamConfig` bean.
- **Born past the boundary (no bump commit)** — several Axon/CQRS apps pinned an Axon starter once at
  project creation that already resolved a post-1.4.18 XStream. There is therefore no bump commit
  anywhere in the repository; the break is latent from the first build, and the only XStream-related
  commit is the fix. For these, the differential recreates the version transition synthetically by
  adding one explicit XStream dependency, so 1.4.17 and 1.4.19 can be pinned and compared.

This is an important finding. The simple model of "dependency update causes tests to fail, then the
developer fixes it" does not cover all real cases. Behavioural breaks can arrive directly,
transitively, or before any relevant client code is written. In modern Spring/Axon applications the
boundary-crossing version often arrives transitively and before any code is written, so a large
fraction of real adaptations have no identifiable bump commit and must be reconstructed from the
dependency tree rather than read from a diff.

The `apache/logging-chainsaw` case is useful but must be classified carefully. The project updated
XStream from 1.4.17 to 1.4.19 and added an explicit `allowTypes` call. Manual validation showed that
the tests passed before the dependency update, failed after updating the dependency, and passed again
after adding the allow-list. This is strong evidence of a behavioural break and adaptation. However,
the adaptation occurs only in a test file, so it should be labelled as a test-level or partial
adaptation rather than a full production-code adaptation. In total, six XStream cases have been fully
confirmed by the three-state differential, with two further cases that are real but too deeply coupled
to isolate in a standalone test.

## 7. Strategy Pivot: Recent Major Releases of Top Maven Libraries

The BUMP-derived strategy revealed two limitations. First, the confirmed behavioural-break catalogue
is small. Second, most BUMP failures are abandoned dependency-update PRs, meaning they do not contain
adaptations. To build a larger dataset, the project has pivoted to a broader strategy: start from
recent major releases of widely used Maven libraries, then mine for projects that crossed those
boundaries and adapted.

The new strategy focuses on popular Maven libraries with relatively clear major version boundaries and
stable Maven coordinates. Candidate libraries include Mockito 5.0, SLF4J 2.0, SnakeYAML 2.0, Flyway
10.0, Jedis 5.0, MongoDB Driver 5.0, Protobuf 4.0, Kafka Clients 4.0, Caffeine 3.0, HikariCP 5.0, and
Apache POI 5.0. The aim is to find client projects that updated into these major releases and then
changed code, tests, or configuration in response. A deliberate selection rule is to use only
libraries whose Maven coordinates stay constant across the major boundary, so that a client's upgrade
is a single `<version>` change the traversal detector can see; libraries that also change coordinates
at their major boundary (for example Jackson 3, RxJava 2→3, HttpClient 4→5) are recorded for reference
only.

A related direction is to mine security-tightening changes. The strongest behavioural examples so far,
including XStream, involve libraries becoming stricter at runtime. These cases often have distinctive
adaptation APIs, such as allow-lists, parser limits, validator settings, or safer constructors. That
makes them easier to search for than generic dependency bumps.

## 8. Early Result: SnakeYAML Smoke Test

**[Figure 3: `figures/fig3_smoke_yield.png` — SnakeYAML smoke-run yield funnel: 385 → 25 → 10 → 0.]**

The first smoke test used the SnakeYAML 1.x to 2.0 boundary. Initial commit-message searches using
generic terms such as *bump*, *upgrade*, and *migrate* returned many commits (385 commits across 295
repositories), but most were naked dependency bumps. These commits changed only the dependency version
and did not include any client code or test adaptation.

After adding a filter requiring the candidate commit to touch `src/main` or `src/test`, the top-25
sample produced no real code adaptations (10 naked bumps were skipped, 0 adaptations found). This
negative result is useful because it shows that generic upgrade searches are good at finding
dependency bumps, but poor at finding adaptations. When a dependency update breaks tests, the actual
fix may occur in a later commit whose message does not mention the dependency name.

Therefore, the next version of the pipeline needs to move beyond generic upgrade mining. It should
combine dependency-boundary detection with a forward scan of later commits, and it should use
library-specific adaptation terms such as `LoaderOptions` for SnakeYAML or `allowTypes` for XStream.

## 9. Next Steps

The next step is to turn the pipeline from a bump finder into an adaptation finder. For each
boundary-crossing dependency update, the pipeline should scan the next set of commits on the same
branch for source, test, or configuration changes. This models the realistic workflow where a
dependency update breaks CI and the adaptation appears in a later commit.

The search should also use library-specific fix signatures instead of generic upgrade terms. For
example, XStream searches should focus on `ForbiddenClassException`, `allowTypes`, and
`allowTypesByWildcard`. SnakeYAML searches should focus on terms such as `SafeConstructor`,
`LoaderOptions`, and `allowDuplicateKeys`. These terms are more likely to find real adaptations than
broad words like "upgrade" or "bump".

Overall, the current findings show that BUMP is useful for identifying behavioural-break seeds, but
not sufficient for building a large adaptation dataset. The strongest evidence so far comes from the
XStream case, which demonstrates the target pattern clearly: the old version passes, the new version
fails, and the new version plus adaptation passes. The revised strategy will use top Maven major
releases, security-tightening boundaries, forward history traversal, and library-specific fix
signatures to find a broader set of client adaptations.
