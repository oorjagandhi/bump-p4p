#!/usr/bin/env python3
"""
BBC-verification agent — orchestrator skeleton.

Implements the per-(break, candidate) state machine from specs/AGENT_DESIGN.md.
Deterministic stages are wired here; the two LLM-judgment seams (test generation,
non-trip diagnosis) are marked SEAM_A / SEAM_B and are meant to be answered by an
agent turn (Claude Agent SDK) or a human for now.

Status: SKELETON. Deterministic plumbing is real; SEAM_A/SEAM_B are stubs that
raise NotImplementedError so a run halts at the judgment point instead of faking it.
"""
from __future__ import annotations
import json, os, subprocess, tempfile, shutil, re

MVN = shutil.which("mvn") or "mvn"   # resolves mvn.cmd on Windows
GIT = shutil.which("git") or "git"
from dataclasses import dataclass, field, asdict

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
NADIA = os.path.join(ROOT, "scripts", "nadia_scripts")
CATALOG = os.path.join(NADIA, "specs", "bump_breaks_catalog.json")

# JDK table (see AGENT_DESIGN §4). Extend as needed.
JDKS = {
    "11": r"C:/Program Files/Eclipse Adoptium/jdk-11.0.31.11-hotspot",
    "17": r"C:/Program Files/Java/jdk-17",
    "21": r"C:/Program Files/Java/jdk-21",
}

OUTCOME_VERIFIED = "verified_bbc"
OUTCOME_SIGNATURE = "signature_confirmed"
OUTCOME_FAILED = "failed"
OUTCOME_SKIP = "skip"


@dataclass
class Candidate:
    repo: str
    adapt_sha: str
    parent_sha: str
    build_system: str = "maven"
    module: str = ""
    production_files: list = field(default_factory=list)


@dataclass
class Result:
    outcome: str
    reason: str = ""
    states: list = field(default_factory=list)   # [{name, config, result, detail}]
    case_json_path: str = ""


# ---- deterministic stages -------------------------------------------------

def load_break(break_id: str) -> dict:
    cat = json.load(open(CATALOG, encoding="utf-8"))
    for b in cat["breaks"]:
        if b["break_id"] == break_id:
            return b
    raise KeyError(break_id)


def jdk_for(brk: dict, repo_dir: str) -> str:
    want = str(brk.get("verify", {}).get("java", "")) or "17"
    path = JDKS.get(want)
    if not path or not os.path.exists(os.path.join(path, "bin", "java.exe")):
        raise EnvironmentError(f"JDK {want} not installed (needed for {brk['break_id']})")
    return path


def clone(repo: str, sha: str, dest: str):
    subprocess.run([GIT, "clone", "--filter=blob:none", f"https://github.com/{repo}.git", dest], check=True)
    subprocess.run([GIT, "-C", dest, "checkout", "-q", "-f", sha], check=True)


def run_state(repo_dir: str, jdk: str, test: str, version_props: dict, heap="-Xmx2g", add_opens=None) -> dict:
    """One differential state: mvn clean test with the given -D overrides. Returns surefire summary."""
    env = dict(os.environ, JAVA_HOME=jdk)
    argline = heap + ("".join(" " + o for o in (add_opens or [])))
    cmd = [MVN, "clean", "test", f"-Dtest={test}", f"-DargLine={argline}",
           "-Dsurefire.failIfNoSpecifiedTests=false"]
    for k, v in version_props.items():
        cmd.append(f"-D{k}={v}")
    p = subprocess.run(cmd, cwd=repo_dir, env=env, capture_output=True, text=True)
    out = p.stdout + p.stderr
    m = re.search(r"Tests run: (\d+), Failures: (\d+), Errors: (\d+)", out)
    run, fail, err = (map(int, m.groups()) if m else (0, 0, 0))
    return {"run": run, "fail": fail, "err": err, "log": out}


def matches_signal(state_log: str, signal_grep: str) -> bool:
    return re.search(signal_grep, state_log) is not None


# ---- version-knob probe (AGENT_GAP_ANALYSIS P3) ---------------------------
#
# WHY THIS EXISTS. The version override used to be a single property name read
# from the catalog, with a TODO admitting it was unfinished. That is wrong often
# enough to be dangerous, because being wrong is SILENT: the state runs, the
# build succeeds, and the differential reports a result for a library version
# nobody chose.
#
# fslev/json-compare is the case that proved it, and the mechanism is worth stating
# exactly. The catalog's version_property for this break is `bbc.jackson.version` --
# a SYNTHETIC name belonging to `gen-harness --reuse-pom`, which REWRITES the client
# pom to use it. This orchestrator does no such rewrite, so `-Dbbc.jackson.version=X`
# against the untouched pom matched nothing and did nothing. The baseline ran on
# 2.15 instead of 2.14.2, the break fired where a PASS was required, and the agent
# reported "baseline did not pass cleanly" -- which reads as "this client is not a
# case" rather than "the harness ran the wrong jar".
#
# Note json-compare declares the version in TWO properties (<jackson.version> and
# <jackson.databind.version>); jackson-core moves with the first alone, so the
# duplication was not the cause here -- but a break whose artifact hangs off the
# second would fail the same silent way, which is why the probe sets every candidate.
#
# The fix is not a longer list of property names -- it is a MEASUREMENT. Ask
# Maven what the build actually resolves to, and refuse to run a differential
# whose version knob cannot be shown to work.

def resolved_version(repo_dir, jdk, module, group_id, artifact_id, props) -> str | None:
    """The version of group:artifact this build ACTUALLY resolves to under `props`.

    Reads it from `mvn dependency:list` rather than from the POM text, so a version
    that arrives through a parent POM or an imported BOM is seen too -- that shape
    (benchto inherits jackson from Spring Boot's BOM, two levels up) is invisible to
    any amount of POM parsing.
    """
    cmd = [MVN, "-B", "dependency:list", f"-DincludeGroupIds={group_id}",
           f"-DincludeArtifactIds={artifact_id}"]
    if module:
        cmd += ["-pl", module]
    for k, v in (props or {}).items():
        cmd.append(f"-D{k}={v}")
    p = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True,
                       env=dict(os.environ, JAVA_HOME=jdk))
    m = re.search(rf"{re.escape(group_id)}:{re.escape(artifact_id)}:jar:([^:\s]+)",
                  p.stdout + p.stderr)
    return m.group(1) if m else None


def candidate_version_props(repo_dir, catalog_prop, keyword) -> list:
    """Property names that might carry the library version, best guess first.

    The catalog's own answer is tried first and kept even when the POM does not
    declare it -- benchto's knob is Spring Boot's `jackson-bom.version`, which
    appears nowhere in benchto's own build files. Everything else is discovered by
    scanning the POMs for `*<keyword>*version*`, which is how projects that spell it
    their own way (adb.jackson.version, jackson2.version, dep.jackson.version) are
    picked up without hardcoding a list.
    """
    names = [catalog_prop] if catalog_prop else []
    for dirpath, _dirs, files in os.walk(repo_dir):
        if ".git" in dirpath:
            continue
        if "pom.xml" not in files:
            continue
        try:
            text = open(os.path.join(dirpath, "pom.xml"), encoding="utf-8",
                        errors="replace").read()
        except OSError:
            continue
        text = re.sub(r"<!--.*?-->", "", text, flags=re.S)   # never read commented-out XML
        for name in re.findall(r"<([\w.\-]+)>\s*[^<\s$][^<]*</\1>", text):
            low = name.lower()
            if keyword in low and "version" in low and name not in names:
                names.append(name)

    # Conventional names, appended last. A project can inherit its version from a
    # parent POM or an imported BOM and declare NOTHING itself -- trinodb/benchto is
    # the case: it names no jackson property anywhere, because the knob is Spring
    # Boot's own `jackson-bom.version`, reachable only because a Maven USER property
    # (-D) outranks a property declared inside an imported BOM.
    #
    # Guessing is safe here precisely because probe_version_props MEASURES the result:
    # a name that controls nothing changes nothing, and a name that works is proven to
    # work before any state runs. That asymmetry is what lets this list be broad
    # rather than exhaustively researched.
    for conv in (f"{keyword}-bom.version", f"{keyword}.version", f"{keyword}.bom.version",
                 f"dep.{keyword}.version", f"{keyword}2.version", f"version.{keyword}"):
        if conv not in names:
            names.append(conv)
    return names


def probe_version_props(repo_dir, jdk, module, group_id, artifact_id,
                        catalog_prop, keyword, probe_to) -> dict:
    """Find the -D properties that actually MOVE the resolved version. Raise if none do.

    Three passes, cheapest first:

      1. All candidates at once. Usually right and costs one Maven invocation.
      2. If that failed, each candidate alone -- because setting every name is NOT
         always harmless. trinodb/benchto is the counterexample: `jackson-bom.version`
         alone resolves jackson-core to the probe version, but the same request with
         the other guesses added does not. A parent POM (airbase here) can use a name
         like `dep.jackson.version` for its own purposes, so a guess that controls
         nothing on its own can still perturb resolution when combined.
      3. Re-add the remaining names one at a time, keeping only those that leave the
         target version correct. This matters for SIBLING SKEW: json-compare's
         jackson-core moves with `jackson.version` alone, but leaving
         `jackson.databind.version` behind would run core and databind at different
         versions -- a difference between states that is nothing to do with the break.

    Every step is measured, never assumed, which is what makes guessing names safe.
    """
    names = candidate_version_props(repo_dir, catalog_prop, keyword)
    if not names:
        raise RuntimeError(f"no candidate version properties found for '{keyword}'")

    def resolves(props):
        return resolved_version(repo_dir, jdk, module, group_id, artifact_id, props) == probe_to

    all_props = {n: probe_to for n in names}
    if resolves(all_props):
        return all_props

    effective = [n for n in names if resolves({n: probe_to})]
    if not effective:
        got = resolved_version(repo_dir, jdk, module, group_id, artifact_id, all_props)
        seen = resolved_version(repo_dir, jdk, module, group_id, artifact_id, {})
        raise RuntimeError(
            f"version knob does not work: asked for {group_id}:{artifact_id}={probe_to} via "
            f"{names}, build resolved {got!r} (resolves {seen!r} with no override). "
            f"Refusing to run a differential whose library version cannot be controlled."
        )

    props = {n: probe_to for n in effective}
    for n in names:
        if n in props:
            continue
        trial = dict(props, **{n: probe_to})
        if resolves(trial):
            props = trial
    return props


# ---- LLM-judgment seams (stubs) ------------------------------------------

def SEAM_A_generate_test(brk: dict, cand: Candidate, repo_dir: str) -> str:
    """Return JUnit source that drives the client's REAL production path (AGENT_DESIGN §2).
    Live: delegates to a Claude turn (agent/seams.py); needs an Anthropic credential in env."""
    import seams
    return seams.generate_test(brk, cand, repo_dir)


def SEAM_B_diagnose_nontrip(brk: dict, cand: Candidate, state2: dict, attempt: int,
                            max_retries: int = 3, current_test: str = "") -> str | None:
    """State 2 didn't fail. Return an adjusted fixture, or None to give up. Live via Claude."""
    import seams
    return seams.diagnose_nontrip(brk, cand, current_test, state2.get("log", ""), attempt, max_retries)


def write_test(repo_dir: str, module: str, src: str, classname: str = "BbcTest"):
    d = os.path.join(repo_dir, module, "src", "test", "java", "bbc") if module \
        else os.path.join(repo_dir, "src", "test", "java", "bbc")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, f"{classname}.java"), "w", encoding="utf-8") as f:
        f.write(src)


# ---- the loop -------------------------------------------------------------

def verify_candidate(break_id: str, cand: Candidate, workdir: str, max_retries=3) -> Result:
    brk = load_break(break_id)
    v = brk.get("verify", {})
    signal = v.get("signal_grep", "")
    baseline = v.get("runnable_baseline")
    add_opens = v.get("jvm_add_opens")
    repo_dir = os.path.join(workdir, cand.repo.replace("/", "_"))

    try:
        clone(cand.repo, cand.adapt_sha, repo_dir)
        jdk = jdk_for(brk, repo_dir)
    except Exception as e:
        return Result(OUTCOME_FAILED, f"setup: {e}")

    # SEAM A: generate + write the driver test (untracked, survives git checkout)
    try:
        test_src = SEAM_A_generate_test(brk, cand, repo_dir)
        write_test(repo_dir, cand.module, test_src)
    except Exception as e:
        return Result(OUTCOME_FAILED, f"SEAM_A failed: {e}")

    test = "bbc.BbcTest"                    # convention
    lib = brk["library"]
    to_version = lib["to_version"]

    # Which -D properties actually control this build's library version? MEASURED,
    # not read from the catalog -- see probe_version_props. Probing against the
    # BASELINE version (not to_version) is deliberate: at both shas the repo already
    # declares to_version, so an override to to_version is indistinguishable from no
    # override working at all, and a broken knob would probe green.
    try:
        version_props = probe_version_props(
            repo_dir, jdk, cand.module, lib["group_id"], lib["artifact_id"],
            v.get("version_property", ""), lib["artifact_id"].split("-")[0].lower(),
            baseline)
    except Exception as e:
        return Result(OUTCOME_FAILED, f"version knob probe: {e}")

    def at(version):
        return {k: version for k in version_props}

    # STATE 3 (adapted) — checkout adapt_sha (already there)
    s3 = run_state(repo_dir, jdk, test, at(to_version), add_opens=add_opens)

    # STATE 2 (new lib, parent code) — checkout parent, keep untracked test
    subprocess.run([GIT, "-C", repo_dir, "checkout", "-q", "-f", cand.parent_sha], check=True)
    s2 = run_state(repo_dir, jdk, test, at(to_version), add_opens=add_opens)

    # diagnose non-trip (SEAM B), bounded
    attempt = 0
    while s2["fail"] == 0 and s2["err"] == 0 and attempt < max_retries:
        attempt += 1
        try:
            new_src = SEAM_B_diagnose_nontrip(brk, cand, s2, attempt, max_retries, test_src)
        except Exception as e:
            return Result(OUTCOME_FAILED, f"SEAM_B failed: {e}", states=[s2])
        if not new_src:
            return Result(OUTCOME_SIGNATURE, "break did not trip after diagnosis")
        test_src = new_src
        write_test(repo_dir, cand.module, new_src)
        s2 = run_state(repo_dir, jdk, test, at(to_version), add_opens=add_opens)

    if not (s2["err"] or s2["fail"]) or not matches_signal(s2["log"], signal):
        return Result(OUTCOME_SIGNATURE, "state2 did not reproduce the signal")

    # STATE 1 (baseline) — parent code + baseline version
    s1 = run_state(repo_dir, jdk, test, at(baseline), add_opens=add_opens)
    if s1["run"] == 0 or s1["fail"] or s1["err"]:
        return Result(OUTCOME_FAILED, "baseline did not pass cleanly", states=[s1, s2, s3])

    if s3["run"] and not (s3["fail"] or s3["err"]):
        # 1 PASS, 2 FAIL+signal, 3 PASS  -> verified
        return Result(OUTCOME_VERIFIED, "oracle satisfied",
                      states=[{"name": "1_baseline", "result": "PASS"},
                              {"name": "2_new_lib_old_code", "result": "FAIL"},
                              {"name": "3_adapted", "result": "PASS"}])
    return Result(OUTCOME_SIGNATURE, "adapted state did not pass (coupling?)", states=[s1, s2, s3])


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="BBC-verification agent orchestrator (skeleton)")
    ap.add_argument("break_id")
    ap.add_argument("--repo"); ap.add_argument("--adapt-sha"); ap.add_argument("--parent-sha")
    a = ap.parse_args()
    cand = Candidate(a.repo, a.adapt_sha, a.parent_sha)
    with tempfile.TemporaryDirectory() as wd:
        print(json.dumps(asdict(verify_candidate(a.break_id, cand, wd)), indent=1, default=str))
