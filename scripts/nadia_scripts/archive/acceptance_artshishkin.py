#!/usr/bin/env python3
"""
Acceptance dry-run #3 — artshishkin xstream case, the TRANSITIVE-crossing shape.

Why this case: the two existing acceptance scripts (acceptance_amirsnw,
acceptance_jadhavspeaks) both target cases that are now in
verified_cases/excluded/no_boundary_crossing/ — amirsnw was born past the 1.4.18
boundary and jadhavspeaks past POI 5.0.0. Neither qualifies as a case any more, so
neither is a meaningful bar for autonomy. artshishkin does qualify: it crossed the
boundary TRANSITIVELY (axon-spring-boot-starter 4.5 -> 4.5.14 in core/pom.xml moved
xstream 1.4.16 -> 1.4.19), adapted in production, and has a recorded 3-state result to
reproduce.

Harness shape — same "plain-vs-configured" two-method driver as amirsnw, for the same
reason: XStreamConfig was CREATED in the fix, so there is no callable pre-adaptation
method at the parent. The driver therefore contrasts a plain `new XStream()` (a faithful
stand-in for Axon's pre-adaptation default serializer) against the real production
`new XStreamConfig().xStream()`, with the xstream version as the only other variable.

Two differences from the amirsnw script, both simplifications:
  - JUnit 5 directly. core/pom.xml already has spring-boot-starter-test (test scope), so
    jupiter is on the platform. The original hand-built harness used a JUnit 4 test plus
    junit-vintage-engine; that scaffolding is unnecessary.
  - JDK 11 (core/pom.xml declares <java.version>11</java.version>).

Still required: an EXPLICIT depth-1 xstream dependency injected into core/pom.xml.
Without it -Dbbc.xstream.version cannot move the version, because xstream is pinned
transitively by Axon and a property override does not reach a transitive dep.

SEAM_A status: the DRIVER below is frozen agent output, exactly as in the other
acceptance scripts — this validates the deterministic half (clone, scaffolding, the
3-state runner, signature match, oracle) given a known-good seam result. To test
AUTONOMY, replace the DRIVER constant with a live seams.generate_test(...) call and
require this same verdict.

Expected (from verified_cases/xstream-axon-artshishkin.json):
  1 plain@1.4.17      PASS
  2 plain@1.4.19      FAIL  ForbiddenClassException: ...core.model.ProductIdDto
  3 configured@1.4.19 PASS
"""
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import orchestrator as O

MVN = shutil.which("mvn") or "mvn"
GIT = shutil.which("git") or "git"

REPO = "artshishkin/art-kargopolov-cqrs-saga-axon-microservices"
ADAPT = "b76d747f8d278fbee27e6e4b82355f5e660bf5f8"
MODULE = "core"
TEST = "bbc.XstreamBbcTest"
SIGNAL = r"ForbiddenClassException:\s*net\.shyshkin\.study\.cqrs\.estore\.core\.model\.ProductIdDto"
JDK = O.JDKS["11"]
BASELINE, BROKEN = "1.4.17", "1.4.19"

# --- SEAM_A output ------------------------------------------------------------
# Derived from the adaptation diff (XStreamConfig.xStream() applying
# allowTypesByWildcard "net.shyshkin.study.cqrs.estore.**") and the domain type it
# protects (ProductIdDto, a Lombok @Data holder for a UUID). The break is on
# DESERIALIZATION: toXML always works, fromXML on a non-allowlisted class is what
# 1.4.18+ default-deny rejects, so the round-trip is the discriminating operation.
DRIVER = r'''package bbc;

import static org.junit.jupiter.api.Assertions.assertEquals;

import com.thoughtworks.xstream.XStream;
import java.util.UUID;
import net.shyshkin.study.cqrs.estore.core.config.XStreamConfig;
import net.shyshkin.study.cqrs.estore.core.model.ProductIdDto;
import org.junit.jupiter.api.Test;

public class XstreamBbcTest {

    private static void roundTrip(XStream xStream) {
        ProductIdDto dto = new ProductIdDto(UUID.randomUUID());
        String xml = xStream.toXML(dto);
        ProductIdDto back = (ProductIdDto) xStream.fromXML(xml);
        assertEquals(dto.getProductId(), back.getProductId());
    }

    /** Pre-adaptation stand-in: Axon's default serializer is a plain XStream. */
    @Test
    void plainXStream() {
        roundTrip(new XStream());
    }

    /** The real production adaptation, called directly (xStream() is a pure method). */
    @Test
    void configuredXStream() {
        roundTrip(new XStreamConfig().xStream());
    }
}
'''

XSTREAM_DEP = """        <dependency>
            <groupId>com.thoughtworks.xstream</groupId>
            <artifactId>xstream</artifactId>
            <version>${bbc.xstream.version}</version>
        </dependency>
"""


def write_test(repo_dir):
    d = os.path.join(repo_dir, MODULE, "src", "test", "java", "bbc")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "XstreamBbcTest.java"), "w", encoding="utf-8") as fh:
        fh.write(DRIVER)


def inject_xstream_dep(repo_dir):
    """Add an explicit depth-1 xstream dep so -Dbbc.xstream.version actually applies.
    Without this the version is fixed at whatever Axon resolves transitively and all
    three states would run on the SAME library — the differential would be vacuous
    and would quietly report PASS/PASS/PASS."""
    pom = os.path.join(repo_dir, MODULE, "pom.xml")
    with open(pom, encoding="utf-8") as fh:
        s = fh.read()
    if "bbc.xstream.version" in s:
        return
    s = s.replace("<dependencies>", "<dependencies>\n" + XSTREAM_DEP, 1)
    with open(pom, "w", encoding="utf-8") as fh:
        fh.write(s)


def run(repo_dir, method, ver):
    env = dict(os.environ, JAVA_HOME=JDK)
    cmd = [MVN, "clean", "test", "-pl", MODULE, "-am",
           f"-Dtest={TEST}#{method}", f"-Dbbc.xstream.version={ver}",
           "-DargLine=-Xmx2g", "-Dsurefire.failIfNoSpecifiedTests=false"]
    p = subprocess.run(cmd, cwd=repo_dir, env=env, capture_output=True,
                       text=True, errors="replace")
    out = p.stdout + p.stderr
    m = re.search(r"Tests run: (\d+), Failures: (\d+), Errors: (\d+)", out)
    run_, fail, err = (list(map(int, m.groups())) if m else (0, 0, 0))
    return {"run": run_, "fail": fail, "err": err, "log": out}


def main():
    wd = os.path.join(os.environ.get("TEMP", "/tmp"), "bbc-acceptance")
    repo_dir = os.path.join(wd, "artshishkin")
    if os.path.isdir(os.path.join(repo_dir, ".git")):
        subprocess.run([GIT, "-C", repo_dir, "checkout", "-q", "-f", ADAPT])
    else:
        os.makedirs(wd, exist_ok=True)
        O.clone(REPO, ADAPT, repo_dir)
    write_test(repo_dir)          # SEAM_A
    inject_xstream_dep(repo_dir)  # harness scaffolding

    print(f"STATE 1 (plain stand-in, xstream {BASELINE}) ...")
    s1 = run(repo_dir, "plainXStream", BASELINE)
    print(f"STATE 2 (plain stand-in, xstream {BROKEN}) ...")
    s2 = run(repo_dir, "plainXStream", BROKEN)
    print(f"STATE 3 (production config, xstream {BROKEN}) ...")
    s3 = run(repo_dir, "configuredXStream", BROKEN)

    s1_pass = bool(s1["run"]) and not (s1["fail"] or s1["err"])
    s2_fail = bool(s2["fail"] or s2["err"])
    s2_signal = bool(re.search(SIGNAL, s2["log"]))
    s3_pass = bool(s3["run"]) and not (s3["fail"] or s3["err"])

    print("\n--- oracle ---")
    print(f"  state1 plain@{BASELINE}      : run={s1['run']} fail={s1['fail']} err={s1['err']}"
          f"  -> {'PASS' if s1_pass else 'NOT-PASS'}")
    print(f"  state2 plain@{BROKEN}      : run={s2['run']} fail={s2['fail']} err={s2['err']}"
          f"  signal={s2_signal} -> {'FAIL(+signal)' if s2_fail and s2_signal else 'NOT-FAIL'}")
    print(f"  state3 config@{BROKEN}     : run={s3['run']} fail={s3['fail']} err={s3['err']}"
          f"  -> {'PASS' if s3_pass else 'NOT-PASS'}")

    # The signature match is not optional. A state-2 failure without it means the test
    # broke for some unrelated reason, which is exactly how a differential produces a
    # confident wrong answer.
    verified = s1_pass and s2_fail and s2_signal and s3_pass
    print(f"\n  OUTCOME: {'verified_bbc' if verified else 'NOT verified'}")
    if not verified:
        print("  (expected PASS / FAIL+signal / PASS — see "
              "verified_cases/xstream-axon-artshishkin.json)")
    return 0 if verified else 1


if __name__ == "__main__":
    sys.exit(main())
