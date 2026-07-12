#!/usr/bin/env bash
# AUTO-GENERATED reuse-pom 3-state differential for xstream-1.4.17-to-1.4.19-forbiddenclass (igniterealtime/Spark).
# Uses the repo's OWN pom (native Maven) — no hand-written dependency list.
# Only the BASELINE version is overridden; states 2 & 3 use the repo's pom as-is.
# Module: 'core' (multi-module builds with -pl core -am).
#   1) parent code + 1.4.17  -> expect PASS
#   2) parent code + 1.4.19 (repo)  -> expect FAIL (com.thoughtworks.xstream.security.ForbiddenClassException: LogPanelPreferenceModel — default-deny deserialization.)
#   3) adapted code + 1.4.19 (repo) -> expect PASS
set -u
export JAVA_HOME="${JAVA_HOME:-/c/Program Files/Java/jdk-17}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${1:-./xstream-diff}"
git clone --quiet https://github.com/igniterealtime/Spark.git "$WORK"; cd "$WORK"
mkdir -p "$(dirname "core/src/test/java/bbc/XstreamBbcTest.java")"
cp "$HERE/XstreamBbcTest.java" "core/src/test/java/bbc/XstreamBbcTest.java"
MVN='mvn clean test -pl core -am -Dtest=XstreamBbcTest -DfailIfNoTests=false -DargLine="--add-opens java.base/java.util=ALL-UNNAMED --add-opens java.base/java.lang=ALL-UNNAMED --add-opens java.base/java.lang.reflect=ALL-UNNAMED --add-opens java.base/java.text=ALL-UNNAMED --add-opens java.base/java.io=ALL-UNNAMED --add-opens java.desktop/java.beans=ALL-UNNAMED"'
report() {
  local res sig
  res=$(grep -haoE 'Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+' core/target/surefire-reports/*XstreamBbcTest.txt 2>/dev/null | head -1)
  sig=$(grep -haoE 'ForbiddenClassException: [A-Za-z.]+' core/target/surefire-reports/*XstreamBbcTest.txt 2>/dev/null | head -1)
  printf '%-42s %s | %s\n' "$1" "$res" "${sig:-PASS}"
}
git checkout --quiet 3821d04ec08e84fef84f32a39fd6b2ce200166e5
python "$HERE/set_baseline_version.py" core/pom.xml com.thoughtworks.xstream 1.4.17
eval "$MVN" >/tmp/bbc_diff.log 2>&1 || true; report "1: parent + 1.4.17 (PASS)"
git checkout -- core/pom.xml
eval "$MVN" >/tmp/bbc_diff.log 2>&1 || true; report "2: parent + 1.4.19 (FAIL)"
git stash -u >/dev/null 2>&1 || true; git checkout --quiet aad38d68; git stash pop >/dev/null 2>&1 || true
eval "$MVN" >/tmp/bbc_diff.log 2>&1 || true; report "3: adapted + 1.4.19 (PASS)"
