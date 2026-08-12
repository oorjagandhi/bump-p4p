#!/usr/bin/env python3
"""
Independent verification of every number quoted in the mid-year report's BUMP breakdown.
Recomputes from raw data (no cached outputs) and ASSERTS the totals are internally
consistent, so a green run is proof the tree adds up.

  Level 0/1 : data/benchmark/*.json  -> failureCategory field  (the ground-truth label)
  Level 2/3 : classify each TEST_FAILURE by the dominant exception in its reproduction log
              (reuses bump_semantic_sweep.classify -- the same function used for the report)
"""
import glob, json, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
NADIA = os.path.dirname(HERE)                       # scripts/nadia_scripts
ROOT = os.path.dirname(os.path.dirname(NADIA))      # repo root (C:\bump-p4p)
sys.path.insert(0, NADIA)
sys.path.insert(0, os.path.join(NADIA, "discover"))  # scripts moved into role folders, 2026-08
from bump_semantic_sweep import classify, read_log  # same classifier the report used

def jload(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)

ok = True
def check(label, got, expect):
    global ok
    flag = "OK " if got == expect else "XX "
    if got != expect: ok = False
    print(f"  [{flag}] {label}: got {got}, expected {expect}")

# ── Level 0/1: failureCategory over the full benchmark set ───────────────────────
bench = sorted(glob.glob(os.path.join(ROOT, "data", "benchmark", "*.json")))
cats = collections.Counter(jload(f).get("failureCategory", "?") for f in bench)
print(f"\n=== Level 0/1: data/benchmark/ ({len(bench)} files) ===")
for k, v in cats.most_common():
    print(f"      {v:4}  {k}")
print(f"      {'sum':>4}  = {sum(cats.values())}")
check("total benchmarks", len(bench), 571)
check("category counts sum to total", sum(cats.values()), len(bench))
check("COMPILATION_FAILURE", cats["COMPILATION_FAILURE"], 235)
check("TEST_FAILURE", cats["TEST_FAILURE"], 188)
check("ENFORCER_FAILURE", cats["ENFORCER_FAILURE"], 121)
check("DEPENDENCY_LOCK_FAILURE", cats["DEPENDENCY_LOCK_FAILURE"], 14)
check("WERROR_FAILURE", cats["WERROR_FAILURE"], 8)
check("DEPENDENCY_RESOLUTION_FAILURE", cats["DEPENDENCY_RESOLUTION_FAILURE"], 5)

# ── Level 2/3: classify the 188 TEST_FAILURE benchmarks by dominant exception ────
# Use the SAME set the report's 188-column came from: the TEST_FAILURE-labelled
# entries in data/benchmark/ (not the separate _merged dir).
tf = [f for f in bench if jload(f).get("failureCategory") == "TEST_FAILURE"]
kinds = collections.Counter()
missing_logs = 0
for f in tf:
    sha = jload(f).get("breakingCommit")
    log = read_log(sha) if sha else None
    if log is None:
        missing_logs += 1
    k, _ = classify(log)
    kinds[k] += 1

print(f"\n=== Level 2/3: {len(tf)} TEST_FAILURE benchmarks, by dominant exception ===")
for k, v in kinds.most_common():
    print(f"      {v:4}  {v/len(tf)*100:5.1f}%  {k}")
print(f"      (reproduction logs missing: {missing_logs})")

assertion = kinds.get("test_assertion", 0)
errors = len(tf) - assertion
behavioural = kinds.get("semantic", 0) + kinds.get("semantic?", 0)
syntactic_ish = kinds.get("missing_class", 0) + kinds.get("syntactic", 0) + kinds.get("jvm_version", 0)

check("TEST_FAILURE files classified", len(tf), 188)
check("kind counts sum to 188", sum(kinds.values()), 188)
check("assertion failures", assertion, 30)
check("errors (= 188 - assertion)", errors, 158)
check("missing_class", kinds.get("missing_class", 0), 69)
check("syntactic", kinds.get("syntactic", 0), 34)
check("binding_init", kinds.get("binding_init", 0), 21)
check("jvm_version", kinds.get("jvm_version", 0), 11)
check("semantic", kinds.get("semantic", 0), 14)
check("semantic?", kinds.get("semantic?", 0), 6)
check("other", kinds.get("other", 0), 3)
check("behavioural (semantic + semantic?)", behavioural, 20)

# ── The 'merged' directory (the real source of the '17') ─────────────────────────
merged = sorted(glob.glob(os.path.join(ROOT, "data", "benchmark_test_failures_merged", "*.json")))
mkinds = collections.Counter()
for f in merged:
    sha = jload(f).get("breakingCommit")
    k, _ = classify(read_log(sha) if sha else None)
    mkinds[k] += 1
print(f"\n=== benchmark_test_failures_merged/ ({len(merged)} files) ===")
for k, v in mkinds.most_common():
    print(f"      {v:4}  {k}")
check("merged dir count (the '17')", len(merged), 17)
check("merged assertion failures", mkinds.get("test_assertion", 0), 0)
check("merged behavioural", mkinds.get("semantic", 0) + mkinds.get("semantic?", 0), 0)

# ── roll-ups quoted in the report ────────────────────────────────────────────────
print("\n=== roll-ups ===")
print(f"      errors / assertion split : {errors} ({errors/188*100:.0f}%) / {assertion} ({assertion/188*100:.0f}%)")
print(f"      behavioural (~11%)       : {behavioural} ({behavioural/188*100:.1f}% of 188)")
print(f"      syntactic-ish (~72%)     : {syntactic_ish + kinds.get('binding_init',0)} "
      f"({(syntactic_ish + kinds.get('binding_init',0))/188*100:.1f}% incl. binding_init)")

print("\n" + ("ALL CHECKS PASSED" if ok else "SOME CHECKS FAILED"))
sys.exit(0 if ok else 1)
