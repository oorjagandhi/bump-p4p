# Mining findings — which libraries can yield verifiable production BBC cases

Recorded 2026-07-08 after re-mining the non-xstream/non-POI libraries.

## The selection criterion

A library only produces a **verifiable production BBC case** if its behavioural
break **forces a change in production code (`src/main`)**. That is the property
that made xstream and POI work — and the property the other five lack.

| Library | Break | Where the adaptation lives | Verifiable? |
|---|---|---|---|
| **xstream** 1.4.18 | default-deny throws `ForbiddenClassException` on deserialize | production serializer allowlist (`src/main`) | ✅ yes |
| **POI** 5.0 | `IOUtils` byte-cap / `POITextExtractor` change | production override (`src/main`) | 🟡 partial (hard to trip) |
| mockito 5.0 | inline mock-maker default + strict stubbing | **test code only** (mockito is test-scoped) | ❌ no |
| slf4j 2.0 | logged-output / binding behaviour | **test assertions** | ❌ no |
| logback 1.4 | output/config change (Jakarta cutover) | **test assertions** | ❌ no |
| httpclient 4.5.13 | reason-phrase formatting change | **test assertions** | ❌ no |
| jsoup 1.15 | trailing-whitespace / output change | **test assertions** | ❌ no |

## The re-mine (evidence)

Ran `bbc_e2e.py run <break_id>` for all five. Every saved candidate was a
**dependabot version bump**, not a code adaptation:

| library | signal | commits mined | repos | verifiable production adaptations |
|---|---|---|---|---|
| mockito | medium | 368 | 293 | **0** |
| slf4j | weak | 286 | 263 | **0** |
| httpclient | weak | 300 | 207 | **0** |
| jsoup | weak | 235 | 209 | **0** |
| logback | weak | 226 | 168 | **0** |
| **total** | | **~1,415** | **~1,140** | **0** |

The `output/*_candidates.jsonl` files for these five therefore contain only
version-bump commits (`is_production_adaptation: false`, `verifiable: false`) —
they are **not** a backlog of unverified adaptations.

## Why this is categorical, not a search-tuning problem

"Weak commit-search signal" (PIPELINE.md) is a symptom. The root cause is that
these breaks manifest at the **test-assertion** level (or, for mockito, in
test-scoped code that never touches `src/main`). Since the dataset targets
production adaptations — and test-file adaptations are deliberately filtered out
(commit 567a616ec) — these libraries can't contribute, no matter how the search
is tuned.

## Implication for scaling

Don't re-mine these five. To grow the dataset toward the scale goal, pick **new
libraries whose break forces a production-code adaptation**, e.g.:

- security / deserialization tightening (Jackson polymorphic-type allowlists, Gson)
- validation / parsing strictness that **throws in production**
- API-contract behavioural changes on `src/main` call paths

That mirrors exactly what made xstream a clean, high-yield case.
