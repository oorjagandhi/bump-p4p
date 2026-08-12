"""
bbc_pipeline.py
───────────────
Orchestrates the BBC-adaptation mining workflow we validated by hand (xstream,
POI, jsoup). It automates the DETERMINISTIC stages; the three JUDGMENT steps
(marked below) are supplied by a human or an LLM agent via a per-break "spec".

Pipeline (each stage is a subcommand):

  1. characterize <bump_sha>
        Read BUMP's reproduction log for a breaking commit and pull out the
        FAILING TEST(s) and their assertion diff.                 [deterministic]

  2. mine <spec.json>
        GitHub code-search for OTHER repos that did the same dependency update
        (repos already on the new version).                        [deterministic]

  3. filter <spec.json> <repo> [repo ...]
        Shallow-clone each repo and keep only those whose code uses the library
        in the AFFECTED way (spec.affected_usage_regex).           [deterministic]

  4. inspect <repo> <artifactId> <keyword> <boundary>
        Find the version-transition commit and what changed alongside the bump
        (delegates to find_adaptation.py).                         [deterministic]

JUDGMENT steps an agent/human must provide in the spec (this is the non-scriptable
part — reasoning, not plumbing):
  • root_cause          — what library behaviour changed (read from the failing
                          test + assertion diff produced by stage 1)
  • affected_usage_regex— the code pattern the break actually affects
                          (e.g. jsoup: \\.outerHtml\\(|\\.html\\(\\) ; POI:
                          setByteArrayMaxOverride ; xstream: allowTypes)
  • mimic test          — a small test reproducing the break, run old-vs-new
                          (see the standalone mimics under scratchpad; generating
                          one per break/repo is the agent's job)

Spec file schema (JSON) — see specs/jsoup-1.15-whitespace.json:
  {
    "break_id": "...",
    "library": {"group_id","artifact_id","from_version","to_version","boundary"},
    "bump_breaking_commit": "<sha>",       # for stage 1
    "code_search_query": "...",            # for stage 2
    "affected_usage_regex": "...",         # for stage 3  (JUDGMENT)
    "root_cause": "..."                    # documentation (JUDGMENT)
  }

Env: set GH_TOKEN for stage 2 (GitHub code search needs auth).
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
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parents[2]
GH = "https://api.github.com"


# ── stage 1: characterize ──────────────────────────────────────────────────────

_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _clean_log(text: str) -> str:
    """BUMP repro logs are ANSI-coloured with embedded carriage returns, which
    breaks line-anchored regexes. Strip escapes and normalise CR -> LF."""
    return _ANSI.sub("", text).replace("\r\n", "\n").replace("\r", "\n")


def characterize(sha: str):
    """Pull the failing test(s) + assertion diff from BUMP's reproduction log.

    DEAD SINCE 2026-08-12: reproductionLogs/ was deleted with the rest of the BUMP
    corpus. The parsing below is kept because it is hardened against three surefire
    formats and ANSI-dirty logs, and re-deriving it would be tedious — but it has no
    input here any more. What it produced is already baked into the catalog: 12 of the
    13 BUMP-sourced breaks carry their `characterization.failing_tests` inline, which
    is what every downstream stage actually reads. To run this again, restore the logs
    from upstream chains-project/bump.
    """
    logs = list((REPO_ROOT / "reproductionLogs").glob(f"**/{sha}*.log"))
    if not logs:
        sys.exit(
            f"no reproduction log for {sha}: reproductionLogs/ was deleted on 2026-08-12.\n"
            "The failing tests it would have extracted are already in "
            "specs/bump_breaks_catalog.json under characterization.failing_tests.\n"
            "To re-run characterize, restore reproductionLogs/ from chains-project/bump.")
    text = _clean_log(logs[0].read_text(encoding="utf-8", errors="replace"))
    print(f"[characterize] {logs[0].relative_to(REPO_ROOT)}\n")

    tests = []
    # (a) inline surefire: "method(pkg.Class)" or "[ERROR] pkg.Class.method"
    #     followed by "Time elapsed ... <<< FAILURE/ERROR". (may be space-indented)
    tests += re.findall(
        r"^\s*(?:\[\w+\]\s*)?([\w.]+(?:\([\w.$]+\)|\.\w+))\s+Time elapsed[^\n]*<<<",
        text, re.M)
    # (b) inline without "Time elapsed": "pkg.Class.method ... <<< FAILURE/ERROR".
    tests += re.findall(
        r"^\s*(?:\[\w+\]\s*)?([\w.$]+(?:\([\w.$]+\)|\.\w+))[^\n]*<<<\s+(?:FAILURE|ERROR)",
        text, re.M)
    # (c) final surefire summary block: "[ERROR]   Class.method:line->..." lines
    #     under a "Failed tests:" / "Tests in error:" heading (optional "- " bullet).
    tests += re.findall(
        r"^\s*(?:\[\w+\]\s+)?[-*]?\s*((?:[\w.$]+\.)?[\w$]+(?:Test|IT|Tests|TestCase|Spec)"
        r"[\w$]*[.#]\w+)(?::\d+)?", text, re.M)
    # (d) Carrotsearch RandomizedTesting: "FAILURE 0.06s J0 | Class.method <<<".
    tests += re.findall(
        r"^\s*(?:FAILURE|ERROR)\s+[\d.]+s\s+J\d+\s+\|\s+([\w.$]+[.#]\w+)\s+<<<",
        text, re.M)

    diffs = re.findall(r"(expected:.*?but was:.*)$", text, re.M)
    exc = re.findall(
        r"^(?:\[\w+\]\s*)?(?:Caused by:\s*)?"
        r"([\w.$]+\.(?:[\w$]*Exception|[\w$]*Error|ComparisonFailure))\b[^\n]*",
        text, re.M)
    # drop the generic JUnit assertion wrapper unless it's the only signal
    exc_specific = [e for e in exc if e != "java.lang.AssertionError"]

    print("FAILING TEST(S):")
    for t in dict.fromkeys(tests):
        print("  -", t)
    print("\nASSERTION DIFF(S):")
    for d in list(dict.fromkeys(diffs))[:5]:
        print("  -", d[:300])
    print("\nEXCEPTION SIGNAL(S):")
    for e in list(dict.fromkeys(exc_specific or exc))[:5]:
        print("  -", e[:200])
    print("\n>>> JUDGMENT: from the above, fill spec.root_cause and "
          "spec.affected_usage_regex.")


# ── stage 2: mine ──────────────────────────────────────────────────────────────

def gh_code_search(query, token, max_pages=3):
    repos, page = {}, 1
    while page <= max_pages:
        r = requests.get(f"{GH}/search/code",
                         headers={"Authorization": f"Bearer {token}",
                                  "Accept": "application/vnd.github+json"},
                         params={"q": query, "per_page": 100, "page": page},
                         timeout=30)
        data = r.json()
        if "items" not in data:
            print(f"[mine] API: {data.get('message')}", file=sys.stderr)
            break
        for it in data["items"]:
            repos[it["repository"]["full_name"]] = True
        if len(data["items"]) < 100:
            break
        page += 1
    return list(repos)


def mine(spec):
    token = os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("set GH_TOKEN for stage 2 (GitHub code search needs auth)")
    q = spec["code_search_query"]
    print(f"[mine] query: {q}")
    repos = gh_code_search(q, token)
    print(f"[mine] {len(repos)} distinct repos did the update:")
    for r in repos:
        print("  ", r)
    return repos


# ── stage 3: filter by affected usage ──────────────────────────────────────────

def _clone_shallow(repo, dest):
    return subprocess.run(
        ["git", "clone", "--depth", "1", "--quiet",
         f"https://github.com/{repo}.git", str(dest)],
        capture_output=True).returncode == 0


def filter_affected(spec, repos):
    regex = re.compile(spec["affected_usage_regex"])     # JUDGMENT input
    lib = spec["library"]["artifact_id"].lower()
    print(f"[filter] affected-usage regex: {spec['affected_usage_regex']}\n")
    affected = []
    with tempfile.TemporaryDirectory() as tmp:
        for repo in repos:
            d = Path(tmp) / repo.replace("/", "__")
            if not _clone_shallow(repo, d):
                print(f"  clone-fail {repo}"); continue
            # walk .java files in-process (portable; avoids shell/Windows-path issues).
            # keep files that BOTH match the affected-usage regex AND reference the lib.
            hits = []
            for jf in d.rglob("*.java"):
                try:
                    txt = jf.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                if lib in txt.lower() and regex.search(txt):
                    hits.append(jf.relative_to(d))
            if hits:
                affected.append(repo)
                print(f"  AFFECTED  {repo}")
                for rp in hits[:3]:
                    print(f"              {rp}")
            else:
                print(f"  (skip)    {repo}  -- no affected usage")
    print(f"\n[filter] {len(affected)}/{len(repos)} repos use the library the "
          f"affected way -> candidates for the mimic/differential.")
    return affected


# ── stage 4: inspect (delegate to find_adaptation.py) ──────────────────────────

def inspect(repo, artifact, keyword, boundary):
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp) / "repo"
        print(f"[inspect] cloning {repo} …")
        if subprocess.run(["git", "clone", "--filter=blob:none", "--quiet",
                           f"https://github.com/{repo}.git", str(d)]).returncode != 0:
            sys.exit("clone failed")
        subprocess.run([sys.executable,
                        str(Path(__file__).with_name("find_adaptation.py")),
                        str(d), artifact, keyword, boundary])


# ── cli ────────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("characterize"); p.add_argument("bump_sha")
    p = sub.add_parser("mine"); p.add_argument("spec")
    p = sub.add_parser("filter"); p.add_argument("spec"); p.add_argument("repos", nargs="*")
    p = sub.add_parser("inspect")
    p.add_argument("repo"); p.add_argument("artifact")
    p.add_argument("keyword"); p.add_argument("boundary")
    args = ap.parse_args()

    if args.cmd == "characterize":
        characterize(args.bump_sha)
    elif args.cmd == "mine":
        mine(json.load(open(args.spec, encoding="utf-8")))
    elif args.cmd == "filter":
        spec = json.load(open(args.spec, encoding="utf-8"))
        repos = args.repos or mine(spec)
        filter_affected(spec, repos)
    elif args.cmd == "inspect":
        inspect(args.repo, args.artifact, args.keyword, args.boundary)


if __name__ == "__main__":
    main()
