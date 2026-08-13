# Behavioural breaking changes in Java dependency upgrades

Research project hunting **behavioural breaking changes (BBCs)**: cases where a Java
library upgrade compiles cleanly but changes what the program *does* at run time, and a
real client repository then changed its **production code** in response.

A case counts only when all three hold, and the third is proved by rebuilding:

1. the client crossed the version boundary where the behaviour changed,
2. it adapted production Java code, and
3. a 3-state differential shows **pass → fail → pass** (old library, new library, client's fix).

**The work lives in [`scripts/nadia_scripts/`](scripts/nadia_scripts/)** — start with its
[`README.md`](scripts/nadia_scripts/README.md) for the findings and screening rules, and
[`PIPELINE.md`](scripts/nadia_scripts/PIPELINE.md) for stage mechanics. The live ledger of
what has been measured is [`output/CENSUS.md`](scripts/nadia_scripts/output/CENSUS.md),
regenerated from the artifacts rather than hand-maintained.

## What's in this repository

Everything lives under [`scripts/nadia_scripts/`](scripts/nadia_scripts/) — the pipeline,
the verified cases, the census, and the report. Nothing else remains at the root.

**The upstream BUMP corpus is gone.** The Java reproduction harness, CI workflows, `RQData/`,
and helper scripts were removed on 2026-08-12, and `data/` and `reproductionLogs/` followed
the same day: the contribution here no longer rests on the BUMP breakdown, and the corpus
cost ~26 MB to carry. Two consequences worth knowing before you go looking for them:

- The mid-year technical report, its figures, and the frozen BUMP numbers were deleted
  with the corpus itself. All of it is in git history; nothing in the live pipeline reads
  it. What survives as the standing record of what has been measured is
  [`output/CENSUS.md`](scripts/nadia_scripts/output/CENSUS.md), which is regenerated from
  the artifacts by `ledger/census.py` and does not depend on BUMP at all.
- The `characterize` stage had no input left, so on 2026-08-13 it was removed along with
  `mine/bbc_pipeline.py` (which implemented it) and `mine/bbc_common.py` (which had served
  a miner deleted earlier still). Nothing was lost: 12 of the 13 BUMP-sourced breaks
  already carry their failing tests inline in `specs/bump_breaks_catalog.json`, which is
  what downstream stages read. `mine/bbc_e2e.py run` now starts at mining.

To restore either, clone [chains-project/bump](https://github.com/chains-project/bump); the
deleted files are also in this repository's history.

## Provenance

This repository began as a fork of [chains-project/bump](https://github.com/chains-project/bump)
and retains its benchmark data under that project's licence. If you use BUMP, cite:

```bibtex
@inproceedings{bump2024,
 title = {BUMP: A Benchmark of Reproducible Breaking Dependency Updates},
 booktitle = {Proceedings of SANER},
 year = {2024},
 doi = {10.1109/SANER60148.2024.00024},
 author = {Frank Reyes and Yogya Gamage and Gabriel Skoglund and Benoit Baudry and Martin Monperrus},
 url = {http://arxiv.org/pdf/2401.09906},
}
```

BUMP's own Docker images and download instructions are at the upstream repository and on
[Zenodo](https://zenodo.org/records/10041883).
