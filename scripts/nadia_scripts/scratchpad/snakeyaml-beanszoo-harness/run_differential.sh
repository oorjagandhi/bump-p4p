#!/usr/bin/env bash
# AUTO-GENERATED reuse-pom 3-state differential for snakeyaml-1.x-to-2.0-safeconstructor (snork-alt/beanszoo).
# Uses the repo's OWN pom (native Maven) — no hand-written dependency list.
# Only the BASELINE version is overridden; states 2 & 3 use the repo's pom as-is.
# Module: 'core' (multi-module builds with -pl core -am).
#   1) parent code + 1.16  -> expect PASS
#   2) parent code + 2.0 (repo)  -> expect FAIL (org.yaml.snakeyaml.constructor.ConstructorException / YAMLException: 'Global tag is not allowed' (or 'could not determine a constructor for the tag') — 2.0 restrictive TagInspector rejects arbitrary-type YAML that 1.x accepted.)
#   3) adapted code + 2.0 (repo) -> expect PASS
set -u
export JAVA_HOME="${JAVA_HOME:-/c/Program Files/Java/jdk-17}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${1:-./snakeyaml-diff}"
git clone --quiet https://github.com/snork-alt/beanszoo.git "$WORK"; cd "$WORK"
mkdir -p "$(dirname "core/src/test/java/bbc/SnakeyamlBbcTest.java")"
cp "$HERE/SnakeyamlBbcTest.java" "core/src/test/java/bbc/SnakeyamlBbcTest.java"
MVN='mvn clean test -pl core -am -Dtest=SnakeyamlBbcTest -DfailIfNoTests=false -DargLine=""'
report() {
  local res sig
  res=$(grep -haoE 'Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+' core/target/surefire-reports/*SnakeyamlBbcTest.txt 2>/dev/null | head -1)
  sig=$(grep -haoE 'Global tag is not allowed|ConstructorException|could not determine a constructor' core/target/surefire-reports/*SnakeyamlBbcTest.txt 2>/dev/null | head -1)
  printf '%-42s %s | %s\n' "$1" "$res" "${sig:-PASS}"
}
git checkout --quiet ea2579dae247ff6f0f1207f99609570b4449f318
python "$HERE/set_baseline_version.py" core/pom.xml org.yaml 1.16
eval "$MVN" >/tmp/bbc_diff.log 2>&1 || true; report "1: parent + 1.16 (PASS)"
git checkout -- core/pom.xml
eval "$MVN" >/tmp/bbc_diff.log 2>&1 || true; report "2: parent + 2.0 (FAIL)"
git stash -u >/dev/null 2>&1 || true; git checkout --quiet 55d17ce2e1a20fa6367a0730d592570f465a9bf3; git stash pop >/dev/null 2>&1 || true
eval "$MVN" >/tmp/bbc_diff.log 2>&1 || true; report "3: adapted + 2.0 (PASS)"
