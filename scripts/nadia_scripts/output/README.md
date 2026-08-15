# output/ — results, split by pipeline stage

Every file here was produced by a script. The folder tells you which stage made it.

`paths.py` at the repo root owns this layout: `out("some_file.jsonl")` routes a filename to
the right folder, so a script that writes a file and a script that later reads it can never
disagree about where it lives.

| folder | stage | question it answers | written by |
|---|---|---|---|
| `01_discover/` | discover | *Who might have adapted to this break?* | `discover/rank_candidates.py`, `mine_advisories.py`, `find_adaptations.py`, `probe_population.py` |
| `02_mine/` | mine | *Which commits are they, exactly?* | `mine/bbc_e2e.py mine-commits` and `classify` |
| `03_screen/` | screen | *Which of those are real candidates?* | `screen/screen_compile_break.py`, `screen/screen_trigger.py` |
| `04_traversal/` | traversal | *Did the client actually cross the boundary?* | `traversal/find_crossing.py` |
| `05_verify/` | verify | *Did the break actually reproduce?* | `agent/run_worklist.py`, `verify/02_verify_bbc.py` |
| `reports/` | — | human-readable summaries of all of the above | several |

**Start with `reports/CENSUS.md`.** It is regenerated from the artifacts, so it is the only
count worth quoting. Prose goes stale; the census does not.

## Reading a filename

Most are `<break_id>_<what>.jsonl`. The suffix tells you how far those rows got:

- `_candidates` — commits the mine found. No judgement applied yet.
- `_PRODONLY` — narrowed to commits that changed production code, not just tests.
- `_SCREENED` — a screen has run; rows carry a verdict.
- `_traversal`, `_UNDECIDED`, `_MVNRECHECK` — boundary-crossing checks. `UNDECIDED` means the
  version could not be resolved, which is **not** the same as "did not cross".
- `_ADAPTATIONS` — commits touching the recovery API, classified by the value they set.
- `_differential` — the three-state verification ledger. One row per run.

## What is deliberately not committed

Checkpoints (`*_mine_checkpoint.jsonl`, `*_classify_checkpoint.jsonl`) are search-resume state
and are gitignored on purpose: a committed checkpoint would make a fresh run silently resume
someone else's stale search instead of mining.
