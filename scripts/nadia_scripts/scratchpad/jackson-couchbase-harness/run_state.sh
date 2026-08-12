#!/bin/bash
# One state of the couchbase differential.  $1=label  $2=core-io sha  $3=jackson version
#
# Windows javac/java cannot read Git Bash's POSIX paths, so all paths below are relative
# to repo/ and the driver is copied in. couchbase targets Java 8; the PATH default here is
# Adoptium 11, which compiles source/target 8 fine, so no JDK override is needed.
#
# THIS BUILD HAS TWO PREREQUISITES THAT ARE NOT ON MAVEN CENTRAL, and both are modules in
# the repo that the root pom does NOT list, so they must be built by hand:
#
#   protostellar   1.0-SNAPSHOT  gRPC/protobuf stubs; core-io references them in 69 files
#   core-io-deps   1.4.7-SNAPSHOT  shades netty + jackson + protostellar into
#                                  com.couchbase.client.core.deps.*
#
# protostellar never changes across states, so bootstrap.sh installs it once. core-io-deps
# is where jackson actually lives, so it is REBUILT PER STATE with -Djackson.version.
#
# core-io-deps is always built from the ADAPTED commit's tree, in every state. That commit
# carries a build-only shade fix (excluding META-INF/versions/**, a workaround for
# MSHADE-406) which is required to repackage jackson 2.15 at all. Holding the shading
# config fixed keeps it out of the differential: the only thing that moves between states 1
# and 2 is -Djackson.version, and between 2 and 3 the core-io source tree.
set -u
M2=../../.bbc_m2
DEPS_TREE=77c218722549          # the adapted commit, source of the shade config
cd "$(dirname "$0")/repo" || exit 1

git reset -q --hard >/dev/null 2>&1
git checkout -q -f "$2" || exit 1
git checkout -q "$DEPS_TREE" -- core-io-deps/ || exit 1
cp ../CouchbaseBbcDriver.java .

# `clean` here is NOT optional. Without it the previous state's shaded jar is still in
# target/ and gets fed back into the shade plugin, which fails on "duplicate entry:
# META-INF/services/...jackson.core.ObjectCodec". Worse than the failure is the near miss:
# this is the step that decides which jackson is baked into the deps jar, so a stale target/
# is exactly how two states could end up running the same jackson while claiming otherwise.
mvn -B -q -f core-io-deps/pom.xml clean install -DskipTests -Djackson.version="$3" \
    -Dmaven.repo.local=$M2 > "../$1.deps.log" 2>&1
if [ $? -ne 0 ]; then echo "$1: core-io-deps BUILD FAILED"; tail -8 "../$1.deps.log"; exit 1; fi

# `-f core-io/pom.xml`, NOT `-pl core-io`: -pl still makes Maven parse every module in the
# root reactor, and scala-implicits/pom.xml cannot be parsed at all -- its artifactId is
# `scala-implicits_${scala.compat.version}` and the property carries a mangled default
# ("2.12 -Dscala.compat.library.version=2.12.17", a command line pasted into a POM), so
# Maven rejects it as an invalid id before any module is built. Targeting core-io's own POM
# resolves the parent through relativePath without pulling in its siblings.
#
# `compile`, not `package`: core-io's package phase shades core-io-deps into the jar, which
# is irrelevant here and slow. target/classes plus the deps jar on the classpath is the
# same code.
mvn -B -q -f core-io/pom.xml clean -Dmaven.repo.local=$M2 >/dev/null 2>&1
mvn -B -q -f core-io/pom.xml -DskipTests compile -Dmaven.repo.local=$M2 > "../$1.build.log" 2>&1
if [ $? -ne 0 ]; then echo "$1: core-io BUILD FAILED"; grep -E "ERROR|error:" "../$1.build.log" | head -8; exit 1; fi

# build-classpath resolves mdep.outputFile against the module's basedir, not the shell cwd,
# so `../cp.txt` from core-io lands in repo/ -- which is where `cat` reads it.
mvn -B -q -f core-io/pom.xml dependency:build-classpath -Dmdep.outputFile=../cp.txt \
    -Dmaven.repo.local=$M2 >/dev/null 2>&1
CP="core-io/target/classes;$(cat cp.txt)"
rm -rf driver && mkdir -p driver
javac -cp "$CP" -d driver CouchbaseBbcDriver.java 2>&1 | head -6
java -cp "driver;$CP" CouchbaseBbcDriver
