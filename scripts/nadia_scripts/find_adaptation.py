"""
find_adaptation.py
──────────────────
Mechanical half of the BBC-adaptation pipeline (the deterministic part).

Given a cloned client repo + the (artifactId, version-property keyword, breaking
boundary), find the TRANSITION COMMIT — the commit where the dependency's version
first crossed the confirmed-breaking boundary — and show what changed ALONGSIDE
the version bump (the candidate adaptation).

It does NOT judge whether the change is a genuine adaptation, its type, or
whether it's test-only — that's the judgment half (human / AI agent), applied to
this output. See verified_cases/ for the resulting curated records.

Usage:
    python find_adaptation.py <repo_dir> <artifactId> <keyword> <boundary>
    e.g. python find_adaptation.py ./sardine httpclient httpclient 4.5.13
"""

import re
import subprocess
import sys


def sh(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          errors="replace").stdout


def pad(v):
    head = re.split(r"[-+]", v.strip(), maxsplit=1)[0]
    nums = []
    for p in head.split("."):
        m = re.match(r"\d+", p)
        if not m:
            break
        nums.append(int(m.group()))
    return tuple((nums + [0, 0, 0])[:3]) if nums else None


def version_in_pom(text, artifact, keyword):
    """Resolve the artifact's version in a pom's text: try a <keyword.version>
    property first, then an inline <version> in the artifact's <dependency>."""
    m = re.search(r"<" + re.escape(keyword) + r"\.version>\s*([\w.\-]+)\s*</", text, re.I)
    if m:
        return m.group(1)
    for mm in re.finditer(
            r"<artifactId>\s*" + re.escape(artifact) + r"\s*</artifactId>(.*?)</dependency>",
            text, re.S | re.I):
        vm = re.search(r"<version>\s*([\w.\-]+)\s*</version>", mm.group(1))
        if vm and "$" not in vm.group(1):
            return vm.group(1)
    return None


def main():
    repo, artifact, keyword, boundary_s = sys.argv[1:5]
    boundary = pad(boundary_s)

    poms = [p for p in sh(["git", "ls-files", "*pom.xml"], repo).splitlines() if p]
    # keep only poms that mention the artifact somewhere in history's current tree
    poms = [p for p in poms if artifact in sh(["git", "show", f"HEAD:{p}"], repo)] or poms

    # Walk commits that touched those poms, oldest first; find the first commit
    # whose resolved version is >= the breaking boundary.
    log = sh(["git", "log", "--reverse", "--format=%H", "--"] + poms, repo).split()
    prev_ver = None
    for sha in log:
        for p in poms:
            text = sh(["git", "show", f"{sha}:{p}"], repo)
            if not text:
                continue
            ver = version_in_pom(text, artifact, keyword)
            if not ver:
                continue
            pv = pad(ver)
            if pv and boundary and pv >= boundary:
                # transition found
                parent_ver = prev_ver or "(unknown)"
                print(f"TRANSITION COMMIT: {sha}")
                print(f"  version crossed boundary: {parent_ver} -> {ver}  (boundary {boundary_s})")
                meta = sh(["git", "show", "--no-patch",
                           "--format=%an | %ad | %s", sha], repo).strip()
                print(f"  {meta}")
                files = sh(["git", "show", "--name-only", "--format=", sha], repo).split("\n")
                files = [f for f in files if f.strip()]
                nonpom = [f for f in files if not f.endswith("pom.xml")]
                code = [f for f in nonpom if f.endswith((".java", ".kt", ".scala", ".groovy"))]
                test_code = [f for f in code if "/test/" in f.lower()]
                prod_code = [f for f in code if "/test/" in f.lower()] and [] or \
                            [f for f in code if "/test/" not in f.lower()]
                print(f"  files changed: {len(files)} total | {len(code)} source "
                      f"({len(prod_code)} prod, {len(test_code)} test)")
                if not code:
                    print("  => POM-ONLY bump (no code changed with it -> not affected, or fixed elsewhere)")
                else:
                    print("  => code changed alongside bump -> CANDIDATE ADAPTATION:")
                    for f in code:
                        tag = "TEST" if "/test/" in f.lower() else "PROD"
                        print(f"       [{tag}] {f}")
                return
            if pv:
                prev_ver = ver
    print("NO TRANSITION FOUND (version never reached the boundary in history, "
          "or version is declared in a way this heuristic missed)")


if __name__ == "__main__":
    main()
