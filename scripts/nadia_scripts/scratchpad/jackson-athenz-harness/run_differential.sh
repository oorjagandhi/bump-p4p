#!/usr/bin/env bash
# 3-state differential for jackson-streamreadconstraints-athenz.
#
# AthenZ bumped jackson-core 2.14.2 -> 2.15.2 @7c140534 (2023-06-02) and adapted @82a1f1a2
# (2023-06-08) -- six days -- raising maxStringLength to 200,000,000.
#
#   1  parent code  + jackson-core 2.14.2  -> parses  (no constraint yet)
#   2  parent code  + jackson-core 2.15.2  -> THROWS  StreamConstraintsException, 20M default
#   3  adapted code + jackson-core 2.15.2  -> parses  (their override raises it to 200M)
#
# State 3 runs THEIR method, ZmsSyncer.setupJsonParserLimits(): package-private, no instance
# state, and their three-arg constructor skips the AWS setup the no-arg one performs. The
# 200000000 comes from their own Config.DEFAULT_JSON_MAX_STRING_LENGTH via putIfAbsent -- we
# supply only the deployment layout their Config expects (an empty zms_syncer.conf) so those
# defaults load.
#
# jackson-databind/-annotations MUST match the core version in each state. Mixing them gives
# ClassNotFoundException: StreamConstraintsException, which is version skew, not the break.
set -eu

REPO=https://github.com/AthenZ/athenz.git
PARENT=ffa5cd11659d3eef5d2e2563fd8f2e13046b5872
ADAPT=82a1f1a2df6f7f7e24f7f79b8b2fc1107607c63b
# Both fall back to whatever the toolkit resolves rather than to the absolute paths of the
# box this was first run on, so the harness still works from a copied folder. `paths.m2_repo()`
# keeps using an existing .bbc_m2 in an ancestor directory when there is one.
JH="${JAVA_HOME:-$(python -c 'import sys;sys.path.insert(0,sys.argv[1]);from orchestrator import JDKS;print(JDKS["21"])' "$(cd "$(dirname "$0")/../../agent" && pwd)")}"
M2="${BBC_M2_REPO:-$(python -c 'import sys;sys.path.insert(0,sys.argv[1]);from paths import str_m2;print(str_m2())' "$(cd "$(dirname "$0")/../.." && pwd)")}"
W="${1:-./work}"

mkdir -p "$W/libs"
for gav in \
  "com/fasterxml/jackson/core/jackson-core/2.14.2/jackson-core-2.14.2.jar" \
  "com/fasterxml/jackson/core/jackson-core/2.15.2/jackson-core-2.15.2.jar" \
  "com/fasterxml/jackson/core/jackson-databind/2.14.2/jackson-databind-2.14.2.jar" \
  "com/fasterxml/jackson/core/jackson-databind/2.15.2/jackson-databind-2.15.2.jar" \
  "com/fasterxml/jackson/core/jackson-annotations/2.14.2/jackson-annotations-2.14.2.jar" \
  "com/fasterxml/jackson/core/jackson-annotations/2.15.2/jackson-annotations-2.15.2.jar" \
  "org/slf4j/slf4j-api/1.7.36/slf4j-api-1.7.36.jar" \
  "com/yahoo/rdl/rdl-java/1.5.4/rdl-java-1.5.4.jar" ; do
  f="$W/libs/$(basename "$gav")"
  [ -f "$f" ] || curl -sfSL -o "$f" "https://repo1.maven.org/maven2/$gav"
done

fetch() { rm -rf "$2"; mkdir -p "$2"; ( cd "$2"
  git init -q; git config core.longpaths true
  git remote add origin "$REPO"
  git fetch -q --depth 1 origin "$1"; git checkout -q FETCH_HEAD ); }
fetch "$PARENT" "$W/parent"
fetch "$ADAPT"  "$W/adapt"

for d in parent adapt; do
  ( cd "$W/$d" && JAVA_HOME="$JH" mvn -B -q -pl syncers/zms_aws_domain_syncer -am \
      -DskipTests -Dmaven.repo.local="$M2" -Denforcer.skip=true -Dlicense.skip=true \
      -Dcheckstyle.skip=true -Dspotbugs.skip=true test-compile )
done

cd "$W"
mkdir -p azroot/zms_syncer/conf && echo '{}' > azroot/zms_syncer/conf/zms_syncer.conf
mkdir -p drv/com/yahoo/athenz/zms_aws_domain_syncer
cp "$(dirname "$0")/AthenzBbcDriver.java" drv/com/yahoo/athenz/zms_aws_domain_syncer/

D15="libs/jackson-databind-2.15.2.jar;libs/jackson-annotations-2.15.2.jar;libs/slf4j-api-1.7.36.jar;libs/rdl-java-1.5.4.jar"
D14="libs/jackson-databind-2.14.2.jar;libs/jackson-annotations-2.14.2.jar;libs/slf4j-api-1.7.36.jar;libs/rdl-java-1.5.4.jar"
"$JH/bin/javac" -nowarn -cp "adapt/syncers/zms_aws_domain_syncer/target/classes;libs/jackson-core-2.15.2.jar;$D15" \
    -d drvout drv/com/yahoo/athenz/zms_aws_domain_syncer/AthenzBbcDriver.java

run() {  # run <label> <tree> <jackson-version> <deps> <mode>
  echo "=== $1 ==="
  TC=$(find "$2" -path "*/target/classes" -type d | tr '\n' ';')
  "$JH/bin/java" -Xmx3g -Dyahoo.auth.zms_syncer_aws.root_path=azroot \
      -cp "libs/jackson-core-$3.jar;$4;$TC;drvout" \
      com.yahoo.athenz.zms_aws_domain_syncer.AthenzBbcDriver "$5" 25
}
run "1 baseline : parent code + jackson-core 2.14.2"  parent 2.14.2 "$D14" plain
run "2 broken   : parent code + jackson-core 2.15.2"  parent 2.15.2 "$D15" plain
run "3 adapted  : adapted code + jackson-core 2.15.2" adapt  2.15.2 "$D15" adapt
