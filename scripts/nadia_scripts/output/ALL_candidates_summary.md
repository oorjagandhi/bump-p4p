# BBC adaptation dataset — all breaks

Consolidated from output/<break>_candidates.jsonl + verified_cases/. Regenerate: `python bbc_e2e.py summarize`.

| Break | signal | candidates | Maven-prod (verifiable) | best candidate | recorded status |
|---|---|---|---|---|---|
| commons-io-2.7-to-2.11-copyfile-iae | medium | 50 | 0 | — | — |
| mockito-4.11-to-5.x-inline | medium | 20 | 0 | — | — |
| logback-1.2.11-to-1.4-jakarta | weak | 20 | 0 | — | — |
| slf4j-1.7.32-to-2.x | weak | 20 | 0 | — | — |
| poi-ooxml-4.1.2-to-5.x | clean | 20 | 2 | jadhavspeaks/file_compare_diffrent_ext@156a9624 | signature_confirmed (poi-fmflatfile.json) |
| poi-4.1.2-to-5.x | clean | 20 | 2 | jadhavspeaks/file_compare_diffrent_ext@156a9624 | signature_confirmed (poi-fmflatfile.json) |
| poi-scratchpad-4.1.2-to-5.x | clean | 6 | 2 | jadhavspeaks/file_compare_diffrent_ext@156a9624 | signature_confirmed (poi-fmflatfile.json) |
| httpclient-4.5.1-to-4.5.13 | weak | 20 | 0 | — | — |
| jsoup-1.14.2-to-1.15.3-whitespace | weak | 20 | 0 | — | — |
| xstream-1.4.17-to-1.4.19-forbiddenclass | clean | 50 | 16 | amirsnw/chainrtrade-axon-CQRS-DDD@d408d4ca | verified_bbc (xstream-axon-artshishkin.json) |
| json-smart-2.4.8-to-2.4.9-maxdepth | weak | 50 | 0 | — | — |
| org-json-strict-type-coercion | medium | 50 | 5 | FamingHou/geospider@e1ce5497 | — |
| h2-1.3-to-2.0-sql-compat | medium | 50 | 2 | LucasG-max/WorkShop-spring-jpa@c4a78a32 | — |
| snakeyaml-1.x-to-2.0-safeconstructor | medium | 5 | 3 | quarkusio/quarkus@06a8c629 | — |
| jackson-databind-default-typing-ptv | medium | _not run_ | – | – | – |
| jackson-core-2.15-streamreadconstraints | medium | 6 | 0 | — | — |

## Verifiable Maven production candidates per break

### commons-io-2.7-to-2.11-copyfile-iae  (signal: medium)
- (no native-Maven production candidates)

### mockito-4.11-to-5.x-inline  (signal: medium)
- (no native-Maven production candidates)

### logback-1.2.11-to-1.4-jakarta  (signal: weak)
- (no native-Maven production candidates)

### slf4j-1.7.32-to-2.x  (signal: weak)
- (no native-Maven production candidates)

### poi-ooxml-4.1.2-to-5.x  (signal: clean)
- `jadhavspeaks/file_compare_diffrent_ext@156a9624` — src/main/java/com/filecomparator/parser/ExcelParser.java — Fix(parser): Increase Excel file size limit
- `ProgrammeVitam/sedatools@e81cded4` — mailextractlib/src/main/java/fr/gouv/vitam/tools/mailextractlib/core/StoreExtractor.java — fix: bypass a POI bug in "msg" opening with MAPIMessage (mai

### poi-4.1.2-to-5.x  (signal: clean)
- `jadhavspeaks/file_compare_diffrent_ext@156a9624` — src/main/java/com/filecomparator/parser/ExcelParser.java — Fix(parser): Increase Excel file size limit
- `ProgrammeVitam/sedatools@e81cded4` — mailextractlib/src/main/java/fr/gouv/vitam/tools/mailextractlib/core/StoreExtractor.java — fix: bypass a POI bug in "msg" opening with MAPIMessage (mai

### poi-scratchpad-4.1.2-to-5.x  (signal: clean)
- `jadhavspeaks/file_compare_diffrent_ext@156a9624` — src/main/java/com/filecomparator/parser/ExcelParser.java — Fix(parser): Increase Excel file size limit
- `ProgrammeVitam/sedatools@e81cded4` — mailextractlib/src/main/java/fr/gouv/vitam/tools/mailextractlib/core/StoreExtractor.java — fix: bypass a POI bug in "msg" opening with MAPIMessage (mai

### httpclient-4.5.1-to-4.5.13  (signal: weak)
- (no native-Maven production candidates)

### jsoup-1.14.2-to-1.15.3-whitespace  (signal: weak)
- (no native-Maven production candidates)

### xstream-1.4.17-to-1.4.19-forbiddenclass  (signal: clean)
- `amirsnw/chainrtrade-axon-CQRS-DDD@d408d4ca` — core/src/main/java/com/chaintrade/core/model/ProductRestModel.java — fix: resolve XStream ForbiddenClassException for ProductRest
- `igniterealtime/Spark@c26602bf` — core/src/main/java/org/jivesoftware/spark/ui/status/CustomMessages.java — Merge pull request #683 from Plyha/xstream
- `igniterealtime/Spark@aad38d68` — core/src/main/java/org/jivesoftware/spark/ui/status/CustomMessages.java — SPARK-2259 XStream ForbiddenClassException in CustomStatusIt
- `einsteinarbert/axon-saga-example@dddd794b` — order-service/src/main/java/com/progressivecoder/ordermanagement/orderservice/config/SwaggerConfig.java — axon saga Xstream ForbiddenClassException site:stackoverflow
- `RicBatista/drools@ce38e409` — kie-ci/src/main/java/org/kie/scanner/KieURLClassLoader.java — JBPM-7999 - xstream ForbiddenClassException with data object
- `artshishkin/art-kargopolov-cqrs-saga-axon-microservices@b76d747f` — core/src/main/java/net/shyshkin/study/cqrs/estore/core/config/XStreamConfig.java — 32.6 Fixing com.thoughtworks.xstream.security.ForbiddenClass
- `Shkr00007/drool-bpm@ce38e409` — kie-ci/src/main/java/org/kie/scanner/KieURLClassLoader.java — JBPM-7999 - xstream ForbiddenClassException with data object
- `gitgabrio/efesto-langchain4j-poc@ce38e409` — kie-ci/src/main/java/org/kie/scanner/KieURLClassLoader.java — JBPM-7999 - xstream ForbiddenClassException with data object

### json-smart-2.4.8-to-2.4.9-maxdepth  (signal: weak)
- (no native-Maven production candidates)

### org-json-strict-type-coercion  (signal: medium)
- `FamingHou/geospider@e1ce5497` — src/main/java/massey/geospider/probe/facebook/FacebookCommentsProbe.java — Fixing bug as below by checking whether the response string 
- `Onto-Med/top-backend@89d27249` — src/main/java/care/smith/top/backend/api/nlp/ConceptPipelineApiDelegateImpl.java — Add concept pipeline JSON config (#225)
- `emkds1729/graylog-plugin-gcp-pubsub@2191ce61` — src/main/java/org/graylog/plugins/gcppubsub/GcpPubSubLogRetriever.java — v2.0.0: replace destructive sanitize() with key-only regex s
- `gridgentoo/pinot@0d92355a` — pinot-core/src/main/java/com/linkedin/pinot/core/realtime/impl/kafka/KafkaJSONMessageDecoder.java — Get quickstart-realtime working again (#3374)
- `NikosNikoTest/incubator-pinot@0d92355a` — pinot-core/src/main/java/com/linkedin/pinot/core/realtime/impl/kafka/KafkaJSONMessageDecoder.java — Get quickstart-realtime working again (#3374)

### h2-1.3-to-2.0-sql-compat  (signal: medium)
- `LucasG-max/WorkShop-spring-jpa@c4a78a32` — src/main/java/com/Projeto_Microservico/Curso/config/TestConfigu.java — Adição do H2 database, test profile, JPA 2.0
- `bizwmh/OASE@524a5222` — oase.h2/src/main/java/biz/oase/h2/H2Console.java — oase.h2 2.0.0

### snakeyaml-1.x-to-2.0-safeconstructor  (signal: medium)
- `quarkusio/quarkus@06a8c629` — extensions/vertx-http/deployment/src/main/java/io/quarkus/vertx/http/deployment/devmode/console/DevConsole.java — Use SafeConstructor class for SnakeYAML
- `smallrye/smallrye-config@0c348b93` — sources/yaml/src/main/java/io/smallrye/config/source/yaml/YamlConfigSource.java — Use snakeyaml SafeConstructor (#858)
- `killbill/killbill-platform@9cd27892` — osgi-bundles/bundles/kpm/src/main/java/org/killbill/billing/osgi/bundles/kpm/impl/YamlParser.java — replace removed snakeyaml's TrustedTagInspector to just retu

### jackson-core-2.15-streamreadconstraints  (signal: medium)
- (no native-Maven production candidates)
