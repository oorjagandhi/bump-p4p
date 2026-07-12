#!/usr/bin/env bash
# 3-state differential for the xstream 1.4.18 default-deny break, with the
# adaptation in PRODUCTION code (mimic/PreferenceStore.java).
#
#   1) xstream 1.4.17, prod NOT adapted            -> expect PASS
#   2) xstream 1.4.19, prod NOT adapted            -> expect FAIL (ForbiddenClassException)
#   3) xstream 1.4.19, prod adapted (allowTypes)   -> expect PASS
#
# Run from this directory. Requires Maven + JDK 11.
set -u
export JAVA_HOME="${JAVA_HOME:-/c/Program Files/Eclipse Adoptium/jdk-11.0.31.11-hotspot}"

run() {
  local label="$1"; shift
  mvn test "$@" >/tmp/xstream_mimic.log 2>&1
  local rc=$?
  local res build
  res=$(grep -oE "Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+" /tmp/xstream_mimic.log | tail -1)
  build=$(grep -oE "BUILD (SUCCESS|FAILURE)" /tmp/xstream_mimic.log | tail -1)
  printf "%-52s %s | %s (exit %s)\n" "$label" "$build" "$res" "$rc"
  grep -m1 "ForbiddenClassException" /tmp/xstream_mimic.log | sed 's/^/     /'
}

run "1) 1.4.17, prod NOT adapted   (expect PASS)" -Dxstream.version=1.4.17
run "2) 1.4.19, prod NOT adapted   (expect FAIL)" -Dxstream.version=1.4.19
run "3) 1.4.19, prod ADAPTED       (expect PASS)" -Dxstream.version=1.4.19 -Dmimic.adapt=true
