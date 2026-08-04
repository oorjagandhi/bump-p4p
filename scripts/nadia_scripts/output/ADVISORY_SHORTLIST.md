# External break candidates — mined from Maven security advisories

Source: OSV Maven feed. Scanned 6815 advisories; 932 distinct (package, fixed-version) candidates whose fix is a stricter-parsing / validation / deserialization tightening (the xstream/json-smart shape).

`break_boundary` = the FIXED (patched) version — where the stricter behaviour lands. Baseline to reproduce the old lenient behaviour = any version below it.

`tier` = adaptation-API class: **deserialize** (allowlist/validator API — cleanest, xstream shape) > **limit** (depth/size/XXE config — json-smart shape) > **validate** (generic — often no distinctive client API). Applications/products filtered out.

| # | tier | score | package | boundary (fixed) | CWE | GHSA / CVE | summary |
|---|---|---|---|---|---|---|---|
| 1 | deserialize | 18 | `com.aerospike:aerospike-client` | 6.2.0 | CWE-502 | CVE-2023-36480 | Aerospike Java Client vulnerable to unsafe deserialization of server responses |
| 2 | deserialize | 17 | `com.fasterxml.jackson.core:jackson-databind` | 2.18.8 | CWE-502 | CVE-2026-54512 | jackson-databind has a PolymorphicTypeValidator bypass via generic type parameters that allows arbitrary class instantiation |
| 3 | deserialize | 17 | `org.apache.flex.blazeds:flex-messaging-core` | 4.7.3 | CWE-502 | CVE-2017-5641 | Apache Flex BlazeDS unsafe deserialization |
| 4 | deserialize | 17 | `org.apache.kafka:connect` | 3.4.0 | CWE-502 | CVE-2023-25194 | Apache Kafka Connect vulnerable to Deserialization of Untrusted Data |
| 5 | deserialize | 17 | `org.apache.kafka:kafka_2.12` | 3.9.1 | CWE-502 | CVE-2025-27818 | Apache Kafka Deserialization of Untrusted Data vulnerability |
| 6 | deserialize | 17 | `org.apache.kafka:kafka_2.12` | 3.4.0 | CWE-502 | CVE-2025-27819 | Apache Kafka Deserialization of Untrusted Data vulnerability |
| 7 | deserialize | 17 | `org.redisson:redisson` | 3.22.0 | CWE-502 | CVE-2023-42809 | Redisson vulnerable to Deserialization of Untrusted Data |
| 8 | deserialize | 16 | `com.alibaba:fastjson` | 1.2.83 | CWE-502 | CVE-2022-25845 | Unsafe deserialization in com.alibaba:fastjson |
| 9 | deserialize | 16 | `com.thoughtworks.xstream:xstream` | 1.4.18 | CWE-502 | CVE-2021-39153 | XStream is vulnerable to an Arbitrary Code Execution attack |
| 10 | deserialize | 16 | `io.ratpack:ratpack-core` | 1.9.0 | CWE-502 | CVE-2021-29485 | Remote Code Execution Vulnerability in Session Storage |
| 11 | deserialize | 16 | `org.apache.activemq:apache-activemq` | 5.16.6 | CWE-502 | CVE-2022-41678 | Apache ActiveMQ Deserialization of Untrusted Data vulnerability |
| 12 | deserialize | 16 | `org.apache.iotdb:iotdb-confignode` | 2.0.5 | CWE-502 | CVE-2025-48459 | Apache IoTDB: Deserialization of untrusted Data |
| 13 | deserialize | 16 | `org.apache.jackrabbit:jackrabbit-core` | 2.22.2 | CWE-502 | CVE-2025-58782 | Apache Jackrabbit: Core and JCR Commons are vulnerable to Deserialization of Untrusted Data |
| 14 | deserialize | 16 | `org.apache.johnzon:johnzon-mapper` | 1.2.21 | CWE-502 | CVE-2023-33008 | Apache Johnzon Deserialization of Untrusted Data vulnerability |
| 15 | deserialize | 16 | `org.apache.juddi:juddi-core` | 3.3.10 | CWE-502 | CVE-2021-37578 | Deserialization of Untrusted Data in Apache jUDDI |
| 16 | deserialize | 16 | `org.apache.karaf.management:org.apache.karaf.management.server` | 4.3.6 | CWE-502 | CVE-2021-41766 | Insecure Java Deserialization in Apache Karaf |
| 17 | deserialize | 15 | `ch.qos.logback:logback-core` | 1.5.34 | CWE-502 | CVE-2026-10532 | Logback vulnerable to Object Injection through HardenedObjectInputStream modules |
| 18 | deserialize | 15 | `ch.qos.logback:logback-core` | 1.5.33 | CWE-502 | CVE-2026-9828 | QOS.CH Sarl logback logback-core has a deserialization of untrusted data vulnerability |
| 19 | deserialize | 15 | `com.fasterxml.jackson.core:jackson-databind` | 2.9.9.2 | CWE-502 | CVE-2019-14439 | Deserialization of untrusted data in FasterXML jackson-databind |
| 20 | deserialize | 15 | `com.fasterxml.jackson.core:jackson-databind` | 2.9.10 | CWE-502 | CVE-2019-14893 | Polymorphic deserialization of malicious object in jackson-databind |
| 21 | deserialize | 15 | `com.fasterxml.jackson.core:jackson-databind` | 2.9.8 | CWE-502 | CVE-2018-19362 | com.fasterxml.jackson.core:jackson-databind vulnerable to Deserialization of Untrusted Data |
| 22 | deserialize | 15 | `com.fasterxml.jackson.core:jackson-databind` | 2.9.9.1 | CWE-502 | CVE-2019-12814 | Deserialization of untrusted data in FasterXML jackson-databind |
| 23 | deserialize | 15 | `com.fasterxml.jackson.core:jackson-databind` | 2.7.9.5 | CWE-502 | CVE-2018-19361 | Deserialization of Untrusted Data in jackson-databind |
| 24 | deserialize | 15 | `com.gradle:gradle-enterprise-maven-extension` | 1.6 | CWE-502 | CVE-2020-15777 | Maven Extension plugin for Gradle Enterprise vulnerable to Deserialization of Untrusted Data |
| 25 | deserialize | 15 | `com.mchange:c3p0` | 0.12.0 | CWE-502,CWE-94 | CVE-2026-27830 | c3p0 vulnerable to Remote Code Execution via unsafe deserialization of userOverridesAsString property |
| 26 | deserialize | 15 | `com.mchange:mchange-commons-java` | 0.4.0 | CWE-502,CWE-74 | CVE-2026-27727 | mchange-commons-java: Remote Code Execution via JNDI Reference Resolution |
| 27 | deserialize | 15 | `org.apache.camel:camel-cassandraql` | 3.21.4 | CWE-502 | CVE-2024-23114 | Deserialization of Untrusted Data in Apache Camel CassandraQL |
| 28 | deserialize | 15 | `org.apache.camel:camel-infinispan` | 4.20.0 | CWE-502 | CVE-2026-6857 | camel-infinispan Vulnerable to Deserialization of Untrusted Data |
| 29 | deserialize | 15 | `org.apache.camel:camel-leveldb` | 4.10.9 | CWE-502 | CVE-2026-25747 | Apache Camel Deserializes Untrusted Data in its LevelDB Component |
| 30 | deserialize | 15 | `org.apache.camel:camel-mina` | 4.14.6 | CWE-502 | CVE-2026-40473 | Camel-MINA Vulnerable to Deserialization of Untrusted Data |
| 31 | deserialize | 15 | `org.apache.camel:camel-pqc` | 4.18.2 | CWE-502 | CVE-2026-40048 | Camel-PQC Vulnerable to Deserialization of Untrusted Data |
| 32 | deserialize | 15 | `org.apache.camel:camel-rabbitmq` | 2.25.1 | CWE-502 | CVE-2020-11972 | Deserialization of Untrusted Data in Apache Camel RabbitMQ |
| 33 | deserialize | 15 | `org.apache.dubbo:dubbo` | 2.7.10 | CWE-502 | CVE-2021-30179 | Deserialization of Untrusted Data in Apache Dubbo |
| 34 | deserialize | 15 | `org.apache.dubbo:dubbo-rpc-http-invoker` | 2.7.5 | CWE-502 | CVE-2019-17564 | Deserialization of Untrusted Data in Apache Dubbo |
| 35 | deserialize | 15 | `org.apache.fory:fory-core` | 1.1.0 | CWE-502 | CVE-2026-50076 | Apache Fory Java SDK Has Deserialization of Untrusted Data in the Java replace-resolve path |
| 36 | deserialize | 15 | `org.apache.hive:hive-exec` | 4.0.0-alpha-2 | CWE-502 | CVE-2022-41137 | Apache Hive: Deserialization of untrusted data when fetching partitions from the Metastore |
| 37 | deserialize | 15 | `org.apache.hugegraph:hg-pd-core` | 1.7.0 | CWE-502 | CVE-2025-26866 | Apache HugeGraph-Server: RAFT and deserialization vulnerability |
| 38 | deserialize | 15 | `org.apache.iotdb:iotdb-parent` | 1.2.2 | CWE-502 | CVE-2023-51656 | Apache IoTDB: Unsafe deserialize map in Sync Tool |
| 39 | deserialize | 15 | `org.apache.karaf.decanter.collector:org.apache.karaf.decanter.collector.log.socket` | 2.12.0 | CWE-502 | CVE-2026-24656 | Apache Karaf Decanter has Deserialization of Untrusted Data in its Log Socket Collector |
| 40 | deserialize | 15 | `org.apache.logging.log4j:log4j-core` | 2.15.0 | CWE-20,CWE-400,CWE-502 | CVE-2021-44228 | Remote code injection in Log4j |
