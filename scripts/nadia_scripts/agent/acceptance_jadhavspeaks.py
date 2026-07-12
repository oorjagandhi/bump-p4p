#!/usr/bin/env python3
"""
Acceptance dry-run (AGENT_DESIGN sec.9.4): drive the orchestrator's real 3-state machinery
autonomously over a KNOWN-good candidate (poi-jadhavspeaks) and confirm it reaches
verified_bbc without hand-typed mvn commands.

Scope: this validates the DETERMINISTIC orchestration (clone, 3 states, signal match, oracle,
classification). SEAM_A here is fed the known-good POI driver test (the exact thing a real
SEAM_A agent turn would produce, per agent/prompts/seam_a_testgen.md). SEAM_B is not needed
because the fixture already trips (its sizing follows seam_b_diagnose.md: distinct +
incompressible + >100MB).
"""
import os, sys, subprocess, re, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import orchestrator as O

MVN = shutil.which("mvn") or "mvn"   # resolves mvn.cmd on Windows

CAND = O.Candidate(
    repo="jadhavspeaks/file_compare_diffrent_ext",
    adapt_sha="156a9624",
    parent_sha="7d6ffdd3",
    build_system="maven",
    production_files=["src/main/java/com/filecomparator/parser/ExcelParser.java"],
)
TEST_CLASS = "bbc.PoiBbcTest"
SIGNAL = r"RecordFormatException|maximum length for this record type is 100,000,000"
HEAP = "-Xmx3g"

# --- SEAM_A output (known-good driver test; what an agent turn would generate) -----------
POI_DRIVER = r'''package bbc;

import static org.junit.jupiter.api.Assertions.assertNotNull;
import com.filecomparator.model.FileContent;
import com.filecomparator.parser.ExcelParser;
import java.io.File;
import java.io.FileOutputStream;
import java.util.Random;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.junit.jupiter.api.Test;

public class PoiBbcTest {
    @Test
    public void reproducesBbc() throws Exception {
        File xlsx = File.createTempFile("bbc-poi-bytecap", ".xlsx");
        xlsx.deleteOnExit();
        Random rnd = new Random(12345);                         // distinct + incompressible
        try (Workbook wb = new XSSFWorkbook()) {
            Sheet sheet = wb.createSheet("s");
            for (int r = 0; r < 4500; r++) {                    // ~135MB sharedStrings.xml
                char[] buf = new char[30000];
                for (int i = 0; i < buf.length; i++) buf[i] = (char) ('a' + rnd.nextInt(26));
                sheet.createRow(r).createCell(0).setCellValue(new String(buf));
            }
            try (FileOutputStream out = new FileOutputStream(xlsx)) { wb.write(out); }
        }
        FileContent content = new ExcelParser().parse(xlsx.getAbsolutePath());
        assertNotNull(content, "parse() returned null / threw");
    }
}
'''

def write_test(repo_dir):
    d = os.path.join(repo_dir, "src", "test", "java", "bbc")
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, "PoiBbcTest.java"), "w").write(POI_DRIVER)

def set_poi_version(repo_dir, ver):
    pom = os.path.join(repo_dir, "pom.xml")
    t = open(pom, encoding="utf-8").read()
    open(pom, "w", encoding="utf-8").write(t.replace("5.2.5", ver))

def run(repo_dir, jdk):
    env = dict(os.environ, JAVA_HOME=jdk)
    cmd = [MVN, "clean", "test", f"-Dtest={TEST_CLASS}", f"-DargLine={HEAP}",
           "-Dsurefire.failIfNoSpecifiedTests=false"]
    p = subprocess.run(cmd, cwd=repo_dir, env=env, capture_output=True, text=True)
    out = p.stdout + p.stderr
    m = re.search(r"Tests run: (\d+), Failures: (\d+), Errors: (\d+)", out)
    run_, fail, err = (list(map(int, m.groups())) if m else (0, 0, 0))
    return {"run": run_, "fail": fail, "err": err, "log": out}

def main():
    brk = O.load_break("poi-4.1.2-to-5.x")
    jdk = O.JDKS["17"]
    wd = os.path.join(os.environ.get("TEMP", "/tmp"), "bbc-acceptance")
    repo_dir = os.path.join(wd, "jadhav")
    if os.path.isdir(os.path.join(repo_dir, ".git")):
        subprocess.run(["git", "-C", repo_dir, "checkout", "-q", "-f", CAND.adapt_sha])
    else:
        os.makedirs(wd, exist_ok=True)
        O.clone(CAND.repo, CAND.adapt_sha, repo_dir)
    write_test(repo_dir)                                        # SEAM_A

    print("STATE 3 (adapted, POI 5.2.5) ...")
    s3 = run(repo_dir, jdk)
    subprocess.run(["git", "-C", repo_dir, "checkout", "-q", "-f", CAND.parent_sha])
    write_test(repo_dir)
    print("STATE 2 (parent, POI 5.2.5) ...")
    s2 = run(repo_dir, jdk)
    set_poi_version(repo_dir, "4.1.2")
    print("STATE 1 (parent, POI 4.1.2) ...")
    s1 = run(repo_dir, jdk)
    subprocess.run(["git", "-C", repo_dir, "checkout", "-q", "-f", "--", "pom.xml"])

    s2_signal = bool(re.search(SIGNAL, s2["log"]))
    print("\n--- oracle ---")
    print(f"  state1 baseline 4.1.2 : run={s1['run']} fail={s1['fail']} err={s1['err']}  -> {'PASS' if s1['run'] and not(s1['fail'] or s1['err']) else 'NOT-PASS'}")
    print(f"  state2 new-lib  5.2.5 : run={s2['run']} fail={s2['fail']} err={s2['err']}  signal={s2_signal} -> {'FAIL(+signal)' if (s2['fail'] or s2['err']) and s2_signal else 'NOT-FAIL'}")
    print(f"  state3 adapted  5.2.5 : run={s3['run']} fail={s3['fail']} err={s3['err']}  -> {'PASS' if s3['run'] and not(s3['fail'] or s3['err']) else 'NOT-PASS'}")

    verified = (s1["run"] and not (s1["fail"] or s1["err"]) and
                (s2["fail"] or s2["err"]) and s2_signal and
                s3["run"] and not (s3["fail"] or s3["err"]))
    print(f"\n  OUTCOME: {'verified_bbc' if verified else 'NOT verified'}")
    return 0 if verified else 1

if __name__ == "__main__":
    sys.exit(main())
