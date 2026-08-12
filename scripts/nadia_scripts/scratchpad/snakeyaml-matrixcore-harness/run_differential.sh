#!/usr/bin/env bash
# 3-state differential for snakeyaml-codepointlimit-matrixcore (SPIGOT-7161).
#
#   1  parent code  + snakeyaml 1.31  -> loads   (limit does not exist yet)
#   2  parent code  + snakeyaml 1.33  -> THROWS  (3 MiB default)
#   3  adapted code + snakeyaml 1.33  -> loads   (setCodePointLimit(Integer.MAX_VALUE))
#
# Gradle/Maven are not used: javac over org/bukkit/configuration/** with -sourcepath
# resolves 779 classes from their own tree. The extra jars are what org.bukkit.Bukkit
# transitively drags in (maven-resolver via LibraryLoader, gson via VersionCommand).
set -eu

REPO=https://github.com/yoricya/MatrixCore-API.git
PARENT=0994345029c4d127696616de3bab3e8044b03749
ADAPT=b24bb75af90daa49b4759f69a9bf7c6adc5d2a06
JB="${JAVA_HOME:-/c/Program Files/Eclipse Adoptium/jdk-11.0.31.11-hotspot}/bin"
W="${1:-./work}"

mkdir -p "$W/libs"
for gav in \
  "org/yaml/snakeyaml/1.31/snakeyaml-1.31.jar" \
  "org/yaml/snakeyaml/1.33/snakeyaml-1.33.jar" \
  "org/jetbrains/annotations/24.0.1/annotations-24.0.1.jar" \
  "com/google/guava/guava/31.1-jre/guava-31.1-jre.jar" \
  "com/google/code/gson/gson/2.10.1/gson-2.10.1.jar" \
  "org/apache/commons/commons-lang3/3.12.0/commons-lang3-3.12.0.jar" \
  "org/apache/maven/maven-resolver-provider/3.8.5/maven-resolver-provider-3.8.5.jar" \
  "org/apache/maven/resolver/maven-resolver-api/1.7.3/maven-resolver-api-1.7.3.jar" \
  "org/apache/maven/resolver/maven-resolver-util/1.7.3/maven-resolver-util-1.7.3.jar" \
  "org/apache/maven/resolver/maven-resolver-impl/1.7.3/maven-resolver-impl-1.7.3.jar" \
  "org/apache/maven/resolver/maven-resolver-spi/1.7.3/maven-resolver-spi-1.7.3.jar" \
  "org/apache/maven/resolver/maven-resolver-connector-basic/1.7.3/maven-resolver-connector-basic-1.7.3.jar" \
  "org/apache/maven/resolver/maven-resolver-transport-http/1.7.3/maven-resolver-transport-http-1.7.3.jar" ; do
  f="$W/libs/$(basename "$gav")"
  [ -f "$f" ] || curl -sfSL -o "$f" "https://repo1.maven.org/maven2/$gav"
done

fetch() { rm -rf "$2"; mkdir -p "$2"; ( cd "$2"
  git init -q; git config core.longpaths true
  git remote add origin "$REPO"
  git fetch -q --depth 1 origin "$1"; git checkout -q FETCH_HEAD ); }
fetch "$PARENT" "$W/parent"
fetch "$ADAPT"  "$W/adapt"

cd "$W"
OTHER=$(ls libs/*.jar | grep -v snakeyaml | tr '\n' ';')
build() {  # build <dir> <snakeyaml-version>
  find "$1/src/main/java/org/bukkit/configuration" -name "*.java" > "s-$1.txt"
  "$JB/javac" -nowarn -cp "libs/snakeyaml-$2.jar;$OTHER" \
      -sourcepath "$1/src/main/java" -d "build-$1-$2" "@s-$1.txt"
}
build parent 1.31
build parent 1.33
build adapt  1.33

cp "$(dirname "$0")/Driver.java" .
"$JB/javac" -cp "build-adapt-1.33;libs/snakeyaml-1.33.jar;$OTHER" -d driver Driver.java

run() { echo "=== $1 ==="
  "$JB/java" -Xmx1g -cp "libs/snakeyaml-$3.jar;$OTHER;build-$2-$3;driver" Driver 4; }
run "1 baseline : parent code + snakeyaml 1.31"  parent 1.31
run "2 broken   : parent code + snakeyaml 1.33"  parent 1.33
run "3 adapted  : adapted code + snakeyaml 1.33" adapt  1.33
