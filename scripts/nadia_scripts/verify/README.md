# verify/ — did the break actually reproduce?

The three-state differential. This is what makes a case a case.

| state | code | library version | must be |
|---|---|---|---|
| 1 baseline | parent commit | the one they came FROM | PASS |
| 2 new lib, old code | parent commit | at or after the boundary | **FAIL, with the catalogued signal** |
| 3 adapted | adaptation commit | the new version | PASS |

All three run the **same driver source**. That is the entire point: the only things that change
are the client's own code and the library version, so anything the differential shows is
attributable to one of those two.

| file | what it is |
|---|---|
| `02_verify_bbc.py` | The hand-run verifier. |
| `test_gates.py`, `test_find_crossing.py` | Offline unit checks. Run them after touching traversal logic — a wrong answer there fails *silently*, producing a confident wrong verdict rather than an error. |

Automated verification lives in `agent/`.

## Two ways to get a result that means nothing

- **A state that ran zero tests.** Void, not negative. Nothing can be concluded from it.
- **A state that ran the same library version as the baseline.** Also void — and far more
  dangerous, because all three states pass and it reads as a clean negative about the client.

Both are defeated the same way: print the resolved library version from inside the driver, so
every state's log carries proof of which jar it actually ran.

## The driver must drive the client's real production method

Not a synthetic library call. The break has to manifest through the application's own code, or
the case says nothing about that client. The adaptation-only call (`allowTypes`,
`setCodePointLimit`) belongs in the production code where the client put it — never in the test,
or the driver will not compile at the baseline.
