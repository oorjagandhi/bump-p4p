#!/usr/bin/env bash
# 3-state differential for the jackson-core 2.14 -> 2.15 StreamReadConstraints behavioural
# break. EXTERNAL break, discovery source = library changelog / release notes (NOT BUMP, NOT
# the CVE advisory feed): jackson-core 2.15.0 added default parser limits (maxNestingDepth=1000,
# maxNumberLength, maxStringLength). JSON that 2.14 parsed now throws StreamConstraintsException.
#
# Adaptation pattern extracted from real client fixes found via mine-commits:
#   dotCMS/core@b30dfa31   "raise Jackson StreamReadConstraints limit in ContentletJsonHelper"
#   cibseven/cibseven@81a8d2b2 "add support for StreamReadConstraints in Jackson 2.15"
#   centiservice/mats3@79e05ec1 "Upgrade Jackson to 2.15.0, and add ... disabling of StreamReadConstraints"
#   ESSI-Lab/DAB@9385e949  "set StreamReadConstraints maxStringLength to 50 MB"
#
# Verified 2026-07-20 (Maven 3.9.11 / JDK 11):
#   STATE 1  parent  + jackson 2.14.2 -> PASS
#   STATE 2  parent  + jackson 2.15.0 -> FAIL (StreamConstraintsException: Depth (1001) exceeds ... (1000))
#   STATE 3  adapted + jackson 2.15.0 -> PASS (JsonFactory w/ raised StreamReadConstraints)
#
# Parent uses plain `new ObjectMapper()` (compiles on 2.14 AND 2.15). The adapted variant uses
# the 2.15-only StreamReadConstraints API and is built only under the 'adapted' profile.
# Run from this dir. Requires Maven + JDK 11.
set -u
export JAVA_HOME="${JAVA_HOME:-/c/Program Files/Eclipse Adoptium/jdk-11.0.31.11-hotspot}"

runstate () {
  local label="$1" prof="$2" ver="$3" cls="$4"
  mvn -q clean test -P"$prof" -Djackson.version="$ver" >/tmp/jc.log 2>&1 || true
  local rpt="target/surefire-reports/com.example.${cls}.txt"
  local res sig
  res=$(grep -aoE "Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+" "$rpt" 2>/dev/null | head -1)
  sig=$(grep -aoE "StreamConstraintsException[^\"]*" "$rpt" 2>/dev/null | head -1)
  [ -z "$res" ] && res="(no report: $(grep -aoE 'BUILD FAILURE|COMPILATION ERROR' /tmp/jc.log | head -1))"
  printf "%-44s | %-38s %s\n" "$label" "$res" "${sig:+<< $sig}"
}

echo "======== jackson-core 2.14 -> 2.15 StreamReadConstraints differential ========"
runstate "STATE 1  parent  + 2.14.2 (expect PASS)" parent  2.14.2 ParentBbcTest
runstate "STATE 2  parent  + 2.15.0 (expect FAIL)" parent  2.15.0 ParentBbcTest
runstate "STATE 3  adapted + 2.15.0 (expect PASS)" adapted 2.15.0 AdaptedBbcTest
echo "=============================================================================="
