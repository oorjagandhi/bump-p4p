# archive/ — one-shot scripts, kept for their reasoning

Nothing here is part of the live pipeline. These ran once, did their job, and are kept
because **the docstring is often the only record of a decision the pipeline still depends
on** — a bug that invalidated earlier results, a distinction that changed what a verdict
means, a screen that ruled a whole library out.

Deleting them would leave the conclusion in place with the reasoning gone.

They still run: the `sys.path` bootstrap includes `archive/`, so their imports resolve.

| script | what it did | why it mattered |
|---|---|---|
| `acceptance_amirsnw.py` | Acceptance dry-run #2 — the "plain-vs-configured / born-past-boundary" harness shape | (amirsnw xstream), exercising SEAM_A (driver-test generation) as a discrete agent step. Unlike jadhavspeaks (pre-adaptation code exists at the parent), amirsnw was BORN past the 1.4.18 boundary and its XStream @Bean was CREATED in the fix, so there is no calla |
| `acceptance_artshishkin.py` | Acceptance dry-run #3 — artshishkin xstream case, the TRANSITIVE-crossing shape. | acceptance_jadhavspeaks) both target cases that are now in verified_cases/excluded/no_boundary_crossing/ — amirsnw was born past the 1.4.18 boundary and jadhavspeaks past POI 5.0.0. Neither qualifies as a case any more, so |
| `acceptance_jadhavspeaks.py` | Acceptance dry-run (AGENT_DESIGN sec.9.4): drive the orchestrator's real 3-state machinery | autonomously over a KNOWN-good candidate (poi-jadhavspeaks) and confirm it reaches verified_bbc without hand-typed mvn commands. Scope: this validates the DETERMINISTIC orchestration (clone, 3 states, signal match, oracle, |
| `add_case_links.py` | Add a `links` block to every verified case: clickable URLs for the adaptation commit and | copying a 8-to-12 character hex string into a GitHub URL by hand. The SHAs also live under different keys depending on when the case was written (`in_repo_version_transition .bump_commit`, `adaptation.bump_commit`, or nowhere at all when the bump is bundled in |
| `audit_traversal.py` | record a mechanical traversal verdict into each verified case. | (a) TRAVERSAL   a real client crossed the break boundary, broke, and adapted (the witnessed bump -> break -> fix pair) (b) MECHANISM   the behavioural break is real and a harness reproduces it via a |
| `boundary_dates.py` | resolve each break's boundary version to its RELEASE DATE. | --- org-json taught this the expensive way. Its break is real, 31 real production adaptations were mined for it, and it can NEVER yield a witnessed crossing — because |
| `build_worklist_from_cases.py` | Build an agent worklist from ALREADY-VERIFIED case files, to re-verify them with the agent. | anything already in verified_cases/ as `already_recorded`, which is right for finding NEW cases and wrong for the other thing you want the agent to do: reproduce known answers. Re-verification is the only measurement of the agent that is unambiguous. On a fres |
| `closeout_traversal.py` | decide the rows `resolve_undecided.py` still could not. | ------------------------ resolve_undecided.py runs `mvn dependency:tree` in ONE module: the one guessed from the adaptation's changed file path (`<x>/src/main/...` -> `<x>/pom.xml`). In a multi-module |
| `collect_code_hits.py` | Collect a raw code-search hit set: every (repo, path) whose CURRENT content contains | --------------------------------------------------------------- find_adaptations' code-search path finds the same files but then dates them inline, and it does so in two ways that are now known to be wrong: |
| `date_hits.py` | Date every repo in a cached code-search hit set: when did this file first contain the | fetching content at each until the identifier appears: up to 100 content fetches per file. Across 241 repos that is ~24k calls against a 5,000/hr limit. Since the identifier is present today and was introduced once, "contains it" is monotonic along the path's  |
| `extract_undecided.py` | pull the UNDECIDED traversal rows out of a classify checkpoint. | resolve_undecided.py takes a corpus of classify rows and re-decides the ones the POM walk gave up on (`traversal.resolution == "unresolved"`). Those rows live inside the classify checkpoint, wrapped in a decision envelope, so they were being extracted by |
| `mine_major_bumps.py` |  | ─────────────────── Discovery-first mining for the "TOP library, RECENT MAJOR release" strategy. For each curated library in specs/top_maven_majors.json (top, simple, NON-Android, |
| `resolve_undecided.py` | decide the traversal rows the POM walk could not. | ----------- verify_traversal resolves a transitively-supplied library version by walking POMs over HTTP (resolve_version.py). That walk cannot see through a BOM or a parent POM it cannot |
| `retraverse.py` | re-run verify_traversal over ALREADY-MINED candidates. | called .get() on GitHub's list responses (JSON arrays), and find_boundary_bump swallowed the AttributeError as "no commits". Both fixed in bbc_e2e.py; every traversal verdict recorded before that fix is meaningless and must be redone. |
| `screen_dated.py` | Turn dated code-search rows into candidate verdicts: is this repo's adaptation a genuine | RECOVERY from the break, or noise that merely mentions the API? Runs after discover/date_hits.py. Three filters, cheapest first, because each costs API calls and the population is mostly noise: |
| `screen_majors.py` | which major boundaries are even ELIGIBLE to yield a BBC case. | --- A BBC case requires a client that COMPILES unchanged across the boundary and fails at run time. A major release that removes public API breaks the client at javac instead, so the |
| `test_date_hits.py` | Offline check of date_hits.date_repo: earliest-across-files, and the prune's exactness. | Stubs the two GitHub calls so this needs no token and no network. The fixture is modelled on apache/tika: an OLD adaptation in a long-named file, and a LATER one in a shorter-named file that the old pick_file would have chosen. |

## If you are looking for something specific

* **why every traversal verdict before 2026-08-03 was void** — `retraverse.py`
* **why `verified_bbc` means two different things** — `audit_traversal.py`
* **how undecided traversals were resolved** — `resolve_undecided.py`, then `closeout_traversal.py`
* **which major boundaries were ruled ineligible** — `screen_majors.py`
* **the code-search discovery route** (as opposed to commit search) — `collect_code_hits.py`, `date_hits.py`, `screen_dated.py`
* **the agent acceptance dry-runs that preceded the registered subagent** — `acceptance_*.py`
