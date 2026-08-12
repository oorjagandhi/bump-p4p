#!/bin/bash
# One state of the benchto differential.  $1=label  $2=sha  $3=jackson version
#
# Windows javac/java cannot read Git Bash's POSIX paths, so all paths below are relative to
# repo/ and the driver is copied in. benchto targets Java 21, which is not the PATH default
# here (Adoptium 11), so the JDK 21 binaries are named explicitly -- JAVA_HOME alone steers
# only Maven.
#
# THE VERSION KNOB IS -Djackson-bom.version, NOT a benchto property. benchto never names a
# jackson version: it inherits airbase as its parent POM, imports spring-boot-dependencies,
# and takes whatever jackson that BOM manages. `jackson-bom.version` is Spring Boot's OWN
# property, and a Maven USER property (-D) outsRanks the value declared inside an imported
# BOM -- verified here by resolving jackson-core at 2.17.2 with no flag and 2.14.2 with it.
# So the differential moves jackson alone while Spring Boot stays pinned at 3.3.5, which is
# what isolates the library from the framework upgrade that delivered it.
set -u
export JAVA_HOME="/c/Program Files/Java/jdk-21"
JAVAC="$JAVA_HOME/bin/javac"
JAVA="$JAVA_HOME/bin/java"
M2=../../.bbc_m2
cd "$(dirname "$0")/repo" || exit 1

# benchto inherits airbase's checkstyle, which enforces LF and FAILS THE BUILD on carriage
# returns. A default Windows clone applies autocrlf=true and rewrites every source file to
# CRLF, so the build dies in checkstyle before ever compiling -- on a pure checkout
# artefact, in files nobody edited. Fixing the checkout keeps the project's own quality
# gates ENABLED, which is the point: -Dcheckstyle.skip would also have made it build, by
# switching off one of their checks.
git config core.autocrlf false
git config core.eol lf
git checkout -q -f "$2" || exit 1
cp ../BenchtoBbcDriver.java .

# -Dair.check.skip-enforcer: airbase runs maven-enforcer's RequireUpperBoundDeps, which FAILS when
# jackson is pinned BELOW what something else in the graph asks for -- exactly what the
# baseline does (jackson-datatype-jsr310:2.13.3 against a transitive that wants newer).
# It is a dependency-hygiene rule about the graph, not about behaviour, and it only objects
# to the deliberate downgrade.
#
# It is skipped in EVERY state, not just the baseline. Skipping it only where it fires
# would mean states 1 and 2 were built under different rules, and the whole value of the
# differential is that the states differ in exactly one thing. States 2 and 3 pass the rule
# on their own; the flag is there to keep them comparable to state 1.
mvn -B -q clean -pl benchto-service -Dmaven.repo.local=$M2 >/dev/null 2>&1
mvn -B -q -DskipTests compile -pl benchto-service -Dmaven.repo.local=$M2 \
    -Dair.check.skip-enforcer=true -Djackson-bom.version="$3" > "../$1.build.log" 2>&1
if [ $? -ne 0 ]; then echo "$1: BUILD FAILED"; grep -E "ERROR|error:" "../$1.build.log" | head -8; exit 1; fi

# build-classpath resolves mdep.outputFile against the -pl module's basedir, not the shell
# cwd, so `../cp.txt` from benchto-service lands in repo/ -- which is where `cat` reads it.
mvn -B -q dependency:build-classpath -pl benchto-service -Dmdep.outputFile=../cp.txt \
    -Dmaven.repo.local=$M2 -Dair.check.skip-enforcer=true -Djackson-bom.version="$3" >/dev/null 2>&1
CP="benchto-service/target/classes;$(cat cp.txt)"
rm -rf driver && mkdir -p driver
"$JAVAC" -cp "$CP" -d driver BenchtoBbcDriver.java 2>&1 | head -6
"$JAVA" -cp "driver;$CP" BenchtoBbcDriver
