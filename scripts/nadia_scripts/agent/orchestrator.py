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

    # version override property is per-break (e.g. bbc.xstream.version); resolved by classify
    prop = v.get("version_property", "")   # TODO: carry from catalog/candidate
    test = "bbc.BbcTest"                    # convention

    # STATE 3 (adapted) — checkout adapt_sha (already there)
    s3 = run_state(repo_dir, jdk, test, {prop: brk["library"]["to_version"]}, add_opens=add_opens)

    # STATE 2 (new lib, parent code) — checkout parent, keep untracked test
    subprocess.run([GIT, "-C", repo_dir, "checkout", "-q", "-f", cand.parent_sha], check=True)
    s2 = run_state(repo_dir, jdk, test, {prop: brk["library"]["to_version"]}, add_opens=add_opens)

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
        s2 = run_state(repo_dir, jdk, test, {prop: brk["library"]["to_version"]}, add_opens=add_opens)

    if not (s2["err"] or s2["fail"]) or not matches_signal(s2["log"], signal):
        return Result(OUTCOME_SIGNATURE, "state2 did not reproduce the signal")

    # STATE 1 (baseline) — parent code + baseline version
    s1 = run_state(repo_dir, jdk, test, {prop: baseline}, add_opens=add_opens)
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
