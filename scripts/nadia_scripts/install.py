#!/usr/bin/env python3
"""Wire this toolkit folder into whatever repository it was just copied into.

The toolkit itself is self-locating: every script resolves `output/`, `specs/` and
`verified_cases/` against its own file, so the folder runs from anywhere with no edits.
Two things it needs, though, CANNOT live inside the folder, because the tools that read
them only look in one place:

  <repo>/.gitignore        git reads ignore rules from the repo root (and from the
                           directories above a file, but never from a sibling folder)
  <repo>/.claude/          Claude Code discovers project agents and settings at the
                           project root, not next to the code they describe

So the masters live in `portable/` here -- versioned, reviewed, copied along with the
folder -- and this script projects them out to the repo root. That is the whole job.

    python install.py                 # install into the repo containing this folder
    python install.py --check         # report drift, change nothing, exit 1 if any
    python install.py --repo <path>   # target a specific repo root
    python install.py --doctor        # only check the environment (JDKs, mvn, git)

Idempotent by construction: the .gitignore rules go inside a delimited block that is
replaced rather than appended, and the settings merge is a union that never drops an
entry the host repo already had. Running it twice is a no-op; running it after editing
`portable/` is how you push a change out.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

TOOLKIT = Path(__file__).resolve().parent
PORTABLE = TOOLKIT / "portable"

BEGIN = "# >>> bbc-toolkit gitignore (managed by install.py) >>>"
END = "# <<< bbc-toolkit gitignore <<<"
CUT = "---8<--- rules below this line are installed ---8<---"


# ---- helpers --------------------------------------------------------------

def _say(ok: bool, msg: str) -> None:
    print(f"  {'ok  ' if ok else 'CHANGE'}  {msg}")


def find_repo_root(start: Path) -> Path:
    """Nearest ancestor holding a .git. Falls back to the toolkit's parent.

    The fallback matters: the folder is legitimately usable outside a git repo (a
    scratch copy on another machine), and refusing to install there would make the
    common case -- copy, run, go -- fail for a reason that does not affect anything.
    """
    for d in (start, *start.parents):
        if (d / ".git").exists():
            return d
    return start.parent if start.parent != start else start


def rules_block() -> str:
    """The installable half of gitignore-block.txt (everything past the cut marker)."""
    text = (PORTABLE / "gitignore-block.txt").read_text(encoding="utf-8")
    body = text.split(CUT, 1)[1] if CUT in text else text
    return body.strip("\n")


# ---- the three installs ---------------------------------------------------

def install_gitignore(repo: Path, apply: bool) -> bool:
    """Replace (or add) the managed block in <repo>/.gitignore. Returns True if current."""
    target = repo / ".gitignore"
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    block = f"{BEGIN}\n{rules_block()}\n{END}"

    if BEGIN in existing and END in existing:
        head, rest = existing.split(BEGIN, 1)
        _, tail = rest.split(END, 1)
        updated = f"{head}{block}{tail}"
    else:
        sep = "" if existing.endswith("\n") or not existing else "\n"
        updated = f"{existing}{sep}\n{block}\n"

    if updated == existing:
        _say(True, ".gitignore block up to date")
        return True
    _say(False, f".gitignore block {'added' if BEGIN not in existing else 'updated'}")
    if apply:
        target.write_text(updated, encoding="utf-8")
    return False


def install_agents(repo: Path, apply: bool) -> bool:
    """Copy portable/claude/agents/*.md to <repo>/.claude/agents/."""
    src_dir = PORTABLE / "claude" / "agents"
    dst_dir = repo / ".claude" / "agents"
    current = True
    for src in sorted(src_dir.glob("*.md")):
        dst = dst_dir / src.name
        want = src.read_text(encoding="utf-8")
        have = dst.read_text(encoding="utf-8") if dst.exists() else None
        if have == want:
            _say(True, f".claude/agents/{src.name}")
            continue
        current = False
        _say(False, f".claude/agents/{src.name} {'differs' if have else 'missing'}")
        if apply:
            dst_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
    return current


def install_settings(repo: Path, apply: bool) -> bool:
    """Union-merge portable permissions into <repo>/.claude/settings.json.

    Union, not overwrite: the host repo may have its own allow-list that has nothing to
    do with this toolkit, and clobbering it would silently re-introduce prompts someone
    already decided about. The only thing this adds is entries that are missing.
    """
    dst = repo / ".claude" / "settings.json"
    want = json.loads((PORTABLE / "claude" / "settings.json").read_text(encoding="utf-8"))
    want_allow = want["permissions"]["allow"]

    have = {}
    if dst.exists():
        try:
            have = json.loads(dst.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"  SKIP    .claude/settings.json is not valid JSON ({e}); left untouched")
            return True

    have_allow = have.get("permissions", {}).get("allow", [])
    missing = [p for p in want_allow if p not in have_allow]
    if not missing:
        _say(True, ".claude/settings.json permissions")
        return True

    _say(False, f".claude/settings.json += {len(missing)} permission(s)")
    if apply:
        merged = dict(have)
        merged.setdefault("permissions", {})
        merged["permissions"] = dict(merged["permissions"])
        merged["permissions"]["allow"] = have_allow + missing
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    return False


# ---- environment ----------------------------------------------------------

def doctor() -> bool:
    """Report what the differential needs and whether this machine has it.

    Advisory, never fatal for the install: you can legitimately install the toolkit on a
    machine that will only run the mining and screening stages, which need neither Maven
    nor a JDK. It exits non-zero only so CI can tell.
    """
    print("\nEnvironment")
    ok = True

    for tool, why in (("git", "cloning candidate repos"),
                      ("mvn", "running the 3-state differential"),
                      ("python", "everything")):
        found = shutil.which(tool)
        _say(bool(found), f"{tool:<7} {found or f'NOT FOUND -- needed for {why}'}")
        ok &= bool(found)

    sys.path.insert(0, str(TOOLKIT / "agent"))
    try:
        from orchestrator import JDKS  # noqa: E402
    except Exception as e:                                    # pragma: no cover
        print(f"  SKIP    could not read the JDK table ({e})")
        return ok

    print("\nJDKs (override any with BBC_JDK_<n>)")
    for ver, path in sorted(JDKS.items(), key=lambda kv: int(kv[0])):
        present = path and (Path(path) / "bin").exists()
        _say(bool(present), f"JDK {ver:<3} {path if present else f'{path or 0} -- set BBC_JDK_{ver}'}")
        ok &= bool(present)

    print("\nMaven repo for differentials (override with BBC_M2_REPO)")
    sys.path.insert(0, str(TOOLKIT))
    from paths import m2_repo                                 # noqa: E402
    repo = m2_repo()
    _say(True, f"{repo}{'' if repo.exists() else '  (will be created on first run)'}")
    return ok


# ---- entry point ----------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", type=Path, help="repo root to install into (default: auto-detect)")
    ap.add_argument("--check", action="store_true", help="report drift without writing")
    ap.add_argument("--doctor", action="store_true", help="only check the environment")
    args = ap.parse_args(argv)

    if args.doctor:
        return 0 if doctor() else 1

    repo = (args.repo or find_repo_root(TOOLKIT)).resolve()
    apply = not args.check
    print(f"toolkit: {TOOLKIT}")
    print(f"repo:    {repo}{'' if (repo / '.git').exists() else '   (no .git here)'}")
    print(f"\n{'Installing' if apply else 'Checking'}")

    current = all([
        install_gitignore(repo, apply),
        install_agents(repo, apply),
        install_settings(repo, apply),
    ])

    doctor()

    if args.check:
        print("\nup to date" if current else "\ndrift found (re-run without --check to fix)")
        return 0 if current else 1
    print("\ndone" if not current else "\nalready installed; nothing to do")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
