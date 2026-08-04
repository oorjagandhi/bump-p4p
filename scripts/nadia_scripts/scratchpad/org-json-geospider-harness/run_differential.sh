#!/usr/bin/env bash
# AUTO-GENERATED 3-state differential for org-json-strict-type-coercion (FamingHou/geospider).
set -eu
export JAVA_HOME="${JAVA_HOME:-/c/Program Files/Java/jdk-17}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${1:-./json-diff}"
git clone --quiet https://github.com/FamingHou/geospider.git "$WORK"
cd "$WORK"
cp "$HERE/pom.xml" ./pom.xml
mkdir -p "$(dirname "src/test/java/bbc/JsonBbcTest.java")"
cp "$HERE/JsonBbcTest.java" "src/test/java/bbc/JsonBbcTest.java"
RPT="target/surefire-reports/bbc.JsonBbcTest.txt"
run() { mvn clean test -Ddep.version="$2" >/tmp/bbc_diff.log 2>&1 || true
        printf '%-38s %s | %s\n' "$1" \
          "$(grep -aoE 'Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+' "$RPT" 2>/dev/null | head -1)" \
          "$(grep -aoE 'is not a string|JSONException' "$RPT" 2>/dev/null | head -1 || echo PASS)"; }
git checkout --quiet 6048b2610fd39cdf3acd7920b859f3d5b261cba4
run "1: parent + pick a pre-strictness org.json (e.g. an early-2020s release) (PASS)" pick a pre-strictness org.json (e.g. an early-2020s release)
run "2: parent + 20230227 (FAIL)" 20230227
git stash -u >/dev/null 2>&1 || true; git checkout --quiet e1ce5497c3fd6a4067e791632172ed45d474ecab; git stash pop >/dev/null 2>&1 || true
run "3: adapted + 20230227 (PASS)" 20230227
