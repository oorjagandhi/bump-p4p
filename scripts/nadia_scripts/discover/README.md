# discover/ — is a case even possible for this library?

The cheapest stage and the one that saves the most time. It answers, *before* you spend a day
mining: does this break have any chance of producing a verified case?

| script | what it does |
|---|---|
| `rank_candidates.py` | Scores libraries from security advisories against the structural filters. **Consult this at pick time** — it already encodes boundary recency and API-removal screening. |
| `mine_advisories.py` | Pulls breaks out of the OSV Maven advisory feed into the catalog. This is how non-BUMP breaks enter the study. |
| `find_adaptations.py` | Searches commits for the *recovery* API and classifies each by the VALUE it sets — raise / lower / knob-at-default. **Only "raise" can ever verify.** |
| `probe_population.py` | Does anyone publicly commit this adaptation at all? Also supplies helpers `find_adaptations` imports. |

## Run find_adaptations before the bump-axis mine

On snakeyaml maxaliases the bump axis returned 967 commits, mostly `2.x → 2.x` bumps that
cannot cross the boundary. `find_adaptations.py` had already produced 27 triaged commits with
4 clean "raise" verdicts — days earlier, for a fraction of the API budget.

**Check `output/01_discover/ADAPTATIONS_<break_id>.md` before mining anything.** It may already
exist, and a previous run's answer is cheaper than a new one.

## The identifier has to be searchable

`find_adaptations.py` is only as good as the identifier you give it, and two things can go
wrong — both measured on fastjson:

- **Not distinctive.** GitHub commit search tokenizes, so `addAccept` matches every "accept
  Android licenses" and "Accept header" commit. `ParserConfig` collides with unrelated Python,
  Go and Rust projects. `setCodePointLimit` and `setMaxAliasesForCollections` are fine.
- **Wrong direction.** `safeMode` is distinctive and finds real fastjson clients — but enabling
  safeMode *tightens* the restriction. Hardening can never produce a pass/fail/pass differential.
  Only the re-permit / raise direction can.

Test a candidate identifier by running it and looking at what fraction of hits are even the
right language.
