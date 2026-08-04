#!/usr/bin/env python3
"""
test_gates.py — regression fixtures for the pipeline's decision gates.

Why this exists: twice in one session a gate returned confident, wrong numbers,
and both times it was caught only by chance, because someone happened to check a
case whose answer was already known.

  1. verify_traversal had NEVER confirmed a candidate — _gh() called .get() on
     GitHub's list responses and find_boundary_bump swallowed the AttributeError
     as "no commits". It reported a plausible-looking negative for every input.
  2. screen_compile_break v1 compared constructor ARITY only, so it passed
     snakeyaml's Constructor(Class) -> Constructor(LoaderOptions) narrowing as
     "behavioural" — same arity, incompatible type.

Neither failure was visible from the output: a gate that says "no" to everything
looks exactly like a gate reporting a genuine negative result. The only defence
is fixtures with independently known answers, covering BOTH polarities — a gate
stuck on "no" passes an all-negative suite.

Every fixture below was established by hand and cross-checked:
  - logging-chainsaw: BUMP recorded the bump commit 19e20b0d itself
  - TVRenamer: gradle, so it also proves non-Maven traversal works
  - the Axon apps: independently confirmed by the 2026-07-20 in-repo audit
  - beanszoo / Dashboard-V-2: verified by compiling their real parent usage
    against snakeyaml jars (javac says "no suitable constructor" / "incompatible
    types: Class<Application> cannot be converted to LoaderOptions")

Run:  python test_gates.py            (needs GH_TOKEN + a local ~/.m2 with the jars)
      python test_gates.py --gate traversal
"""

import argparse
import sys

import bbc_e2e as B
import screen_compile_break as S

XS = "xstream-1.4.17-to-1.4.19-forbiddenclass"
SY = "snakeyaml-1.x-to-2.0-safeconstructor"

# (label, break_id, repo, sha, expect_traversal_confirmed)
TRAVERSAL_FIXTURES = [
    ("chainsaw BUNDLED (BUMP-recorded bump 19e20b0d)", XS,
     "apache/logging-chainsaw", "7ec771e2fbc0", True),
    ("TVRenamer POST_MERGE_FIX (gradle build file)", XS,
     "The-Ant-Forge/TVRenamer", "b236f68e", True),
    # Transitive crossing: the client bumped axon-spring-boot-starter 4.5 -> 4.5.14,
    # which moved xstream 1.4.16 -> 1.4.19 across the 1.4.18 boundary. Recorded as a
    # NON-traversal until 2026-08-04 — declared-version traversal cannot see it, and
    # the failure message ("transitive dependency, or born on the new version")
    # conflated a real crossing with a non-case. This is the known-POSITIVE for the
    # transitive resolver; if it ever reverts to False the POM walk has regressed.
    ("Axon artshishkin — TRANSITIVE crossing via axon-spring-boot-starter", XS,
     "artshishkin/art-kargopolov-cqrs-saga-axon-microservices", "b76d747f8d27", True),
    # Same shape, but its chain is BOM/parent-managed and does not resolve from
    # Maven Central alone -> reported `unresolved`. traversal_confirmed is False,
    # but the verdict is UNDECIDED, not a negative: needs `mvn dependency:tree`.
    ("Axon amirsnw — unresolved chain (undecided, not a negative)", XS,
     "amirsnw/chainrtrade-axon-CQRS-DDD", "d408d4cac768", False),
    # Second TRANSITIVE positive, and a caution about trusting written records.
    # order-service/pom.xml (the module holding the adaptation) went
    # axon-spring-boot-starter 4.0.3 -> 4.6.1, moving xstream 1.4.10 -> 1.4.19.
    # The case file asserted crossed_boundary: false, "4.6.1 set in the first commit
    # and never bumped" -- true of the ROOT pom, false of the module pom. The resolver
    # was right and the hand audit was wrong; always resolve the module pom nearest
    # the adaptation.
    ("Axon einsteinarbert — TRANSITIVE crossing in the MODULE pom", XS,
     "einsteinarbert/axon-saga-example", "dddd794b5d0f", True),
    # Clean known-NEGATIVE: born at/above the boundary, resolvable on both sides.
    # Needed because every other negative here is `unresolved`, and a resolver stuck
    # on "cannot resolve" would pass an all-unresolved suite.
    ("poi jadhavspeaks — born at/above 5.0.0, no crossing", "poi-4.1.2-to-5.x",
     "jadhavspeaks/file_compare_diffrent_ext", "156a9624", False),
]

# (label, break_id, repo, sha, from_v, to_v, expected verdict)
COMPILE_FIXTURES = [
    ("beanszoo: extends Constructor, implicit super() removed at 2.0", SY,
     "snork-alt/beanszoo", "55d17ce2e1a20fa6367a0730d592570f465a9bf3",
     "1.33", "2.2", "compile_break"),
    ("Dashboard-V-2: Constructor(Class) narrowed to Constructor(LoaderOptions)", SY,
     "adityajoy-1902/Dashboard-V-2", "8c39d993d6f4062b677ca25dc527ba0f9fe64347",
     "1.33", "2.2", "compile_break"),
    ("quarkus: new Yaml() idiom compiles across the boundary", SY,
     "quarkusio/quarkus", "06a8c629", "1.33", "2.2", "behavioural"),
]


def run_traversal(token):
    print("\n== gate: verify_traversal ==")
    fails = 0
    for label, bid, repo, sha, expect in TRAVERSAL_FIXTURES:
        brk = B.get_break(bid)
        t = B.verify_traversal(repo, sha, brk, token)
        got = bool(t.get("traversal_confirmed"))
        ok = got == expect
        fails += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}\n"
              f"         expected={expect} got={got}  {t.get('reason','')[:76]}")
    return fails


def run_compile(token):
    print("\n== gate: screen_compile_break ==")
    fails = 0
    for label, bid, repo, sha, fv, tv, expect in COMPILE_FIXTURES:
        brk = B.get_break(bid)
        lib = brk["library"]
        fj = S.resolve_jar(lib["group_id"], lib["artifact_id"], fv)
        tj = S.resolve_jar(lib["group_id"], lib["artifact_id"], tv)
        if not tj:
            print(f"  [SKIP] {label} — no {tv} jar available")
            continue
        res = S.screen(repo, sha, brk, token, fj, tj)
        got = res["verdict"]
        ok = got == expect
        fails += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}\n"
              f"         expected={expect} got={got}  {res.get('reason','')[:76]}")
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", choices=["traversal", "compile", "all"], default="all")
    args = ap.parse_args()
    token = B._token()
    fails = 0
    if args.gate in ("traversal", "all"):
        fails += run_traversal(token)
    if args.gate in ("compile", "all"):
        fails += run_compile(token)
    print(f"\n{'ALL FIXTURES PASS' if not fails else str(fails) + ' FIXTURE(S) FAILED'}")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
