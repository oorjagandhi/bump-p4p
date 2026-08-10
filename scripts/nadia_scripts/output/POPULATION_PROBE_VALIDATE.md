# Population probe — does anyone publicly commit the adaptation?

Every other screen measures the LIBRARY. This measures the POPULATION: are there public commits calling the escape-hatch API the boundary added? commons-net passed every library-side screen and still yielded zero, because **0 of 519** mined commits named its fix.

Search terms are derived, not hand-written: public members present in the boundary jar and absent from its predecessor — `api_removals` in reverse — ranked so opt-back-out verbs (`allow`, `trust`, `enable`, `set…`) come first.

**A negative screen.** High hits do not promise cases: they may be exploit demos (fastjson, Text4Shell) or people adopting the API rather than adapting to the break. It tells you where NOT to spend a day.

Tier `validate`, 3 identifiers per library. 8 with a population, 20 with none, 21 added no new API.

## Has a public population

| library | transition | total | best single identifier | hits |
|---|---|---:|---|---:|
| `software.amazon.awssdk:cloudfront` | 2.41.29 → 2.41.30 | 101 | `trustStore` | **49** |
| `org.apache.commons:commons-text` | 1.9 → 1.10.0 | 61 | `round` | **33** |
| `com.microsoft.commondatamodel:objectmodel` | 1.7.3 → 1.7.4 | 50 | `enable` | **50** |
| `org.eclipse.jetty:jetty-http` | 12.0.30 → 12.0.31 | 32 | `allows` | **32** |
| `commons-net:commons-net` | 3.8.0 → 3.9.0 | 3 | `setDataTimeout` | **3** |
| `io.netty:netty-handler` | 4.1.117.Final → 4.1.118.Final | 2 | `trustManager` | **2** |
| `org.apache.logging.log4j:log4j-core` | 2.3.1 → 2.3.2 | 1 | `newBuilder` | **1** |
| `com.googlecode.owasp-java-html-sanitizer:owasp-java-html-sanitizer` | 20200713.1 → 20211018.1 | 1 | `allowStyling` | **1** |

## No public population — do not mine

| library | transition | identifiers probed |
|---|---|---|
| `org.apache.polaris:polaris-core` | 1.4.0 → 1.4.1 | `parse`, `scheme`, `rawPath` |
| `org.apache.polaris:polaris-runtime-service` | 1.4.0 → 1.4.1 | `allowlist` |
| `org.apache.solr:solr-core` | 9.10.0 → 9.10.1 | `allowSlotBorrowing`, `allowPartialResults`, `allowOverseerPendingTasksToComplete` |
| `io.dropwizard:dropwizard-validation` | 1.3.20 → 1.3.21 | `addViolation`, `escapeExpressions`, `escapeMessageParameter` |
| `org.http4s:http4s-client_2.12` | 0.21.28 → 0.21.29 | `unsafeRetriable` |
| `de.tum.in.ase:artemis-java-test-sandbox` | 1.11.1 → 1.11.2 | `checkLink` |
| `io.ratpack:ratpack-core` | 1.7.4 → 1.7.5 | `trustManagerFactory`, `enableMetricsCollection` |
| `org.apache.avro:avro-compiler` | 1.12.0 → 1.12.1 | `setNullSafeAnnotationNotNull`, `setNullSafeAnnotationNullable`, `ignoredField` |
| `org.apache.santuario:xmlsec` | 2.1.3 → 2.1.4 | `newDocument` |
| `org.http4s:http4s-core_2.13` | 0.21.33 → 0.21.34 | `unsafeParse`, `unsafeDuration`, `unsafeFromLong` |
| `org.springframework:spring-context` | 6.2.6 → 6.2.7 | `enableAspectJWeaving` |
| `org.yamcs:yamcs-core` | 5.12.6 → 5.12.7 | `allowUnknownKeys`, `allowContainerlessCommands`, `enable` |
| `com.cedarpolicy:cedar-java` | 2.3.5 → 2.3.6 | `escape` |
| `com.google.protobuf:protobuf-java` | 3.21.6 → 3.21.7 | `mergeGroupField`, `mergeMessageField` |
| `com.graphhopper:graphhopper-web-bundle` | 3.0-pre5 → 3.2 | `resolveCustomModelFiles`, `loadLandmarkSplittingFeatureCollection` |
| `com.microsoft.sqlserver:mssql-jdbc` | 10.2.4.jre8 → 10.2.4.jre11 | `setShardingKey`, `setShardingKeyIfValid`, `endRequest` |
| `dev.sigstore:sigstore-java` | 1.1.0 → 1.2.0 | `withSignedData` |
| `org.apache.flink:flink-core` | 1.9.2 → 1.9.3 | `enableForceAvro`, `enableForceKryo`, `enableTimeToLive` |
| `org.apache.sling:org.apache.sling.jcr.base` | 3.1.10 → 3.1.12 | `allowLoginAdministrative` |
| `org.apache.tomcat.embed:tomcat-embed-core` | 11.0.14 → 11.0.15 | `setStrictSni`, `setSniHostName`, `setClientIdentifierFunction` |

Read the per-identifier hits, not the total. commons-net scores 3 in aggregate purely from an unrelated `setDataTimeout` cleanup, while its real escape hatch `setIpAddressFromPasvResponse` scores **0** — and commons-net did in fact yield nothing after a full day of mining.

## Added no new public API

No escape hatch was added, so there is no derived identifier to search. Not fatal — the adaptation may be a config change or a call the client deletes — but there is nothing for this screen to measure.

| library | transition |
|---|---|
| `org.jdbi:jdbi3-freemarker` | 3.52.1 → 3.53.0 |
| `org.apache.cxf:cxf-rt-transports-jms` | 3.6.7 → 3.6.8 |
| `org.openrefine:main` | 3.8.2 → 3.8.3 |
| `org.springframework:spring-beans` | 5.2.19.RELEASE → 5.2.20.RELEASE |
| `com.cronutils:cron-utils` | 9.1.5 → 9.1.6 |
| `io.spinnaker.echo:echo-pipelinetriggers` | 2026.0-23 → 2026.0.1 |
| `org.apache.wicket:wicket-util` | 10.0.0 → 10.1.0 |
| `ai.h2o:h2o-core` | 3.46.0.9 → 3.46.0.10 |
| `com.sap.scimono:scimono-server` | 0.0.18 → 0.0.19 |
| `com.vaadin:vaadin` | 14.13.0 → 14.13.1 |
| `com.vaadin:vaadin-upload-flow` | 14.13.0 → 14.13.1 |
| `fr.opensagres.xdocreport:fr.opensagres.xdocreport.template.freemarker` | 2.1.0 → 2.2.0 |
| `io.netty.incubator:netty-incubator-codec-bhttp` | 0.0.12.Final → 0.0.13.Final |
| `org.apache.camel:camel-neo4j` | 4.10.7 → 4.10.8 |
| `org.apache.cxf:cxf-rt-rs-security-jose` | 4.0.4 → 4.0.5 |
| `org.apache.kerby:ldap-backend` | 2.0.2 → 2.0.3 |
| `org.apache.rocketmq:rocketmq-namesrv` | 4.9.6 → 4.9.7 |
| `org.apache.thrift:libthrift` | 0.9.3 → 0.9.3-1 |
| `org.apache.xmlgraphics:batik-svgbrowser` | 1.13 → 1.14 |
| `org.apache.xmlgraphics:xmlgraphics-commons` | 2.4 → 2.6 |
| `org.boofcv:boofcv-core` | 0.43 → 0.43.1 |
