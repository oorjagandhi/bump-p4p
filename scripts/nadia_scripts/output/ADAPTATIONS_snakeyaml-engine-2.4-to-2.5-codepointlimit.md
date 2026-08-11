# Adaptations to `snakeyaml-engine-2.4-to-2.5-codepointlimit`

Commits touching `setCodePointLimit`, classified by the VALUE they set. The library's own default is taken as 3,145,728.

**RAISE is the only verdict that can yield a case.** A knob left at the library's default behaves identically before and after for every input size, so it cannot produce a pass/fail/pass differential; LOWER is security hardening. Measured five for five on snakeyaml, the split follows what the project is: applications raise, libraries and plugins expose a knob.

36 distinct commit(s) after fork collapse; **12 worth reading**.

| verdict | value | repo | date | commit | forks |
|---|---:|---|---|---|---:|
| raise | 67,108,864 | `AxDevv/FAWE-Folia` | 2022-09-26 | Update Upstream | 14 |
| raise | 67,108,864 | `EngineHub/WorldEdit` | 2022-09-26 | Use SnakeYaml 1.32+, set loader code point limit. (# | 6 |
| raise | 52,428,800 | `fglock/PerlOnJava` | 2026-03-14 | Fix Storable YAML codePointLimit for large CPAN meta |  |
| raise | 2,147,483,647 | `OussamaLakhdar90/veritas` | 2026-07-05 | Fix info/servers placeholder in corrected YAML (rais |  |
| raise | 10,485,760 | `Enterprise-Content-Management/infoarchive-sip-sdk` | 2024-09-04 | Minor release for 12.8.4 to Increase codePointLimit  |  |
| needs_reading | context.getYamlCodePointLimit() | `jenkinsci/configuration-as-code-plugin` | 2023-11-13 | SnakeYaml loader options to allow configuration of C | 1 |
| needs_reading | (int)length + 10000 | `ome/bioformats` | 2025-03-19 | Miscellaneous fixes |  |
| needs_reading | final int codePointLimit | `jenkinsci/pipeline-utility-steps-plugin` | 2023-06-19 | Merge pull request #206 from pascal-hofmann/feature/ |  |
| needs_reading | 5MB | `HyacinthHaru/HikariCanvas` | 2026-05-16 | M16-P1: 安全 P0 7 项（鉴权 / DoS / IDOR / Origin） |  |
| needs_reading | final int codePointLimit | `jenkinsci/pipeline-utility-steps-plugin` | 2023-04-14 | [JENKINS-71077] Allow overriding codePointLimit to a |  |
| needs_reading | codePointLimit | `membrane/api-gateway` | 2026-08-10 | Lift the 3 MiB size limit on OpenAPI documents (#312 |  |
| needs_reading | this.getOptions().getCodePointLimit() | `bspfsystems/YamlConfiguration` | 2022-11-02 | Updates: |  |
| lower | 8,192 | `slxxxj/jetbrains-cc-gui` | 2026-03-02 | Feature/v0.2.4 (#513) (#536) | 3 |
| lower | 8,192 | `slxxxj/jetbrains-cc-gui` | 2026-03-02 | Feature/v0.2.4 (#513) | 3 |
| lower | 5 | `akashgit/jackson-dataformats-text` | 2022-09-24 | support overriding the codePointLimit (#339) | 2 |
| lower | 65,536 | `anishi1222/multi-agent-code-reviewer` | 2026-03-02 | security: address security review findings (#47) |  |
| lower | 262,144 | `operaton/operaton-starter` | 2026-06-14 | feat(story-8-2): Add examples configuration and safe |  |
| lower | 1,048,576 | `jakefearsd/wikantik` | 2026-05-03 | security(mcp): strict page-name validator + YAML loa |  |
| no_call | — | `19h/mw` | 2018-02-08 | Allow limiting comment length by characters rather t | 33 |
| no_call | — | `slxxxj/jetbrains-cc-gui` | 2026-03-03 | Feature/v0.2.4 (#513) (#536) (#556) | 3 |
| no_call | — | `typesafegithub/github-actions-typing` | 2024-05-10 | fix(deps): update dependency com.charleskorn.kaml:ka | 1 |
| no_call | — | `ljhthink/Prism` | 2026-08-09 | feat(skills): M4 Phase B SKILL.md 解析器 + SkillRegistr |  |
| no_call | — | `slackhq/foundry` | 2024-04-24 | Update dependency com.charleskorn.kaml:kaml to v0.59 |  |
| no_call | — | `adorsys/keycloak-config-cli` | 2026-02-25 | Fix YAML codePointLimit test |  |
| no_call | — | `adorsys/keycloak-config-cli` | 2026-02-25 | Fix YAML codePointLimit test |  |
| no_call | — | `wikimedia/mediawiki-extensions` | 2025-01-16 | Update git submodules |  |
| no_call | — | `wikimedia/mediawiki-extensions-ReportIncident` | 2024-12-03 | dialog: Remove jquery.codePointLimit dependency |  |
| no_call | — | `zerobias-org/util` | 2026-02-09 | fix(build-tools): SnakeYAML code point limit and opt |  |
| no_call | — | `wikimedia/mediawiki-extensions-ReportIncident` | 2025-01-16 | Merge "dialog: Remove jquery.codePointLimit dependen |  |
| no_call | — | `izumacha/batch-scheduler` | 2026-07-15 | fix(config): loadFromStringにもオーバーサイズ拒否を追加 (#26) |  |
| no_call | — | `izumacha/batch-scheduler` | 2026-07-17 | fix(config): actually enforce YAML alias-bomb / nest |  |
| no_call | — | `wikimedia/mediawiki-extensions-ReportIncident` | 2024-11-29 | dialog: Prevent filling details over the character l |  |
| no_call | — | `wikimedia/mediawiki-extensions` | 2024-11-29 | Update git submodules |  |
| no_call | — | `wikimedia/mediawiki-extensions-ReportIncident` | 2023-10-31 | Enforce a character count limit on textarea fields |  |
| no_call | — | `wikimedia/mediawiki-extensions` | 2023-11-02 | Update git submodules |  |
| no_call | — | `PingCAP-QE/ee-ops` | 2023-12-17 | chore(deps): update dependency configuration-as-code |  |

## Worth reading

- **AxDevv/FAWE-Folia@87f68068** — Update Upstream
  - value: `67108864`  files changed: 2  library confirmed: False
  - `loaderOptions.setCodePointLimit(yamlCodePointLimit);`
- **EngineHub/WorldEdit@0ef38b52** — Use SnakeYaml 1.32+, set loader code point limit. (#2194)
  - value: `67108864`  files changed: 2  library confirmed: False
  - `loaderOptions.setCodePointLimit(yamlCodePointLimit);`
- **fglock/PerlOnJava@f4bc5594** — Fix Storable YAML codePointLimit for large CPAN metadata
  - value: `52428800`  files changed: 2  library confirmed: True
  - `.setCodePointLimit(50 * 1024 * 1024)  // 50MB limit for large CPAN metadata files`
- **OussamaLakhdar90/veritas@e6238ac0** — Fix info/servers placeholder in corrected YAML (raise YAML limits + Swagger-2 servers) (#2
  - value: `2147483647`  files changed: 2  library confirmed: False
  - `options.setCodePointLimit(Integer.MAX_VALUE);   // no 3 MB cap — match swagger-parser`
- **Enterprise-Content-Management/infoarchive-sip-sdk@4b617cd8** — Minor release for 12.8.4 to Increase codePointLimit of LoaderOptions in Snakeyaml from 3M 
  - value: `10485760`  files changed: 4  library confirmed: False
  - `loaderOptions.setCodePointLimit(CODE_POINT_LIMIT);`
- **jenkinsci/configuration-as-code-plugin@652ee9ba** — SnakeYaml loader options to allow configuration of CodePointLimit for YAML input files (#2
  - value: `context.getYamlCodePointLimit()`  files changed: 3  library confirmed: False
  - `        prop = getPropertyOrEnv(CASC_YAML_CODE_POINT_LIMIT_ENV, CASC_YAML_CODE_POINT_LIMIT_PROPERTY);`
- **ome/bioformats@a1c16b11** — Miscellaneous fixes
  - value: `(int)length + 10000`  files changed: 2  library confirmed: False
  - `loadingConfig.setCodePointLimit((int)length + 10000);`
- **jenkinsci/pipeline-utility-steps-plugin@b750cd96** — Merge pull request #206 from pascal-hofmann/feature/add-codepointlimit
  - value: `final int codePointLimit`  files changed: 3  library confirmed: False
  - `	private static /*almost final*/ int MAX_CODE_POINT_LIMIT = Integer.getInteger(MAX_CODE_POINT_LIMIT_PROPERTY, LIBRARY_DEFAULT_CODE_POINT_LIMIT);; 	pri`
- **HyacinthHaru/HikariCanvas@46952698** — M16-P1: 安全 P0 7 项（鉴权 / DoS / IDOR / Origin）
  - value: `5MB`  files changed: 18  library confirmed: None
  - `- `Interpolator`：单值 `MAX_VALUE_LEN=16384`、整次 `MAX_OUTPUT_LEN=1048576`；超阈抛 IAE。常量公开。;         int wsAuthTimeoutSeconds = 5;;     private static final i`
- **jenkinsci/pipeline-utility-steps-plugin@78e3face** — [JENKINS-71077] Allow overriding codePointLimit to allow reading larger yaml files
  - value: `final int codePointLimit`  files changed: 3  library confirmed: False
  - `	private static /*almost final*/ int MAX_CODE_POINT_LIMIT = Integer.getInteger(MAX_CODE_POINT_LIMIT_PROPERTY, LIBRARY_DEFAULT_CODE_POINT_LIMIT);; 	pri`
- **membrane/api-gateway@f2947f12** — Lift the 3 MiB size limit on OpenAPI documents (#3122)
  - value: `codePointLimit`  files changed: 4  library confirmed: False
  - ` * default here is {@link Integer#MAX_VALUE}. Set {@value #CODE_POINT_LIMIT_PROPERTY} to put a;         String value = System.getProperty(CODE_POINT_L`
- **bspfsystems/YamlConfiguration@b0eb7bbc** — Updates:
  - value: `this.getOptions().getCodePointLimit()`  files changed: 8  library confirmed: False
  - `        this.codePointLimit = 3 * 1024 * 1024; // 3 MB;      * {@link Integer#MAX_VALUE} (please use this wisely).;      * {@link Integer#MAX_VALUE} (`
