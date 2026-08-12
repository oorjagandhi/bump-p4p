#!/bin/bash
# One state of the json-compare differential.  $1=label  $2=sha  $3=jackson version
# Windows javac/java cannot read the POSIX paths Git Bash uses, so everything below is
# relative to repo/ and the driver is copied in.
set -u
M2=../../.bbc_m2
cd "$(dirname "$0")/repo" || exit 1
git checkout -q "$2" || exit 1
cp ../JsonCompareBbcDriver.java .
mvn -B -q clean -Dmaven.repo.local=$M2 >/dev/null 2>&1
mvn -B -q -DskipTests package -Dmaven.repo.local=$M2 \
    -Djackson.version="$3" -Djackson.databind.version="$3" > "../$1.build.log" 2>&1
if [ $? -ne 0 ]; then echo "$1: BUILD FAILED"; tail -6 "../$1.build.log"; exit 1; fi
mvn -B -q dependency:build-classpath -Dmdep.outputFile=cp.txt -Dmaven.repo.local=$M2 \
    -Djackson.version="$3" -Djackson.databind.version="$3" >/dev/null 2>&1
CP="target/classes;$(cat cp.txt)"
rm -rf driver && mkdir -p driver
javac -cp "$CP" -d driver JsonCompareBbcDriver.java 2>&1 | head -5
java -cp "driver;$CP" JsonCompareBbcDriver
