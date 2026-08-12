#!/bin/bash
# One-time setup for the vespa differential.
#
# vespa cannot be built module-by-module from a fresh clone. Its own bootstrap.sh explains
# why, and this follows that script's documented sequence rather than inventing one:
#
#   "mvn is unable to resolve references to a plugin, if the same mvn program builds the
#    plugin in the same reactor build. Therefore, we need to manually build all plugins
#    first."
#
# bundle-plugin is registered as a BUILD EXTENSION and defines the custom packaging type
# `container-plugin`, so without it installed Maven cannot even PARSE the reactor -- the
# failure is "Unknown packaging: container-plugin" across dozens of modules, before any
# compilation is attempted.
#
# Order matters and is theirs:
#   1. container-dependency-versions  (where <jackson2.version> is declared)
#   2. parent                          (dependencyManagement for everything)
#   3. root pom, non-recursively
#   4. maven-plugins/                  (bundle-plugin, config-class-plugin, abi-check-plugin)
#
# Everything here is jackson-version-independent: these are build tooling and POMs, so they
# are installed ONCE and shared by all states. Only the document module is rebuilt per state.
set -u
export JAVA_HOME="/c/Program Files/Java/jdk-17"
M2=../../.bbc_m2
cd "$(dirname "$0")/repo" || exit 1

# vespa's build reads dist/vtag.map; their bootstrap generates it before anything else.
if [ ! -f dist/vtag.map ]; then
  echo "[bootstrap] generating dist/vtag.map..."
  ./dist/getversionmap.sh . > dist/vtag.map || { echo "[bootstrap] vtag.map FAILED"; exit 1; }
fi

run() {
  echo "[bootstrap] $1"
  shift
  mvn -B -q --no-snapshot-updates -DskipTests install -Dmaven.repo.local=$M2 "$@" \
      >> ../bootstrap.log 2>&1
  if [ $? -ne 0 ]; then echo "[bootstrap] FAILED -- see bootstrap.log"; tail -15 ../bootstrap.log; exit 1; fi
}

: > ../bootstrap.log
run "container-dependency-versions"  -f container-dependency-versions/pom.xml
run "parent"                         -f parent/pom.xml
run "root pom (non-recursive)"       -N
run "maven-plugins"                  -f maven-plugins/pom.xml
echo "[bootstrap] done."
