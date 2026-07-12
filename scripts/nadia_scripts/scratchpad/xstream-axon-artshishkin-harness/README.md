# xstream Axon BBC — verification harness (artshishkin)

Reproduces `verified_cases/xstream-axon-artshishkin.json` — a **native-Maven** external
production adaptation to the xstream 1.4.18 default-deny break, verified on a real
Axon/Spring-Boot project.

## Result (verified 2026-07-07, Maven / JDK 11)

| State | Config | Result |
|---|---|---|
| 1 | plain `new XStream()` + xstream **1.4.17** | **PASS** |
| 2 | plain `new XStream()` + xstream **1.4.19** | **FAIL** — `ForbiddenClassException: …core.model.ProductIdDto` |
| 3 | `new XStreamConfig().xStream()` + xstream **1.4.19** | **PASS** |

## Reproduce

```bash
git clone https://github.com/artshishkin/art-kargopolov-cqrs-saga-axon-microservices.git
cd art-kargopolov-cqrs-saga-axon-microservices
git checkout b76d747f8d278fbee27e6e4b82355f5e660bf5f8   # the fix commit (XStreamConfig)
mkdir -p core/src/test/java/bbc && cp <here>/XstreamBbcTest.java core/src/test/java/bbc/
```

Then apply the two `core/pom.xml` edits below and run:

```bash
export JAVA_HOME=<jdk-11>
RPT=core/target/surefire-reports/bbc.XstreamBbcTest.txt
mvn clean test -pl core -Dtest=bbc.XstreamBbcTest#plainXStream      -Dbbc.xstream.version=1.4.17   # PASS
mvn clean test -pl core -Dtest=bbc.XstreamBbcTest#plainXStream      -Dbbc.xstream.version=1.4.19   # FAIL (ForbiddenClassException)
mvn clean test -pl core -Dtest=bbc.XstreamBbcTest#configuredXStream -Dbbc.xstream.version=1.4.19   # PASS
```

## Two required `core/pom.xml` edits (harness scaffolding, not app changes)

1. **Explicit xstream dependency** — Axon pins xstream 1.4.19 transitively, so a
   property/`-D` override alone does NOT change the resolved version. Adding a
   direct (depth-1) dependency makes the baseline override actually apply:
   ```xml
   <properties><bbc.xstream.version>1.4.19</bbc.xstream.version></properties>
   ...
   <dependency>
     <groupId>com.thoughtworks.xstream</groupId>
     <artifactId>xstream</artifactId>
     <version>${bbc.xstream.version}</version>
   </dependency>
   ```
2. **JUnit vintage engine** — the project runs on the JUnit 5 platform, so a JUnit 4
   test needs the vintage engine to be executed:
   ```xml
   <dependency>
     <groupId>org.junit.vintage</groupId><artifactId>junit-vintage-engine</artifactId>
     <version>5.9.3</version><scope>test</scope>
   </dependency>
   ```

## Design note (transparency)

`XStreamConfig` was **created** in the fix commit, so it doesn't exist at the parent.
The differential therefore contrasts a plain `new XStream()` (a faithful stand-in for
Axon's pre-adaptation default) against the production `XStreamConfig`, both present at
the adapted commit, swapping only the xstream version. This keeps the library version /
the adaptation as the only variables — exactly what the 3-state model requires.
