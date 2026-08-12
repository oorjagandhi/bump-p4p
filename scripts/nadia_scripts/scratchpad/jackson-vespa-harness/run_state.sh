#!/bin/bash
# One state of the vespa differential.  $1=label  $2=sha  $3=jackson version
#
# Windows javac/java cannot read Git Bash's POSIX paths, so all paths below are relative to
# repo/ and the driver is copied in. vespa 8 targets Java 17, which is not the PATH default
# here (Adoptium 11), so the JDK 17 binaries are named explicitly -- JAVA_HOME alone steers
# only Maven.
#
# RUN bootstrap.sh ONCE FIRST. vespa's reactor cannot even be PARSED until its own
# bundle-plugin is installed; see the comments there.
#
# The version knob is -Djackson2.version, vespa's own property, declared in
# container-dependency-versions/pom.xml. A Maven USER property (-D) overrides it -- verified
# by resolving jackson-core at 2.15.0 with no flag and 2.14.2 with it.
set -u
export JAVA_HOME="/c/Program Files/Java/jdk-17"
JAVAC="$JAVA_HOME/bin/javac"
JAVA="$JAVA_HOME/bin/java"
M2=../../.bbc_m2
cd "$(dirname "$0")/repo" || exit 1

git checkout -q -f "$2" || exit 1
cp ../VespaBbcDriver.java .

# -pl document -am: document depends on vespajlib, config, predicate-search-core and
# annotations, all built from source in this reactor. The custom plugins they need are
# already installed by bootstrap.sh, so this no longer trips over "Unknown packaging".
mvn -B -q --no-snapshot-updates clean -pl document -am -Dmaven.repo.local=$M2 >/dev/null 2>&1
mvn -B -q --no-snapshot-updates -DskipTests install -pl document -am -Dmaven.repo.local=$M2 \
    -Djackson2.version="$3" > "../$1.build.log" 2>&1
if [ $? -ne 0 ]; then echo "$1: BUILD FAILED"; grep -E "ERROR|error:" "../$1.build.log" | head -8; exit 1; fi

# build-classpath resolves mdep.outputFile against the -pl module's basedir, not the shell
# cwd, so `../cp.txt` from document lands in repo/ -- which is where `cat` reads it.
# jackson-core is `provided` scope in document, so the default (all scopes) is what puts it
# on the classpath at all.
mvn -B -q dependency:build-classpath -pl document -Dmdep.outputFile=../cp.txt \
    -Dmaven.repo.local=$M2 -Djackson2.version="$3" >/dev/null 2>&1
CP="document/target/classes;$(cat cp.txt)"
rm -rf driver && mkdir -p driver
"$JAVAC" -cp "$CP" -d driver VespaBbcDriver.java 2>&1 | head -6
"$JAVA" -cp "driver;$CP" VespaBbcDriver
