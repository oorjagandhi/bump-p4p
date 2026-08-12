#!/bin/bash
# One-time setup for the couchbase differential.
#
# couchbase-jvm-clients cannot be built from a fresh clone against Maven Central alone.
# core-io depends on com.couchbase.client:protostellar:1.0-SNAPSHOT, which is NOT published
# (repo1 returns 404) and is not in the root pom's <modules> list -- it is a module in the
# tree that couchbase's own CI builds separately. core-io references its generated gRPC
# stubs in 69 files, so it cannot be excluded.
#
# protostellar is identical in all three states, so it is built once here rather than per
# state. Codegen runs through protoc-jar, which downloads a protoc binary; it works on
# Windows and writes generated sources into repo/protostellar/src/main/java. Those are
# untracked, so the `git reset --hard` in run_state.sh leaves them alone.
#
# Run this once after cloning, before run_state.sh.
set -u
cd "$(dirname "$0")/repo" || exit 1

if [ ! -d ../../.bbc_m2/com/couchbase/client/protostellar/1.0-SNAPSHOT ]; then
  echo "[bootstrap] building protostellar 1.0-SNAPSHOT (protoc codegen)..."
  mvn -B -q -f protostellar/pom.xml install -DskipTests \
      -Dmaven.repo.local=../../.bbc_m2 > ../bootstrap.log 2>&1
  if [ $? -ne 0 ]; then echo "[bootstrap] FAILED (protostellar)"; tail -10 ../bootstrap.log; exit 1; fi
fi
echo "[bootstrap] protostellar present."

# test-utils is a TEST-scope dependency of core-io and is never loaded by the driver, but
# dependency:build-classpath resolves the whole graph before it will emit anything, and
# fails on this one sibling SNAPSHOT. -DincludeScope=compile does not help: the scope
# filter is applied AFTER resolution. So it has to exist. It does not depend on core-io,
# so there is no cycle.
if [ ! -d ../../.bbc_m2/com/couchbase/client/test-utils/1.4.7-SNAPSHOT ]; then
  echo "[bootstrap] building test-utils 1.4.7-SNAPSHOT..."
  mvn -B -q -f test-utils/pom.xml install -DskipTests \
      -Dmaven.repo.local=../../.bbc_m2 > ../bootstrap-testutils.log 2>&1
  if [ $? -ne 0 ]; then echo "[bootstrap] FAILED (test-utils)"; tail -10 ../bootstrap-testutils.log; exit 1; fi
fi
echo "[bootstrap] test-utils present."

# ...and test-utils' POM names the root as its parent, which Maven can only read through
# relativePath while building in-tree. Resolving it from the repository -- which is what
# build-classpath ends up doing -- needs the parent POM installed. `-N` is what makes this
# possible at all: a normal `install` at the root builds the reactor, which cannot even be
# parsed (see the scala-implicits note in run_state.sh).
if [ ! -d ../../.bbc_m2/com/couchbase/client/couchbase-jvm-clients/1.13.7-SNAPSHOT ]; then
  echo "[bootstrap] installing root parent POM (non-recursive)..."
  mvn -B -q -N install -DskipTests -Dmaven.repo.local=../../.bbc_m2 > ../bootstrap-parent.log 2>&1
  if [ $? -ne 0 ]; then echo "[bootstrap] FAILED (parent pom)"; tail -10 ../bootstrap-parent.log; exit 1; fi
fi
echo "[bootstrap] root parent POM present."
