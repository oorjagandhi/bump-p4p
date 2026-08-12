"""
02_verify_bbc.py
────────────────
Phase 2: Clone each candidate repo, build it, and confirm BBCs.

Only writes CONFIRMED BBCs to the output file.
All other outcomes (syntactic BC, no BC, infrastructure errors) are logged
to a separate all_results.jsonl for auditing but kept out of verified_bbcs.jsonl.

Candidate model: each record is a (bump_sha, adapt_sha) pair. Verification takes
the baseline at bump_sha~1, applies the pom diff from bump_sha alone (must break
tests = behavioural break), then checks out adapt_sha (must be green = the
adaptation resolves it → confirmed_bbc). For same-commit candidates
adapt_sha == bump_sha, identical to the original behaviour; for two-commit
candidates (e.g. dependabot bump + maintainer fix) adapt_sha is the PR's merge
commit, which contains both the bump and the fix. Records that predate this
model (only "sha") fall back to bump_sha = adapt_sha = sha.

Fixes vs previous version:
  - Windows-safe directory deletion (handles locked .git files)
  - Automatic Java version detection from pom.xml, now also falling back
    to the parent POM (<parent><relativePath>) when the child pom doesn't
    declare compiler settings itself — common in multi-module projects
  - Multiple Java home support (pass --java8, --java11, --java17, --java21)
  - Only confirmed_bbc records written to --out
  - Separate --all-results file for full audit log
  - Optional --m2-repo to point every candidate at one persistent local
    Maven repo, so dependency downloads are cached across candidates
    instead of every clone re-downloading its whole dependency tree
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
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


# ── Windows-safe delete ───────────────────────────────────────────────────────

def force_rmtree(path: Path):
    """Delete a directory tree even if Windows has locked .git files."""
    def handle_error(func, fpath, exc_info):
        # Remove read-only flag and retry
        try:
            os.chmod(fpath, stat.S_IWRITE)
            func(fpath)
        except Exception:
            pass  # best effort
    shutil.rmtree(path, onerror=handle_error)


# ── Java version detection ────────────────────────────────────────────────────

def detect_required_java(repo_dir: Path, _depth: int = 0) -> int | None:
    """
    Read the pom.xml and figure out what Java version the project needs.
    Returns an integer like 8, 11, 17, 21, or None if unknown.

    Falls back to the parent POM (via <parent><relativePath>, default
    "../pom.xml") when this pom doesn't declare compiler settings itself —
    common in multi-module projects (e.g. Spring Boot) where the parent
    owns build/compiler config and the child pom has none of it.
    """
    pom_path = repo_dir / "pom.xml"
    if not pom_path.exists() or _depth > 5:
        return None
    try:
        tree = ElementTree.parse(pom_path)
        root = tree.getroot()
        # Strip namespace for easier searching
        ns = re.match(r'\{.*\}', root.tag)
        ns = ns.group(0) if ns else ''

        # Look for maven.compiler.source / maven.compiler.release in <properties>
        for props in root.iter(f'{ns}properties'):
            for tag in ['maven.compiler.release', 'maven.compiler.source',
                        'maven.compiler.target', 'java.version']:
                el = props.find(f'{ns}{tag}')
                if el is not None and el.text:
                    ver = el.text.strip().replace('1.', '')
                    try:
                        return int(ver)
                    except ValueError:
                        pass

        # Look inside maven-compiler-plugin config
        for plugin in root.iter(f'{ns}plugin'):
            aid = plugin.find(f'.//{ns}artifactId')
            if aid is not None and 'compiler' in (aid.text or ''):
                for tag in ['release', 'source', 'target']:
                    el = plugin.find(f'.//{ns}{tag}')
                    if el is not None and el.text:
                        ver = el.text.strip().replace('1.', '')
                        try:
                            return int(ver)
                        except ValueError:
                            pass

        # Not declared here — check the parent POM, if one exists on disk.
        parent = root.find(f'{ns}parent')
        if parent is not None:
            rel_path_el = parent.find(f'{ns}relativePath')
            rel_path = (rel_path_el.text.strip()
                        if rel_path_el is not None and rel_path_el.text else "../pom.xml")
            if rel_path:  # an explicit empty <relativePath/> means "no parent on disk"
                parent_pom = (pom_path.parent / rel_path)
                parent_dir = parent_pom.parent if parent_pom.name == "pom.xml" else parent_pom
                if (parent_dir / "pom.xml").exists():
                    return detect_required_java(parent_dir, _depth + 1)
    except Exception:
        pass
    return None


def pick_java_home(required_version: int | None, java_homes: dict) -> str | None:
    """
    Given the required Java version and a dict of {version: path},
    return the best matching JAVA_HOME path.
    """
    if not java_homes:
        return None
    if required_version is None:
        # Default to Java 8 when the pom declares no compiler version. These
        # older-library-bump projects typically predate the JDK's JAXB removal
        # (javax.xml.bind, gone in Java 11), so building them on 11 fails to
        # COMPILE at baseline (e.g. "cannot find symbol: class XmlTransient").
        # Java 8 still ships JAXB and compiles old source levels; projects that
        # genuinely need 11+ almost always declare maven.compiler.* and are
        # matched above, so they're unaffected by this fallback.
        return java_homes.get(8) or java_homes.get(11) or next(iter(java_homes.values()))

    # Exact match first
    if required_version in java_homes:
        return java_homes[required_version]

    # For old projects (6, 7) use Java 8 as it still supports those source levels
    if required_version <= 8:
        return java_homes.get(8) or java_homes.get(11)

    # For newer versions find the closest available
    available = sorted(java_homes.keys())
    for v in available:
        if v >= required_version:
            return java_homes[v]

    # Fall back to highest available
    return java_homes[available[-1]]


# ── subprocess helpers ────────────────────────────────────────────────────────

def run(cmd, cwd=None, timeout=300, env=None):
    result = subprocess.run(
        cmd, shell=True, cwd=cwd, timeout=timeout,
        capture_output=True, text=True, env=env
    )
    return result.returncode, result.stdout, result.stderr


def mvn(cmd_suffix, cwd, timeout=300, java_home=None, m2_repo=None):
    env = os.environ.copy()
    if java_home:
        env["JAVA_HOME"] = java_home
        # Windows uses semicolon in PATH, Linux uses colon
        sep = ";" if os.name == "nt" else ":"
        bin_dir = str(Path(java_home) / "bin")
        env["PATH"] = bin_dir + sep + env.get("PATH", "")

    # Pointing every candidate at the same local repo means dependencies
    # downloaded for one candidate are cached for the next, instead of
    # every fresh clone re-downloading its whole dependency tree from
    # Maven Central.
    repo_flag = f'-Dmaven.repo.local="{m2_repo}" ' if m2_repo else ""

    full_cmd = (
        f"mvn {cmd_suffix} "
        "-Dorg.slf4j.simpleLogger.log.org.apache.maven.cli.transfer.Slf4jMavenTransferListener=warn "
        "-Dmaven.javadoc.skip=true -Dsource.skip=true "
        f"{repo_flag}"
        "--batch-mode --no-transfer-progress"
    )
    rc, out, err = run(full_cmd, cwd=cwd, timeout=timeout, env=env)
    return rc, out + "\n" + err


# ── git helpers ───────────────────────────────────────────────────────────────

def git(cmd, cwd, timeout=120):
    rc, out, err = run(f"git {cmd}", cwd=cwd, timeout=timeout)
    return rc, out, err


def clone_repo(repo_url: str, dest: Path, shas) -> bool:
    rc, _, err = run(
        f"git clone --filter=blob:none --no-checkout {repo_url} {dest}",
        timeout=300
    )
    if rc != 0:
        print(f"  [clone fail] {err[:200]}", file=sys.stderr)
        return False
    # Fetch every sha we need (bump commit + its adaptation commit, which may be
    # a separate PR merge commit). --depth=50 also brings each one's ancestors
    # so bump_sha~1 (the baseline) is available.
    for sha in dict.fromkeys(s for s in shas if s):   # dedup, drop falsy
        git(f"fetch --depth=50 origin {sha}", cwd=dest)
    return True


def checkout(sha: str, cwd: Path):
    git(f"checkout -f {sha}", cwd=cwd)


def apply_pom_only(pom_file: str, sha_adapt: str, cwd: Path) -> bool:
    rc, patch, err = run(
        f"git show {sha_adapt} -- {pom_file}",
        cwd=cwd, timeout=30
    )
    if rc != 0 or not patch.strip():
        return False
    patch_path = cwd / "_pom.patch"
    patch_path.write_text(patch, encoding="utf-8")
    rc, out, err = run("git apply --whitespace=fix _pom.patch", cwd=cwd, timeout=30)
    try:
        patch_path.unlink()
    except Exception:
        pass
    return rc == 0


# ── classification ────────────────────────────────────────────────────────────

COMPILE_ERROR_PATTERNS = [
    r"COMPILATION ERROR",
    r"cannot find symbol",
    r"error: package .* does not exist",
    r"\[ERROR\].*\.java:\[\d+,\d+\]",
    r"does not override abstract method",
    r"is not abstract and does not implement",
    r"cannot be cast to",
    r"release version \d+ not supported",
    r"Source option \d+ is no longer supported",
]

def classify_mvn_output(output: str) -> str:
    for pat in COMPILE_ERROR_PATTERNS:
        if re.search(pat, output, re.IGNORECASE):
            return "syntactic_bc"
    if re.search(r"BUILD SUCCESS", output) and not re.search(
            r"Tests run:.*(?:Failures|Errors): [1-9]", output):
        return "green"
    if re.search(r"Tests run:.*(?:Failures|Errors): [1-9]", output):
        return "bbc_candidate"
    if re.search(r"BUILD FAILURE", output):
        return "bbc_candidate"
    return "unknown"


def extract_test_summary(output: str) -> dict:
    summary = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for m in re.finditer(
        r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+),\s*Skipped:\s*(\d+)",
        output
    ):
        summary["tests"]    += int(m.group(1))
        summary["failures"] += int(m.group(2))
        summary["errors"]   += int(m.group(3))
        summary["skipped"]  += int(m.group(4))
    return summary


def extract_exception_types(output: str) -> list:
    found = set()
    for m in re.finditer(r"(java\.[\w]+\.[\w]+(?:Exception|Error))", output):
        found.add(m.group(1))
    for m in re.finditer(r"Caused by:\s+([\w\.]+(?:Exception|Error))", output):
        found.add(m.group(1))
    return sorted(found)


def classify_bc_effect(output: str) -> str:
    if re.search(r"AssertionError|AssertionFailedError|ComparisonFailure", output):
        if re.search(r"expected[: <]", output, re.IGNORECASE):
            return "TestAssertion"
        return "ProgramAssertion"
    if re.search(r"NullPointerException|IllegalStateException|"
                 r"IllegalArgumentException|ClassCastException|"
                 r"ArrayIndexOutOfBoundsException", output):
        return "RuntimeException"
    if re.search(r"IOException|SQLException|FileNotFoundException|SocketException", output):
        return "CheckedException"
    if re.search(r"TimedOutException|SocketTimeoutException|ConditionTimeoutException", output):
        return "ResourceError"
    if re.search(r"\bError\b", output):
        return "Error"
    return "Unknown"


# A "behavioural break" means: client code that compiles and runs against the
# new version, but now behaves differently (assertion failures, changed runtime
# exceptions from working code). The patterns below are the OPPOSITE of that —
# they mean the bumped dependency set is broken/unresolvable/internally
# inconsistent, so the library's own classes never even load. That is an
# incomplete-bump artefact, not a BBC, and must not be confirmed.
#
# Telltales:
#   - Maven can't resolve the new artifact (version not on Central yet, etc.)
#   - The library's OWN class fails its static initializer / can't be found,
#     usually because two co-versioned modules (e.g. jackson-databind vs
#     jackson-annotations) are mismatched.
#
# Deliberately NOT included: NoSuchMethodError / NoSuchFieldError /
# AbstractMethodError / IncompatibleClassChangeError — those ARE genuine
# binary-incompatibility BBC signals (a member the client uses was removed or
# changed in the new version) and should still reach the confirm step.
DEPENDENCY_FAILURE_PATTERNS = [
    r"Could not resolve dependencies",
    r"Could not find artifact",
    r"Failure to find .* in ",
    r"Could not transfer artifact",
    r"Non-resolvable .* POM",
    r"ExceptionInInitializerError",
    r"Could not initialize class",
]

def is_dependency_failure(output: str) -> bool:
    return any(re.search(p, output, re.IGNORECASE) for p in DEPENDENCY_FAILURE_PATTERNS)


# ── per-test result collection (differential methodology) ──────────────────────
# Rather than demanding a fully green baseline, we diff per-test outcomes across
# stages: a BBC is a test that PASSES at baseline, FAILS under the bump, and is
# GREEN again after the adaptation. Pre-existing failures (flaky/environment
# tests) are therefore tolerated — they never entered the baseline-pass set, so
# they can't masquerade as a break. Per-test outcomes come from Surefire/Failsafe
# JUnit XML reports under each module's target/.

def _report_dirs(repo_dir: Path):
    return (list(repo_dir.glob("**/target/surefire-reports"))
            + list(repo_dir.glob("**/target/failsafe-reports")))


def clear_test_reports(repo_dir: Path):
    """Delete all surefire/failsafe report dirs so the next run's collected
    results reflect ONLY that run. Without this, a module that fails to recompile
    under the bump would keep its stale baseline reports and be misread as green."""
    for d in _report_dirs(repo_dir):
        try:
            force_rmtree(d)
        except Exception:
            pass  # best effort


_STATUS_RANK = {"pass": 0, "skip": 0, "fail": 1, "error": 1}


def collect_test_results(repo_dir: Path) -> dict:
    """Parse every TEST-*.xml report into {(classname, name): status} where
    status is 'pass' | 'fail' | 'error' | 'skip'. A <testcase> is fail/error if
    it has a <failure>/<error> child, skip if <skipped>, else pass. If the same
    test appears more than once, the worse outcome wins."""
    results = {}
    for d in _report_dirs(repo_dir):
        for xml in d.glob("TEST-*.xml"):
            try:
                root = ElementTree.parse(xml).getroot()
            except Exception:
                continue
            for tc in root.iter("testcase"):
                key = (tc.get("classname", ""), tc.get("name", ""))
                status = "pass"
                for child in tc:
                    tag = child.tag.lower()
                    if tag in ("failure", "error", "skipped"):
                        status = "skip" if tag == "skipped" else tag
                        break
                prev = results.get(key)
                if prev is None or _STATUS_RANK[status] > _STATUS_RANK[prev]:
                    results[key] = status
    return results


def passing_set(results: dict) -> set:
    return {k for k, s in results.items() if s == "pass"}


def failing_set(results: dict) -> set:
    return {k for k, s in results.items() if s in ("fail", "error")}


# ── per-candidate verification ────────────────────────────────────────────────

def verify_candidate(rec: dict, work_dir: Path, java_homes: dict, timeout: int, m2_repo: str = None) -> dict:
    result = {**rec, "verification": {}}
    v = result["verification"]

    repo_url = f"https://github.com/{rec['repo']}.git"
    # Unified model: the version bump and the adaptation may be the same commit
    # (adapt_sha == bump_sha) or two commits (e.g. dependabot bump + maintainer
    # fix, with adapt_sha = the PR's merge commit). Old records only have "sha".
    # NOT rec.get("bump_sha", rec["sha"]) — Python evaluates the default eagerly, so
    # that raises KeyError on records that carry bump_sha/adapt_sha and no legacy
    # "sha". The documented two-commit model therefore never ran.
    bump_sha  = rec.get("bump_sha") or rec.get("sha")
    adapt_sha = rec.get("adapt_sha") or rec.get("sha") or bump_sha
    if not bump_sha:
        raise KeyError("record needs bump_sha (or legacy sha)")
    pom_file  = rec["pom_file"]
    v["bump_sha"]  = bump_sha
    v["adapt_sha"] = adapt_sha

    repo_dir = work_dir / rec["repo"].replace("/", "__")

    # Clean up any leftover from a previous run
    if repo_dir.exists():
        print(f"  [cleanup] removing previous clone")
        force_rmtree(repo_dir)
    repo_dir.mkdir(parents=True)

    try:
        # ── Step 1: clone ─────────────────────────────────────────────────────
        print(f"  [clone] {repo_url}")
        if not clone_repo(repo_url, repo_dir, [bump_sha, adapt_sha]):
            v["status"] = "clone_failed"
            return result

        # ── Step 2: baseline ──────────────────────────────────────────────────
        sha_before = bump_sha + "~1"
        checkout(sha_before, repo_dir)

        # Detect Java version needed and pick best JDK
        required_java = detect_required_java(repo_dir)
        java_home = pick_java_home(required_java, java_homes)
        v["detected_java_version"] = required_java
        v["java_home_used"] = java_home
        print(f"  [java] detected={required_java}  using={java_home}")

        print(f"  [baseline] {sha_before[:12]}")
        clear_test_reports(repo_dir)
        rc, out = mvn("test -fae", repo_dir, timeout=timeout, java_home=java_home, m2_repo=m2_repo)
        v["baseline_classify"] = classify_mvn_output(out)
        v["baseline_tests"]    = extract_test_summary(out)
        v["baseline_rc"]       = rc

        # Differential methodology: we NO LONGER require a fully green baseline.
        # Pre-existing failures (flaky/environment tests) are tolerated — we only
        # track tests that pass HERE and later break under the bump. But the
        # baseline must still (a) compile and (b) actually run some tests, or
        # there is no per-test signal to diff against.
        if v["baseline_classify"] == "syntactic_bc":
            v["status"] = "baseline_compile_error"
            v["baseline_snippet"] = out[-2000:]
            return result
        if is_dependency_failure(out):
            v["status"] = "baseline_dependency_error"
            v["baseline_snippet"] = out[-2000:]
            return result

        baseline_results = collect_test_results(repo_dir)
        baseline_pass = passing_set(baseline_results)
        v["baseline_passed_count"] = len(baseline_pass)
        v["baseline_failed_count"] = len(failing_set(baseline_results))
        if not baseline_pass:
            # No green tests to diff against (no tests ran, or all pre-failing).
            v["status"] = "baseline_no_passing_tests"
            v["baseline_snippet"] = out[-2000:]
            return result

        # ── Step 3: pom-only (new dep version, old java files) ────────────────
        print(f"  [pom-only] applying dep bump without java adaptations")
        checkout(sha_before, repo_dir)

        if not apply_pom_only(pom_file, bump_sha, repo_dir):
            v["status"] = "pom_patch_failed"
            return result

        clear_test_reports(repo_dir)
        rc, out = mvn("test -fae", repo_dir, timeout=timeout, java_home=java_home, m2_repo=m2_repo)
        v["pom_only_classify"]   = classify_mvn_output(out)
        v["pom_only_tests"]      = extract_test_summary(out)
        v["pom_only_rc"]         = rc
        v["pom_only_snippet"]    = out[-3000:]
        v["exception_types"]     = extract_exception_types(out)
        v["bc_effect_category"]  = classify_bc_effect(out)

        # A compile failure under the new version is a syntactic breaking change:
        # the client source no longer compiles against the bumped API.
        if v["pom_only_classify"] == "syntactic_bc":
            v["status"] = "syntactic_bc"
            return result

        # If the bumped dependency set can't be resolved, or the library's own
        # classes can't initialize (co-versioned modules mismatched — e.g.
        # jackson-databind vs jackson-annotations), the bump itself is
        # broken/incomplete. That is NOT a BBC.
        if is_dependency_failure(out):
            v["status"] = "dependency_resolution_error"
            return result

        # Differential core: which tests that PASSED at baseline now fail/error
        # under the bump? Those are the behavioural breaks the bump introduced.
        pom_results = collect_test_results(repo_dir)
        broken_by_bump = sorted(baseline_pass & failing_set(pom_results))
        v["broken_by_bump_count"] = len(broken_by_bump)
        v["broken_by_bump"] = [f"{c}#{n}" for c, n in broken_by_bump[:50]]

        if not broken_by_bump:
            # The bump broke no previously-passing test → not a behavioural break.
            v["status"] = "no_bc"
            return result

        # ── Step 4: adapted state — the bump-broken tests should recover ──────
        # adapt_sha == bump_sha for same-commit candidates (identical to the
        # original behaviour); for two-commit candidates it's the PR merge
        # commit, which contains both the bump and the fix.
        print(f"  [adapted] {adapt_sha[:12]}"
              + ("" if adapt_sha == bump_sha else f"  (PR merge; bump={bump_sha[:8]})"))
        checkout(adapt_sha, repo_dir)
        clear_test_reports(repo_dir)
        rc, out = mvn("test -fae", repo_dir, timeout=timeout, java_home=java_home, m2_repo=m2_repo)
        v["adapted_classify"] = classify_mvn_output(out)
        v["adapted_tests"]    = extract_test_summary(out)
        v["adapted_rc"]       = rc

        adapted_pass = passing_set(collect_test_results(repo_dir))
        broken_set = set(broken_by_bump)
        still_broken = sorted(broken_set - adapted_pass)
        v["recovered_count"] = len(broken_set & adapted_pass)
        v["still_broken"] = [f"{c}#{n}" for c, n in still_broken[:50]]

        # Confirmed only when EVERY test the bump broke is green again after the
        # adaptation — that's the adaptation resolving the behavioural break.
        if not still_broken:
            v["status"] = "confirmed_bbc"
        else:
            v["status"] = "bbc_adaptation_incomplete"

        return result

    finally:
        # Always clean up the clone, even on error — fixes WinError 5
        print(f"  [cleanup] removing clone")
        force_rmtree(repo_dir)


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="Verify BBC candidates — outputs only confirmed BBCs")
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--work-dir",   default="bbc-work")
    ap.add_argument("--out",        default="output/verified_bbcs.jsonl",
                    help="Output file — ONLY confirmed BBCs written here")
    ap.add_argument("--all-results", default="output/all_results.jsonl",
                    help="Full audit log including filtered/failed candidates")
    ap.add_argument("--timeout",    type=int, default=360)
    ap.add_argument("--limit",      type=int, default=None)
    ap.add_argument("--m2-repo",    default=None,
                    help="Persistent local Maven repo dir (passed as -Dmaven.repo.local) "
                         "so dependency downloads are cached across candidates instead of "
                         "being re-fetched for every clone. Consider raising --timeout for "
                         "the first run while this cache is still cold.")
    # Java homes — pass whichever you have installed
    ap.add_argument("--java8",  default=None, help="Path to Java 8  JAVA_HOME")
    ap.add_argument("--java11", default=None, help="Path to Java 11 JAVA_HOME")
    ap.add_argument("--java17", default=None, help="Path to Java 17 JAVA_HOME")
    ap.add_argument("--java21", default=None, help="Path to Java 21 JAVA_HOME")
    args = ap.parse_args()

    # Build the java_homes dict from whatever was provided
    java_homes = {}
    for ver, path in [(8, args.java8), (11, args.java11),
                      (17, args.java17), (21, args.java21)]:
        if path:
            java_homes[ver] = path

    if not java_homes:
        print("WARNING: No --java8/11/17/21 paths provided. "
              "Will use system default Java (may cause build failures for old projects).")

    # mvn() runs with cwd=repo_dir (the per-candidate clone), so a relative
    # --m2-repo would resolve inside that clone and get deleted along with
    # it after every candidate, defeating the cache entirely. Resolve to
    # an absolute path up front so it stays put across candidates.
    m2_repo = None
    if args.m2_repo:
        m2_repo = str(Path(args.m2_repo).resolve())
        Path(m2_repo).mkdir(parents=True, exist_ok=True)
        print(f"Using shared local Maven repo: {m2_repo}\n")

    work_dir = Path(args.work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    for out_path in [Path(args.out), Path(args.all_results)]:
        out_path.parent.mkdir(parents=True, exist_ok=True)

    candidates = []
    with open(args.candidates) as f:
        for line in f:
            line = line.strip()
            if line:
                candidates.append(json.loads(line))

    if args.limit:
        candidates = candidates[:args.limit]

    print(f"Verifying {len(candidates)} candidates")
    print(f"Java homes: {java_homes}\n")

    confirmed = 0
    counts = {}

    with open(args.out, "w") as f_confirmed, \
         open(args.all_results, "w") as f_all:

        for i, rec in enumerate(candidates, 1):
            # Same fallback verify_candidate uses. This line required the legacy
            # 'sha' unconditionally, so the documented two-commit model
            # (bump_sha + adapt_sha, e.g. dependabot bump + maintainer fix)
            # crashed with KeyError before any verification ran.
            _bump = rec.get("bump_sha") or rec.get("sha", "?")
            _adapt = rec.get("adapt_sha") or rec.get("sha", "?")
            _shown = _bump[:8] if _bump == _adapt else f"{_bump[:8]}->{_adapt[:8]}"
            print(f"[{i}/{len(candidates)}] {rec['repo']}  {_shown}  "
                  f"{rec.get('artifact_id','?')}  "
                  f"{rec.get('old_version','?')} -> {rec.get('new_version','?')}")
            try:
                result = verify_candidate(rec, work_dir, java_homes, args.timeout, m2_repo)
            except subprocess.TimeoutExpired:
                result = {**rec, "verification": {"status": "timeout"}}
            except Exception as e:
                result = {**rec, "verification": {"status": f"error: {e}"}}

            status = result["verification"].get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
            print(f"  → {status}\n")

            # Write everything to the audit log
            f_all.write(json.dumps(result) + "\n")
            f_all.flush()

            # Write ONLY confirmed BBCs to the main output
            if status == "confirmed_bbc":
                confirmed += 1
                f_confirmed.write(json.dumps(result) + "\n")
                f_confirmed.flush()
                print(f"  ★ CONFIRMED BBC written to {args.out}")

    print("\n── Summary ──────────────────────────────")
    for status, count in sorted(counts.items()):
        print(f"  {status:<35} {count}")
    print(f"\n  CONFIRMED BBCs: {confirmed}")
    print(f"  Written to:     {args.out}")
    print(f"  Full audit log: {args.all_results}")


if __name__ == "__main__":
    main()