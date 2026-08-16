# Limit-tier candidate ranking (PARTIAL)

`rank_candidates.py --tier limit --limit 120 --since 2022`, stopped after **41 of ~120** probed.
**28 mineable, 13 rejected.** Resume with the same command (BBC_RESUME is on by default).

## Read this before mining anything from the list

The ranker automates screening rules 1 (no public API removed, via javap) and 3 (boundary
recency). It CANNOT see rule 2 -- is the restriction on by default -- which needs a sources-jar
diff, and it has no idea whether any client ever adapted. Both fastjson and snakeyaml-maxaliases
passed the automated screens and died on grounds the ranker could not see. Treat this as a
shortlist to hand-screen, never a queue to mine.

**A REJECT is about the TRANSITION, not the library.** The advisory feed names one fix version
per advisory, and that is not always the behavioural boundary. snakeyaml is rejected here at
1.30 -> 1.31 (one signature removed), while the transition that produced FOUR verified cases is
1.31 -> 1.32, which this advisory never points at. Relying on the ranker alone would have
discarded snakeyaml entirely. Both snakeyaml-codepointlimit and org-json had their boundaries
pinned EMPIRICALLY, against the advisory's stated version, for exactly this reason.

## Mineable

| score | released | package | transition |
|---:|---|---|---|
| 13 | ? | `org.http4k:http4k-format-xml` | 6.49.0.0 -> 6.50.0.0 |
| 13 | ? | `tools.jackson.core:jackson-core` | 3.1.0 -> 3.1.1 |
| 12 | ? | `org.assertj:assertj-core` | 3.27.6 -> 3.27.7 |
| 11 | 2025-03 | `io.github.robothy:local-s3-rest` | 1.20 -> 1.21 |
| 11 | ? | `io.netty:netty-codec-dns` | 4.2.12.Final -> 4.2.13.Final |
| 11 | ? | `io.netty:netty-codec-redis` | 4.2.14.Final -> 4.2.15.Final |
| 11 | 2024-11 | `io.netty:netty-common` | 4.1.114.Final -> 4.1.115.Final |
| 11 | ? | `io.openremote:openremote-manager` | 1.21.0 -> 1.22.0 |
| 11 | 2023-08 | `org.apache.ivy:ivy` | 2.5.1 -> 2.5.2 |
| 11 | ? | `org.msgpack:msgpack-core` | 0.9.10 -> 0.9.11 |
| 11 | ? | `org.postgresql:postgresql` | 42.7.10 -> 42.7.11 |
| 10 | ? | `io.micronaut:micronaut-context` | 4.10.21 -> 4.10.22 |
| 10 | ? | `io.netty:netty-codec-compression` | 4.2.12.Final -> 4.2.13.Final |
| 10 | ? | `io.netty:netty-codec-http2` | 4.2.14.Final -> 4.2.15.Final |
| 10 | ? | `io.netty:netty-codec-stomp` | 4.2.15.Final -> 4.2.16.Final |
| 10 | ? | `io.openremote:openremote-agent` | 1.24.1 -> 1.24.2 |
| 10 | 2025-06 | `io.qameta.allure.plugins:xunit-xml-plugin` | 2.34.0 -> 2.34.1 |
| 10 | 2022-08 | `io.undertow:undertow-core` | 2.2.18.Final -> 2.2.19.Final |
| 10 | 2026-04 | `org.apache.opennlp:opennlp-tools` | 2.5.8 -> 2.5.9 |
| 10 | 2022-02 | `org.apache.poi:poi-scratchpad` | 5.2.0 -> 5.2.1 |
| 10 | 2024-06 | `org.cyclonedx:cyclonedx-core-java` | 9.0.3 -> 9.0.4 |
| 10 | 2023-08 | `org.eclipse.leshan:leshan-core` | 1.4.2 -> 1.5.0 |
| 10 | 2022-09 | `org.eclipse.milo:sdk-server` | 0.6.7 -> 0.6.8 |
| 10 | 2023-02 | `org.neo4j.procedure:apoc` | 4.4.0.13 -> 4.4.0.14 |
| 9 | ? | `ca.uhn.hapi.fhir:org.hl7.fhir.utilities` | 6.9.9 -> 6.9.10 |
| 9 | 2025-06 | `com.powsybl:powsybl-commons` | 6.7.1 -> 6.7.2 |
| 9 | 2023-09 | `commons-io:commons-io` | 2.13.0 -> 2.14.0 |
| 9 | 2024-09 | `de.gematik.refv.commons:commons` | 2.5.0 -> 2.5.1 |

`released: ?` generally means a very recent release. That is a REJECTION reason, not a neutral
one: a boundary shipped weeks ago has no clients who have crossed it yet. Recency cuts both ways.

## Rejected (compile break on this transition)

| package | signatures removed | advisory |
|---|---:|---|
| `com.arcadedb:arcadedb-engine` | 1 | ArcadeDB: IMPORT DATABASE allows SSRF and arbitrary local file read by authentic |
| `com.typesafe.play:play_2.13` | 3 | Denial of service binding form from JSON in Play Framework |
| `com.amazon.ion:ion-java` | 1 | Ion Java StackOverflow vulnerability |
| `com.datadoghq:dd-java-agent` | 9 | dd-trace-java: Improper parsing of W3C baggage headers may lead to DoS |
| `commons-fileupload:commons-fileupload` | 1 | Apache Commons FileUpload denial of service vulnerability |
| `io.opentelemetry:opentelemetry-api` | 0 | OpenTelemetry Java SDK has Unbounded Memory Allocation in W3C Baggage Propagatio |
| `org.apache.tomcat:tomcat-coyote` | 2 | HTTP/2 Stream Cancellation Attack |
| `org.eclipse.jetty.ee10:jetty-ee10-servlets` | 0 | Eclipse Jetty has a denial of service vulnerability on DosFilter |
| `org.neo4j.procedure:apoc-core` | 1 | XML External Entity (XXE) vulnerability in apoc.import.graphml |
| `org.yaml:snakeyaml` | 1 | Uncontrolled Resource Consumption in snakeyaml |
| `com.drewnoakes:metadata-extractor` | 13 | Allocation of Resources Without Limits or Throttling in metadata-extractor |
| `com.rabbitmq:amqp-client` | 1 | RabbitMQ Java client's Lack of Message Size Limitation leads to Remote DoS Attac |
| `io.github.bonigarcia:webdrivermanager` | 2 | BoniGarcia WebDriverManager Affected By Improper Restriction of XML External Ent |
