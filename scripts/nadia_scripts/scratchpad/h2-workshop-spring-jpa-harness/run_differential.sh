#!/usr/bin/env bash
# AUTO-GENERATED 3-state differential for h2-1.3-to-2.0-sql-compat (LucasG-max/WorkShop-spring-jpa).
set -eu
export JAVA_HOME="${JAVA_HOME:-/c/Program Files/Java/jdk-17}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${1:-./h2-diff}"
git clone --quiet https://github.com/LucasG-max/WorkShop-spring-jpa.git "$WORK"
cd "$WORK"
cp "$HERE/pom.xml" ./pom.xml
mkdir -p "$(dirname "src/test/java/bbc/H2BbcTest.java")"
cp "$HERE/H2BbcTest.java" "src/test/java/bbc/H2BbcTest.java"
RPT="target/surefire-reports/bbc.H2BbcTest.txt"
run() { mvn clean test -Ddep.version="$2" >/tmp/bbc_diff.log 2>&1 || true
        printf '%-38s %s | %s\n' "$1" \
          "$(grep -aoE 'Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+' "$RPT" 2>/dev/null | head -1)" \
          "$(grep -aoE 'SqlException|Syntax error|reserved keyword' "$RPT" 2>/dev/null | head -1 || echo PASS)"; }
git checkout --quiet a4c20aeca9df8cdf71c6011ccbd2b3cc50e0be3f
run "1: parent + 1.3.175 (or 1.4.200) (PASS)" 1.3.175 (or 1.4.200)
run "2: parent + 2.0.206 (FAIL)" 2.0.206
git stash -u >/dev/null 2>&1 || true; git checkout --quiet c4a78a32714ca7ccaaf24fcd0c406032c7955e5b; git stash pop >/dev/null 2>&1 || true
run "3: adapted + 2.0.206 (PASS)" 2.0.206
