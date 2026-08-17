# Moving this toolkit to another repository

The short version:

```bash
cp -r scripts/nadia_scripts  <other-repo>/wherever/bbc-toolkit
cd <other-repo>/wherever/bbc-toolkit
python install.py
```

`install.py` prints what it changed and then what your machine is missing. That is the
whole procedure — there is no config file to edit and no path to search-and-replace.

---

## Why an installer at all, when it's "just one folder"

Everything the *pipeline* needs is inside the folder and stays inside it. Every script
resolves `output/`, `specs/` and `verified_cases/` against its own `__file__`, and
`paths.py` owns the layout, so the folder runs from a repo root, from `tools/`, or from
three directories down with no edits. That part genuinely is copy-and-paste.

Two things cannot live inside the folder, because the programs that read them only ever
look in one place:

| what | where it must be | why |
|---|---|---|
| ignore rules | `<repo>/.gitignore` | git reads ignore rules from the repo root and from directories above a file — never from a sibling folder |
| agents, permissions | `<repo>/.claude/` | Claude Code discovers project agents and settings at the project root, not next to the code they describe |

So the **masters live here**, in `portable/`, and travel with the folder. `install.py`
projects them out to the repo root. That is its only job.

```
portable/
  gitignore-block.txt          -> merged into <repo>/.gitignore
  claude/agents/*.md           -> copied to <repo>/.claude/agents/
  claude/settings.json         -> union-merged into <repo>/.claude/settings.json
```

**`portable/` is the master copy.** Edit the agent definition there, re-run `install.py`,
and the repo root picks it up. `install.py --check` reports drift without writing and
exits non-zero, so it works as a CI or pre-commit guard against the two copies diverging.

## What the install does to a repo that already has its own setup

Non-destructively, in all three cases — the target repo is assumed to have a life of its
own:

- **`.gitignore`** — rules go inside a `# >>> bbc-toolkit ... # <<<` block that is
  *replaced* on re-run, never appended twice. Existing rules are untouched.
- **`.claude/settings.json`** — the permission list is a **union**. Entries the host repo
  already had are never removed. Clobbering them would silently re-introduce prompts
  someone had already decided about.
- **`.claude/agents/`** — only the toolkit's own agent files are written, by name.

Running it twice is a no-op.

## Why the ignore rules are all `**/`-prefixed

Because the folder moves. A rule written `scripts/nadia_scripts/output/**/*_checkpoint.jsonl`
stops matching the moment the folder lands anywhere else — and **a prefixed rule that stops
matching is invisible**. Nothing errors. The mining checkpoints, the cloned client repos and
the hundreds-of-megabytes Maven cache just start getting committed. `**/` costs nothing and
cannot fail this way.

---

## Environment: the part that is genuinely machine-specific

`python install.py --doctor` reports all of it.

**JDKs.** `agent/orchestrator.py` scans the usual install roots for each major version it
needs (8, 11, 17, 21) — Program Files, `/usr/lib/jvm`, `JavaVirtualMachines`, SDKMAN,
`~/.jdks`, and the home directory. It accepts a directory only if `bin/java` is actually
there, so JREs and half-deleted installs are skipped. Override any one with
`BBC_JDK_8` / `BBC_JDK_11` / `BBC_JDK_17` / `BBC_JDK_21` rather than editing source.

> **Java 8 is not optional.** Clients old enough to be crossing these boundaries routinely
> predate the JDK's JAXB removal, so on 11+ they fail to compile *at baseline* — which the
> oracle reads as "baseline did not pass cleanly", i.e. as a false fact about the client.

**Maven repo.** `paths.m2_repo()` decides where `-Dmaven.repo.local` points, in this order:

1. `BBC_M2_REPO` — worth setting: this cache reaches hundreds of MB, which is a real
   constraint on a small system drive.
2. An **existing** `.bbc_m2` in any ancestor directory. Defaulting past a populated cache
   does not error; it just silently re-downloads everything into a second copy.
3. `<toolkit>/.bbc_m2` — inside the folder, correct on a machine that has never run this.

It is deliberately not `~/.m2`. A differential has to prove *which jar it resolved*, and a
shared repo full of other projects' artifacts and their `*.lastUpdated` failure markers is
exactly what makes that unprovable.

**Maven settings.** Every invocation runs under `agent/settings-bbc.xml`, which mirrors
Central only. A `<mirrorOf>*</mirrorOf>` in a user-level `settings.xml` has already caused
one false negative here. Set `BBC_MVN_SETTINGS=""` to fall back to `~/.m2/settings.xml`.

**GitHub token.** The mining and screening stages call the GitHub API and will rate-limit
without one. `github_token.txt` and `.env` are both in the installed ignore block.

## What not to copy

`install.py` does not care, but these are large and entirely regenerable — leave them
behind and the pipeline rebuilds them:

```
scratchpad/*/repo/    cloned client repositories
bbc-work/             hand-run verification clones
_runlogs/             per-state build logs
.bbc_m2/              the Maven cache
__pycache__/
```

`output/` and `verified_cases/` are the opposite: they are the research record, not build
output. ~11 MB together, and `ledger/census.py` regenerates `CENSUS.md` from them. Take
them if you want the findings; drop them if you want a clean pipeline with no results yet.
