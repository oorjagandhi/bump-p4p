# mine/ — find the commits

`bbc_e2e.py` is the orchestrator for the commit-search route and the largest script in the
repo. Most other scripts import it for its GitHub and version helpers.

```
python mine/bbc_e2e.py --help
```

The subcommands you will actually use:

| subcommand | what it does |
|---|---|
| `mine-commits <break_id>` | GitHub commit search using the catalog's search terms. |
| `classify <repo> <sha> <break_id>` | Splits a commit's files into production vs test, reads the dependency version at the commit and its parent, detects the build system. |
| `traversal <repo> <sha> <break_id>` | Did this client cross the boundary? |
| `run <break_id>` | mine → classify → traversal in one pass. |

## Only Maven clients are verifiable

The verification harness is Maven. Gradle and sbt candidates are flagged and de-prioritised at
`classify`, not verified. If a worklist row says `"build_system": "maven"`, that is a *claim*
made by the classifier — check it against the repo before spending a verification run on it.
At least one row has been wrong.

## Prefer the adaptation axis

This is the *bump* axis: it finds commits that bump the version. Many of them changed no Java
at all, and many bump between two versions on the same side of the boundary.
`discover/find_adaptations.py` searches for the recovery API instead, and on the breaks measured
so far it produced better candidates for a fraction of the API budget. Use this when the
adaptation identifier is not searchable, or to cover what identifiers miss.
