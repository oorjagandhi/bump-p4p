#!/bin/bash
# One state of the arangodb differential.  $1=label  $2=sha  $3=jackson version
#
# UNIQUE IN THIS CORPUS: the trigger is THEIR OWN TEST, not an authored driver.
# JacksonConfigurationTest round-trips a 40,000,000-character string through their serde and
# asserts it comes back equal. Every other case for this break needed a hand-written trigger
# because no project ships a fixture that large -- arangodb GENERATES one, so their suite
# can express the break directly.
#
# The test is added BY the adaptation commit, so for the baseline and broken states it is
# copied into the parent checkout. Its imports (ContentType, InternalSerdeProvider,
# JacksonSerde) all exist at the parent, so it compiles there unchanged -- nothing about the
# test is modified, and it is theirs in every state.
#
# arangodb targets Java 8; JDK 17 compiles that fine and is what Maven gets here. Javadoc
# and gpg are skipped: the release-profile javadoc run dies inside the JDK 17 javadoc tool
# itself ("java.lang.IllegalStateException: ERRONEOUS"), which has nothing to do with the
# break, and neither goal affects the classes under test.
# The version knob is -Dadb.jackson.version, their own property.
set -u
export JAVA_HOME="/c/Program Files/Java/jdk-17"
M2=../../.bbc_m2
TEST=driver/src/test/java/com/arangodb/serde/JacksonConfigurationTest.java
FIX=5b1b958a5bde
cd "$(dirname "$0")/repo" || exit 1

git checkout -q -f "$2" || exit 1
# Bring their test in when the state predates it. `git checkout <fix> -- <path>` takes the
# file verbatim from the adaptation commit, so no hand-editing is possible.
if [ ! -f "$TEST" ]; then
  mkdir -p "$(dirname $TEST)"
  git checkout -q "$FIX" -- "$TEST" || exit 1
fi

# -pl driver -am builds core, jackson-serde-json and the rest of what driver needs.
mvn -B -q clean -pl driver -am -Dmaven.repo.local=$M2 >/dev/null 2>&1
mvn -B -q -DskipTests install -pl driver -am -Dmaven.repo.local=$M2 \
    -Dadb.jackson.version="$3" -Dgpg.skip=true -Dmaven.javadoc.skip=true > "../$1.build.log" 2>&1
if [ $? -ne 0 ]; then echo "$1: BUILD FAILED"; grep -E "ERROR|error:" "../$1.build.log" | head -8; exit 1; fi

# Run ONLY their constraints test. -DfailIfNoSpecifiedTests guards against the class being
# silently skipped, which would look like a pass.
mvn -B -pl driver surefire:test -Dtest=JacksonConfigurationTest -DfailIfNoSpecifiedTests=true \
    -Dmaven.repo.local=$M2 -Dadb.jackson.version="$3" > "../$1.test.log" 2>&1
rc=$?
echo "--- $1 (jackson $3) ---"
grep -E "Tests run|StreamConstraintsException|BUILD SUCCESS|BUILD FAILURE" "../$1.test.log" | head -6
echo "exit=$rc"
