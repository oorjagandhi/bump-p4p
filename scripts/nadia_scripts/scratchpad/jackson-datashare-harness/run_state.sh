#!/bin/bash
# One state of the datashare differential.  $1=label  $2=sha  $3=jackson version
# Windows javac/java cannot read Git Bash's POSIX paths, so all paths below are relative
# to repo/ and the driver is copied in. datashare targets Java 17.
#
# JAVA_HOME steers Maven, but NOT the bare javac/java on PATH -- this machine's PATH puts
# Adoptium 11 first, so the driver has to name the JDK 17 binaries explicitly. Without
# this the module compiles at 61.0 and javac 11 then refuses to read its own build
# ("class file has wrong version 61.0, should be 55.0"). datashare is the first case in
# the set that needs a JDK other than the PATH default.
set -u
export JAVA_HOME="/c/Program Files/Java/jdk-17"
JAVAC="$JAVA_HOME/bin/javac"
JAVA="$JAVA_HOME/bin/java"
M2=../../.bbc_m2
cd "$(dirname "$0")/repo" || exit 1
git checkout -q "$2" || exit 1
cp ../DatashareBbcDriver.java .
mvn -B -q clean -pl datashare-api -am -Dmaven.repo.local=$M2 >/dev/null 2>&1
mvn -B -q -DskipTests package -pl datashare-api -am -Dmaven.repo.local=$M2 \
    -Djackson.version="$3" > "../$1.build.log" 2>&1
if [ $? -ne 0 ]; then echo "$1: BUILD FAILED"; grep -E "ERROR|error:" "../$1.build.log" | head -8; exit 1; fi
mvn -B -q dependency:build-classpath -pl datashare-api -Dmdep.outputFile=../cp.txt \
    -Dmaven.repo.local=$M2 -Djackson.version="$3" >/dev/null 2>&1
# build-classpath resolves mdep.outputFile against the -pl module's basedir, not the shell
# cwd, so `../cp.txt` from datashare-api lands in repo/ -- which is where `cat` reads it.
CP="datashare-api/target/classes;$(cat cp.txt)"
rm -rf driver && mkdir -p driver
"$JAVAC" -cp "$CP" -d driver DatashareBbcDriver.java 2>&1 | head -6
"$JAVA" -cp "driver;$CP" DatashareBbcDriver
