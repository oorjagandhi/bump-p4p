# agent/ — automated verification

Runs the three-state differential without a human hand-writing each driver.

| file | what it is |
|---|---|
| `run_worklist.py` | The deterministic harness. Clones, pins the library version, runs the three states, writes a ledger row to `output/05_verify/_<lib>_differential.jsonl`. |
| `orchestrator.py` | The state machine underneath it. Most other agent scripts import this. |
| `fanout.py` | Turns a mined candidate corpus into a worklist. |
| `seams.py` | The judgement seams — driver authoring, failure diagnosis. |
| `bbc_common.py` | Shared helpers. |
| `worklist_*.json` | One per break: the candidates to run. |
| `reverify_*.json` | Re-runs cases whose answers are already KNOWN. This is how the agent gets *measured* rather than merely used. |

The `bbc-driver-author` subagent (`.claude/agents/bbc-driver-author.md`) drives
`run_worklist.py` one candidate at a time and carries the full recovery table — every failure
mode found so far, each keyed on the symptom that identifies it.

## Measure before you trust

Run `reverify_*.json` — candidates with known answers — before running fresh ones. A fresh
candidate has nothing to contradict a wrong result, so a harness fault gets recorded as a fact
about the client and nothing downstream will ever catch it.

## Read the ledger row before believing the verdict

Two failure shapes produce results that look completely legitimate:

- **`run == 0` in any state → void, not negative.** Zero tests executed is not a negative
  result. Find out why Maven stopped before reading anything into it.
- **`run >= 1`, every state passes → check `version_pinned`.** If the row has `version_props`
  but no `version_pinned` key, the version knob never armed and all three states ran the
  *same* jar. That scores `signature_confirmed` — indistinguishable from a real negative.

Both are cheap to defend against: have the driver print the resolved library version, so every
state's log proves which jar it actually ran.
