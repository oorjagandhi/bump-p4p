"""
bbc_e2e.py
──────────
End-to-end orchestrator for the BBC → external-production-adaptation workflow we
validated by hand on xstream/TVRenamer. It automates the DETERMINISTIC stages and
leaves clearly-marked seams for the two AI/human JUDGMENT stages.

Flow (each stage a subcommand), driven by specs/bump_breaks_catalog.json:

  characterize <break_id>          [deterministic]  failing test + signal from BUMP
                                                    (delegates to bbc_pipeline.characterize)
  mine-commits <break_id>          [deterministic]  GitHub COMMIT search for adaptation
                                                    commits (the winning tool for
                                                    bump-TRIGGERED fixes), per the
                                                    break's mining.commit_search_terms
  classify <repo> <sha> <break_id> [deterministic]  split a commit's files into
                                                    production (src/main) vs test, read
                                                    the dependency version at the commit
                                                    and its parent (transition), and
                                                    detect the build system. SCOPE: we
                                                    only VERIFY Maven clients (is_maven /
                                                    verifiable) — the harness is Maven, so
                                                    Gradle/sbt candidates are flagged and
                                                    de-prioritised, not verified.
  gen-harness <break_id> --repo --adapt-sha --parent-sha --out
                                   [scaffold]       emit a Maven harness (pom.xml),
                                                    a run_differential.sh, and a TEST
                                                    STUB derived from the BUMP failing
                                                    test — the stub body is the JUDGMENT
                                                    seam an agent/human completes
  run <break_id>                   [orchestration]  characterize -> mine -> classify,
                                                    printing production candidates ready
                                                    for gen-harness + verify

JUDGMENT seams (an AI agent or human supplies these; everything else is plumbing):
  • root_cause / affected_usage         — read from characterize output (spec.*)
  • mining.commit_search_terms          — the adaptation signature to search for
  • the generated test's BODY           — how to exercise the affected production path
                                          (gen-harness emits a stub + the characterization)

Env: GH_TOKEN required for mine-commits / classify (GitHub search + contents API).
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests

from bbc_pipeline import _clean_log, characterize  # reuse hardened log parsing

try:  # commit messages can contain non-cp1252 chars (e.g. CJK) on Windows
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
CATALOG = HERE / "specs" / "bump_breaks_catalog.json"
GH = "https://api.github.com"


# ── catalog helpers ─────────────────────────────────────────────────────────────

def load_catalog():
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def get_break(break_id):
    for b in load_catalog()["breaks"]:
        if b["break_id"] == break_id:
            return b
    sys.exit(f"break_id '{break_id}' not in {CATALOG.name}. "
             f"Known: {[b['break_id'] for b in load_catalog()['breaks']]}")


def _token():
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not tok:
        sys.exit("set GH_TOKEN (GitHub search + contents API need auth)")
    return tok


def _gh(url, token, **params):
    r = requests.get(url, headers={"Authorization": f"Bearer {token}",
                                   "Accept": "application/vnd.github+json"},
                     params=params, timeout=30)
    return r.json()


def _library_keyword(brk):
    m = brk.get("mining", {})
    if m.get("library_keyword"):
        return m["library_keyword"]
    # default: the artifact id's most distinctive token
    return brk["library"]["artifact_id"].split("-")[0]


# ── stage 2: mine-commits (COMMIT search) ───────────────────────────────────────

def gh_commit_search(query, token, max_pages=2):
    """Search commit MESSAGES. This is what surfaces bump-triggered fixes
    ('Fix XStream security exception', 'resolve ForbiddenClassException', …) —
    far better than code search for finding the ADAPTATION rather than mere usage."""
    out, page = [], 1
    while page <= max_pages:
        data = _gh(f"{GH}/search/commits", token, q=query, per_page=50, page=page)
        items = data.get("items")
        if items is None:
            print(f"[mine-commits] API: {data.get('message')}", file=sys.stderr)
            break
        out.extend(items)
        if len(items) < 50:
            break
        page += 1
    return out


def mine_commits(brk, token):
    mining = brk.get("mining", {})
    terms = mining.get("commit_search_terms")
    if not terms:
        sys.exit(f"break '{brk['break_id']}' has no mining.commit_search_terms — "
                 f"fill it in the catalog (JUDGMENT: the adaptation signature).")
    kw = _library_keyword(brk)
    seen, rows = set(), []
    for term in terms:
        q = f"{kw} {term}"
        print(f"[mine-commits] q='{q}'")
        for it in gh_commit_search(q, token):
            repo = it["repository"]["full_name"]
            sha = it["sha"]
            if (repo, sha) in seen:
                continue
            seen.add((repo, sha))
            rows.append({"repo": repo, "sha": sha,
                         "message": it["commit"]["message"].splitlines()[0][:80],
                         "matched_term": term})
    print(f"[mine-commits] {len(rows)} distinct commits across {len({r['repo'] for r in rows})} repos")
    return rows


# ── stage 3: classify a commit (production vs test + version transition) ─────────

BUILD_FILES = ["pom.xml", "build.gradle", "build.gradle.kts", "build.sbt", "ivy.xml"]


_SRC_EXT = (".java", ".scala", ".kt")


def _is_test_path(fn):
    return "src/test/" in fn or "/test/" in fn or re.search(r"(Test|IT|Spec)\.(java|scala|kt)$", fn)


def _is_prod_java(fn):
    return fn.endswith(_SRC_EXT) and not _is_test_path(fn) and (
        "src/main/" in fn or "src/java/" in fn or "src/" not in fn)


def _is_library_source(repo, prod_files, group_id, artifact_id):
    """Distinguish a client CALL from the library's own DEFINITION. Filters the
    'vendored/forked library source' false positive (e.g. apache/poi and its forks
    match a POI-API commit search, but the changed file IS the API, not a use of it)."""
    group_path = group_id.replace(".", "/")               # org.apache.poi -> org/apache/poi
    # (a) a changed file sits in the library's OWN package under src/main -> it's the lib
    if any(f"src/main/java/{group_path}" in f or f"src/java/{group_path}" in f
           for f in prod_files):
        return True
    # (b) the repo itself is (a fork of) the artifact
    base = artifact_id.split("-")[0].lower()               # poi-ooxml -> poi
    leaf = repo.split("/")[-1].lower()
    if leaf == base or leaf.endswith(base) or base in leaf:
        return True
    return False


def dep_version(text, group_id, artifact_id):
    """Best-effort read of the dependency version from pom.xml or gradle text."""
    if text is None:
        return None
    # gradle: 'group:artifact:1.2.3'  or  "group:artifact:1.2.3"
    m = re.search(rf"{re.escape(group_id)}:{re.escape(artifact_id)}:([0-9][\w.\-]*)", text)
    if m:
        return m.group(1)
    # gradle legacy: name: 'artifact', version: '1.2.3'
    m = re.search(rf"name:\s*['\"]{re.escape(artifact_id)}['\"].*?version:\s*['\"]([0-9][\w.\-]*)['\"]",
                  text, re.S)
    if m:
        return m.group(1)
    # maven: <artifactId>artifact</artifactId> ... <version>1.2.3</version>
    m = re.search(rf"<artifactId>\s*{re.escape(artifact_id)}\s*</artifactId>.*?"
                  rf"<version>\s*([0-9][^<]*)</version>", text, re.S)
    if m:
        return m.group(1).strip()
    return None


def classify_commit(repo, sha, brk, token):
    commit = _gh(f"{GH}/repos/{repo}/commits/{sha}", token)
    if "files" not in commit:
        return {"error": commit.get("message", "no files")}
    files = [f["filename"] for f in commit["files"]]
    prod = [f for f in files if _is_prod_java(f)]
    test = [f for f in files if _is_test_path(f)]
    parent = commit["parents"][0]["sha"] if commit.get("parents") else None

    gid, aid = brk["library"]["group_id"], brk["library"]["artifact_id"]
    ver_at = ver_parent = None
    for bf in BUILD_FILES:
        at = _gh_file(repo, bf, sha, token)
        v = dep_version(at, gid, aid)
        if v:
            ver_at = v
            if parent:
                ver_parent = dep_version(_gh_file(repo, bf, parent, token), gid, aid)
            break

    lib_source = _is_library_source(repo, prod, gid, aid)
    build_system = _detect_build_system(repo, sha, token)
    return {
        "repo": repo, "sha": sha, "parent": parent,
        "message": commit["commit"]["message"].splitlines()[0][:80],
        "production_files": prod,
        "test_files": test,
        "library_source": lib_source,
        "build_system": build_system,          # maven | gradle | sbt | unknown
        "is_maven": build_system == "maven",   # verification scope: Maven only
        "is_production_adaptation": bool(prod) and not lib_source,
        "verifiable": bool(prod) and not lib_source and build_system == "maven",
        "test_only": bool(test) and not prod,
        "version_at_commit": ver_at,
        "version_at_parent": ver_parent,
        "version_changed_here": bool(ver_at and ver_parent and ver_at != ver_parent),
    }


def _detect_build_system(repo, ref, token):
    """We only VERIFY Maven clients (the harness is Maven). Detect the build system
    so non-Maven candidates (Gradle/sbt) can be flagged and de-prioritised."""
    for fname, system in [("pom.xml", "maven"), ("build.sbt", "sbt"),
                          ("build.gradle", "gradle"), ("build.gradle.kts", "gradle")]:
        if _gh_file(repo, fname, ref, token) is not None:
            return system
    return "unknown"


def _gh_file(repo, path, ref, token):
    import base64
    d = _gh(f"{GH}/repos/{repo}/contents/{path}", token, ref=ref)
    if isinstance(d, dict) and d.get("content"):
        try:
            return base64.b64decode(d["content"]).decode("utf-8", "replace")
        except Exception:
            return None
    return None


def find_dep_version_decl(pom_text, group_id, artifact_id):
    """How is the target dependency's version declared? Returns
    ('property', name) | ('literal', value) | (None, None). Lets the reuse-pom
    harness override ONLY the baseline version, whichever way it's written."""
    if not pom_text:
        return (None, None)
    m = re.search(rf"<groupId>\s*{re.escape(group_id)}\s*</groupId>\s*"
                  rf"<artifactId>\s*{re.escape(artifact_id)}\s*</artifactId>\s*"
                  rf"<version>\s*([^<]+?)\s*</version>", pom_text, re.S)
    if not m:
        return (None, None)
    v = m.group(1).strip()
    pm = re.match(r"\$\{([^}]+)\}", v)
    return ("property", pm.group(1)) if pm else ("literal", v)


def pom_java_release(pom_text):
    """Read the repo's Java level from its pom (release/target/source) -> '8','11','17'."""
    for tag in ("maven.compiler.release", "maven.compiler.target", "maven.compiler.source"):
        m = re.search(rf"<{tag}>\s*([0-9.]+)\s*</{tag}>", pom_text or "")
        if m:
            return m.group(1).split(".")[-1]
    return None


# ── stage 5: gen-harness (Maven pom + differential runner + test STUB) ──────────

POM_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!-- AUTO-GENERATED Maven harness for the {break_id} BBC differential.
     Compiles the target repo's untouched production source and runs ONE authored
     test; the dependency version is parameterised via -D{prop}. -->
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>bbc.harness</groupId>
  <artifactId>{artifact}-bbc-harness</artifactId>
  <version>1.0</version>
  <properties>
    <maven.compiler.release>{java}</maven.compiler.release>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <{prop}>{to_version}</{prop}>
  </properties>
  <dependencies>
    <dependency>
      <groupId>{group_id}</groupId>
      <artifactId>{artifact_id}</artifactId>
      <version>${{{prop}}}</version>
    </dependency>
    <dependency>
      <groupId>junit</groupId><artifactId>junit</artifactId>
      <version>4.13.2</version><scope>test</scope>
    </dependency>
    <!-- TODO(JUDGMENT): add the repo's OTHER compile deps so src/main compiles
         (copy from its pom.xml / build.gradle). -->
  </dependencies>
  <build>
    <sourceDirectory>src/main/java</sourceDirectory>
    <testSourceDirectory>src/test/java</testSourceDirectory>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-surefire-plugin</artifactId><version>3.2.5</version>
        <configuration>
          <includes><include>**/{test_class}.java</include></includes>
          <argLine>{add_opens}</argLine>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
"""

TEST_STUB = """package {test_pkg};

import static org.junit.Assert.*;
import org.junit.Test;

/**
 * AUTO-GENERATED STUB for the {break_id} BBC differential.
 *
 * Derived from the BUMP failing test:
 *   {bump_failing_test}
 * Break signal: {signal}
 *
 * JUDGMENT SEAM — an agent/human must complete the body so it exercises the
 * AFFECTED PRODUCTION PATH (not a test-only reimplementation): call the client's
 * real production entry point that triggers the library's changed behaviour, then
 * assert the pre-break outcome. It must PASS on {baseline_version}, FAIL on
 * {to_version} with '{signal}', and PASS again once the production adaptation is
 * present.  Keep ALL library config in production code, never here.
 */
public class {test_class} {{

    @Test
    public void reproducesBbc() throws Exception {{
        // TODO(JUDGMENT): construct realistic input, call the production path
        // (e.g. the client's load()/parse()/deserialize()), assert the survivor value.
        fail("stub not implemented — complete the body from the characterization above");
    }}
}}
"""

RUN_SH = """#!/usr/bin/env bash
# AUTO-GENERATED 3-state differential for {break_id} ({repo}).
set -eu
export JAVA_HOME="${{JAVA_HOME:-{java_home_hint}}}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${{1:-./{artifact}-diff}}"
git clone --quiet https://github.com/{repo}.git "$WORK"
cd "$WORK"
cp "$HERE/pom.xml" ./pom.xml
mkdir -p "$(dirname "src/test/java/{test_path}")"
cp "$HERE/{test_class}.java" "src/test/java/{test_path}"
RPT="target/surefire-reports/{test_fqcn}.txt"
run() {{ mvn clean test -D{prop}="$2" >/tmp/bbc_diff.log 2>&1 || true
        printf '%-38s %s | %s\\n' "$1" \\
          "$(grep -aoE 'Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+' "$RPT" 2>/dev/null | head -1)" \\
          "$(grep -aoE '{signal_grep}' "$RPT" 2>/dev/null | head -1 || echo PASS)"; }}
git checkout --quiet {parent_sha}
run "1: parent + {baseline_version} (PASS)" {baseline_version}
run "2: parent + {to_version} (FAIL)" {to_version}
git stash -u >/dev/null 2>&1 || true; git checkout --quiet {adapt_sha}; git stash pop >/dev/null 2>&1 || true
run "3: adapted + {to_version} (PASS)" {to_version}
"""


SET_BASELINE_PY = '''import re, sys
# Force EVERY dependency under <groupId> to version <newv> in a Maven pom (covers
# multi-artifact libraries, e.g. poi + poi-ooxml + poi-scratchpad). Handles both a
# literal version and a ${property} placeholder in the <version> tag.
pom, group, newv = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(pom, encoding="utf-8").read()
pat = re.compile(r"(<groupId>\\s*" + re.escape(group) +
                 r"\\s*</groupId>\\s*<artifactId>[^<]+</artifactId>\\s*<version>\\s*)([^<]+?)(\\s*</version>)", re.S)
n = len(pat.findall(s))
open(pom, "w", encoding="utf-8").write(pat.sub(lambda m: m.group(1) + newv + m.group(3), s))
print(f"[set-baseline] {group}:* -> {newv} at {n} site(s)" +
      ("" if n else "  (0 sites — versions managed by a parent/BOM or a property block; override manually)"))
'''

RUN_SH_REUSE = """#!/usr/bin/env bash
# AUTO-GENERATED reuse-pom 3-state differential for {break_id} ({repo}).
# Uses the repo's OWN pom (native Maven) — no hand-written dependency list.
# Only the BASELINE version is overridden; states 2 & 3 use the repo's pom as-is.
# Module: '{module}' (multi-module builds with -pl {module} -am).
#   1) parent code + {baseline_version}  -> expect PASS
#   2) parent code + {to_version} (repo)  -> expect FAIL ({signal})
#   3) adapted code + {to_version} (repo) -> expect PASS
set -u
export JAVA_HOME="${{JAVA_HOME:-{java_home_hint}}}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${{1:-./{artifact}-diff}}"
git clone --quiet https://github.com/{repo}.git "$WORK"; cd "$WORK"
mkdir -p "$(dirname "{test_rel}")"
cp "$HERE/{test_class}.java" "{test_rel}"
MVN='mvn clean test {pl_arg} -Dtest={test_class} -DfailIfNoTests=false -DargLine="{add_opens}"'
report() {{
  local res sig
  res=$(grep -haoE 'Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+' {report_glob} 2>/dev/null | head -1)
  sig=$(grep -haoE '{signal_grep}' {report_glob} 2>/dev/null | head -1)
  printf '%-42s %s | %s\\n' "$1" "$res" "${{sig:-PASS}}"
}}
git checkout --quiet {parent_sha}
python "$HERE/set_baseline_version.py" {pom_rel} {group_id} {baseline_version}
eval "$MVN" >/tmp/bbc_diff.log 2>&1 || true; report "1: parent + {baseline_version} (PASS)"
git checkout -- {pom_rel}
eval "$MVN" >/tmp/bbc_diff.log 2>&1 || true; report "2: parent + {to_version} (FAIL)"
git stash -u >/dev/null 2>&1 || true; git checkout --quiet {adapt_sha}; git stash pop >/dev/null 2>&1 || true
eval "$MVN" >/tmp/bbc_diff.log 2>&1 || true; report "3: adapted + {to_version} (PASS)"
"""


def gen_harness(brk, repo, adapt_sha, parent_sha, out_dir, reuse_pom=False, token=None, module=""):
    v = brk.get("verify", {})
    lib = brk["library"]
    match_artifact = re.split(r"[/\s]", lib["artifact_id"].strip())[0]  # "poi / poi-ooxml" -> "poi"
    test_class = f"{match_artifact.split('-')[0].capitalize()}BbcTest"
    test_pkg = "bbc"
    java = str(v.get("java", 17))
    to_version = lib.get("to_version") or lib.get("at_version") or "REPLACE"

    # multi-module layout: source + pom live under <module>/ and we build it in-reactor
    mod = module.strip("/")
    mod_dir = f"{mod}/" if mod else ""
    pom_rel = f"{mod}/pom.xml" if mod else "pom.xml"
    pl_arg = f"-pl {mod} -am" if mod else ""

    if reuse_pom:  # read the (module) pom to pick the Java level and warn on managed versions
        if not token:
            token = _token()
        pom_text = _gh_file(repo, pom_rel, adapt_sha, token)
        if pom_text is None:
            sys.exit(f"--reuse-pom: {repo}@{adapt_sha[:8]} has no {pom_rel} — "
                     f"not native-Maven, or wrong --module (scope is Maven only).")
        java = pom_java_release(pom_text) or java
        kind, val = find_dep_version_decl(pom_text, lib["group_id"], match_artifact)
        if kind is None:
            print(f"[gen-harness] WARN: {match_artifact} version not found in {pom_rel}'s "
                  f"dependency block (managed by a parent/BOM?). Baseline override may "
                  f"no-op — check set_baseline_version.py output when you run it.")
        else:
            print(f"[gen-harness] {pom_rel}: {match_artifact} version is a {kind}"
                  + (f" (${{{val}}})" if kind == 'property' else f" ({val})"))

    ctx = dict(
        break_id=brk["break_id"], group_id=lib["group_id"], artifact_id=lib["artifact_id"],
        artifact=match_artifact, match_artifact=match_artifact,
        to_version=to_version,
        baseline_version=v.get("runnable_baseline", lib.get("from_version", "REPLACE")),
        prop="dep.version", java=java,
        add_opens=" ".join(v.get("jvm_add_opens", [])),
        test_class=test_class, test_pkg=test_pkg,
        test_path=f"{test_pkg}/{test_class}.java",
        test_fqcn=f"{test_pkg}.{test_class}",
        module=mod, pom_rel=pom_rel, pl_arg=pl_arg,
        test_rel=f"{mod_dir}src/test/java/{test_pkg}/{test_class}.java",
        report_glob=f"{mod_dir}target/surefire-reports/*{test_class}.txt",
        bump_failing_test="; ".join(brk.get("characterization", {}).get("failing_tests", ["?"])),
        signal=brk.get("characterization", {}).get("signal", "?"),
        signal_grep=v.get("signal_grep", "Exception"),
        repo=repo, adapt_sha=adapt_sha, parent_sha=parent_sha,
        java_home_hint=v.get("java_home_hint", "/c/Program Files/Java/jdk-17"),
    )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{test_class}.java").write_text(TEST_STUB.format(**ctx), encoding="utf-8")
    if reuse_pom:
        (out / "set_baseline_version.py").write_text(SET_BASELINE_PY, encoding="utf-8")
        (out / "run_differential.sh").write_text(RUN_SH_REUSE.format(**ctx), encoding="utf-8")
        print(f"[gen-harness] REUSE-POM harness written to {out}/ (uses the repo's own pom):")
        print(f"  - {test_class}.java        (JUDGMENT: complete reproducesBbc())")
        print(f"  - set_baseline_version.py  (baseline dep-version override helper)")
        print(f"  - run_differential.sh      (bash run_differential.sh)")
        return
    (out / "pom.xml").write_text(POM_TEMPLATE.format(**ctx), encoding="utf-8")
    (out / "run_differential.sh").write_text(RUN_SH.format(**ctx), encoding="utf-8")
    print(f"[gen-harness] wrote harness to {out}/")
    print(f"  - pom.xml               (add the repo's other compile deps)")
    print(f"  - {test_class}.java     (JUDGMENT: complete reproducesBbc())")
    print(f"  - run_differential.sh   (bash run_differential.sh)")


# ── orchestration ────────────────────────────────────────────────────────────────

def summarize():
    """Consolidate output/<break>_candidates.jsonl (from `run`) + verified_cases/*.json
    into one dataset table across all catalog breaks."""
    cat = load_catalog()
    cases = {}
    cdir = HERE / "verified_cases"
    for cf in cdir.glob("*.json"):
        try:
            d = json.loads(cf.read_text(encoding="utf-8"))
        except Exception:
            continue
        repo = (d.get("adaptation", {}) or {}).get("repo")
        if repo:
            cases[repo] = (d.get("status", "?"), cf.name)

    lines = ["# BBC adaptation dataset — all breaks\n",
             f"Consolidated from output/<break>_candidates.jsonl + verified_cases/. "
             f"Regenerate: `python bbc_e2e.py summarize`.\n",
             "| Break | signal | candidates | Maven-prod (verifiable) | best candidate | recorded status |",
             "|---|---|---|---|---|---|"]
    detail = ["\n## Verifiable Maven production candidates per break\n"]
    for b in cat["breaks"]:
        bid = b["break_id"]
        sig = b.get("mining", {}).get("signal_quality", "?")
        f = HERE / "output" / f"{bid}_candidates.jsonl"
        if not f.exists():
            lines.append(f"| {bid} | {sig} | _not run_ | – | – | – |")
            continue
        rows = [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
        ver = [c for c in rows if c.get("verifiable")]
        best = ver[0] if ver else None
        # recorded status: any case file whose repo appears among this break's candidates
        repos = {c["repo"] for c in rows}
        status = next((f"{st} ({fn})" for r, (st, fn) in cases.items() if r in repos), "—")
        best_s = f"{best['repo']}@{best['sha'][:8]}" if best else "—"
        lines.append(f"| {bid} | {sig} | {len(rows)} | {len(ver)} | {best_s} | {status} |")
        detail.append(f"### {bid}  (signal: {sig})")
        if ver:
            for c in ver[:8]:
                pf = (c.get("production_files") or ["?"])[0]
                detail.append(f"- `{c['repo']}@{c['sha'][:8]}` — {pf} — {c['message'][:60]}")
        else:
            detail.append("- (no native-Maven production candidates)")
        detail.append("")
    out = HERE / "output" / "ALL_candidates_summary.md"
    out.write_text("\n".join(lines + detail), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[summarize] wrote {out.relative_to(HERE)}")


def run(break_id):
    brk = get_break(break_id)
    token = _token()
    print(f"\n=== characterize {break_id} ===")
    sha = brk["clients"][0]["breaking_commit"]
    characterize(sha)
    print(f"\n=== mine-commits {break_id} ===")
    rows = mine_commits(brk, token)
    print(f"\n=== classify candidates (production adaptations first) ===")
    results = []
    for r in rows[:20]:
        c = classify_commit(r["repo"], r["sha"], brk, token)
        if c.get("error"):
            continue
        results.append(c)
    # verifiable Maven production adaptations first; then non-Maven prod; then rest.
    results.sort(key=lambda c: (not c["verifiable"], c["library_source"],
                                not c["is_production_adaptation"], c["test_only"]))
    for c in results:
        tag = ("LIB-SOURCE" if c["library_source"]
               else "PROD" if c["is_production_adaptation"]
               else "TEST-ONLY" if c["test_only"] else "?")
        bs = c.get("build_system", "unknown")
        star = "*" if c["verifiable"] else " "   # * = Maven prod adaptation = ready to verify
        ver = f"{c['version_at_parent']}->{c['version_at_commit']}" if c["version_changed_here"] else f"@{c['version_at_commit']}"
        print(f" {star}[{tag:9}|{bs:6}] {c['repo']}@{c['sha'][:8]}  {ver}  {c['message']}")
        for f in c["production_files"][:3]:
            print(f"                     {f}")
    # persist candidates so a run's results are a durable artifact, not just stdout
    out_file = HERE / "output" / f"{break_id}_candidates.jsonl"
    out_file.parent.mkdir(exist_ok=True)
    with out_file.open("w", encoding="utf-8") as fh:
        for c in results:
            fh.write(json.dumps(c) + "\n")
    verifiable = [c for c in results if c["verifiable"]]
    print(f"\n{len(verifiable)} Maven production adaptation(s) ready to verify (marked *). "
          f"We only run the differential on MAVEN clients (the harness is Maven).")
    print(f"[run] saved {len(results)} candidates -> {out_file.relative_to(HERE)}")
    print(f"Next: pick a * candidate, then:")
    print(f"  python bbc_e2e.py gen-harness {break_id} --repo <r> --adapt-sha <s> --parent-sha <p> --out scratchpad/{break_id}-harness")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("characterize").add_argument("break_id")
    sub.add_parser("mine-commits").add_argument("break_id")
    p = sub.add_parser("classify"); p.add_argument("repo"); p.add_argument("sha"); p.add_argument("break_id")
    p = sub.add_parser("gen-harness")
    p.add_argument("break_id"); p.add_argument("--repo", required=True)
    p.add_argument("--adapt-sha", required=True); p.add_argument("--parent-sha", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--reuse-pom", action="store_true",
                   help="native-Maven repos: reuse the repo's own pom (no hand-written dep list); "
                        "override only the baseline version")
    p.add_argument("--module", default="",
                   help="for multi-module repos: the module dir holding the source "
                        "(e.g. 'core'); builds with -pl <module> -am")
    sub.add_parser("run").add_argument("break_id")
    sub.add_parser("summarize")
    args = ap.parse_args()

    if args.cmd == "characterize":
        brk = get_break(args.break_id)
        characterize(brk["clients"][0]["breaking_commit"])
    elif args.cmd == "mine-commits":
        for r in mine_commits(get_break(args.break_id), _token()):
            print(f"  {r['repo']}@{r['sha'][:8]}  [{r['matched_term']}]  {r['message']}")
    elif args.cmd == "classify":
        print(json.dumps(classify_commit(args.repo, args.sha, get_break(args.break_id), _token()), indent=2))
    elif args.cmd == "gen-harness":
        gen_harness(get_break(args.break_id), args.repo, args.adapt_sha, args.parent_sha,
                    args.out, reuse_pom=args.reuse_pom,
                    token=(_token() if args.reuse_pom else None), module=args.module)
    elif args.cmd == "run":
        run(args.break_id)
    elif args.cmd == "summarize":
        summarize()


if __name__ == "__main__":
    main()
