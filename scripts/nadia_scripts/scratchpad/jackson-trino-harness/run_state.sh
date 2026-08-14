#!/bin/bash
# One state of the trino differential.  $1=label  $2=sha  $3=jackson version
#
# Windows javac/java cannot read Git Bash's POSIX paths, so all paths below are relative to
# repo/ and the driver is copied in. trino 419-era targets Java 17.
#
# THE CLONE MUST BE SPARSE AND LONG-PATH ENABLED. A full checkout of trino fails on Windows
# before it finishes -- plugin/trino-delta-lake ships Hive-partition test fixtures whose
# directory names blow past MAX_PATH ("Filename too long", "cannot create directory"). So
# the harness clones with --no-checkout and excludes those fixture trees. bootstrap.sh does
# that once. Note `git checkout -f` below re-applies the sparse rules, so the excluded trees
# stay excluded when states switch commits.
#
# The version knob is -Ddep.jackson.version, trino's own property. Note it is a property
# they ADDED at 2d697eb0 (2023-05-19) -- before that jackson came from the airbase parent,
# which is where the actual boundary crossing happened. See the case file.
set -u
export JAVA_HOME="/c/Program Files/Java/jdk-17"
JAVAC="$JAVA_HOME/bin/javac"
JAVA="$JAVA_HOME/bin/java"
M2=../../.bbc_m2
cd "$(dirname "$0")/repo" || exit 1

git checkout -q -f "$2" || exit 1
cp ../TrinoBbcDriver.java .

# -pl plugin/trino-prometheus -am builds core/trino-spi, lib/trino-plugin-toolkit and the
# rest of what the prometheus plugin needs. Checks are skipped -- they are slow, they are
# not what is being measured, and they are skipped IDENTICALLY in every state:
#   air.check.skip-*  airbase's enforcer/checkstyle/modernizer/dependency checks. Modernizer
#                     matters here: the adaptation's own helper is annotated
#                     @SuppressModernizer precisely because trino BANS direct JsonFactory
#                     use, so leaving the check on would make the PARENT state fail a style
#                     gate rather than the differential.
mvn -B -q clean -pl plugin/trino-prometheus -am -Dmaven.repo.local=$M2 >/dev/null 2>&1
mvn -B -q -DskipTests install -pl plugin/trino-prometheus -am -Dmaven.repo.local=$M2 \
    -Ddep.jackson.version="$3" -Dair.check.skip-all=true -Dmaven.javadoc.skip=true \
    > "../$1.build.log" 2>&1
if [ $? -ne 0 ]; then echo "$1: BUILD FAILED"; grep -E "ERROR|error:" "../$1.build.log" | head -8; exit 1; fi

# build-classpath resolves mdep.outputFile against the -pl module's basedir, not the shell
# cwd, so `../../cp.txt` from plugin/trino-prometheus lands in repo/.
mvn -B -q dependency:build-classpath -pl plugin/trino-prometheus -Dmdep.outputFile=../../cp.txt \
    -Dmaven.repo.local=$M2 -Ddep.jackson.version="$3" -Dair.check.skip-all=true >/dev/null 2>&1
CP="plugin/trino-prometheus/target/classes;$(cat cp.txt)"
rm -rf driver && mkdir -p driver
"$JAVAC" -cp "$CP" -d driver TrinoBbcDriver.java 2>&1 | head -6
"$JAVA" -cp "driver;$CP" TrinoBbcDriver
