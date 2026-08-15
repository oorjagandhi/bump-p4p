# BBC adaptation dataset — all breaks

Consolidated from output/<break>_candidates.jsonl + verified_cases/. Regenerate: `python bbc_e2e.py summarize`.

| Break | signal | candidates | Maven-prod (verifiable) | best candidate | recorded status |
|---|---|---|---|---|---|
| commons-io-2.7-to-2.11-copyfile-iae | medium | 50 | 0 | — | — |
| mockito-4.11-to-5.x-inline | medium | 20 | 0 | — | — |
| logback-1.2.11-to-1.4-jakarta | weak | 0 | 0 | — | — |
| slf4j-1.7.32-to-2.x | weak | 20 | 0 | — | — |
| poi-ooxml-4.1.2-to-5.x | clean | 20 | 2 | jadhavspeaks/file_compare_diffrent_ext@156a9624 | — |
| poi-4.1.2-to-5.x | clean | 20 | 2 | jadhavspeaks/file_compare_diffrent_ext@156a9624 | — |
| poi-scratchpad-4.1.2-to-5.x | clean | 6 | 2 | jadhavspeaks/file_compare_diffrent_ext@156a9624 | — |
| httpclient-4.5.1-to-4.5.13 | weak | 20 | 0 | — | — |
| jsoup-1.14.2-to-1.15.3-whitespace | weak | 0 | 0 | — | — |
| xstream-1.4.17-to-1.4.19-forbiddenclass | clean | 11 | 11 | igniterealtime/Spark@c26602bf | verified_bbc (xstream-axon-artshishkin.json) |
| json-smart-2.4.8-to-2.4.9-maxdepth | weak | 200 | 1 | toscollection/tcommon-studio-se@e6b72f14 | — |
| org-json-strict-type-coercion | medium | 50 | 5 | FamingHou/geospider@e1ce5497 | — |
| h2-1.3-to-2.0-sql-compat | medium | 50 | 2 | LucasG-max/WorkShop-spring-jpa@c4a78a32 | — |
| snakeyaml-1.x-to-2.0-safeconstructor | medium | 7 | 7 | snork-alt/beanszoo@55d17ce2 | — |
| jackson-databind-default-typing-ptv | medium | _not run_ | – | – | – |
| jackson-core-2.15-streamreadconstraints | medium | 6 | 0 | — | — |
| fastjson-1.2.80-to-1.2.83-autotype | clean | 1 | 1 | apache/rocketmq-connect@9bd9f899 | — |
| commons-beanutils-1.9.3-to-1.9.4-classproperty | clean | 1 | 1 | j-easy/easy-props@b723efb7 | — |
| kubernetes-client-5.0.2-to-5.0.3-safeconstructor | clean | 0 | 0 | — | — |
| commons-net-3.8.0-to-3.9.0-pasv-host | clean | 0 | 0 | — | — |
| snakeyaml-1.31-to-1.32-codepointlimit | clean | _not run_ | – | – | – |

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
- `igniterealtime/Spark@c26602bf` — core/src/main/java/org/jivesoftware/spark/ui/status/CustomMessages.java — Merge pull request #683 from Plyha/xstream
- `igniterealtime/Spark@aad38d68` — core/src/main/java/org/jivesoftware/spark/ui/status/CustomMessages.java — SPARK-2259 XStream ForbiddenClassException in CustomStatusIt
- `einsteinarbert/axon-saga-example@dddd794b` — order-service/src/main/java/com/progressivecoder/ordermanagement/orderservice/config/SwaggerConfig.java — axon saga Xstream ForbiddenClassException site:stackoverflow
- `artshishkin/art-kargopolov-cqrs-saga-axon-microservices@b76d747f` — core/src/main/java/net/shyshkin/study/cqrs/estore/core/config/XStreamConfig.java — 32.6 Fixing com.thoughtworks.xstream.security.ForbiddenClass
- `igniterealtime/openfire-fastpath-plugin@5bbd65a4` — src/java/org/jivesoftware/openfire/fastpath/dataforms/FormManager.java — 1.FormManager,java load workgroupForm: xstream have Type lim
- `Sage-Bionetworks/Synapse-Repository-Services@140f09a1` — lib/jdomodels/src/main/java/org/sagebionetworks/evaluation/dao/SubmissionUtils.java — Needed more cases of .allowTypesByWildcard(new String[] {org
- `iitsoftware/swiftmq-client@e3143433` — src/main/java/com/swiftmq/filetransfer/protocol/v941/FileQueryPropsReply.java — Remove XStream dependency and related functionality
- `collectionspace/services@6593d7fb` — services/id/service/src/main/java/org/collectionspace/services/id/IDGeneratorSerializer.java — Bump xstream from 1.4.10 to 1.4.19 in /services/id/service

### json-smart-2.4.8-to-2.4.9-maxdepth  (signal: weak)
- `toscollection/tcommon-studio-se@e6b72f14` — main/plugins/org.talend.core.runtime/src/main/java/org/talend/core/database/conn/version/EDatabaseVersion4Drivers.java — chore(TUP-38551) json-smart:2.4.7 ( CVE-2023-1370) (#6096)

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
- `snork-alt/beanszoo@55d17ce2` — core/src/main/java/com/dataheaps/beanszoo/lifecycle/YamlConfigurationReader.java — migrate build to Java 21
- `adityajoy-1902/Dashboard-V-2@8c39d993` — src/main/java/com/example/dashboard/service/ApplicationConfigService.java — Fix Windows compatibility: Update SnakeYAML to v2.0 and add 
- `GoogleCloudPlatform/appengine-plugins@feed4c64` — src/main/java/com/google/cloud/tools/project/AppYaml.java — Bump snakeyaml from 1.32 to 2.0 (#915)
- `liquibase/liquibase@febd6a51` — liquibase-core/src/main/java/liquibase/util/SnakeYamlUtil.java — Snakeyaml 2.0 (#3893)
- `kafka-ops/julie@3fae19d8` — src/main/java/com/purbon/kafka/topology/AccessControlManager.java — While you were gone... (#566)
- `apache/linkis@bce24744` — linkis-commons/linkis-common/src/main/java/org/apache/linkis/common/utils/ByteTimeUtils.java — [1.9.0 release] [PES][EC][publicservice][spark] feat: Result
- `apache/linkis@1596145e` — linkis-commons/linkis-common/src/main/java/org/apache/linkis/common/utils/AESUtils.java — Master feature (#5293)

### jackson-core-2.15-streamreadconstraints  (signal: medium)
- (no native-Maven production candidates)

### fastjson-1.2.80-to-1.2.83-autotype  (signal: clean)
- `apache/rocketmq-connect@9bd9f899` — connectors/rocketmq-connect-debezium/kafka-connect-adaptor/src/main/java/org/apache/rocketmq/connect/kafka/connect/adaptor/schema/Converters.java — [ISSUE #207]RecordConverter support convert record key (#213

### commons-beanutils-1.9.3-to-1.9.4-classproperty  (signal: clean)
- `j-easy/easy-props@b723efb7` — src/main/java/org/jeasy/props/PropertyInjector.java — Add ability to inject properties in non public classes

### kubernetes-client-5.0.2-to-5.0.3-safeconstructor  (signal: clean)
- (no native-Maven production candidates)

### commons-net-3.8.0-to-3.9.0-pasv-host  (signal: clean)
- (no native-Maven production candidates)
