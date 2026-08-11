#!/usr/bin/env bash
# 3-state differential for snakeyaml-codepointlimit-infoarchive.
#
# Not run through 02_verify_bbc.py: infoarchive-sip-sdk builds with Gradle and the verifier
# drives Maven. Only the `core` package of the `yaml` module is compiled, which is enough to
# exercise YamlMap.from(String) and nothing more.
#
#   1  parent code  + snakeyaml 1.31  -> loads   (limit does not exist yet)
#   2  parent code  + snakeyaml 2.0   -> THROWS  (3 MB default limit)
#   3  adapted code + snakeyaml 2.0   -> loads   (their fix raises it to 10 MB)
#
# States 2 and 3 share a snakeyaml jar, so the only variable between them is their commit.
set -eu

REPO=https://github.com/Enterprise-Content-Management/infoarchive-sip-sdk.git
PARENT=c9e9e1e0df543f85d89b6bb1a10a39d00ebce5d9
ADAPT=4b617cd8b9ebcf66cd42494eb2384398089eaf6e
JB="${JAVA_HOME:-/c/Program Files/Eclipse Adoptium/jdk-11.0.31.11-hotspot}/bin"
W="${1:-./work}"

mkdir -p "$W/libs"
for gav in \
  "commons-io/commons-io/2.11.0/commons-io-2.11.0.jar" \
  "org/atteo/evo-inflector/1.3/evo-inflector-1.3.jar" \
  "com/google/code/findbugs/jsr305/3.0.2/jsr305-3.0.2.jar" \
  "org/yaml/snakeyaml/1.31/snakeyaml-1.31.jar" \
  "org/yaml/snakeyaml/2.0/snakeyaml-2.0.jar" ; do
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

DEPS="../libs/commons-io-2.11.0.jar;../libs/evo-inflector-1.3.jar;../libs/jsr305-3.0.2.jar"
build() {  # build <srcdir> <snakeyaml-version> <outdir>
  ( cd "$1" && "$JB/javac" -nowarn \
      -cp "../libs/snakeyaml-$2.jar;$DEPS" -d "../$3" \
      yaml/src/main/java/com/opentext/ia/yaml/core/*.java )
}
build parent 1.31 build-parent-1.31
build parent 2.0  build-parent-2.0
build adapt  2.0  build-adapt-2.0

cp Driver.java "$W/" 2>/dev/null || cp "$(dirname "$0")/Driver.java" "$W/"
( cd "$W" && "$JB/javac" -cp build-parent-1.31 -d driver Driver.java )

run() {  # run <label> <classes> <snakeyaml-version>
  echo "=== $1 ==="
  ( cd "$W" && "$JB/java" -Xmx1g \
      -cp "libs/snakeyaml-$3.jar;libs/commons-io-2.11.0.jar;libs/evo-inflector-1.3.jar;libs/jsr305-3.0.2.jar;$2;driver" \
      Driver 4 )
}
run "1 baseline : parent code + snakeyaml 1.31" build-parent-1.31 1.31
run "2 broken   : parent code + snakeyaml 2.0"  build-parent-2.0  2.0
run "3 adapted  : adapted code + snakeyaml 2.0" build-adapt-2.0   2.0
