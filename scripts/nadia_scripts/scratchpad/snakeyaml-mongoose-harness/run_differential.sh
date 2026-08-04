#!/usr/bin/env bash
# 3-state differential for the snakeyaml 1.x -> 2.0 default-deny behavioural break
# (CVE-2022-1471 / GHSA-mjmj-j48q-9wg2). EXTERNAL break: discovered via mine_advisories.py
# from the OSV Maven advisory feed, NOT from BUMP.
#
# The production loader pattern (parent vs. adapted) is extracted verbatim from real client
# adaptations found by mining commit search:
#   - telaminai/mongoose-plugins @ 9e5916e1  "TagInspector permits FQN tags"
#   - quarkusio/quarkus          @ 06a8c629  parent was literally `new Yaml()`
#   - Minekarta-Studio/KartaEmeraldCurrency @ 8bb46ffa  setTagInspector(tag -> tag==PlayerData)
#
# Verified 2026-07-20 (Maven 3.9.11 / JDK 11):
#   STATE 1  parent  + snakeyaml 1.33 -> PASS
#   STATE 2  parent  + snakeyaml 2.0  -> FAIL  (YAMLException: Global tag is not allowed: ...MyNode)
#   STATE 3  adapted + snakeyaml 2.0  -> PASS  (opts.setTagInspector re-permits the type)
#
# The parent uses plain `new Yaml()` (compiles unchanged on 1.33 AND 2.0) so states 1/2 differ
# only in the library version. The adapted variant uses the 2.0-only setTagInspector API and is
# built only under the 'adapted' profile (state 3). Run from this dir. Requires Maven + JDK 11.
set -u
export JAVA_HOME="${JAVA_HOME:-/c/Program Files/Eclipse Adoptium/jdk-11.0.31.11-hotspot}"

runstate () {
  local label="$1" prof="$2" ver="$3" cls="$4"
  # `mvn clean` is required: incremental compile would reuse the prior state's classes.
  mvn -q clean test -P"$prof" -Dsnakeyaml.version="$ver" >/tmp/sy.log 2>&1 || true
  local rpt="target/surefire-reports/com.example.${cls}.txt"
  local res sig
  res=$(grep -aoE "Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+" "$rpt" 2>/dev/null | head -1)
  sig=$(grep -aoE "Global tag is not allowed[^\"]*" "$rpt" 2>/dev/null | head -1)
  [ -z "$res" ] && res="(no report: $(grep -aoE 'BUILD FAILURE|COMPILATION ERROR' /tmp/sy.log | head -1))"
  printf "%-44s | %-38s %s\n" "$label" "$res" "${sig:+<< $sig}"
}

echo "============ snakeyaml 1.x -> 2.0 default-deny differential ============"
runstate "STATE 1  parent  + 1.33  (expect PASS)" parent  1.33 ParentBbcTest
runstate "STATE 2  parent  + 2.0   (expect FAIL)" parent  2.0  ParentBbcTest
runstate "STATE 3  adapted + 2.0   (expect PASS)" adapted 2.0  AdaptedBbcTest
echo "======================================================================="
