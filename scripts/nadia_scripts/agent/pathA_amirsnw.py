#!/usr/bin/env python3
"""
Path A LIVE run — amirsnw xstream case, exercising SEAM_A (seams.generate_test) for real
via the Anthropic SDK, then running the same 3-state oracle as acceptance_amirsnw.py.

This is the re-verification of the two seam fixes:
  1. _detect_framework now reports Jupiter for Spring-Boot-transitive JUnit5.
  2. seam_a_testgen.md Shape-B path emits preAdaptation()/adapted() two-method driver.

Success = generated test is Jupiter + has methods preAdaptation & adapted, AND the oracle
holds: preAdaptation@1.4.17 PASS, preAdaptation@1.4.19 FAIL+signal, adapted@1.4.19 PASS.
"""
import os, sys, subprocess, re, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import orchestrator as O
import seams

MVN = shutil.which("mvn") or "mvn"
GIT = shutil.which("git") or "git"
REPO = "amirsnw/chainrtrade-axon-CQRS-DDD"
ADAPT = "d408d4ca"
PARENT = "7823c47b44a43e45067a47b76404a25fb9257231"
MODULE = "product-service"
PROD = "product-service/src/main/java/productservice/config/EventProcessingConfig.java"
TEST = "bbc.BbcTest"
SIGNAL = r"ForbiddenClassException: [A-Za-z.]+"
JDK = O.JDKS["17"]


def inject_xstream_dep(repo_dir):
    pom = os.path.join(repo_dir, MODULE, "pom.xml")
    t = open(pom, encoding="utf-8").read()
    if "bbc.xstream.version" in t:
        return
    props = ("<properties><bbc.xstream.version>1.4.19</bbc.xstream.version></properties>\n"
             "    <dependencies>\n"
             "        <dependency><groupId>com.thoughtworks.xstream</groupId>"
             "<artifactId>xstream</artifactId><version>${bbc.xstream.version}</version></dependency>")
    t = t.replace("<dependencies>", props, 1)
    open(pom, "w", encoding="utf-8").write(t)


def run(repo_dir, method, ver):
    env = dict(os.environ, JAVA_HOME=JDK)
    cmd = [MVN, "clean", "test", "-pl", MODULE, "-am", f"-Dtest={TEST}#{method}",
           f"-Dbbc.xstream.version={ver}", "-DargLine=-Xmx2g",
           "-Dsurefire.failIfNoSpecifiedTests=false"]
    p = subprocess.run(cmd, cwd=repo_dir, env=env, capture_output=True, text=True)
    out = p.stdout + p.stderr
    m = re.search(r"Tests run: (\d+), Failures: (\d+), Errors: (\d+)", out)
    r, f, e = (list(map(int, m.groups())) if m else (0, 0, 0))
    return {"run": r, "fail": f, "err": e, "log": out}


def main():
    wd = os.path.join(os.environ.get("TEMP", "/tmp"), "bbc-acceptance")
    repo_dir = os.path.join(wd, "amirsnw")
    if os.path.isdir(os.path.join(repo_dir, ".git")):
        subprocess.run([GIT, "-C", repo_dir, "checkout", "-q", "-f", ADAPT])
    else:
        os.makedirs(wd, exist_ok=True)
        O.clone(REPO, ADAPT, repo_dir)

    brk = O.load_break("xstream-1.4.17-to-1.4.19-forbiddenclass")
    cand = O.Candidate(REPO, ADAPT, PARENT, module=MODULE, production_files=[PROD])

    # ---- SEAM_A LIVE ----
    print("=== SEAM_A: detected framework ===")
    print("  ", seams._detect_framework(repo_dir))
    print("=== SEAM_A: calling Claude live (this costs API budget) ===")
    src = seams.generate_test(brk, cand, repo_dir)
    print("----- generated bbc/BbcTest.java -----")
    print(src)
    print("--------------------------------------")

    is_jupiter = "org.junit.jupiter" in src
    has_pre = re.search(r"\bpreAdaptation\s*\(", src) is not None
    has_adapted = re.search(r"\badapted\s*\(", src) is not None
    print(f"  shape check: jupiter={is_jupiter} preAdaptation={has_pre} adapted={has_adapted}")

    d = os.path.join(repo_dir, MODULE, "src", "test", "java", "bbc")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "BbcTest.java"), "w", encoding="utf-8").write(src)
    inject_xstream_dep(repo_dir)

    print("\nSTATE 1 (preAdaptation, 1.4.17) ..."); s1 = run(repo_dir, "preAdaptation", "1.4.17")
    print("STATE 2 (preAdaptation, 1.4.19) ...");   s2 = run(repo_dir, "preAdaptation", "1.4.19")
    print("STATE 3 (adapted, 1.4.19) ...");          s3 = run(repo_dir, "adapted", "1.4.19")

    s2_signal = bool(re.search(SIGNAL, s2["log"]))
    print("\n--- oracle ---")
    print(f"  state1 pre@1.4.17  : run={s1['run']} fail={s1['fail']} err={s1['err']} -> {'PASS' if s1['run'] and not(s1['fail'] or s1['err']) else 'NOT-PASS'}")
    print(f"  state2 pre@1.4.19  : run={s2['run']} fail={s2['fail']} err={s2['err']} signal={s2_signal} -> {'FAIL(+signal)' if (s2['fail'] or s2['err']) and s2_signal else 'NOT-FAIL'}")
    print(f"  state3 adapt@1.4.19: run={s3['run']} fail={s3['fail']} err={s3['err']} -> {'PASS' if s3['run'] and not(s3['fail'] or s3['err']) else 'NOT-PASS'}")
    verified = (s1["run"] and not (s1["fail"] or s1["err"]) and
                (s2["fail"] or s2["err"]) and s2_signal and
                s3["run"] and not (s3["fail"] or s3["err"]))
    print(f"\n  SHAPE OK: {is_jupiter and has_pre and has_adapted}")
    print(f"  OUTCOME : {'verified_bbc' if verified else 'NOT verified'}")
    if not verified and not s2_signal:
        print("\n  [state2 tail]\n" + "\n".join(s2["log"].splitlines()[-25:]))
    return 0 if verified else 1


if __name__ == "__main__":
    sys.exit(main())
