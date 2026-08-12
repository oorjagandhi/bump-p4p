# Adaptations to `snakeyaml-1.25-to-1.26-maxaliases`

Commits touching `setMaxAliasesForCollections`, classified by the VALUE they set. The library's own default is taken as 50.

**RAISE is the only verdict that can yield a case.** A knob left at the library's default behaves identically before and after for every input size, so it cannot produce a pass/fail/pass differential; LOWER is security hardening. Measured five for five on snakeyaml, the split follows what the project is: applications raise, libraries and plugins expose a knob.

27 distinct commit(s) after fork collapse; **11 worth reading**.

| verdict | value | repo | date | commit | forks |
|---|---:|---|---|---|---:|
| raise | 1,000 | `jdxia/shardingsphere` | 2024-03-18 | Override maxAliasesForCollections at LoaderOptions ( | 6 |
| raise | 512 | `kangarko/Foundation` | 2021-04-12 | SimpleYaml > setMaxAliasesForCollections to 512, clo | 1 |
| raise | 2,147,483,647 | `YuaZer/CatServer` | 2022-09-19 | Fix java.lang.NoSuchMethodError: org.yaml.snakeyaml. | 1 |
| raise | 100 | `Mirantis/pipeline-library` | 2024-05-13 | setMaxAliasesForCollections |  |
| needs_reading | options, Integer.MAX_VALUE | `liquibase/liquibase` | 2025-05-30 | Fix for YAML changelogs with many references to be p | 1 |
| needs_reading | int value | `link-it/govcat` | 2026-04-17 | Issue 264: resi configurabili i parametri SnakeYAML  |  |
| needs_reading | limit | `Locke/owl-performance` | 2021-04-28 | optionally set SnakeYAML maxAliasesForCollections pa |  |
| needs_reading | 50)` + `setCodePointLimit(5MB | `HyacinthHaru/HikariCanvas` | 2026-05-16 | M16-P1: 安全 P0 7 项（鉴权 / DoS / IDOR / Origin） |  |
| needs_reading | maxAliasesForCollections | `circe/circe-yaml` | 2022-09-14 | Merge pull request #205 from hcdeng/master |  |
| needs_reading | final int maxAliasesForCollections | `jenkinsci/pipeline-utility-steps-plugin` | 2022-07-01 | Provide some ways of specifying maxAliasesForCollect |  |
| needs_reading | final int maxAliasesForCollections | `jenkinsci/pipeline-utility-steps-plugin` | 2023-01-09 | Merge pull request #152 from jenkinsci/maxaliasforco |  |
| knob_at_default | 50 | `keaipiao/sosoGitHub` | 2026-05-22 | docs(repo-detail): PR-2 /autoplan 评审收敛 — ADR-14~23 全 |  |
| knob_at_default | 50 | `keaipiao/sosoGitHub` | 2026-05-22 | feat(repo-detail): PR-2 阶段 3 D2 (1/N) — B2 V20 埋点表 + |  |
| knob_at_default | 50 | `ljhthink/Prism` | 2026-08-09 | feat(skills): M4 Phase B SKILL.md 解析器 + SkillRegistr |  |
| knob_at_default | 50 | `jakefearsd/wikantik` | 2026-05-03 | security(mcp): strict page-name validator + YAML loa |  |
| knob_at_default | 50 | `watson-song/snap-agent` | 2026-07-22 | feat: v0.5 Plugin Architecture Refactor — hot-plugga |  |
| lower | 0 | `slxxxj/jetbrains-cc-gui` | 2026-03-03 | fix: harden skill discovery against path traversal a | 3 |
| lower | 10 | `slxxxj/jetbrains-cc-gui` | 2026-03-02 | Feature/v0.2.4 (#513) (#536) | 3 |
| lower | 10 | `slxxxj/jetbrains-cc-gui` | 2026-03-02 | Feature/v0.2.4 (#513) | 3 |
| lower | 10 | `yasirhamza/AndroDR` | 2026-04-02 | fix: input validation hardening from security audit |  |
| lower | 0 | `pt9912/d-migrate` | 2026-06-06 | feat(parquet): S4 — ParquetSingleFileManifest{Writer |  |
| no_call | — | `apache/shardingsphere` | 2024-12-11 | Optimize loader options config of YAML, change maxAl | 4 |
| no_call | — | `slxxxj/jetbrains-cc-gui` | 2026-03-03 | Feature/v0.2.4 (#513) (#536) (#556) | 3 |
| no_call | — | `Mirantis/pipeline-library` | 2024-05-13 | Revert "setMaxAliasesForCollections" |  |
| no_call | — | `link-it/govway` | 2026-03-31 | [Utils, GovWayCore, GovWayConsole] |  |
| no_call | — | `izumacha/batch-scheduler` | 2026-07-17 | fix(config): actually enforce YAML alias-bomb / nest |  |
| no_call | — | `leadingfellows/config-parser` | 2026-05-20 | fix: Yaml::parse regression on symfony/yaml 6.x |  |

## Worth reading

- **jdxia/shardingsphere@eeac1c7c** — Override maxAliasesForCollections at LoaderOptions (#30505)
  - value: `1000`  files changed: 2  library confirmed: True
  - `result.setMaxAliasesForCollections(1000);`
- **kangarko/Foundation@c6b2ccc9** — SimpleYaml > setMaxAliasesForCollections to 512, closes #98
  - value: `512`  files changed: 1  library confirmed: True
  - `loaderOptions.setMaxAliasesForCollections(512);`
- **YuaZer/CatServer@6d6b2d34** — Fix java.lang.NoSuchMethodError: org.yaml.snakeyaml.LoaderOptions.setMaxAliasesForCollecti
  - value: `2147483647`  files changed: 1  library confirmed: True
  - `try { if (!incompatible) loaderOptions.setMaxAliasesForCollections(Integer.MAX_VALUE); /* // SPIGOT-5881: Not `
- **Mirantis/pipeline-library@5808aa5c** — setMaxAliasesForCollections
  - value: `100`  files changed: 1  library confirmed: True
  - `options.setMaxAliasesForCollections(100)`
- **liquibase/liquibase@bc566aa8** — Fix for YAML changelogs with many references to be parsed successfully with snakeyaml (#69
  - value: `options, Integer.MAX_VALUE`  files changed: 2  library confirmed: True
  - `SnakeYamlUtil.setMaxAliasesForCollections(options, Integer.MAX_VALUE);`
- **link-it/govcat@6b8dc365** — Issue 264: resi configurabili i parametri SnakeYAML in YamltoJsonUtils.java: maxAliasesFor
  - value: `int value`  files changed: 9  library confirmed: True
  - `	private static int maxAliasesForCollections = 500;; 	private static int nestingDepthLimit = 50;; 		options.setCodePointLimit(Integer.MAX_VALUE);`
- **Locke/owl-performance@50438d08** — optionally set SnakeYAML maxAliasesForCollections parameter
  - value: `limit`  files changed: 3  library confirmed: True
  - `loadingConfig.setMaxAliasesForCollections(limit);`
- **HyacinthHaru/HikariCanvas@46952698** — M16-P1: 安全 P0 7 项（鉴权 / DoS / IDOR / Origin）
  - value: `50)` + `setCodePointLimit(5MB`  files changed: 18  library confirmed: True
  - `- `Interpolator`：单值 `MAX_VALUE_LEN=16384`、整次 `MAX_OUTPUT_LEN=1048576`；超阈抛 IAE。常量公开。;         int wsAuthTimeoutSeconds = 5;;     private static final i`
- **circe/circe-yaml@6434da6b** — Merge pull request #205 from hcdeng/master
  - value: `maxAliasesForCollections`  files changed: 3  library confirmed: True
  - `options.setMaxAliasesForCollections(maxAliasesForCollections)`
- **jenkinsci/pipeline-utility-steps-plugin@c138cfb7** — Provide some ways of specifying maxAliasesForCollections to readYaml step
  - value: `final int maxAliasesForCollections`  files changed: 4  library confirmed: True
  - `	public static /*almost final*/ int DEFAULT_MAX_ALIASES_FOR_COLLECTIONS = Integer.getInteger(DEFAULT_MAX_ALIASES_PROPERTY, -1);; 	public static /*almo`
- **jenkinsci/pipeline-utility-steps-plugin@3b6b5a55** — Merge pull request #152 from jenkinsci/maxaliasforcollections
  - value: `final int maxAliasesForCollections`  files changed: 4  library confirmed: True
  - `	public static final int HARDCODED_CEILING_MAX_ALIASES_FOR_COLLECTIONS = 1000;; 	private static /*almost final*/ int DEFAULT_MAX_ALIASES_FOR_COLLECTIO`
