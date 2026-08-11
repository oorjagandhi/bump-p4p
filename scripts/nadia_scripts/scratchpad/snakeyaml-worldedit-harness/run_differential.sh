#!/usr/bin/env bash
# 3-state differential for snakeyaml-codepointlimit-worldedit.
#
# EngineHub/WorldEdit@0ef38b52 "Use SnakeYaml 1.32+, set loader code point limit. (#2194)"
# bumps snakeyaml 1.26 -> 1.33 AND applies the fix in ONE commit, so the baseline below is
# the version they were actually on -- not a stand-in chosen by us.
#
#   1  parent code  + snakeyaml 1.26  -> loads
#   2  parent code  + snakeyaml 1.33  -> THROWS (3 MiB default limit)
#   3  adapted code + snakeyaml 1.33  -> loads  (their fix sets 64 MB)
#
# Gradle is not used: 02_verify_bbc.py drives Maven, and javac -sourcepath resolves the 17
# classes this path needs straight from their own source tree.
set -eu

REPO=https://github.com/EngineHub/WorldEdit.git
PARENT=7e61ff19ca27dcf103c65564d298df611c6bf7c3
ADAPT=0ef38b529231283ceaeb00b0eaaeb670fb3f0a44
JB="${JAVA_HOME:-/c/Program Files/Eclipse Adoptium/jdk-11.0.31.11-hotspot}/bin"
W="${1:-./work}"

mkdir -p "$W/libs"
for gav in \
  "org/yaml/snakeyaml/1.26/snakeyaml-1.26.jar" \
  "org/yaml/snakeyaml/1.33/snakeyaml-1.33.jar" \
  "com/google/guava/guava/31.1-jre/guava-31.1-jre.jar" \
  "com/google/code/findbugs/jsr305/3.0.2/jsr305-3.0.2.jar" ; do
  f="$W/libs/$(basename "$gav")"
  [ -f "$f" ] || curl -sfSL -o "$f" "https://repo1.maven.org/maven2/$gav"
done

fetch() {  # fetch <sha> <dir> -- one commit, no history
  rm -rf "$2"; mkdir -p "$2"; ( cd "$2"
    git init -q; git config core.longpaths true
    git remote add origin "$REPO"
    git fetch -q --depth 1 origin "$1"; git checkout -q FETCH_HEAD )
}
fetch "$PARENT" "$W/parent"
fetch "$ADAPT"  "$W/adapt"

DEPS="libs/guava-31.1-jre.jar;libs/jsr305-3.0.2.jar"
build() {  # build <dir> <snakeyaml-version>
  ( cd "$W" && "$JB/javac" -nowarn \
      -cp "libs/snakeyaml-$2.jar;$DEPS" \
      -sourcepath "$1/worldedit-core/src/main/java" -d "build-$1-$2" \
      "$1/worldedit-core/src/main/java/com/sk89q/util/yaml/YAMLProcessor.java" )
}
build parent 1.26
build parent 1.33
build adapt  1.33

cp "$(dirname "$0")/Driver.java" "$W/"
( cd "$W" && "$JB/javac" -cp build-adapt-1.33 -d driver Driver.java )

run() {  # run <label> <dir> <snakeyaml-version>
  echo "=== $1 ==="
  ( cd "$W" && "$JB/java" -Xmx1g \
      -cp "libs/snakeyaml-$3.jar;build-$2-$3;$DEPS;driver" Driver 4 )
}
run "1 baseline : parent code + snakeyaml 1.26"  parent 1.26
run "2 broken   : parent code + snakeyaml 1.33"  parent 1.33
run "3 adapted  : adapted code + snakeyaml 1.33" adapt  1.33
