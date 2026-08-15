# traversal/ — did the client actually cross the boundary?

The gate that separates *"adapted to this break"* from *"wrote this code while already past it"*.

- `find_crossing.py` — walks a build file's history to find the commit that moved the library
  across the boundary.
- `resolve_version.py` — what version a build file actually declares at a given commit.

## Three outcomes, and the differences matter

| outcome | meaning | counts? |
|---|---|---|
| **crossed** | was below the boundary, ended up at or above it | yes |
| **born past the boundary** | first version already at or above it — never crossed, so the restrictive default was a latent bug, not a break they lived through | no |
| **unresolved / transitive** | the version is BOM- or parent-managed and could not be resolved | no — out of scope |

**Transitive is out of scope by decision.** The study covers direct-dependency bumps only.
Record the count as an excluded category (the rarity argument needs the denominator, and a
reviewer will ask), but do not pursue them.

That scoping is not free: transitive delivery produced two verified cases before the rule
changed, both Axon-mediated. They stay in `verified_cases/`; the rule is not retroactive.

## Why "unresolved" is not "did not cross"

They look the same in a summary table and mean opposite things. One is a measurement; the
other is a failure to measure. Keep them distinct in anything you report.

The one-shot scripts that resolved undecided rows, and the audit that found every pre-2026-08-03
traversal verdict was void, are in `archive/`.
