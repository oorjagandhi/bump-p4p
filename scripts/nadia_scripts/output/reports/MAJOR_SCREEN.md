# Major-boundary screen — which majors can reach run time

A client crossing a boundary that removed public API fails at javac and never reaches the behavioural change. This screens that out before any mining is spent, using the same javap diff `rank_candidates.py` applies to advisories.

**MINEABLE means only that clients compile across the boundary.** It does not mean behaviour changed. Confirm the restriction is ACTIVE BY DEFAULT from the sources-jar diff before mining — see the relaxation (mybatis) and opt-in (avro) failure modes.

Screened 11: **1 mineable**, 10 reject, 0 unavailable.

| library | transition | released | removed sigs | removed classes | verdict |
|---|---|---|---:|---:|---|
| `org.mockito:mockito-core` | 4.11.0 → 5.0.0 | 2023-01 | 8 | 1 | **REJECT** |
| `org.slf4j:slf4j-api` | 1.7.36 → 2.0.0 | 2022-08 | 3 | 1 | **REJECT** |
| `org.yaml:snakeyaml` | 1.33 → 2.0 | 2023-02 | 38 | 0 | **REJECT** |
| `org.flywaydb:flyway-core` | 9.22.3 → 10.0.0 | 2023-10 | 58 | 80 | **REJECT** |
| `redis.clients:jedis` | 4.4.6 → 5.0.0 | 2023-09 | 2177 | 14 | **REJECT** |
| `org.mongodb:mongodb-driver-sync` | 4.11.1 → 5.0.0 | 2024-03 | 11 | 0 | **REJECT** |
| `com.google.protobuf:protobuf-java` | 3.25.9 → 4.26.0 | 2024-03 | 24 | 4 | **REJECT** |
| `org.apache.kafka:kafka-clients` | 3.9.0 → 4.0.0 | 2025-03 | 256 | 39 | **REJECT** |
| `com.github.ben-manes.caffeine:caffeine` | 2.9.3 → 3.0.0 | 2021-08 | 78 | 6 | **REJECT** |
| `com.zaxxer:HikariCP` | 4.0.3 → 5.0.0 | 2021-11 | 0 | 0 | **MINEABLE** |
| `org.apache.poi:poi` | 4.1.2 → 5.0.0 | 2021-01 | 706 | 95 | **REJECT** |

## Rejected: the boundary removes public API

| library | removed sigs | example |
|---|---:|---|
| `redis.clients:jedis` | 2177 | `redis.clients.jedis.graph.RedisGraphCommands: public abstract java.util.List<java.util.List<java.lang.String>> graphSlowlog(java.lang.St` |
| `org.apache.poi:poi` | 706 | `org.apache.poi.common.usermodel.GenericRecord: public default java.lang.Enum getGenericRecordType();` |
| `org.apache.kafka:kafka-clients` | 256 | `org.apache.kafka.common.KafkaFuture: public abstract <R> org.apache.kafka.common.KafkaFuture<R> thenApply(org.apache.kafka.comm` |
| `com.github.ben-manes.caffeine:caffeine` | 78 | `com.github.benmanes.caffeine.cache.AsyncCache: public abstract java.util.concurrent.CompletableFuture<V> get(K, java.util.function.BiFunc` |
| `org.flywaydb:flyway-core` | 58 | `org.flywaydb.core.internal.database.h2.H2Database: public final void ensureSupported();` |
| `org.yaml:snakeyaml` | 38 | `org.yaml.snakeyaml.TypeDescription: public java.lang.Class<? extends java.lang.Object> getListPropertyType(java.lang.String);` |
| `com.google.protobuf:protobuf-java` | 24 | `com.google.protobuf.ArrayDecoders: public static void setRecursionLimit(int);` |
| `org.mongodb:mongodb-driver-sync` | 11 | `com.mongodb.client.FindIterable: public abstract com.mongodb.client.FindIterable<TResult> oplogReplay(boolean);` |
| `org.mockito:mockito-core` | 8 | `org.mockito.internal.exceptions.Reporter: public static java.lang.AssertionError argumentsAreDifferent(java.lang.String, java.util.L` |
| `org.slf4j:slf4j-api` | 3 | `org.slf4j.event.LoggingEvent: public abstract org.slf4j.Marker getMarker();` |
