# scratchpad/ — the per-case verification harnesses

**The name is historical and misleading. Nothing in here is disposable.**

Each `*-harness/` folder is the actual apparatus that verified one case: a driver test, a
runner script, and usually a `pom.xml` that wraps the client's real `src/main` source. The
verified case JSON files cite these paths as their provenance — deleting a harness would
orphan the evidence for a case.

(A rename to `harnesses/` was attempted and blocked by an OS file lock on one of the cloned
repos inside. It is still worth doing.)

## What is tracked and what is not

| tracked | not tracked (gitignored, regenerable) |
|---|---|
| the driver `.java` | `repo/` — the cloned client project |
| `run_state.sh` / `run_differential.sh` / `bootstrap.sh` | `target/`, `*.log`, `*.cp`, `cp.txt` |
| `pom.xml` where the harness needs one | |

So a harness folder that looks nearly empty is normal. The clone is fetched on demand.

## Why harnesses exist at all

Some clients cannot be verified through their own build — the build needs a database, a live
server, a nine-variable environment, or it is Gradle and the runner is Maven. Wrapping the
untouched `src/main` in a minimal Maven project keeps the *client's real production code* in
the differential while dropping everything irrelevant to it.

That is a legitimate method and several verified cases were made this way. What it costs is
reproducibility by the automated pipeline: a harness case is reproducible by running the script
here, not by pointing `agent/run_worklist.py` at the repo.

## Two disk notes

- `jackson-trino-harness/repo/` and `jackson-datashare-harness/repo/` hold full upstream clones.
  They are gitignored and can be deleted to reclaim disk; they will be re-cloned on demand.
- `advisories/`, `rankjars/` and the `*_mine.txt` files are working data from discovery runs.
