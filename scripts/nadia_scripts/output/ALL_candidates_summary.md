# BBC adaptation dataset — all breaks

Consolidated from output/<break>_candidates.jsonl + verified_cases/. Regenerate: `python bbc_e2e.py summarize`.

| Break | signal | candidates | Maven-prod (verifiable) | best candidate | recorded status |
|---|---|---|---|---|---|
| mockito-4.11-to-5.x-inline | medium | 20 | 0 | — | — |
| logback-1.2.11-to-1.4-jakarta | weak | 20 | 0 | — | — |
| slf4j-1.7.32-to-2.x | weak | 20 | 0 | — | — |
| poi-ooxml-4.1.2-to-5.x | clean | 20 | 2 | jadhavspeaks/file_compare_diffrent_ext@156a9624 | signature_confirmed (poi-fmflatfile.json) |
| poi-4.1.2-to-5.x | clean | 20 | 2 | jadhavspeaks/file_compare_diffrent_ext@156a9624 | signature_confirmed (poi-fmflatfile.json) |
| poi-scratchpad-4.1.2-to-5.x | clean | 20 | 5 | jadhavspeaks/file_compare_diffrent_ext@156a9624 | signature_confirmed (poi-fmflatfile.json) |
| httpclient-4.5.1-to-4.5.13 | weak | 20 | 0 | — | — |
| jsoup-1.14.2-to-1.15.3-whitespace | weak | 20 | 0 | — | — |
| xstream-1.4.17-to-1.4.19-forbiddenclass | clean | 20 | 12 | amirsnw/chainrtrade-axon-CQRS-DDD@d408d4ca | verified_bbc (xstream-axon-artshishkin.json) |

## Verifiable Maven production candidates per break

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
- `SilkKirk/ruoyi-vue-backend@6381d71d` — ruoyi-common/src/main/java/com/ruoyi/common/utils/Threads.java — 优化：移除commons-lang3依赖，清理MyBatis-Flex冗余配置，用Hutool替换手写工具类
- `victoryshining/zhongxun-onlineschool@6fc95273` — src/main/java/org/olat/core/commons/modules/bc/meta/MetaInfoFileImpl.java — OO-2853: update commons-io, commons-codec, jersey, poi, pdfb
- `OpenOLAT/OpenOLAT@6fc95273` — src/main/java/org/olat/core/commons/modules/bc/meta/MetaInfoFileImpl.java — OO-2853: update commons-io, commons-codec, jersey, poi, pdfb

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
