#!/bin/bash
# One-time setup for the trino differential.
#
# trino CANNOT BE CHECKED OUT IN FULL ON WINDOWS. plugin/trino-delta-lake ships Databricks
# test fixtures under Hive-partition directory names that exceed MAX_PATH, and a plain
# `git checkout` dies partway with "Filename too long" / "cannot create directory", leaving
# no root pom.xml. Two settings plus a sparse cone fix it:
#
#   core.longpaths=true    let git use the \\?\ long-path API
#   core.protectNTFS=false the fixture names contain '%3A' and ':' sequences
#   sparse-checkout        skip the offending fixture trees
#
# SPARSE MUST BE --no-cone (EXCLUDE), NOT A CONE (INCLUDE). The obvious move -- a cone of
# just the four paths the differential builds -- makes Maven unusable: trino's root pom
# lists 100+ <module>s, and Maven refuses to process the POM at all if any listed module
# directory is missing ("Child module .../client/trino-cli of .../pom.xml does not exist"),
# even when building with -pl. So every module directory has to exist. The exclusion form
# materialises the whole tree EXCEPT the two test-resource trees whose names are too long,
# which is what both git and Maven can live with. ~334 MB.
#
# Run once after cloning with:  git clone --filter=blob:none --no-checkout <url> repo
# The first checkout takes several minutes; that is the sparse rules being applied to a
# repository this size, not a hang.
set -u
cd "$(dirname "$0")/repo" || exit 1

git config core.longpaths true
git config core.protectNTFS false
git sparse-checkout set --no-cone '/*' \
    '!/plugin/trino-delta-lake/src/test/resources/**' \
    '!/plugin/trino-hive/src/test/resources/**'
echo "[bootstrap] sparse rules set:"
git sparse-checkout list
