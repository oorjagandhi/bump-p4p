# Triage of the 12 queued candidates (2026-07-15)

The 12 queued rows collapse to **6 distinct (repo, commit)** pairs — the POI rows are the
same 3 repos counted once per POI artifact (poi / poi-ooxml / poi-scratchpad).

Method: fetched each commit's real adaptation diff (production files) + read the classifier's
recorded dependency version at commit vs parent. A candidate is only a `verified_bbc`
differential target if (a) the diff adapts to the *specific* catalog break and (b) a version
transition crosses the break boundary.

| # | repo | break | diff verdict | version @parent→@commit | outcome |
|---|---|---|---|---|---|
| 1 | LucasG-max/WorkShop-spring-jpa | h2 1.3→2.0 | **adds H2 for the first time** (new test-profile config), not adapting to a break | none / none | **skip** (false positive) |
| 2 | bizwmh/OASE | h2 1.3→2.0 | adds `-baseDir`+`user.dir` to H2Console — an H2-2.0 *console base-dir* behaviour, **not** the catalog's SQL-compat break | none / none | **skip** (off-boundary, weak) |
| 3 | ProgrammeVitam/sedatools | poi 4.1.2→5.x | real byte-cap API `IOUtils.setByteArrayMaxOverride(100MB→MAX_VALUE)`, but self-documented as a workaround for a **POI 4.0/4.1 MSG bug** — right API family, wrong boundary | none / none | **signature-only** (not 4→5) |
| 4 | SilkKirk/ruoyi-vue-backend | poi 4.1.2→5.x | swaps POI `IOUtils` → Hutool `IoUtil` (dependency consolidation), no POI-break code | none / none | **skip** (false positive) |
| 5 | victoryshining/zhongxun-onlineschool | poi 4.1.2→5.x | moves `IOUtils` import poi→commons-io; POI **3.14→3.16**, not even 4→5 | 3.14 → 3.16 | **skip** (misbucketed) |
| 6 | RicBatista/drools | xstream 1.4.18 forbiddenclass | causally about `ForbiddenClassException`, but fix is a `KieURLClassLoader`/type-resolver workaround — **no** XStream security API (`allowTypes`/`addPermission`); giant multi-module build | none / none | **signature-only**, untractable |

## Verdict

- **0** clean `verified_bbc` differential targets among the 12.
- **3** outright false positives (1, 4, 5) — fanout keyword-matched commit messages, not adaptations.
- **2** signature-only (3 sedatools, 6 drools) — real causal link but no standalone-runnable
  adaptation on the catalog boundary; drools also untractable to build.
- **1** off-boundary/weak (2 OASE).

No differential was run: every candidate either fails precondition (no version transition across
the boundary) or has no break-adaptation to reproduce. Spending the Anthropic-key seam on these
would not yield a `verified_bbc`.

Corroborates memory: *fanout mis-buckets candidates* and weak-signal breaks (h2/poi-3.x noise)
produce keyword false-positives. The real dataset growth needs cleaner mining signatures or a
version-transition precondition applied *before* candidates reach the queue.

---

## Fixes applied (2026-07-15)

### Lever 0 — boundary precondition in `fanout.py`  ✅ live
Drops a candidate only when its version is *resolvable AND provably below* the break's
`to_version`. `None` is kept (genuine cases are frequently None). Immediately dropped
victoryshining (poi 3.16) → queue 12 → 9. Drops are reported, never silent.

### Lever 1 — version resolver in `bbc_e2e.py`  ✅ code fixed, needs re-mine
Root cause of the `None`-blindness (why the other 5 false positives slip through): the old
`dep_version` only read the ROOT `pom.xml` with a `[0-9]`-anchored regex, so it returned None on:
- **property versions** `<version>${poi.version}</version>` — now resolved via `<properties>`
  (incl. one level of nesting; `${project.version}` honestly stays None).
- **multi-module repos** — new `_module_poms()` searches the module pom nearest each changed
  file (e.g. `mailextractlib/pom.xml`) before root.
- **version-less parent/BOM-managed blocks** — now correctly None instead of bleeding the
  *next* dependency's `<version>` (a latent correctness bug).
Proven by 8 offline unit tests (literal / property / nested / managed / cross-bleed / gradle /
project.version / wrong-group). **Not yet applied to the queue** — re-mining regenerates the
`version_at_commit` fields and needs a `GITHUB_TOKEN` (absent in this session).

### Lever 2 — mining signature in the catalog  ✅ live
`poi-scratchpad` search term `"IOUtils"` (matched any commons-io use, the Hutool refactor, the
import move) → `"IOUtils.setByteArrayMaxOverride"`. Kills the ruoyi/victoryshining class of
false positive at the source.

### To actually clean the queue (needs your GitHub token)
```
export GITHUB_TOKEN=...            # or set in your own terminal
python bbc_e2e.py mine-commits poi-scratchpad-4.1.2-to-5.x   # re-mine with tightened signature
python bbc_e2e.py classify ...                               # re-resolve versions per candidate
python agent/fanout.py                                       # boundary filter now has real versions
```
Expect: more candidates gain a real `version_at_commit`, so the boundary filter catches the
POI-4.x-era and sub-boundary cases (sedatools, etc.) that currently pass as `unconfirmed`.

---

## Re-mine done (2026-07-15, with GH_TOKEN) — results

Re-ran `bbc_e2e.py run` for poi / poi-ooxml / poi-scratchpad / h2 / xstream with the fixes live.

**Resolver fix landed:** `bizwmh/OASE` now reads **@2.2.224** (was None), `igniterealtime/Spark`
**@1.4.18** (was None) — multi-module/property resolution working. That Spark resolution exposed
and fixed a boundary bug: the filter must key on `verify.break_boundary` (xstream 1.4.18), NOT
`library.to_version` (1.4.19), or genuine boundary-pinned cases get dropped.

**Signature fix landed:** the `IOUtils` → `IOUtils.setByteArrayMaxOverride` change removed the
ruoyi (Hutool refactor) and victoryshining (3.14→3.16 import move) false positives *at the mining
stage* — they no longer appear at all. Better on-signal candidates surfaced instead (morpheus45
"crash IOUtils au remplissage", tpunder "setByteArrayMaxOverride to avoid RecordFormatException",
MarDream large-xlsx OOM) — though those are gradle/sbt/unknown, so out of the Maven verify scope.

**Queue: 12 → 6** (4 distinct repos; sedatools counts once per POI artifact):

| repo | break | version | boundary_status | note |
|---|---|---|---|---|
| bizwmh/OASE | h2 | 2.2.224 | on_or_past | genuinely on H2-2.x; triage says console baseDir, not SQL-compat |
| LucasG-max/WorkShop-spring-jpa | h2 | None | unconfirmed | adds H2 first-time — false positive deterministic filters can't catch |
| ProgrammeVitam/sedatools | poi | None | unconfirmed | POI-4.x-era byte-cap workaround (off-boundary) |
| RicBatista/drools | xstream | None | unconfirmed | classloader workaround, no `allowTypes`; untractable build |

The remaining 4 are genuine judgment calls (the LLM/human seam's job), not mechanical noise.
The mechanical false positives that motivated this work are eliminated.
