"""Offline checks for traversal/find_crossing.declared_version.

This function decides what version a build file declares at a commit, which is what the
boundary bisect reads. A wrong answer here does not fail loudly -- it produces a confident
crossing verdict for the wrong commit, or hides a crossing entirely. All three cases below
were real defects found on 2026-08-13 by diffing it against resolve_version.declared_version
(a different function with the same name, which answers the full-resolve question).

Every case reads a version OLDER than the truth, which in a bisect is the dangerous
direction: a pre-boundary version read at a post-boundary commit places the crossing later
than it happened, or misses it.

No network, no token.
"""
import pathlib
import sys

_NS = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_NS / "traversal"))
sys.path.insert(0, str(_NS))

import find_crossing as FC

G, A, KW = "com.fasterxml.jackson.core", "jackson-core", "jackson"

CASES = [
    ("plain property",
     """<project><properties><jackson.version>2.14.2</jackson.version></properties>
     <dependencies><dependency><groupId>com.fasterxml.jackson.core</groupId>
     <artifactId>jackson-core</artifactId><version>${jackson.version}</version>
     </dependency></dependencies></project>""",
     "2.14.2",
     "the ordinary case: property declared and referenced"),

    ("commented-out property above the live one",
     """<project><properties>
     <!-- <jackson.version>2.9.0</jackson.version> -->
     <jackson.version>2.15.0</jackson.version></properties></project>""",
     "2.15.0",
     "REGRESSION: read the dead 2.9.0 as live, because the regex ran before comments were "
     "stripped. Common shape -- someone pins a version, comments it out, puts the live one "
     "below."),

    ("live property has a SHORTER name than a legacy one",
     """<project><properties>
     <jackson.version>2.15.0</jackson.version>
     <jackson-bom-legacy.version>2.9.0</jackson-bom-legacy.version></properties>
     <dependencies><dependency><groupId>com.fasterxml.jackson.core</groupId>
     <artifactId>jackson-core</artifactId><version>${jackson.version}</version>
     </dependency></dependencies></project>""",
     "2.15.0",
     "REGRESSION: the 'prefer the most specific property' heuristic ranked by NAME LENGTH, "
     "so a dead longer-named property beat the live one. Now the property the dependency "
     "actually references wins."),

    ("repackaged fork reusing the artifactId",
     """<project><dependencies><dependency><groupId>org.someone.repack</groupId>
     <artifactId>jackson-core</artifactId><version>1.0.0</version></dependency>
     </dependencies></project>""",
     None,
     "REGRESSION: matched artifactId anywhere in the file, attributing a fork's version to "
     "the real library. Now the groupId is checked inside the <dependency> block -- and the "
     "loose fallback is disabled once --group is given, or it would re-admit the reject."),

    ("dependencyManagement only",
     """<project><dependencyManagement><dependencies><dependency>
     <groupId>com.fasterxml.jackson.core</groupId><artifactId>jackson-core</artifactId>
     <version>2.16.1</version></dependency></dependencies></dependencyManagement></project>""",
     "2.16.1",
     "must still be found when the version is only under dependencyManagement"),

    ("direct version, correct groupId",
     """<project><dependencies><dependency><groupId>com.fasterxml.jackson.core</groupId>
     <artifactId>jackson-core</artifactId><version>2.15.0</version></dependency>
     </dependencies></project>""",
     "2.15.0",
     "the groupId check must not reject a legitimate direct declaration"),

    ("version is an unresolvable ${...} reference",
     """<project><dependencies><dependency><groupId>com.fasterxml.jackson.core</groupId>
     <artifactId>jackson-core</artifactId><version>${some.bom.version}</version>
     </dependency></dependencies></project>""",
     None,
     "None is CORRECT here and must stay None: it is what surfaces as `undecided`, which "
     "the census must never count as a negative."),
]


def main():
    failures = 0
    for name, pom, want, why in CASES:
        got = FC.declared_version(pom, "auto", A, keyword=KW, group=G)
        ok = got == want
        failures += not ok
        print(f"[{'ok ' if ok else 'FAIL'}] {name}\n        want={want!r} got={got!r}")
        if not ok:
            print(f"        {why}")

    # strip_comments is used by anything that reads a POM by regex; check it directly too.
    assert FC.strip_comments("<a/><!-- <b>x</b> --><c/>") == "<a/><c/>"
    assert FC.strip_comments(None) == ""

    print(f"\n{len(CASES) - failures}/{len(CASES)} passed")
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
