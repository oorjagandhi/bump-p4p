#!/usr/bin/env python3
"""
Add a `links` block to every verified case: clickable URLs for the adaptation commit and
the bump commit that crossed the break boundary.

WHY. Every case file already carries the two SHAs that matter, but reading one meant
copying a 8-to-12 character hex string into a GitHub URL by hand. The SHAs also live under
different keys depending on when the case was written (`in_repo_version_transition
.bump_commit`, `adaptation.bump_commit`, or nowhere at all when the bump is bundled into
the adaptation commit), so "where is the bump" was a per-file question. This resolves that
once and writes the answer down.

RESOLUTION ORDER for the bump commit, most explicit first:
  1. in_repo_version_transition.bump_commit  — the field newer cases use
  2. adaptation.bump_commit                  — the field xstream-tvrenamer uses
  3. traversal.distance_commits == 0         — bundled: the bump IS the adaptation commit
  4. otherwise                               — no URL, and a note saying so rather than a guess

Nothing is inferred beyond those rules. A case whose bump commit cannot be resolved gets
`bump_commit: null` with `_bump_commit_note` explaining what the file does say, because a
URL that silently points at the wrong commit is worse than no URL.

Usage:
  python add_case_links.py            # report what would change
  python add_case_links.py --write    # write it
  python add_case_links.py --write --include-excluded
"""
from __future__ import annotations
import argparse, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CASES = os.path.join(os.path.dirname(HERE), "verified_cases")

VERIFIED_DIRS = ("jackson-core", "snakeyaml", "xstream", "pending_differential")


def case_files(include_excluded: bool) -> list:
    out = []
    for dirpath, dirs, files in os.walk(CASES):
        rel = os.path.relpath(dirpath, CASES)
        top = rel.split(os.sep)[0]
        if top == "drivers":
            continue
        if top == "excluded" and not include_excluded:
            continue
        if rel != "." and top not in VERIFIED_DIRS and top != "excluded":
            continue
        out += [os.path.join(dirpath, f) for f in files if f.endswith(".json")]
    return sorted(out)


def commit_url(repo: str, sha: str) -> str:
    return f"https://github.com/{repo}/commit/{sha}"


def leading_sha(value) -> str | None:
    """The commit SHA at the START of a field, or None if the field does not begin with one.

    Several of these fields hold PROSE, not a SHA -- xstream-axon-artshishkin's bump_commit
    is a sentence about which release added the starter, and xstream-tvrenamer's is a SHA
    followed by an explanation. Pasting either into a URL yields a link to nothing, which is
    worse than no link, so only a leading hex token of plausible length is accepted and
    everything else is refused.
    """
    if not isinstance(value, str):
        return None
    head = value.strip().split()[0] if value.strip() else ""
    ok = 7 <= len(head) <= 40 and all(c in "0123456789abcdefABCDEF" for c in head)
    return head if ok else None


def resolve_bump(case: dict) -> tuple:
    """(sha, note). sha is None when the file does not determine one."""
    trans = case.get("in_repo_version_transition") or {}
    adapt = case.get("adaptation") or {}
    trav = case.get("traversal") or {}

    for field, raw in (("in_repo_version_transition.bump_sha", trans.get("bump_sha")),
                       ("in_repo_version_transition.bump_commit", trans.get("bump_commit")),
                       ("adaptation.bump_commit", adapt.get("bump_commit"))):
        sha = leading_sha(raw)
        if sha:
            # Keep the rest of the field when it carried prose, so linking loses nothing.
            extra = raw.strip()[len(sha):].strip()
            return sha, (f"from {field}: {extra}" if extra else None)

    dist = trav.get("distance_commits", trans.get("distance_commits"))
    if dist == 0:
        return adapt.get("commit"), ("bundled: this file records distance_commits = 0, so the "
                                     "version bump is in the adaptation commit itself")
    if dist == 1 and (adapt.get("parent") or adapt.get("parent_commit")):
        # Not a guess: distance 1 means the bump is the immediately preceding commit, which is
        # the recorded parent. Confirmed on voyanttools/trombone, whose parent d03c123773d1 is
        # titled "update xstream version" and touches pom.xml.
        return (adapt.get("parent") or adapt.get("parent_commit")), (
            "derived: this file records distance_commits = 1 and names no bump SHA, so the bump "
            "is the adaptation's parent commit")
    if dist is None:
        return None, "no bump commit recorded in this file, and no distance_commits to infer one from"
    return None, (f"no bump commit recorded in this file; traversal says the bump is "
                  f"{dist} commit(s) before the adaptation, which does not name it")


def build_links(case: dict) -> dict | None:
    adapt = case.get("adaptation") or {}
    repo, adapt_sha = adapt.get("repo"), adapt.get("commit")
    if not repo or not adapt_sha:
        return None
    links = {"repo": f"https://github.com/{repo}",
             "adaptation_commit": commit_url(repo, adapt_sha)}
    parent = adapt.get("parent") or adapt.get("parent_commit")
    if parent:
        links["parent_commit"] = commit_url(repo, parent)
    bump_sha, note = resolve_bump(case)
    links["bump_commit"] = commit_url(repo, bump_sha) if bump_sha else None
    if note:
        links["_bump_commit_note"] = note
    return links


def insert_links_text(text: str, links: dict) -> str:
    """Splice a `links` block in after the case_id line, leaving the rest of the file alone.

    Re-serialising with json.dump was the obvious implementation and the wrong one: these
    files are hand-formatted (two-space indent, blank lines between top-level blocks) and
    json.dump normalises all of it, turning a five-line addition into a thousand-line diff
    that buries the actual change. So the block is spliced in as TEXT, matching the file's
    own indent, and every other byte is left as it was.

    Re-running is safe: an existing top-level `links` block is removed first.
    """
    lines = text.split("\n")

    # Drop a previous block, so this is idempotent. Values are plain strings, so the block
    # ends at the first line that is exactly the closing brace at the block's own indent.
    for i, line in enumerate(lines):
        stripped = line.lstrip()
        if stripped.startswith('"links":') and stripped.rstrip().endswith("{"):
            indent = line[:len(line) - len(stripped)]
            for j in range(i + 1, len(lines)):
                if lines[j].rstrip() in (indent + "},", indent + "}"):
                    del lines[i:j + 1]
                    break
            break

    anchor = next((i for i, l in enumerate(lines) if l.lstrip().startswith('"case_id"')), None)
    if anchor is None:
        anchor = 0                              # no case_id: put it first, after the brace
    indent = lines[anchor][:len(lines[anchor]) - len(lines[anchor].lstrip())] or " "
    step = indent                               # the file's own indent is its step

    body = [f'{indent}"links": {{']
    items = [(k, v) for k, v in links.items()]
    for n, (k, v) in enumerate(items):
        comma = "" if n == len(items) - 1 else ","
        body.append(f"{indent}{step}{json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}{comma}")
    body.append(f"{indent}}},")

    return "\n".join(lines[:anchor + 1] + body + lines[anchor + 1:])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="write the files (default: report only)")
    ap.add_argument("--include-excluded", action="store_true",
                    help="also link the cases under excluded/")
    args = ap.parse_args()

    changed = skipped = 0
    for path in case_files(args.include_excluded):
        text = open(path, encoding="utf-8", newline="").read()
        case = json.loads(text)
        links = build_links(case)
        rel = os.path.relpath(path, CASES)
        if not links:
            print(f"[skip] {rel}: no adaptation.repo/commit to link")
            skipped += 1
            continue
        bump = links["bump_commit"] or f"(none — {links.get('_bump_commit_note','')[:60]})"
        print(f"[ok  ] {rel}\n        adaptation: {links['adaptation_commit']}\n"
              f"        bump:       {bump}")
        if args.write:
            new_text = insert_links_text(text, links)
            json.loads(new_text)                # never write a file we just broke
            # newline="": the spliced text already carries the file's own line endings, and
            # Windows text mode would rewrite every one of them.
            with open(path, "w", encoding="utf-8", newline="") as f:
                f.write(new_text)
        changed += 1

    print(f"\n{changed} case(s) {'written' if args.write else 'would change'}, {skipped} skipped")
    if not args.write:
        print("(dry run — pass --write to apply)")


if __name__ == "__main__":
    main()
