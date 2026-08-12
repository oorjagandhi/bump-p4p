#!/usr/bin/env python3
"""
mine_major_bumps.py
───────────────────
Discovery-first mining for the "TOP library, RECENT MAJOR release" strategy.

For each curated library in specs/top_maven_majors.json (top, simple, NON-Android,
recent major boundary), find client repos that upgraded ACROSS the major boundary and
ADAPTED to it -- preferring cases where the upgrade broke TESTS (test files touched, or
the message names a failure/fix). Every emitted row carries BOTH:

    - bump_commit       : the commit that crosses the major boundary in the client's own
                          build file (pom.xml / build.gradle), AND
    - adaptation_commit : the fix. This may be the SAME sha as the bump (bump-and-fix in
                          one commit) or a LATER sha (bump, then a separate fix).

It does NOT re-implement mining. It reuses the proven machinery in bbc_e2e.py:

    mine_commits        -> GitHub COMMIT-message search for upgrade/adaptation commits
    classify_commit     -> production vs test file split + dep version at commit & parent
    verify_traversal    -> walk the build-file history to find the boundary-crossing bump
                           and measure its commit-distance from the adaptation (0 = same
                           commit). find_boundary_bump only fires on a DIRECT-dep bump, so
                           transitive / BOM-managed / born-on-new clients correctly drop out.

Usage:
    export GH_TOKEN=...                     # GitHub search + contents API need auth
    python mine_major_bumps.py --list                 # show the seed catalog
    python mine_major_bumps.py                         # mine every library
    python mine_major_bumps.py --only mockito-core-5   # one library
    python mine_major_bumps.py --cap 20 --include-android

Output:
    output/major_bumps_candidates.jsonl     # every confirmed bump+adaptation row
    output/MAJOR_BUMPS_SHORTLIST.md         # ranked, human-readable
"""

# Scripts live one level down (discover/, mine/, traversal/, screen/, verify/) since
# the 2026-08 reorganisation, but they still import each other by module name and
# resolve data paths (output/, specs/, verified_cases/) against nadia_scripts/.
# This puts that root on sys.path so both keep working from anywhere.
import pathlib as _pl, sys as _sys
_NS_ROOT = _pl.Path(__file__).resolve().parent.parent
for _d in (_NS_ROOT, *(_NS_ROOT / _s for _s in
           ('discover', 'mine', 'traversal', 'screen', 'verify'))):
    if str(_d) not in _sys.path:
        _sys.path.insert(0, str(_d))

import argparse
import json
import sys
from pathlib import Path

# reuse the deterministic mining/verification stages we already validated
from bbc_e2e import (
    mine_commits,
    classify_commit,
    verify_traversal,
    _crosses_boundary,
    _token,
    CLASSIFY_CAP,
)

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent.parent
SEED = HERE / "specs" / "top_maven_majors.json"
OUT_DIR = HERE / "output"

# words in a commit message that suggest the upgrade broke (and someone fixed) tests /
# compilation -- the "with test failures" half of the lecturer's brief.
TEST_FAILURE_HINTS = [
    "test", "failing", "failure", "broke", "broken", "fix", "compile", "compilation",
    "error", "migrat", "adapt", "deprecat", "removed", "no longer", "replace",
]


def brk_from_seed(lib):
    """Build the minimal 'break' dict the bbc_e2e stages expect, from a seed entry.
    We don't have a known exception signal here (this is discovery, not a known break),
    so verify.signal_grep is left generic; the boundary is what the traversal needs."""
    return {
        "break_id": lib["id"],
        "library": {"group_id": lib["group_id"], "artifact_id": lib["artifact_id"]},
        "verify": {"break_boundary": lib["boundary"]},
        "mining": {
            "library_keyword": lib.get("keyword", lib["artifact_id"].split("-")[0]),
            "commit_search_terms": lib.get("search_terms", [lib["boundary"], "upgrade", "migrate"]),
        },
    }


def test_failure_signal(message):
    m = (message or "").lower()
    return sorted({h for h in TEST_FAILURE_HINTS if h in m})


def mine_library(lib, token, cap):
    """Return a list of confirmed rows (each with a bump + adaptation) for one library."""
    brk = brk_from_seed(lib)
    boundary = lib["boundary"]
    print(f"\n=== {lib['id']}  ({lib['group_id']}:{lib['artifact_id']}  boundary {boundary}) ===")
    rows = mine_commits(brk, token)
    if not rows:
        print("  (no commit-search hits)")
        return []

    confirmed = []
    naked_bumps = 0  # boundary-crossing bumps with NO code change (nothing to adapt)
    for r in rows[:cap]:
        c = classify_commit(r["repo"], r["sha"], brk, token)
        if c.get("error"):
            continue

        # The brief wants adaptations, not naked version bumps. A commit that changes ONLY
        # the build file (no src/main, no src/test) is a bump that needed no adaptation (or
        # whose failure lives only in CI) -- skip it, but count it so we can report the ratio.
        has_code_adaptation = bool(c.get("production_files")) or bool(c.get("test_files"))

        # A) fast path: THIS commit itself bumps the dep across the boundary (bump==fix).
        same_commit = (
            c.get("version_changed_here")
            and _crosses_boundary(c["version_at_parent"], c["version_at_commit"], boundary)
        )

        if same_commit and not has_code_adaptation:
            naked_bumps += 1
            continue  # naked bump: crosses the boundary but changes no code -> not an adaptation

        if same_commit:
            bump = {
                "bump_sha": c["sha"],
                "from": c["version_at_parent"],
                "to": c["version_at_commit"],
                "buildfile": "(same commit)",
                "distance_commits": 0,
            }
        else:
            # A separate adaptation must itself carry a code change (else it's just another
            # naked bump / no-op that happens to postdate the real bump).
            if not has_code_adaptation:
                continue
            # B) walk the build-file history for a boundary-crossing DIRECT-dep bump that
            #    precedes this adaptation (find_boundary_bump inside verify_traversal).
            t = verify_traversal(r["repo"], r["sha"], brk, token)
            if not t.get("traversal_confirmed"):
                continue  # no real direct bump -> transitive / BOM / born-on-new -> drop
            b = t["bump"]
            bump = {
                "bump_sha": b["bump_sha"],
                "from": b.get("from"),
                "to": b.get("to"),
                "buildfile": b.get("buildfile"),
                "distance_commits": t.get("distance_commits"),
            }

        tf = test_failure_signal(c["message"])
        row = {
            "library_id": lib["id"],
            "group_artifact": f"{lib['group_id']}:{lib['artifact_id']}",
            "boundary": boundary,
            "repo": r["repo"],
            "build_system": c.get("build_system"),
            "is_maven": c.get("is_maven"),
            "bump_commit": bump["bump_sha"],
            "bump_from": bump["from"],
            "bump_to": bump["to"],
            "bump_buildfile": bump["buildfile"],
            "adaptation_commit": c["sha"],
            "same_commit": bump["bump_sha"] == c["sha"],
            "commit_distance": bump["distance_commits"],
            "adaptation_message": c["message"],
            "touches_production": bool(c.get("production_files")),
            "touches_tests": bool(c.get("test_files")),
            "production_files": c.get("production_files", [])[:5],
            "test_files": c.get("test_files", [])[:5],
            "test_failure_signal": tf,
            "bump_url": f"https://github.com/{r['repo']}/commit/{bump['bump_sha']}",
            "adaptation_url": f"https://github.com/{r['repo']}/commit/{c['sha']}",
        }
        confirmed.append(row)
        kind = "SAME-COMMIT" if row["same_commit"] else f"+{row['commit_distance']} commits"
        tflag = "TESTS" if row["touches_tests"] else ("prod" if row["touches_production"] else "build-only")
        print(f"  [OK {kind:>14} | {tflag:10}] {r['repo']}  "
              f"{row['bump_from']}->{row['bump_to']}  {c['message'][:52]}")
    if naked_bumps:
        print(f"  ({naked_bumps} naked boundary-crossing bump(s) skipped — build-file only, "
              f"no code adaptation)")
    return confirmed


def rank_key(row):
    """Best first: real test-failure adaptations on Maven, then same-commit, then prod."""
    return (
        not row["touches_tests"],          # test-breaking upgrades first (the brief)
        not row["is_maven"],               # Maven verifiable next (our harness is Maven)
        not row["touches_production"],
        not row["same_commit"],
        row["commit_distance"] if row["commit_distance"] is not None else 999,
    )


def write_outputs(all_rows):
    OUT_DIR.mkdir(exist_ok=True)
    all_rows.sort(key=rank_key)

    jsonl = OUT_DIR / "major_bumps_candidates.jsonl"
    with jsonl.open("w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row) + "\n")

    lines = [
        "# Top-library recent-major-release — bump + adaptation candidates",
        "",
        "Discovery-first mining (`mine_major_bumps.py`) over the curated top / simple / "
        "non-Android libraries in `specs/top_maven_majors.json`. Every row has BOTH a "
        "**bump commit** (crosses the major boundary in the client's own build file) and an "
        "**adaptation commit** (same sha = bump-and-fix in one; or a later sha = separate fix).",
        "",
        "Ranked: test-breaking upgrades first, then Maven-verifiable, then production, then "
        "same-commit. `dist` = commits between bump and adaptation (0 = same commit).",
        "",
        "| # | library | repo | bump→ | dist | touches | signal | bump | adaptation |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(all_rows, 1):
        touches = "tests" if r["touches_tests"] else ("prod" if r["touches_production"] else "build")
        sig = ",".join(r["test_failure_signal"][:4]) or "-"
        lines.append(
            f"| {i} | `{r['library_id']}` | {r['repo']} | {r['bump_from']}→{r['bump_to']} | "
            f"{r['commit_distance']} | {touches} | {sig} | "
            f"[{r['bump_commit'][:8]}]({r['bump_url']}) | "
            f"[{r['adaptation_commit'][:8]}]({r['adaptation_url']}) |"
        )
    md = OUT_DIR / "MAJOR_BUMPS_SHORTLIST.md"
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"\n[write] {len(all_rows)} confirmed bump+adaptation rows")
    print(f"[write] {jsonl.relative_to(HERE)}")
    print(f"[write] {md.relative_to(HERE)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="mine a single library id from the seed catalog")
    ap.add_argument("--cap", type=int, default=CLASSIFY_CAP,
                    help=f"max commits to classify per library (default {CLASSIFY_CAP})")
    ap.add_argument("--include-android", action="store_true",
                    help="also mine libraries flagged android:true / android_adjacent (default: skip)")
    ap.add_argument("--list", action="store_true", help="print the seed catalog and exit")
    args = ap.parse_args()

    seed = json.loads(SEED.read_text(encoding="utf-8"))
    libs = seed["libraries"]

    if args.list:
        print(f"{'id':22} {'group:artifact':48} {'boundary':10} android")
        for l in libs:
            print(f"{l['id']:22} {l['group_id']+':'+l['artifact_id']:48} "
                  f"{l['boundary']:10} {l.get('android')}")
        print(f"\n{len(libs)} libraries. Coordinate-changing majors (reference only, not auto-mined): "
              f"{[c.get('lib') for c in seed.get('coordinate_change_majors', []) if c.get('lib')]}")
        return

    if args.only:
        libs = [l for l in libs if l["id"] == args.only]
        if not libs:
            sys.exit(f"--only '{args.only}' not in seed catalog (use --list)")
    elif not args.include_android:
        libs = [l for l in libs if not l.get("android")]

    token = _token()
    all_rows = []
    for lib in libs:
        try:
            all_rows.extend(mine_library(lib, token, args.cap))
        except SystemExit:
            raise
        except Exception as e:
            print(f"  [error] {lib['id']}: {e}", file=sys.stderr)

    write_outputs(all_rows)


if __name__ == "__main__":
    main()
