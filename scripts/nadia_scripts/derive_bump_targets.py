"""
derive_bump_targets.py
──────────────────────
Build a mining target list for 01_mine_candidates_bump.py straight from BUMP's
CONFIRMED behavioural breaks (data/benchmark_test_failures/*.json — the
failureCategory == TEST_FAILURE subset).

Rationale: the hand-coded BUMP_TARGETS in 01 covers only 7 libraries, far too
narrow to reach a hundreds-scale dataset. BUMP already confirmed 188 behavioural
breaking updates spanning ~49 libraries; each records the exact
(groupId, artifactId, previousVersion → newVersion) that broke tests. We turn
those into per-library MATCH RULES so the miner finds REAL client projects that
performed the same behaviourally-breaking transition and ADAPTED their code (the
adaptation is the research artifact; BUMP already supplies the "this transition
is behavioural" evidence, so no local rebuild is needed).

Match rule: a mined bump (old → new) matches a library if it crosses at least
one confirmed-breaking version BOUNDARY for that library. The boundary per BUMP
transition is derived from its versionUpdateType:
    major  →  (new_major, 0, 0)          e.g. slf4j 1.x → 2.x  ⇒  (2,0,0)
    minor  →  (new_major, new_minor, 0)  e.g. jackson 2.4 → 2.9 ⇒ (2,9,0)
    other/patch → the exact new version  e.g. httpclient → 4.5.13 ⇒ (4,5,13)
A mined bump (o, n) matches when  o < V <= n  for some boundary V — i.e. it
started below a confirmed-breaking version and reached or passed it.

Excluded: build/test-infrastructure artifacts — adaptations to those are
build-config tweaks, not client code adapting to a library's behaviour change.

Output: output/bump_targets_from_test_failures.json  (consumed by 01 via
        --target-set bump-tf).  Also prints a human-readable summary.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

TF_DIR = Path(__file__).resolve().parents[2] / "data" / "benchmark_test_failures"
OUT = Path(__file__).resolve().parent / "output" / "bump_targets_from_test_failures.json"

# Build/test-infra artifacts to exclude (not client-code adaptations).
INFRA_ARTIFACTS = {
    "junit-platform-surefire-provider", "plexus-utils", "plexus-io",
    "surefire-junit4", "surefire-junit47", "versions-maven-plugin",
}

# Java import-package prefix per groupId where it differs from the groupId
# itself (used for the library-reference signal in 01). Default = groupId.
PACKAGE_MAP = {
    "org.apache.httpcomponents": ["org.apache.http", "org.apache.hc"],
    "org.jenkins-ci.plugins": ["org.kohsuke.github"],
    "org.yaml": ["org.yaml.snakeyaml"],
    "commons-io": ["org.apache.commons.io"],
    "com.squareup.okhttp3": ["okhttp3"],
    "com.sun.xml.bind": ["javax.xml.bind", "com.sun.xml.bind"],
    "org.hibernate.validator": ["org.hibernate.validator", "javax.validation"],
    "net.minidev": ["net.minidev.json"],
    "org.jetbrains.kotlin": ["kotlin"],
}

# Keyword that identifies a <…version> PROPERTY bump for this library
# (e.g. <jackson.version>). Default = artifactId's first '-' token.
KEYWORD_OVERRIDE = {
    "slf4j-api": "slf4j", "jackson-databind": "jackson", "jackson-core": "jackson",
    "logback-classic": "logback", "log4j-core": "log4j", "log4j-api": "log4j",
    "mockito-core": "mockito", "poi-scratchpad": "poi", "poi-ooxml": "poi",
    "snakeyaml": "snakeyaml", "json-smart": "json-smart",
}


def pad3(version: str):
    """(major, minor, patch) ints from a Maven version, or None."""
    if not version:
        return None
    head = re.split(r"[-+]", version.strip(), maxsplit=1)[0]
    nums = []
    for part in head.split("."):
        m = re.match(r"\d+", part)
        if not m:
            break
        nums.append(int(m.group()))
    if not nums:
        return None
    return tuple((nums + [0, 0, 0])[:3])


def boundary(old, new, vtype):
    """Confirmed-breaking version boundary for one transition, or None."""
    if not old or not new or new <= old:
        return None
    if vtype == "major" and new[0] != old[0]:
        return (new[0], 0, 0)
    if vtype == "minor" and new[0] == old[0] and new[1] != old[1]:
        return (new[0], new[1], 0)
    return new  # other/patch: exact new version


def keyword_for(artifact_id):
    if artifact_id in KEYWORD_OVERRIDE:
        return KEYWORD_OVERRIDE[artifact_id]
    return artifact_id.split("-")[0]


def main():
    if not TF_DIR.exists():
        sys.exit(f"not found: {TF_DIR}")

    by_artifact = defaultdict(list)
    for fn in sorted(TF_DIR.glob("*.json")):
        d = json.load(open(fn, encoding="utf-8"))
        u = d.get("updatedDependency", {})
        g = (u.get("dependencyGroupID") or "").strip()
        a = (u.get("dependencyArtifactID") or "").strip()
        if not g or not a or a in INFRA_ARTIFACTS:
            continue
        by_artifact[(g, a)].append({
            "old": pad3(u.get("previousVersion")), "new": pad3(u.get("newVersion")),
            "type": u.get("versionUpdateType", "other"),
            "prev": u.get("previousVersion"), "newv": u.get("newVersion"),
            "url": d.get("url"),
        })

    targets, dropped_no_boundary = [], []
    for (g, a), breaks in sorted(by_artifact.items(), key=lambda x: -len(x[1])):
        thresholds = sorted({b for b in
                             (boundary(x["old"], x["new"], x["type"]) for x in breaks)
                             if b is not None})
        if not thresholds:
            dropped_no_boundary.append(f"{g}:{a}")
            continue
        ranges = sorted({f'{x["prev"]}→{x["newv"]}' for x in breaks})
        targets.append({
            "name": f"{g}:{a}",
            "group_id": g,
            "artifact_id": a,
            "packages": PACKAGE_MAP.get(g, [g]),
            "keyword": keyword_for(a),
            "match_thresholds": [list(t) for t in thresholds],
            "tier": "bump-tf",
            "evidence_count": len(breaks),
            "search_range": "; ".join(ranges[:5]),
            "example_prs": [b["url"] for b in breaks[:3]],
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    json.dump(targets, open(OUT, "w", encoding="utf-8"), indent=2)

    total = sum(t["evidence_count"] for t in targets)
    print(f"target libraries written : {len(targets)}  (covering {total} behavioural breaks)")
    print(f"excluded build/test-infra : {len(INFRA_ARTIFACTS)}")
    if dropped_no_boundary:
        print(f"dropped (no usable boundary): {len(dropped_no_boundary)} -> {dropped_no_boundary}")
    print(f"written                   : {OUT}")
    print()
    print(f"{'#brk':>4}  {'thresholds':<22}  group:artifact")
    print("-" * 72)
    for t in targets:
        th = ",".join(".".join(map(str, v)) for v in t["match_thresholds"][:3])
        print(f"{t['evidence_count']:>4}  {th:<22}  {t['name']}")


if __name__ == "__main__":
    main()
