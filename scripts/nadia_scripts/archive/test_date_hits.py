"""Offline check of date_hits.date_repo: earliest-across-files, and the prune's exactness.

Stubs the two GitHub calls so this needs no token and no network. The fixture is modelled
on apache/tika: an OLD adaptation in a long-named file, and a LATER one in a shorter-named
file that the old pick_file would have chosen.
"""
import sys, pathlib
sys.path.insert(0, r"C:\bump-p4p\scripts\nadia_scripts\discover")
sys.path.insert(0, r"C:\bump-p4p\scripts\nadia_scripts")

import date_hits as D
import bbc_e2e as B

IDENT = "setStreamReadConstraints"

# path -> list of (sha, date, contains_identifier), newest first
REPO = {
    # short path, newer file: call introduced 2025-12-17
    "a/src/main/java/Short.java": [
        ("s3", "2026-01-05", True),
        ("s2", "2025-12-17", True),
        ("s1", "2025-11-01", False),
    ],
    # long path, older file: call introduced 2023-10-14  <-- the true answer
    "a/src/main/java/very/deep/pkg/LongerName.java": [
        ("l4", "2024-05-05", True),
        ("l3", "2023-10-14", True),
        ("l2", "2023-06-01", False),
        ("l1", "2021-01-01", False),
    ],
    # decoy: history starts AFTER 2023-10-14, so it must be pruned without any bisect
    "a/src/main/java/Late.java": [
        ("x2", "2026-02-02", True),
        ("x1", "2024-01-01", True),
    ],
}

fetched = []          # (path, sha) content fetches -- what the prune should reduce


def fake_gh(url, token, **kw):
    path = kw.get("path")
    if kw.get("page", 1) > 1:
        return []
    return [{"sha": sha, "commit": {"author": {"date": d + "T00:00:00Z"},
                                    "message": f"commit {sha}"}}
            for sha, d, _ in REPO[path]]


def fake_gh_file(repo, path, sha, token):
    fetched.append((path, sha))
    for s, _, has in REPO[path]:
        if s == sha:
            return IDENT if has else "nothing here"
    return None


B._gh = fake_gh
B._gh_file = fake_gh_file
D.B = B

paths = D.pick_files(list(REPO))
print("pick_files order (shortest first):")
for p in paths:
    print("   ", p)
assert len(paths) == 3, "all three prod files must be dated, not one"

row = D.date_repo("a/b", paths, IDENT, "tok", max_files=12)

print("\nresult date :", row.get("date"))
print("result path :", row.get("path"))
print("bisected    :", row.get("files_bisected"), "of", row.get("files_considered"))
for f in row["per_file"]:
    print("   ", f)

assert row["date"] == "2023-10-14", f"expected earliest 2023-10-14, got {row['date']}"
assert row["path"].endswith("LongerName.java"), row["path"]
# Visiting oldest-history-first means the truly-oldest file is bisected FIRST, after which
# every later-starting file is pruned. So one bisect, not one per file.
assert row["files_bisected"] == 1, f"only the oldest-starting file needs a bisect, got {row['files_bisected']}"
assert sum(1 for f in row["per_file"] if f.get("skipped")) == 2, "both later files should be pruned"
for pruned in ("a/src/main/java/Late.java", "a/src/main/java/Short.java"):
    assert not any(p == pruned for p, _ in fetched), f"{pruned} must cost ZERO content fetches"

print("\nPASS: earliest-across-files correct; prune exact and free")
print("content fetches:", len(fetched), "(all on the one bisected file)")
print("old pick_file would have returned:",
      sorted(REPO, key=lambda p: (len(p), p))[0], "-> 2025-12-17 (out of window)")
