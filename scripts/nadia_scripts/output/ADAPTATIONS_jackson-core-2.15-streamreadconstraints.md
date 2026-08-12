# Adaptations to `jackson-core-2.15-streamreadconstraints`

Commits touching `maxStringLength`, classified by the VALUE they set. The library's own default is taken as 20,000,000.

**RAISE is the only verdict that can yield a case.** A knob left at the library's default behaves identically before and after for every input size, so it cannot produce a pass/fail/pass differential; LOWER is security hardening. Measured five for five on snakeyaml, the split follows what the project is: applications raise, libraries and plugins expose a knob.

99 distinct commit(s) after fork collapse; **69 worth reading**.

| verdict | value | repo | date | commit | forks |
|---|---:|---|---|---|---:|
| raise | 100,000,000 | `mkarjun/LCS` | 2026-04-13 | fix(lambda): raise Jackson maxStringLength for large | 7 |
| raise | 200,000,000 | `mmaudet/eu-dss-module` | 2026-05-31 | fix(server): raise Jackson maxStringLength to 200M s |  |
| raise | 2,147,483,647 | `havochvatten/MSP-Symphony` | 2025-06-09 | Override maxStringLength |  |
| needs_reading | — | `521mc/qwer` | 2026-02-06 | fix(minecraft): render nested return objects without | 26 |
| needs_reading | — | `jss-shawn/ggs` | 2026-07-09 | feat(FactSystem): add maxStringLength metadata with  | 6 |
| needs_reading | — | `nestjs/nest` | 2026-01-21 | fix(common): Fix skipping maxArrayLength and maxStri | 5 |
| needs_reading | — | `nestjs/nest` | 2026-01-21 | Merge pull request #16230 from chojs23/fix/console-l | 5 |
| needs_reading | — | `openclaw/mcporter` | 2025-12-06 | fix(cli): prevent silent string truncation to 10k ch | 2 |
| needs_reading | JSON.DEFAULT_MAX_STRING_LEN).build() | `TwoHeadsDragon/metersphere` | 2023-06-26 | build: jackson-core default maxStringLength 调整 | 2 |
| needs_reading | — | `skjolber/json-log-filter` | 2026-05-03 | Variuos fixes and cleanups (#262) |  |
| needs_reading | g_defaultStringLength ? g_defaultStringLength : kDefMaxStringLength | `clockworkengineer/JSON_Lib` | 2026-05-13 | refactor(string): move max string length state from  |  |
| needs_reading | deprecated | `dexie/Dexie.js` | 2026-03-31 | Merge pull request #2290 from dexie/liz/rename-maxSt |  |
| needs_reading | — | `aself101/mcp-secure-server` | 2026-06-12 | fix(pipeline-factory): thread maxStringLength from s |  |
| needs_reading | — | `Daniel-Alievsky/algart-tiff` | 2026-05-31 | TiffSampleType.Formatter: adding maxStringLength |  |
| needs_reading | — | `dexie/dexie-cloud-sdk` | 2026-03-18 | feat: string offloading support |  |
| needs_reading | — | `dlta17/yaml-security-lib` | 2026-07-30 | v1.6.0 |  |
| needs_reading | — | `dexie/Dexie.js` | 2026-03-19 | feat(dexie-cloud): string offloading for long string |  |
| needs_reading | — | `apache/druid` | 2026-03-23 | minor: change maxStringLength default (#19198) |  |
| needs_reading | deprecated | `dexie/Dexie.js` | 2026-03-31 | rename maxStringLength to largeStringThreshold (keep |  |
| needs_reading | — | `CaoGiaHieu-dev/dynamic_logger` | 2026-07-30 | [Release]: 0.5.0 - Fix: sync formatting, remove isol |  |
| needs_reading | — | `Opetushallitus/kielitutkintorekisteri` | 2026-05-18 | Pienennä Jackson maxStringLength -oletusarvo 10 mega |  |
| needs_reading | MAX_STRING_LENGTH).build() | `ailyedu2030/micro-course` | 2026-07-14 | fix: inject Spring ObjectMapper and raise Jackson ma |  |
| needs_reading | ) | `clockworkengineer/JSON_Lib` | 2026-05-01 | Embedded Phase 6.4: compile-time configurable maxPar |  |
| needs_reading | — | `taras/executable.md` | 2026-03-17 | fix: verbose log maxStringLength 200, trim GitHubCom |  |
| needs_reading | — | `Hahn-Schickard/Open62541-Conan-Recipe` | 2026-01-28 | add 0011-undifine-maxStringLength.patch |  |
| needs_reading | — | `FasterXML/jackson-core` | 2026-01-27 | Fix #1538: increase default StreamReadConstraints.ma |  |
| needs_reading | — | `andymerskin/spotr` | 2026-02-19 | perf: add `maxStringLength` option operating on quer |  |
| needs_reading | — | `aeonite-org/aeonite-cts` | 2026-07-25 | Add apply-budget overlength mutate test |  |
| needs_reading | — | `dexie/Dexie.js` | 2026-03-19 | Merge pull request #2266 from dexie/liz/min-string-l |  |
| needs_reading | — | `adokky/zero-json` | 2025-12-09 | `ZeroJsonConfiguration`: `maxOutputBytes` -> `maxEnc |  |
| needs_reading | — | `Uluops/-uluops-registry-mcp` | 2026-06-17 | fix: raise per-string cap so realistic definition YA |  |
| needs_reading | — | `dexie/dexie-web` | 2026-03-18 | docs: add string offloading documentation |  |
| needs_reading | getMaxStringLength()).build( | `vdaburon/har-to-jmeter-convertor` | 2026-02-04 | Add new classe MyMapperFactory to set the new stream |  |
| needs_reading | — | `ohbee-labs/-ohbee-safe-json` | 2026-05-17 | feat(types): define SafeJsonOptions and SafeJsonInst |  |
| needs_reading | — | `aeonite-org/aeonite-specs` | 2026-07-25 | Document datatype/kind hints and value budgets |  |
| needs_reading | — | `brendadeeznuts1111/project-R-score` | 2026-07-28 | feat(console-depth): stripANSI wrapper + ignored-opt |  |
| needs_reading | — | `Dune172/d2r-skill-randomizer` | 2026-03-09 | Fix chat disable crash — keep widget types, neuter v |  |
| needs_reading | — | `proteinjs/util` | 2025-12-10 | chore: `DevLogWriter` increase `maxStringLength` (1k |  |
| needs_reading | — | `ethan-godden/Diaram` | 2026-07-09 | Cap oversized debuggee String reads before truncatio |  |
| needs_reading | — | `kesslerio/attio-mcp-server` | 2026-02-09 | fix: bump response maxStringLength from 40KB to 500K |  |
| needs_reading | — | `HelenB00/nest` | 2026-01-21 | fix(common): Fix skipping maxArrayLength and maxStri |  |
| needs_reading | — | `AltoPelago/sansa` | 2026-07-25 | Add mutation value budget limits |  |
| needs_reading | — | `emonkak/barebind` | 2025-12-24 | feat(debug.value): increase `maxStringLength` in Deb |  |
| needs_reading | — | `jdereg/json-io` | 2026-01-15 | Performance: Optimize JsonWriter hot paths with memb |  |
| needs_reading | — | `kesslerio/attio-mcp-server` | 2026-02-09 | fix: bump response maxStringLength from 40KB to 500K |  |
| needs_reading | — | `HelenB00/nest` | 2026-01-21 | Merge pull request #16230 from chojs23/fix/console-l |  |
| needs_reading | — | `ztur211/network-monitoring` | 2026-05-31 | fix(api): validate onboarding fieldValues are bounde |  |
| needs_reading | — | `dexie/Dexie.js` | 2026-03-19 | fix(cloud): enforce minimum maxStringLength of 100 |  |
| needs_reading | — | `Uluops/-uluops-ops-mcp` | 2026-07-18 | docs(readme): document payload size limits (0.11.0) |  |
| needs_reading | — | `danfry1/bonsai-js` | 2026-06-02 | fix(security): bound parser recursion and cap method |  |
| needs_reading | — | `emonkak/barebind` | 2025-08-01 | refactor(debug): s/maxLength/maxStringLength/ |  |
| needs_reading | it changes the bytecode)" | `bmc4j/bmc4j` | 2026-06-13 | Bound symbolic-string length under StringMode.NONE v |  |
| needs_reading | — | `WojciechKownacki/21kb-Engine` | 2026-07-13 | Add LIB-037/038: unified input limits and call-depth |  |
| needs_reading | — | `MatthiasBurger-Coder/forensics_tracing` | 2025-09-26 | Add `maxStringLength` parameter to control string tr |  |
| needs_reading | — | `Justino-code/dumpkit` | 2026-05-20 | git commit -m "chore: prepare for v0.1.0 release |  |
| needs_reading | — | `whoughton/lz77` | 2026-04-22 | Add benchmark tracking infrastructure and fix maxStr |  |
| needs_reading | — | `aboutcircles/group-tms` | 2026-02-23 | fix(logging): cap formatError output to prevent 400K |  |
| needs_reading | — | `eleven-labs/nest-profiler` | 2026-07-22 | feat(nest-profiler): configurable body-capture limit |  |
| needs_reading | — | `dmarigliano/super-router` | 2026-08-03 | fix: keep redactText output within maxStringLength |  |
| needs_reading | — | `zb-sj/storybook-addon-react-grab` | 2026-06-24 | docs: correct README — react-grab repo link, toolbar |  |
| needs_reading | — | `schizoidcock/mcx` | 2026-02-27 | feat(cli): configurable result truncation in mcx_exe |  |
| needs_reading | — | `ohbee-labs/-ohbee-safe-json` | 2026-05-17 | test: add comprehensive test suite (62 tests across  |  |
| needs_reading | — | `Arize-ai/project-rosetta-stone` | 2026-02-22 | Add AX synthetic request harness and increase serial |  |
| needs_reading | default: 1000, maximum length for strings before truncation in JSON format | `trojs/logger` | 2026-02-09 | Updates documentation with new log options |  |
| needs_reading | — | `Mearman/BSIF` | 2026-02-02 | feat(parser): add security limits for document size, |  |
| needs_reading | — | `schizoidcock/mcx` | 2026-02-28 | feat(mcp): add configurable truncation to mcx_run_sk |  |
| needs_reading | — | `07artem132/SignalCli.NET` | 2026-05-22 | @ |  |
| needs_reading | — | `ojson-platform/http` | 2026-02-05 | docs: expand API Overview in all with-* readmes |  |
| needs_reading | config.getMaxResponseSize() | `FortnoxAB/reactive-wizard` | 2023-04-26 | Set maxStringLength in Jackson JsonFactory to maxRes |  |
| lower | 262,144 | `JHyunJung/passkey-package` | 2026-07-04 | fix(G02): Jackson StreamReadConstraints로 트리 완전파싱 전 과 |  |
| no_call | — | `Dom-303/pinflow` | 2026-04-01 | refactor(runtime): SerializationOptions extends Seri | 1 |
| no_call | — | `PretendoNetwork/nex-protocols-go` | 2025-07-08 | feat(messaging): add MaxStringLength and MaxBinarySi | 1 |
| no_call | — | `eclipse-openj9/openj9` | 2025-01-15 | Merge pull request #20941 from keithc-ca/maxstringle | 1 |
| no_call | — | `dexie/dexie-web` | 2026-04-13 | Merge pull request #34 from dexie/liz/rename-maxStri |  |
| no_call | — | `ACDPDEV/retro-arc.h` | 2026-07-06 | feat(Common): add InvertString, MaxStringLength, Rep |  |
| no_call | — | `Adgo0001/EduGPT-Backend` | 2026-05-25 | set tika maxStringLength via static initializer (cor |  |
| no_call | — | `dexie/dexie-web` | 2026-03-31 | docs: rename maxStringLength to largeStringThreshold |  |
| no_call | — | `aivorynet/agent-dotnet` | 2026-02-18 | Fix build: add missing MaxStringLength and MaxCollec |  |
| no_call | — | `aelassas/servy` | 2026-04-22 | fix(service): EnvironmentVariableHelper.cs - MaxExpa |  |
| no_call | — | `occamsshavingkit/muc-opcua` | 2026-07-09 | fix(057): correct MaxArrayLength/MaxStringLength Nod |  |
| no_call | — | `OPCF-Members/Opc2Aml` | 2025-09-10 | Fix MaxStringLength Error (#135) |  |
| no_call | — | `ACDPDEV/retro-arc.h` | 2026-07-07 | feat(utils): add UTF-8 Length() and improve string f |  |
| no_call | — | `skmtkytr/stor` | 2026-04-12 | Security: add decoding limits to bencode parser |  |
| no_call | — | `microsoft/mu_feature_dfci` | 2026-07-28 | DfciPkg: Fix off-by-one heap overflow in GetIssuerNa |  |
| no_call | — | `pythonite42/sauf_o_mat_zieefaegge` | 2025-09-24 | maxStringLength integrated |  |
| no_call | — | `mw10013/tanstack-cloudflare-effect-saas` | 2026-03-29 | refactor: move trimFields to SchemaEx, inline maxStr |  |
| no_call | — | `open-vela/apps_netutils_connectedhomeip` | 2021-03-04 | Use SafeString api calculate the MaxStringLength in  |  |
| no_call | — | `TaiPhung217/d8` | 2026-07-28 | [test] Reduce FastArray size in lower_limits_mode |  |
| no_call | — | `jeremymitaux/BlocRoc` | 2026-03-27 | feat(ticket): define data structures and storage ite |  |
| no_call | — | `ozalpd/OzzCodeGen` | 2026-03-23 | Bump version to 2.1.2 and rename MaxLength resource  |  |
| no_call | — | `ailyedu2030/micro-course` | 2026-07-14 | fix: disable subtitle_enable to prevent 20MB+ TTS re |  |
| no_call | — | `FlavioCFOliveira/gengo` | 2026-04-05 | cover remaining uncovered branches in IntBetween and |  |
| no_call | — | `MatthiasBurger-Coder/forensics_tracing` | 2025-09-26 | Add `maxStringLength` parameter to control string tr |  |
| no_call | — | `taoxee/VibeMeet2Notes` | 2026-02-28 | fix: aliyun ASR use DashScope OSS upload instead of  |  |
| no_call | — | `eclipse-openj9/openj9-docs` | 2025-03-20 | Add documentation for -Xtrace:maxstringlength option |  |
| no_call | — | `aws-observability/aws-otel-python-instrumentation` | 2026-06-16 | fix(debugger): align capture-limit defaults with Jav |  |
| no_call | — | `v8/v8` | 2026-06-15 | [test] Reduce FastArray size in lower_limits_mode |  |
| no_call | — | `schizoidcock/mcx` | 2026-02-28 | fix(mcp): bug fixes and input validation |  |
| no_call | — | `Ishou/wordsparrow` | 2026-07-31 | fix(deps): update dependency tools.jackson.core:jack |  |

## Worth reading

- **mkarjun/LCS@d16945f3** — fix(lambda): raise Jackson maxStringLength for large inline zip uploads (#412) (#418)
  - value: `100000000`  files changed: 2  library confirmed: True
  - `.maxStringLength(MAX_STRING_LENGTH)`
- **mmaudet/eu-dss-module@ff05ad9b** — fix(server): raise Jackson maxStringLength to 200M so large docs (base64-in-JSON) parse — 
  - value: `200000000`  files changed: 1  library confirmed: True
  - `.maxStringLength(MAX_JSON_STRING_LEN)`
- **havochvatten/MSP-Symphony@92f60258** — Override maxStringLength
  - value: `2147483647`  files changed: 4  library confirmed: True
  - `.maxStringLength(Integer.MAX_VALUE)`
- **521mc/qwer@843b149e** — fix(minecraft): render nested return objects without [Object] truncation in planner output
  - value: `None`  files changed: 2  library confirmed: None
  - `maxStringLength: 10_000,`
- **jss-shawn/ggs@0ecda619** — feat(FactSystem): add maxStringLength metadata with string validation
  - value: ``  files changed: 7  library confirmed: None
  - `int Fact::maxStringLength() const`
- **nestjs/nest@979a8e2f** — fix(common): Fix skipping maxArrayLength and maxStringLength option
  - value: `None`  files changed: 2  library confirmed: None
  - `if (typeof this.options.maxStringLength !== 'undefined') {; it('should respect maxStringLength when set to 0', () => {`
- **nestjs/nest@3d1b44c0** — Merge pull request #16230 from chojs23/fix/console-logger-option
  - value: `None`  files changed: 2  library confirmed: None
  - `if (typeof this.options.maxStringLength !== 'undefined') {; it('should respect maxStringLength when set to 0', () => {`
- **openclaw/mcporter@4a07ceed** — fix(cli): prevent silent string truncation to 10k characters in raw output (#22)
  - value: `None`  files changed: 2  library confirmed: None
  - `console.log(inspect(raw, { depth: 2, maxStringLength: null, breakLength: 80 }));`
- **TwoHeadsDragon/metersphere@e30f7ef2** — build: jackson-core default maxStringLength 调整
  - value: `JSON.DEFAULT_MAX_STRING_LEN).build()`  files changed: 3  library confirmed: True
  - `    public static final int DEFAULT_MAX_STRING_LEN = 20_000_000_0;;     public static final int DEFAULT_MAX_STRING_LEN = 20_000_000_0;`
- **skjolber/json-log-filter@03a61b93** — Variuos fixes and cleanups (#262)
  - value: `None`  files changed: 22  library confirmed: None
  - `if(endQuoteIndex - offset >= maxStringLength + 2) {; if(endQuoteIndex - offset < maxStringLength + 2) {`
- **clockworkengineer/JSON_Lib@6e972638** — refactor(string): move max string length state from static to instance (task 3b)
  - value: `g_defaultStringLength ? g_defaultStringLength : kDefMaxStringLength`  files changed: 4  library confirmed: None
  - `String() : m_maxStringLength(g_defaultStringLength ? g_defaultStringLength : kDefMaxStringLength) {}`
- **dexie/Dexie.js@8df183b8** — Merge pull request #2290 from dexie/liz/rename-maxStringLength-to-largeStringThreshold
  - value: `deprecated`  files changed: 3  library confirmed: None
  - `// Validate largeStringThreshold (preferred) or maxStringLength (deprecated) —`
- **aself101/mcp-secure-server@3bb01491** — fix(pipeline-factory): thread maxStringLength from server options into Layer 1 (0.0.17-sec
  - value: `None`  files changed: 9  library confirmed: None
  - `- **pipeline-factory:** thread `maxStringLength` from server options into Layer 1 — the option exist; - `StructureValidationLayer` has accepted a `max`
- **Daniel-Alievsky/algart-tiff@d3b19f07** — TiffSampleType.Formatter: adding maxStringLength
  - value: `None`  files changed: 1  library confirmed: None
  - `private int maxStringLength = 10000;; return maxStringLength;`
- **dexie/dexie-cloud-sdk@f4421de1** — feat: string offloading support
  - value: `None`  files changed: 4  library confirmed: None
  - `private maxStringLength: number = DEFAULT_MAX_STRING_LENGTH; if (typeof val === 'string' && val.length > this.maxStringLength && this.maxStringLength `
- **dlta17/yaml-security-lib@3376a612** — v1.6.0
  - value: `None`  files changed: 5  library confirmed: None
  - `maxStringLength: 0,         // 0 = unlimited; * @param {{maxNodes?: number, maxAlias?: number, maxAliasDepth?: number, maxExpansion?: number, maxI`
- **dexie/Dexie.js@18f3a1bb** — feat(dexie-cloud): string offloading for long strings during sync (#2264)
  - value: `None`  files changed: 6  library confirmed: None
  - `maxStringLength?: number;; // Validate maxStringLength — Infinity disables offloading, otherwise must be`
- **apache/druid@27a8fc30** — minor: change maxStringLength default (#19198)
  - value: `None`  files changed: 9  library confirmed: None
  - `|`druid.indexing.formats.maxStringLength`|Maximum number of characters to store per string dimension; | maxStringLength | For `string` typed dimension`
- **dexie/Dexie.js@0a5b51d0** — rename maxStringLength to largeStringThreshold (keep backward compat)
  - value: `deprecated`  files changed: 3  library confirmed: None
  - `// Validate largeStringThreshold (preferred) or maxStringLength (deprecated) —`
- **CaoGiaHieu-dev/dynamic_logger@37d532c3** — [Release]: 0.5.0 - Fix: sync formatting, remove isolate claims. - Feature: minLevel, maxSt
  - value: `None`  files changed: 6  library confirmed: None
  - `- **Feature:** Added `maxStringLength` to `configure()` and `log()`. When truncation is; structure, `minLevel`, `colorEnabled`, `maxStringLength`, `fo`
- **Opetushallitus/kielitutkintorekisteri@e63d135f** — Pienennä Jackson maxStringLength -oletusarvo 10 megatavuun
  - value: `None`  files changed: 1  library confirmed: None
  - `fun RestClient.Builder.withJacksonStreamMaxStringLength(maxStringLength: Int = 10_000_000): RestClie`
- **ailyedu2030/micro-course@94109aac** — fix: inject Spring ObjectMapper and raise Jackson maxStringLength to 100MB
  - value: `MAX_STRING_LENGTH).build()`  files changed: 1  library confirmed: True
  - `    private static final int MAX_STRING_LENGTH = 100 * 1024 * 1024; // 100MB`
- **clockworkengineer/JSON_Lib@efc4d024** — Embedded Phase 6.4: compile-time configurable maxParserDepth and maxStringLength via CMake
  - value: `)`  files changed: 6  library confirmed: None
  - `REQUIRE(EmbeddedJSON::Limits::kMaxStringLength == EmbeddedJSON::Limits::maxStringLength());`
- **taras/executable.md@cec6dc1f** — fix: verbose log maxStringLength 200, trim GitHubComment content
  - value: `None`  files changed: 2  library confirmed: None
  - `inspect(value, { colors: true, compact: true, breakLength: Infinity, depth: 2, maxStringLength: 200 `
- **Hahn-Schickard/Open62541-Conan-Recipe@1b822348** — add 0011-undifine-maxStringLength.patch
  - value: `None`  files changed: 2  library confirmed: None
  - `- patch_file: "patches/0011-undifine-maxStringLength.patch"; patch_description: "Undefine maxStringLength definition for Windows builds"`
- **FasterXML/jackson-core@a004e978** — Fix #1538: increase default StreamReadConstraints.maxStringLength to 100M
  - value: `None`  files changed: 3  library confirmed: None
  - `#1538: Increase default `StreamReadConstraints.maxStringLength` to 100M (from 20M)`
- **andymerskin/spotr@0b3c64a0** — perf: add `maxStringLength` option operating on query + collection fields
  - value: `None`  files changed: 12  library confirmed: None
  - `### `maxStringLength` (optional); private _maxStringLength: number;`
- **aeonite-org/aeonite-cts@2deca4e5** — Add apply-budget overlength mutate test
  - value: `None`  files changed: 1  library confirmed: None
  - `"maxStringLength": 4; "errorBudget": "maxStringLength",`
- **dexie/Dexie.js@bceab2cf** — Merge pull request #2266 from dexie/liz/min-string-length
  - value: `None`  files changed: 2  library confirmed: None
  - `options.maxStringLength < MIN_STRING_LENGTH ||; `maxStringLength must be Infinity or a finite number in [${MIN_STRING_LENGTH}, ${MAX_SERVER_STRING_L`
- **adokky/zero-json@bc071925** — `ZeroJsonConfiguration`: `maxOutputBytes` -> `maxEncodedBytes`, added `maxStringLength`
  - value: `None`  files changed: 16  library confirmed: None
  - `maxLength: Int = config.maxStringLength; maxLength: Int = config.maxStringLength`
- **Uluops/-uluops-registry-mcp@a01a6b1e** — fix: raise per-string cap so realistic definition YAML passes direct MCP fields
  - value: `None`  files changed: 3  library confirmed: None
  - `// mcp-secure-server >= 0.0.17, which exposes maxStringLength at create time.; maxStringLength: 500 * 1024,`
- **dexie/dexie-web@ab8f4e91** — docs: add string offloading documentation
  - value: `None`  files changed: 3  library confirmed: None
  - `Strings longer than `maxStringLength` (default **32,768 characters**) are also offloaded to blob sto; maxStringLength: 32768, // default (32KB charact`
- **vdaburon/har-to-jmeter-convertor@f6cac376** — Add new classe MyMapperFactory to set the new streamReadConstraints maxStringLength
  - value: `getMaxStringLength()).build(`  files changed: 3  library confirmed: True
  - `.maxStringLength(getMaxStringLength()).build();`
- **ohbee-labs/-ohbee-safe-json@2a4a10e6** — feat(types): define SafeJsonOptions and SafeJsonInstance interfaces
  - value: `None`  files changed: 1  library confirmed: None
  - `maxStringLength?: number;`
- **aeonite-org/aeonite-specs@470bf3f5** — Document datatype/kind hints and value budgets
  - value: `None`  files changed: 1  library confirmed: None
  - ``maxPreconditions`, `maxValueNodes`, `maxValueDepth`, and `maxStringLength`; scalar values at depth `1`. `maxStringLength` limits the longest supplied`
- **brendadeeznuts1111/project-R-score@2cb44db5** — feat(console-depth): stripANSI wrapper + ignored-option runtime probes
  - value: `None`  files changed: 4  library confirmed: None
  - `* on Bun 1.4.0: `getters`, `maxArrayLength`, `maxStringLength`, `showProxy`,; test('Bun.inspect silently ignores maxStringLength / showProxy / numeric`
- **Dune172/d2r-skill-randomizer@596ea5c6** — Fix chat disable crash — keep widget types, neuter via maxStringLength/alwaysAcceptsKeyInp
  - value: `None`  files changed: 2  library confirmed: None
  - `"maxStringLength": 0; "maxStringLength": 0,`
- **proteinjs/util@4319235c** — chore: `DevLogWriter` increase `maxStringLength` (1k -> 2k).
  - value: `None`  files changed: 1  library confirmed: None
  - `maxStringLength: 2000,`
- **ethan-godden/Diaram@423d77e8** — Cap oversized debuggee String reads before truncation
  - value: `None`  files changed: 1  library confirmed: None
  - `// debugger before truncation to maxStringLength, so a pathological debuggee String; // way maxStringLength bounds the stored text; over-ceiling strin`
- **kesslerio/attio-mcp-server@14e42eb2** — fix: bump response maxStringLength from 40KB to 500KB for bulk search results
  - value: `None`  files changed: 1  library confirmed: None
  - `maxStringLength: 500000, // 500KB for response content - needed for bulk search results`
- **HelenB00/nest@b9fbf0e2** — fix(common): Fix skipping maxArrayLength and maxStringLength option
  - value: `None`  files changed: 2  library confirmed: None
  - `if (typeof this.options.maxStringLength !== 'undefined') {; it('should respect maxStringLength when set to 0', () => {`
- **AltoPelago/sansa@e026cc94** — Add mutation value budget limits
  - value: `None`  files changed: 8  library confirmed: None
  - `maxStringLength: 65536; `maxValueNodes`, `maxValueDepth`, and `maxStringLength` are planning budgets over supplied values fo`
- **emonkak/barebind@1dcde42c** — feat(debug.value): increase `maxStringLength` in DebugValueContext to 128
  - value: `None`  files changed: 2  library confirmed: None
  - `maxStringLength: 128,`
- **jdereg/json-io@b69fa0d0** — Performance: Optimize JsonWriter hot paths with member variable hoisting
  - value: `None`  files changed: 4  library confirmed: None
  - `* Pre-fetched: `skipNullFields`, `json5TrailingCommas`, `json5UnquotedKeys`, `maxStringLength`; private final int maxStringLength;`
- **kesslerio/attio-mcp-server@21d76dc0** — fix: bump response maxStringLength from 40KB to 500KB for bulk search results (#1110)
  - value: `None`  files changed: 1  library confirmed: None
  - `maxStringLength: 500000, // 500KB for response content - needed for bulk search results`
- **HelenB00/nest@cde50a08** — Merge pull request #16230 from chojs23/fix/console-logger-option
  - value: `None`  files changed: 2  library confirmed: None
  - `if (typeof this.options.maxStringLength !== 'undefined') {; it('should respect maxStringLength when set to 0', () => {`
- **ztur211/network-monitoring@c6301a2a** — fix(api): validate onboarding fieldValues are bounded strings or finite numbers
  - value: `None`  files changed: 4  library confirmed: None
  - `New `apps/api/src/common/validators/is-string-or-number-record.validator.ts` exports `IsStringOrNumb; @IsStringOrNumberRecord({ maxStringLength: 1000 `
- **dexie/Dexie.js@37676f73** — fix(cloud): enforce minimum maxStringLength of 100
  - value: `None`  files changed: 2  library confirmed: None
  - `options.maxStringLength < MIN_STRING_LENGTH ||; `maxStringLength must be Infinity or a finite number in [${MIN_STRING_LENGTH}, ${MAX_SERVER_STRING_L`
- **Uluops/-uluops-ops-mcp@c3116584** — docs(readme): document payload size limits (0.11.0)
  - value: `None`  files changed: 1  library confirmed: None
  - `maxStringLength: 128 * 1024,       // Layer 1 per-string cap (raw_markdown); The per-tool `maxArgsSize` (2 MB for `save_run`) and the 500 KB message e`
- **danfry1/bonsai-js@afa00ff7** — fix(security): bound parser recursion and cap method/string output sizes (#48)
  - value: `None`  files changed: 9  library confirmed: None
  - `- Added `maxStringLength` (default 100,000) and enforced it as a ceiling on every string produced by; - `maxStringLength` option on `bonsai(options)` `
- **emonkak/barebind@358a45cf** — refactor(debug): s/maxLength/maxStringLength/
  - value: `None`  files changed: 1  library confirmed: None
  - `maxStringLength: number;; maxStringLength: 16,`
- **bmc4j/bmc4j@e6f11346** — Bound symbolic-string length under StringMode.NONE via a bytecode transform (#314)
  - value: `it changes the bytecode)"`  files changed: 9  library confirmed: None
  - `        for (int i = 0; i < n; i++) {;         for (int i = 0; i < s.length(); i++) {`
- **WojciechKownacki/21kb-Engine@8cc3ed2c** — Add LIB-037/038: unified input limits and call-depth reentrancy guard
  - value: `None`  files changed: 6  library confirmed: None
  - `//   - maxStringLength: the largest a single String ScriptValue argument may; std::size_t maxStringLength = 65536U;`
- **MatthiasBurger-Coder/forensics_tracing@07e26b69** — Add `maxStringLength` parameter to control string truncation in BtmGen plugin and escape t
  - value: `None`  files changed: 3  library confirmed: None
  - `val maxStringLength: Property<Int> = objects.property(Int::class.java); maxStringLength.convention(0)`
- **Justino-code/dumpkit@ddac2d0b** — git commit -m "chore: prepare for v0.1.0 release
  - value: `None`  files changed: 18  library confirmed: None
  - `| `maxStringLength` | `number` | `5000` | Maximum string length |; | `maxStringLength` | `number` | `5000` | Maximum string length |`
- **whoughton/lz77@0ac13301** — Add benchmark tracking infrastructure and fix maxStringLength off-by-one
  - value: `None`  files changed: 9  library confirmed: None
  - `// escape-doubling branch. Blocks are kept short enough (< maxStringLength = 99); settings.maxStringLength = Math.pow(settings.refIntBase, 1) - 2 + se`
- **aboutcircles/group-tms@42b5cc98** — fix(logging): cap formatError output to prevent 400KB log lines
  - value: `None`  files changed: 2  library confirmed: None
  - `: inspect(current, { depth: 2, maxStringLength: 1000, breakLength: 120 });; it("truncates long string properties via maxStringLength", () => {`
- **eleven-labs/nest-profiler@33fe3cbb** — feat(nest-profiler): configurable body-capture limits with untruncated option (#218)
  - value: `None`  files changed: 10  library confirmed: None
  - `The inner content caps applied to every captured request/response body (`maxStringLength`, `maxItems; bodyCaptureLimits: { maxStringLength: 0, maxItem`
- **dmarigliano/super-router@0f7eaf64** — fix: keep redactText output within maxStringLength
  - value: `None`  files changed: 2  library confirmed: None
  - `] as const)("never returns more than maxStringLength when it %s", (_case, input, limit) => {; expect(redactText(input, { maxStringLength: limit }).len`
- **zb-sj/storybook-addon-react-grab@bf9f88bb** — docs: correct README — react-grab repo link, toolbar toggle behavior, option defaults
  - value: `None`  files changed: 1  library confirmed: None
  - `maxStringLength: 80,  // default: 80 — truncate long string arg values; | `maxStringLength` | `number` | `80` | Length limit for serialized string val`
- **schizoidcock/mcx@08254b52** — feat(cli): configurable result truncation in mcx_execute
  - value: `None`  files changed: 5  library confirmed: None
  - `| **Configurable Truncation** | Control result size via `truncate`, `maxItems`, `maxStringLength` |; | `maxStringLength` | `500` | Max string length |`
- **ohbee-labs/-ohbee-safe-json@64c3c35b** — test: add comprehensive test suite (62 tests across 6 files)
  - value: `None`  files changed: 6  library confirmed: None
  - `const result = safeClone(long, { maxStringLength: 100 }) as string;; const result = safeClone("hello", { maxStringLength: 100 }) as string;`
- **Arize-ai/project-rosetta-stone@c822728e** — Add AX synthetic request harness and increase serialization limit
  - value: `None`  files changed: 4  library confirmed: None
  - `maxStringLength: 10_000,`
- **trojs/logger@3e528802** — Updates documentation with new log options
  - value: `default: 1000, maximum length for strings before truncation in JSON format`  files changed: 1  library confirmed: None
  - `* maxStringLength (default: 1000, maximum length for strings before truncation in JSON format)`
- **Mearman/BSIF@cba22902** — feat(parser): add security limits for document size, depth, and string length
  - value: `None`  files changed: 2  library confirmed: None
  - `readonly maxStringLength?: number;   // default 64KB; const maxStringLen = limits?.maxStringLength ?? DEFAULT_MAX_STRING_LENGTH;`
- **schizoidcock/mcx@73d87e4f** — feat(mcp): add configurable truncation to mcx_run_skill and mcx_list
  - value: `None`  files changed: 2  library confirmed: None
  - `maxStringLength: z.number(); maxStringLength: params.maxStringLength,`
- **07artem132/SignalCli.NET@9e1c1376** — @
  - value: `None`  files changed: 5  library confirmed: None
  - `// StreamReadConstraints.maxStringLength за замовчуванням = 20 000 000 символів.; // StreamReadConstraints.maxStringLength за замовчуванням = 20 000 0`
- **ojson-platform/http@f3d0d501** — docs: expand API Overview in all with-* readmes
  - value: `None`  files changed: 5  library confirmed: None
  - `### options.maxStringLength`
- **FortnoxAB/reactive-wizard@6f06ced3** — Set maxStringLength in Jackson JsonFactory to maxResponseSize in HttpClient.
  - value: `config.getMaxResponseSize()`  files changed: 2  library confirmed: True
  - `.maxStringLength(config.getMaxResponseSize())`
