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

| path | holds |
|---|---|
| `scripts/nadia_scripts/` | the pipeline, the verified cases, the census, the report |
| `data/benchmark/` | BUMP's 571 breaking updates + their failure categories |
| `data/benchmark_test_failures*/` | the TEST_FAILURE subsets |
| `reproductionLogs/` | BUMP's build logs, read by the `characterize` stage |

`data/` and `reproductionLogs/` are **kept as evidence, not as scaffolding**: the mid-year
report's BUMP breakdown is re-derived from them by
[`report/verify_numbers.py`](scripts/nadia_scripts/report/verify_numbers.py), so removing
them would make those numbers unverifiable. The rest of the upstream BUMP harness (the
Java reproduction tooling, CI workflows, RQ data, and helper scripts) was removed in
August 2026 — it is unused here and remains available upstream.

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
