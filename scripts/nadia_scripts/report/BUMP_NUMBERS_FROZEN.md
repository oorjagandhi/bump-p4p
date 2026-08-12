# BUMP corpus numbers — frozen record

The BUMP benchmark data (`data/`, `reproductionLogs/`) and the script that
re-derived these numbers (`report/verify_numbers.py`) were deleted on 2026-08-12:
the project's contribution no longer rests on the BUMP breakdown, and the corpus
cost ~26 MB to carry.

This is the **last output of `verify_numbers.py` against the real data**, captured
immediately before deletion. It is a record, not a measurement — nothing here can be
recomputed in this repository any more. To re-derive, clone upstream
`chains-project/bump` and restore the script from git history
(`git show e4b0b5ccc:scripts/nadia_scripts/report/verify_numbers.py`).

```

=== Level 0/1: data/benchmark/ (571 files) ===
       235  COMPILATION_FAILURE
       188  TEST_FAILURE
       121  ENFORCER_FAILURE
        14  DEPENDENCY_LOCK_FAILURE
         8  WERROR_FAILURE
         5  DEPENDENCY_RESOLUTION_FAILURE
       sum  = 571
  [OK ] total benchmarks: got 571, expected 571
  [OK ] category counts sum to total: got 571, expected 571
  [OK ] COMPILATION_FAILURE: got 235, expected 235
  [OK ] TEST_FAILURE: got 188, expected 188
  [OK ] ENFORCER_FAILURE: got 121, expected 121
  [OK ] DEPENDENCY_LOCK_FAILURE: got 14, expected 14
  [OK ] WERROR_FAILURE: got 8, expected 8
  [OK ] DEPENDENCY_RESOLUTION_FAILURE: got 5, expected 5

=== Level 2/3: 188 TEST_FAILURE benchmarks, by dominant exception ===
        69   36.7%  missing_class
        34   18.1%  syntactic
        30   16.0%  test_assertion
        21   11.2%  binding_init
        14    7.4%  semantic
        11    5.9%  jvm_version
         6    3.2%  semantic?
         3    1.6%  other
      (reproduction logs missing: 0)
  [OK ] TEST_FAILURE files classified: got 188, expected 188
  [OK ] kind counts sum to 188: got 188, expected 188
  [OK ] assertion failures: got 30, expected 30
  [OK ] errors (= 188 - assertion): got 158, expected 158
  [OK ] missing_class: got 69, expected 69
  [OK ] syntactic: got 34, expected 34
  [OK ] binding_init: got 21, expected 21
  [OK ] jvm_version: got 11, expected 11
  [OK ] semantic: got 14, expected 14
  [OK ] semantic?: got 6, expected 6
  [OK ] other: got 3, expected 3
  [OK ] behavioural (semantic + semantic?): got 20, expected 20

=== benchmark_test_failures_merged/ (17 files) ===
         9  syntactic
         8  missing_class
  [OK ] merged dir count (the '17'): got 17, expected 17
  [OK ] merged assertion failures: got 0, expected 0
  [OK ] merged behavioural: got 0, expected 0

=== roll-ups ===
      errors / assertion split : 158 (84%) / 30 (16%)
      behavioural (~11%)       : 20 (10.6% of 188)
      syntactic-ish (~72%)     : 135 (71.8% incl. binding_init)

ALL CHECKS PASSED
```
