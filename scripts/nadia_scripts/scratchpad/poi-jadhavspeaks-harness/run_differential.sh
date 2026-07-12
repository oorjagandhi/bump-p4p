#!/usr/bin/env bash
# AUTO-GENERATED reuse-pom 3-state differential for poi-4.1.2-to-5.x (jadhavspeaks/file_compare_diffrent_ext).
# Uses the repo's OWN pom.xml (native Maven) — no hand-written dependency list.
# Only the BASELINE version is overridden; states 2 & 3 use the repo's pom as-is.
#   1) parent code + 4.1.2  -> expect PASS
#   2) parent code + 5.0.0 (repo)  -> expect FAIL (POI 5 extraction failures in fscrawler's Tika parser tests (see poi-ooxml note: crypt ClassNotFoundException / extractor change).)
#   3) adapted code + 5.0.0 (repo) -> expect PASS
set -u
export JAVA_HOME="${JAVA_HOME:-/c/Program Files/Java/jdk-17}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${1:-./poi-diff}"
git clone --quiet https://github.com/jadhavspeaks/file_compare_diffrent_ext.git "$WORK"; cd "$WORK"
mkdir -p "$(dirname "src/test/java/bbc/PoiBbcTest.java")"
cp "$HERE/PoiBbcTest.java" "src/test/java/bbc/PoiBbcTest.java"
MVN='mvn clean test -Dtest=PoiBbcTest -DfailIfNoTests=false -DargLine="-Xmx3g"'
report() {
  local res sig
  res=$(grep -haoE 'Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+' target/surefire-reports/*PoiBbcTest.txt 2>/dev/null | head -1)
  sig=$(grep -haoE 'ClassNotFoundException: [A-Za-z.]+|RecordFormatException' target/surefire-reports/*PoiBbcTest.txt 2>/dev/null | head -1)
  printf '%-42s %s | %s\n' "$1" "$res" "${sig:-PASS}"
}
git checkout --quiet 7d6ffdd3000e705e051ba71f37a6f6789a1bbd9e
python "$HERE/set_baseline_version.py" pom.xml org.apache.poi 4.1.2
eval "$MVN" >/tmp/bbc_diff.log 2>&1 || true; report "1: parent + 4.1.2 (PASS)"
git checkout -- pom.xml
eval "$MVN" >/tmp/bbc_diff.log 2>&1 || true; report "2: parent + 5.0.0 (FAIL)"
git stash -u >/dev/null 2>&1 || true; git checkout --quiet 156a9624; git stash pop >/dev/null 2>&1 || true
eval "$MVN" >/tmp/bbc_diff.log 2>&1 || true; report "3: adapted + 5.0.0 (PASS)"
