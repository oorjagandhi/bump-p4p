# Adaptations to `fastjson-1.2.80-to-1.2.83-autotype`

Commits touching `safeMode`, classified by the VALUE they set. The library's own default is taken as 0.

**RAISE is the only verdict that can yield a case.** A knob left at the library's default behaves identically before and after for every input size, so it cannot produce a pass/fail/pass differential; LOWER is security hardening. Measured five for five on snakeyaml, the split follows what the project is: applications raise, libraries and plugins expose a knob.

125 distinct commit(s) after fork collapse; **35 worth reading**.

| verdict | value | repo | date | commit | forks |
|---|---:|---|---|---|---:|
| needs_reading | — | `CubePlus1/screeps-cn` | 2026-05-17 | Add safeMode map overlay and fix zoom during animati | 2 |
| needs_reading | — | `0x7eTeam/fastjson-1.2.83-rce` | 2026-07-20 | Fastjson 1.2.83 @JSONType RCE 漏洞测试环境 | 2 |
| needs_reading | — | `alib8b8/aflare` | 2026-08-09 | fix: --safe-mode 接入 PolicyExecutor，safeMode 贯穿调用链 |  |
| needs_reading | — | `hat47x/kj-atlas` | 2026-08-12 | docs(issues): escalate SEC-AI-SAFEMODE-01 — no SafeM |  |
| needs_reading | — | `jongtix/aaa-collector` | 2026-07-08 | ✨ feat(collector): SafeMode 저장 계층에 TTL + 백오프 수준 지속 저 |  |
| needs_reading | — | `Gameknight963/MZDO` | 2026-07-27 | added safemode |  |
| needs_reading | — | `AceSLS/SLSsteam` | 2026-07-27 | fix(SafeMode): Only download updates.yaml when eithe |  |
| needs_reading | — | `designer-kevinxie/wenzi` | 2026-07-30 | Merge pull request #1 from designer-kevinxie/docs/do |  |
| needs_reading | — | `hat47x/kj-atlas` | 2026-08-12 | docs(issues): record empirical confirmation of SEC-A |  |
| needs_reading | — | `hat47x/kj-atlas` | 2026-08-01 | fix(security): apply SafeMode to document.json in ex |  |
| needs_reading | — | `readmeio/markdown` | 2026-08-12 | fix: propagate safeMode thru components (#1593) |  |
| needs_reading | — | `markup-carve/carve-php` | 2026-07-30 | docs: state the default explicitly, and stop the Saf |  |
| needs_reading | — | `hat47x/kj-atlas` | 2026-08-12 | docs(issues): complete SEC-AI-SAFEMODE-01 decision p |  |
| needs_reading | — | `hat47x/kj-atlas` | 2026-07-22 | fix(security): close SafeMode text-leak gaps in expo |  |
| needs_reading | — | `GomdimApps/web-escpos-printer` | 2026-08-13 | feat: add safeMode compatibility fallback for PDF417 |  |
| needs_reading | — | `hat47x/kj-atlas` | 2026-08-02 | docs(DOMAIN-W-ITERATION-01): record SafeMode share b |  |
| needs_reading | — | `Naiker12/Sparta-Agent` | 2026-07-15 | feat(security): expose safe_mode status to frontend |  |
| needs_reading | — | `GomdimApps/web-escpos-printer` | 2026-08-13 | Merge pull request #3 from GomdimApps/printer |  |
| needs_reading | encoder, element.safeMode, 'qrcode', ( | `GomdimApps/web-escpos-printer` | 2026-08-13 | feat: add safeMode support to qrcode element to enab |  |
| needs_reading | — | `hat47x/kj-atlas` | 2026-08-02 | feat(DOMAIN-W-ITERATION-01): add verified SafeMode s |  |
| needs_reading | — | `hat47x/kj-atlas` | 2026-08-07 | test(security): cover SafeMode on shipped worker exp |  |
| needs_reading | — | `ksmartdata/docker-images` | 2026-08-04 | enable fastjson safeMode for rocketmq broker/nameser |  |
| needs_reading | — | `intelseclab/poc-archive` | 2026-07-31 | feat: ingest CVE-2026-16723 Alibaba Fastjson 1.2.68- |  |
| needs_reading | — | `LoRexxar/Kunlun-M` | 2026-05-21 | feat: 扩展 framework-dependency 规则覆盖 Log4j/Fastjson/Co |  |
| needs_reading | — | `huimzjty/vulwiki` | 2022-09-13 | fastjson safeMode |  |
| needs_reading | — | `sanhng/nhungnguoivodanh` | 2020-06-04 | Updated fastjson_safemode (markdown) |  |
| needs_reading | — | `sanhng/nhungnguoivodanh` | 2020-05-31 | Updated fastjson_safemode (markdown) |  |
| needs_reading | — | `sanhng/nhungnguoivodanh` | 2020-03-28 | Updated fastjson_safemode (markdown) |  |
| needs_reading | — | `sanhng/nhungnguoivodanh` | 2020-03-28 | Created fastjson_safemode (markdown) |  |
| needs_reading | — | `jd-opensource/joyrpc` | 2020-05-29 | Fastjson默认改成SafeMode |  |
| needs_reading | — | `lWoHvYe/unicorn` | 2021-10-22 | fastjson-autoType白名单机制。待转换为safeMode |  |
| needs_reading | — | `dinosn/fastjson-jsontype-rce-lab` | 2026-07-27 | Add fastjson2 autoType lab: remote class load with a |  |
| needs_reading | — | `w6fux5/ChainKit` | 2026-04-03 | test(tron): add Nile testnet E2E integration tests |  |
| needs_reading | — | `lWoHvYe/unicorn` | 2021-10-23 | 引入fastjson.properties配置，safeMode改造，完成50%。开启之后，部分情况下从 |  |
| needs_reading | — | `lWoHvYe/unicorn` | 2021-10-23 | fastjson开启safeMode后，从redis中取出的对象将变为JSON(JSONObject、J |  |
| no_call | — | `GAMPA228/cpa` | 2026-06-06 | Merge pull request #3735 from router-for-me/safemode | 44 |
| no_call | — | `Wiks3n-0/tron` | 2022-05-24 | dependency: upgrade for security. | 13 |
| no_call | — | `AceSLS/SLSsteam` | 2026-06-11 | Merge pull request #121 from yesyes0649/20260610-saf | 1 |
| no_call | — | `AceSLS/SLSsteam` | 2026-07-14 | chore(SafeMode): Bump version | 1 |
| no_call | — | `Fithub-System/Fithub-portal-admin` | 2026-07-19 | Phase 1.3: SafeMode Offline Sync Engine |  |
| no_call | — | `kamanager2012/agent-constraint-system` | 2026-07-22 | fix: persistent SafeMode and AssetTracker in Codex+G |  |
| no_call | — | `drvolpe/TALOS` | 2026-07-31 | Merge pull request #45 from drvolpe/update-us-ignore |  |
| no_call | — | `1diot9/FastjsonExpToolkit` | 2026-08-02 | Include safemode_enabled in version benchmark output |  |
| no_call | — | `zromick/video-compressor` | 2026-05-31 | Add SafeMode: two-pass compression to prevent file e |  |
| no_call | — | `1diot9/FastjsonExpToolkit` | 2026-08-02 | Wire SafeMode probe into version detection results. |  |
| no_call | — | `jongtix/aaa-collector` | 2026-07-08 | 📝 docs(collector): SafeMode TTL·백오프 라이프사이클 @MX 주석·Ja |  |
| no_call | — | `Hackebein/wiki.vrchat.com` | 2026-07-26 | Created page with "[[File:Safemode.png|thumb|"안전 모드" |  |
| no_call | — | `Gyerchak/OpenCodeBox` | 2026-08-13 | refactor: rename sonicsafe.sh to opencode-safemode.s |  |
| no_call | — | `nangchang/DevIsland` | 2026-06-15 | fix: show settings pane for safemoded plugins with r |  |
| no_call | — | `hat47x/kj-atlas` | 2026-08-13 | docs(issues): mark SEC-AI-SAFEMODE-01 AC-7 done (out |  |
| no_call | — | `1diot9/FastjsonExpToolkit` | 2026-08-02 | Complete SafeMode probe wiring across API, Web, and  |  |
| no_call | — | `Felix-LeeSM/table-view` | 2026-05-27 | feat(sql): add PostgreSQL MERGE parser safemode (#16 |  |
| no_call | — | `Olegerorr/version_InfiniteYieldPlus` | 2026-06-24 | Disable SafeMode in saveinstance.luau |  |
| no_call | — | `sas152ana/Telegram-SafeMode` | 2026-05-13 | Rename Telegram-SafeMode.txt to Telegram-SafeMode.pa |  |
| no_call | — | `sonatique/Adoc.Net` | 2026-06-12 | fix(security)!: default ParseOptions.SafeMode to Saf |  |
| no_call | — | `hat47x/kj-atlas` | 2026-08-13 | docs(issues): mark SEC-AI-SAFEMODE-01 Done (all ACs  |  |
| no_call | — | `AceSLS/SLSsteam` | 2026-07-28 | chore(SafeMode): Bump version |  |
| no_call | — | `trankhahao1305-spec/windear-landing` | 2026-08-10 | Add SafeMode resilience for Resend daily quota limit |  |
| no_call | — | `AceSLS/SLSsteam` | 2026-07-22 | chore(SafeMode): Update |  |
| no_call | — | `hat47x/kj-atlas` | 2026-08-13 | docs(dogfood): record P0 SafeMode fix + document bou |  |
| no_call | — | `Hackebein/wiki.vrchat.com` | 2026-07-20 | Created page with "[[File:Safemode.png|thumb|L'icône |  |
| no_call | — | `OneUptime/blog` | 2026-08-07 | validate: 2026-08-07-hdfs-safemode-block-reports |  |
| no_call | — | `DineroLabs/dinero-v8` | 2026-08-06 | feat(rpc): reorg.status, registered alongside safemo |  |
| no_call | — | `AceSLS/SLSsteam` | 2026-07-28 | chore(SafeMode): Update res/updates.yaml |  |
| no_call | — | `875341583/RTS_Game` | 2026-07-27 | P3-1: Replay system — record/playback command stream |  |
| no_call | — | `pr1m0rdial/Stuff` | 2026-07-04 | Create safemode |  |
| no_call | — | `nangchang/DevIsland` | 2026-06-09 | Merge pull request #262 from nangchang/gemini/safemo |  |
| no_call | — | `piotogomes/COOEP` | 2026-07-07 | safemode |  |
| no_call | — | `Neigbjik-Tso/flowexis` | 2026-07-20 | graphql-alt: Add Epoch.safeMode |  |
| no_call | — | `majidhussainqadri1-dot/20-sabri-unified-application-shell` | 2026-08-01 | test: cover package ownership, SafeMode ordering, an |  |
| no_call | — | `jeffnash/CLIProxyAPI` | 2026-06-06 | Merge pull request #3735 from router-for-me/safemode |  |
| no_call | — | `AceSLS/SLSsteam` | 2026-08-04 | chore(SafeMode): Add client hash from 2026.08.04 |  |
| no_call | — | `opencolin/clawcamp-site` | 2026-04-05 | Rebrand safemode site from Maritime to SafeMode with |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Retry official p1ctl Exit Safemode probe |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Run official p1ctl Exit Safemode probe |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Retry official palera1n Exit Safemode V3 |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Run official palera1n Exit Safemode V3 |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Retry official palera1n Exit Safemode V3 |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Run official palera1n Exit Safemode V3 |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Run official palera1n Exit Safemode V2 |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Dispatch official Exit Safemode linker patch |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Dispatch official Exit Safemode linker patch |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Retry official palera1n Exit Safemode helper |  |
| no_call | — | `code-saturne/code_saturne` | 2026-07-31 | [Lagr] add an option to set fail_safemode. |  |
| no_call | — | `majidhussainqadri1-dot/20-sabri-unified-application-shell` | 2026-08-01 | review: make File 22 SafeMode reflection independent |  |
| no_call | — | `majidhussainqadri1-dot/20-sabri-unified-application-shell` | 2026-08-01 | review: eagerly load package-owned SafeMode before F |  |
| no_call | — | `sas152ana/Telegram-SafeMode` | 2026-07-05 | Update Telegram-SafeMode.patch |  |
| no_call | — | `jayool/LumaDeck` | 2026-08-06 | fix(slssteam): stop forcing SafeMode=yes, let SLSste |  |
| no_call | — | `kim666489/Dobina-cli-client` | 2026-07-05 | Add safemode |  |
| no_call | — | `kim666489/Dobina-cli-client` | 2026-07-05 | add SafeMode |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Retry official p1ctl Exit Safemode probe status |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Check official p1ctl Exit Safemode probe status |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Add official p1ctl Exit Safemode injection verificat |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Add shared official Exit Safemode device phase |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Add small official Exit Safemode V3 workflow |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Retry official Exit Safemode linker patch dispatch |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Retry official Exit Safemode XPC linker fix |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Apply official Exit Safemode XPC linker fix |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Run exact official palera1n Exit Safemode action |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Add exact official palera1n Exit Safemode workflow |  |
| no_call | — | `hoanbklucky/eel4664-robotics-labs-webots-version` | 2026-08-14 | add Python installation instruction and how to turn  |  |
| no_call | — | `meloothman/hardware-tracker-frontend` | 2026-07-04 | safemode für jokeapi |  |
| no_call | — | `bmax121/KernelPatch` | 2026-07-31 | fix: some devices cannot enter safemode using the vo |  |
| no_call | — | `AceSLS/SLSsteam` | 2026-07-28 | fix(SafeMode): Add new version to res/updates.yaml |  |
| no_call | — | `clqwnless/stoic` | 2026-08-05 | Update requirements & add an option to install the s |  |
| no_call | — | `sekkit/maddog` | 2026-07-16 | fix: keep desktop bindings aligned with SafeMode |  |
| no_call | — | `tsionely/eni_dcim` | 2026-07-16 | [sim-run] phase4b safemode no-race timeout |  |
| no_call | — | `AceSLS/SLSsteam` | 2026-07-25 | chore(SafeMode): Add client hash from 2026.07.25 |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Record official p1ctl Exit Safemode probe [skip ci] |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Record official p1ctl Exit Safemode probe [skip ci] |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Record official p1ctl Exit Safemode probe [skip ci] |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Record official palera1n Exit Safemode V4 [skip ci] |  |
| no_call | — | `NightVibes33/Codex-DEB-Test` | 2026-07-25 | Record official palera1n Exit Safemode V4 [skip ci] |  |
| no_call | — | `1diot9/FastjsonExpToolkit` | 2026-08-03 | Fix root-path discovery so vulhub-style / deser poin |  |
| no_call | — | `Byron4j/CookBook` | 2026-05-06 | feat(docs): 新增 Fastjson2 使用指南 |  |
| no_call | — | `sanhng/nhungnguoivodanh` | 2020-06-15 | Updated fastjson_safemode (markdown) |  |
| no_call | — | `sanhng/nhungnguoivodanh` | 2020-06-15 | Updated fastjson_safemode (markdown) |  |
| no_call | — | `sanhng/nhungnguoivodanh` | 2020-06-10 | Updated fastjson_safemode (markdown) |  |
| no_call | — | `sanhng/nhungnguoivodanh` | 2020-06-08 | Updated fastjson_safemode (markdown) |  |
| no_call | — | `zoloz-pte-ltd/zoloz-integration-examples` | 2020-10-30 | fix stc: set fastjson safemode |  |
| no_call | — | `zoloz-pte-ltd/zoloz-integration-examples` | 2020-10-24 | check logger enability; set fastjson safemode |  |
| no_call | — | `wangwenyuan/javatodo` | 2021-08-28 | 开启fastjson的safeMode模式 |  |
| no_call | — | `Evan-Sukhoi/SUSTechCampus` | 2023-12-03 | 解决了登录时token的com.alibaba.fastjson.JSONException: safe |  |
| no_call | — | `zoloz-pte-ltd/zoloz-integration-examples` | 2020-11-05 | check logging; set fastjson safemode |  |
| no_call | — | `zoloz-pte-ltd/zoloz-integration-examples` | 2020-11-05 | check logger enability; set fastjson safemode |  |

## Worth reading

- **CubePlus1/screeps-cn@ab1ea341** — Add safeMode map overlay and fix zoom during animation
  - value: `None`  files changed: 5  library confirmed: None
  - `const roomStats = new Map<string, { own?: { user: string; level: number }; mineral?: string; density; renderer?.setRoomSafeMode(room, !!stat.safeMode)`
- **0x7eTeam/fastjson-1.2.83-rce@21f52866** — Fastjson 1.2.83 @JSONType RCE 漏洞测试环境
  - value: `None`  files changed: 5  library confirmed: True
  - `**无需 autoTypeSupport=true，无需第三方依赖，仅需 safeMode 未启用（默认）。**; 1. 启用 SafeMode: `-Dfastjson.parser.safeMode=true``
- **alib8b8/aflare@1c7eb601** — fix: --safe-mode 接入 PolicyExecutor，safeMode 贯穿调用链
  - value: `None`  files changed: 2  library confirmed: None
  - `cli.HandleRun(args, dryRun, safeMode); cli.HandleRunFile(command, dryRun, false, "", safeMode)`
- **hat47x/kj-atlas@47db342a** — docs(issues): escalate SEC-AI-SAFEMODE-01 — no SafeMode filter on Web AI path either
  - value: `None`  files changed: 1  library confirmed: None
  - `- `suggestLayout`（`client.ts:447`）は `JSON.stringify({ doc, instruction })` で**全文書を送信**。呼び出し元 `App.ts; - `generateNarrative` も同形。`safeMode` の useState（`
- **jongtix/aaa-collector@f7678dbf** — ✨ feat(collector): SafeMode 저장 계층에 TTL + 백오프 수준 지속 저장 추가
  - value: `None`  files changed: 3  library confirmed: None
  - `redisTemplate.opsForValue().set(safeModeKey(alias), SAFE_MODE_ON, ttl);`
- **Gameknight963/MZDO@78698ebc** — added safemode
  - value: `None`  files changed: 1  library confirmed: None
  - `private readonly static bool safeMode;; private static readonly string safeModeFile = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "s`
- **AceSLS/SLSsteam@12a8e2f9** — fix(SafeMode): Only download updates.yaml when either SafeMode or WarnHashMissmatch is ena
  - value: `None`  files changed: 2  library confirmed: None
  - `return g_config.safeMode.get() || g_config.warnHashMissmatch.get();`
- **designer-kevinxie/wenzi@cfd44a97** — Merge pull request #1 from designer-kevinxie/docs/document-safemode-field
  - value: `None`  files changed: 1  library confirmed: None
  - `"safeMode": true                   // 寫入 manifest.json,但目前沒有元件讀取,先保留欄位`
- **hat47x/kj-atlas@c15957a8** — docs(issues): record empirical confirmation of SEC-AI-SAFEMODE-01
  - value: `None`  files changed: 1  library confirmed: None
  - `- **AI リクエストモデルに SafeMode パラメータは無い**。`SuggestLayoutRequest`（models.py:1449）/ `SuggestMergesRequest`（`
- **hat47x/kj-atlas@c1fd9ca4** — fix(security): apply SafeMode to document.json in export bundles
  - value: `None`  files changed: 4  library confirmed: None
  - `test("defaults to safe mode for exports when context.safeMode is omitted", async () => {; safeMode: false,`
- **readmeio/markdown@87761afb** — fix: propagate safeMode thru components (#1593)
  - value: `None`  files changed: 11  library confirmed: None
  - `describe('safeMode', () => {; it('does not evaluate JSX attribute expressions when safeMode is true', () => {`
- **markup-carve/carve-php@b29f8bf9** — docs: state the default explicitly, and stop the SafeMode table implying it (#469)
  - value: `None`  files changed: 1  library confirmed: None
  - `| `new CarveConverter(safeMode: true)` | `SafeMode::defaults()` | none |`
- **hat47x/kj-atlas@af78cdd9** — docs(issues): complete SEC-AI-SAFEMODE-01 decision package
  - value: `None`  files changed: 1  library confirmed: None
  - `| **ADR-0068** | `/ai/*` リクエストモデルへ `safeMode` を追加し、未レビュー本文を拒否（D1=C・D2=B・D3=A 推奨） | 小〜中 | 現行ルートに直接適用。`
- **hat47x/kj-atlas@5cdcb665** — fix(security): close SafeMode text-leak gaps in export/canvas surfaces; file document.json
  - value: `None`  files changed: 11  library confirmed: None
  - `- `buildExportBundle`/`buildExportBundleWithWorkers`（`03_Implement/frontend/src/export/bundle_export; - 既存テスト `bundle_export.test.ts:387`「defaults to `
- **GomdimApps/web-escpos-printer@10e7e27b** — feat: add safeMode compatibility fallback for PDF417 printing and support custom feed befo
  - value: ``  files changed: 11  library confirmed: None
  - `Utils/safemode.ts             # safeMode() — shared raster-image fallback for pdf417/etc. safeMode e`
- **hat47x/kj-atlas@84ebc523** — docs(DOMAIN-W-ITERATION-01): record SafeMode share boundary
  - value: `None`  files changed: 1  library confirmed: None
  - `- 通常のローカル保存は従来どおり本文を保持し、`exportInfo`を付けない。外部共有用の別操作はUI上のSafeMode設定にかかわらず必ずSafeModeを適用し、`exportInfo`へ; - import/exportはmetadataの未知キー、不正型、`safeModeAppli`
- **Naiker12/Sparta-Agent@c72e5288** — feat(security): expose safe_mode status to frontend
  - value: `None`  files changed: 5  library confirmed: None
  - `safeMode: mod.isSafeMode(); win.webContents.send('security:status-changed', { loaded: false, auditEnabled: false, safeMode: fals`
- **GomdimApps/web-escpos-printer@6cbb1eda** — Merge pull request #3 from GomdimApps/printer
  - value: ``  files changed: 18  library confirmed: None
  - `Utils/safemode.ts             # safeMode() — shared raster-image fallback for pdf417/etc. safeMode e`
- **GomdimApps/web-escpos-printer@b592c44b** — feat: add safeMode support to qrcode element to enable raster-based printing as a fallback
  - value: `encoder, element.safeMode, 'qrcode', (`  files changed: 10  library confirmed: None
  - `if (safeMode(encoder, element.safeMode, 'qrcode', () => buildQrCodeRasterImage(element, imageMaxWidt`
- **hat47x/kj-atlas@aa74a0c9** — feat(DOMAIN-W-ITERATION-01): add verified SafeMode share bundles
  - value: `None`  files changed: 11  library confirmed: None
  - `- 探究全体: `{ scope: "full", safeModeApplied: true }`; - 選択ラウンドまで: `{ scope: "round", selectedRoundId: string, safeModeApplied: true }``
- **hat47x/kj-atlas@c6c8c872** — test(security): cover SafeMode on shipped worker export path (SEC-EXPORT-BUNDLE-02)
  - value: `None`  files changed: 2  library confirmed: None
  - `safeMode: true,; safeMode: true,`
- **ksmartdata/docker-images@ad1f2b1f** — enable fastjson safeMode for rocketmq broker/nameserver/controller/exporter (#34)
  - value: `None`  files changed: 7  library confirmed: None
  - `JAVA_OPT="${JAVA_OPT} -Dfastjson.parser.safeMode=true"; JAVA_OPT="${JAVA_OPT} -Dfastjson.parser.safeMode=true"`
- **intelseclab/poc-archive@6698d982** — feat: ingest CVE-2026-16723 Alibaba Fastjson 1.2.68-1.2.83 RCE
  - value: `None`  files changed: 41  library confirmed: True
  - `</code></pre><hr><h2 id=remediation>Remediation</h2><div class=overflow-x-auto><table><thead><tr><th; | **Config Hardening** | Start the JVM with `-Df`
- **LoRexxar/Kunlun-M@48222fd7** — feat: 扩展 framework-dependency 规则覆盖 Log4j/Fastjson/Collections/XStream/Jackson/Actuator/Fil
  - value: `None`  files changed: 11  library confirmed: True
  - `Fastjson 1.2.68-1.2.80 autoType safeMode 绕过; self.vulnerability = "Fastjson safeMode 绕过 RCE"`
- **huimzjty/vulwiki@6faad010** — fastjson safeMode
  - value: `None`  files changed: 2  library confirmed: True
  - `safeMode开启`
- **sanhng/nhungnguoivodanh@d899a205** — Updated fastjson_safemode (markdown)
  - value: `None`  files changed: 1  library confirmed: True
  - `### 4. safeMode场景如何做autoType`
- **sanhng/nhungnguoivodanh@1be61461** — Updated fastjson_safemode (markdown)
  - value: `None`  files changed: 1  library confirmed: None
  - `在1.2.68之后的版本，在1.2.68版本中，fastjson增加了safeMode的支持。safeMode打开后，完全禁用autoType。所有的安全修复版本sec10也支持SafeMode配置。`
- **sanhng/nhungnguoivodanh@5fd657ca** — Updated fastjson_safemode (markdown)
  - value: `None`  files changed: 1  library confirmed: None
  - `在1.2.68之后的版本，在1.2.68版本中，fastjson增加了safeMode的支持。safeMode打开后，完全禁用autoType。`
- **sanhng/nhungnguoivodanh@fd1c2068** — Created fastjson_safemode (markdown)
  - value: `None`  files changed: 1  library confirmed: None
  - `在1.2.68之后的版本，在1.2.68版本中，fastjson增加了safeMode的支持。safeMode引入后，完全禁用autoType。; -Dfastjson.parser.safeMode=true`
- **jd-opensource/joyrpc@fdb776de** — Fastjson默认改成SafeMode
  - value: `None`  files changed: 3  library confirmed: True
  - `[fastjson.parser.safeMode]`
- **lWoHvYe/unicorn@b2c10a70** — fastjson-autoType白名单机制。待转换为safeMode
  - value: `None`  files changed: 1  library confirmed: True
  - `// 开启safeMode https://github.com/alibaba/fastjson/wiki/fastjson_safemode`
- **dinosn/fastjson-jsontype-rce-lab@ed271f43** — Add fastjson2 autoType lab: remote class load with autoType disabled
  - value: `None`  files changed: 21  library confirmed: True
  - `fj2-controls: ## fastjson2 controls: plain parse / safeMode / JDK17 / Jackson / allowlist; Reproduced on **fastjson2 2.0.57** (latest at the time of w`
- **w6fux5/ChainKit@ffa2052b** — test(tron): add Nile testnet E2E integration tests
  - value: `None`  files changed: 4  library confirmed: None
  - `// node's fastjson parser due to its safeMode autoType restriction.`
- **lWoHvYe/unicorn@ddee4702** — 引入fastjson.properties配置，safeMode改造，完成50%。开启之后，部分情况下从redis取出的对象JSONObject未转成对应的实体。在使用时，引发类型
  - value: `None`  files changed: 12  library confirmed: True
  - `#on safeMode; fastjson.parser.safeMode=true`
- **lWoHvYe/unicorn@9203efd8** — fastjson开启safeMode后，从redis中取出的对象将变为JSON(JSONObject、JSONArray)。在使用时需注意。另外一些情况下取出的JSONObject
  - value: `None`  files changed: 2  library confirmed: True
  - `// TODO: 2021/10/23 先简单处理，开启safeMode后，从缓存中取出时，结果JSON类型。当前只用到SimpleGranteAuthority,后续用到别的需同步调整`
