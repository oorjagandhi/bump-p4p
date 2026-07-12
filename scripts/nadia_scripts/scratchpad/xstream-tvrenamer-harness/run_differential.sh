#!/usr/bin/env bash
# 3-state differential for the REAL The-Ant-Forge/TVRenamer xstream break, using
# a Maven harness around the repo's untouched production source.
#
# Verified 2026-07-06 (Maven 3.9.11 / JDK 17):
#   STATE 1  parent 16803ddb + xstream 1.4.17  -> PASS
#   STATE 2  parent 16803ddb + xstream 1.4.20  -> FAIL (ForbiddenClassException: org.tvrenamer.model.UserPreferences)
#   STATE 3  adapted b236f68e + xstream 1.4.20 -> PASS
#
# Usage: run from an empty dir. Requires git, Maven, JDK 17.
set -eu
export JAVA_HOME="${JAVA_HOME:-/c/Program Files/Java/jdk-17}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${1:-./tvrenamer-diff}"

git clone --quiet https://github.com/The-Ant-Forge/TVRenamer.git "$WORK"
cd "$WORK"
cp "$HERE/pom.xml" ./pom.xml
mkdir -p src/test/java/org/tvrenamer/controller
cp "$HERE/PreferencesBbcTest.java" src/test/java/org/tvrenamer/controller/PreferencesBbcTest.java

RPT=target/surefire-reports/org.tvrenamer.controller.PreferencesBbcTest.txt
runstate() {
  # NOTE: `mvn clean` is required — incremental compile skips the recompile after
  # a git checkout and would silently reuse the previous state's .class files.
  mvn clean test -Dxstream.version="$2" >/tmp/tvrun.log 2>&1 || true
  local res sig
  res=$(grep -aoE "Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+" "$RPT" 2>/dev/null | head -1)
  sig=$(grep -aoE "ForbiddenClassException: [A-Za-z.]+" "$RPT" 2>/dev/null | head -1)
  printf "%-40s %s | %s\n" "$1" "$res" "${sig:-PASS}"
}

git checkout --quiet 16803ddb
runstate "STATE 1: parent + 1.4.17 (PASS)" 1.4.17
runstate "STATE 2: parent + 1.4.20 (FAIL)" 1.4.20
git stash -u >/dev/null 2>&1 || true
git checkout --quiet b236f68e
git stash pop >/dev/null 2>&1 || true
runstate "STATE 3: adapted + 1.4.20 (PASS)" 1.4.20
