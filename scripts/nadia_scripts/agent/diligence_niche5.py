#!/usr/bin/env python3
"""Due-diligence mine of the 5 untapped BUMP semantic libraries (niche).
Reuses bbc_e2e.mine_commits + classify_commit. Reports verifiable Maven production
adaptations per library. Expectation: ~0 (documents that BUMP's semantic pool is exhausted)."""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bbc_e2e as B

# --- make GitHub calls survive the SECONDARY rate limit ----------------------
# We've run many mines this session; GH throttles bursts. Wrap _gh so every call
# paces itself and, on a rate-limit response, sleeps (escalating) and retries.
_orig_gh = B._gh
_PACE = 3.0            # seconds between calls (keeps us under the secondary limit)
_BACKOFFS = [20, 40, 60, 90, 120]


def _gh_resilient(url, token, **params):
    for attempt in range(len(_BACKOFFS) + 1):
        res = _orig_gh(url, token, **params)
        msg = res.get("message", "") if isinstance(res, dict) else ""
        if isinstance(res, dict) and "rate limit" in msg.lower():
            if attempt < len(_BACKOFFS):
                wait = _BACKOFFS[attempt]
                print(f"[backoff] rate-limited; sleeping {wait}s (attempt {attempt+1})", flush=True)
                time.sleep(wait)
                continue
        time.sleep(_PACE)
        return res
    return res


B._gh = _gh_resilient
# -----------------------------------------------------------------------------

LIBS = [
    dict(break_id="dropwizard-sentry-2.0.22-to-2.0.28",
         library=dict(group_id="org.dhatim", artifact_id="dropwizard-sentry", to_version="2.0.28"),
         mining=dict(library_keyword="dropwizard-sentry",
                     commit_search_terms=["ConfigurationParsingException", "dropwizard-sentry"])),
    dict(break_id="plexus-io-3.2.0-to-3.3.0",
         library=dict(group_id="org.codehaus.plexus", artifact_id="plexus-io", to_version="3.3.0"),
         mining=dict(library_keyword="plexus-io",
                     commit_search_terms=["ArchiverException", "plexus-io 3.3"])),
    dict(break_id="graalvm-js-22.0-to-22.1",
         library=dict(group_id="org.graalvm.js", artifact_id="js-scriptengine", to_version="22.1.0"),
         mining=dict(library_keyword="graalvm",
                     commit_search_terms=["js-scriptengine", "GraalVM 22.1", "polyglot"])),
    dict(break_id="hibernate-validator-6.2-to-8.0",
         library=dict(group_id="org.hibernate.validator", artifact_id="hibernate-validator", to_version="8.0.1"),
         mining=dict(library_keyword="hibernate-validator",
                     commit_search_terms=["NoProviderFoundException", "hibernate-validator 8", "jakarta validation"])),
    dict(break_id="quarkus-google-cloud-grpc-1.4-to-2.2",
         library=dict(group_id="io.quarkiverse.googlecloudservices",
                      artifact_id="quarkus-google-cloud-common-grpc", to_version="2.2.0"),
         mining=dict(library_keyword="quarkus-google-cloud",
                     commit_search_terms=["quarkus-google-cloud", "quarkus google cloud grpc"])),
]

CAP = 20  # classify at most this many per lib (bounds API calls; due-diligence, not exhaustive)


def main():
    token = B._token()
    summary = []
    for brk in LIBS:
        bid = brk["break_id"]
        print(f"\n===== {bid} =====")
        rows = B.mine_commits(brk, token)
        ver = []
        for r in rows[:CAP]:
            c = B.classify_commit(r["repo"], r["sha"], brk, token)
            if c.get("error"):
                continue
            if (c["verifiable"] and c["is_production_adaptation"]
                    and not c["library_source"] and not c["test_only"]):
                ver.append(c)
                print(f"  * VERIFIABLE {c['repo']}@{c['sha'][:10]} @{c['version_at_commit']} {c['message'][:50]}")
        distinct = {c["sha"][:10] for c in ver}
        print(f"  -> {len(rows)} commits, {len(ver)} verifiable maven-prod, {len(distinct)} distinct")
        summary.append((bid, len(rows), len(ver), len(distinct)))

    print("\n===== SUMMARY (niche-5 due diligence) =====")
    print(f"{'break_id':40} {'commits':7} {'verif':5} {'distinct'}")
    for bid, nc, nv, nd in summary:
        print(f"{bid:40} {nc:7} {nv:5} {nd}")
    print(f"\nTOTAL verifiable across all 5: {sum(s[2] for s in summary)}")


if __name__ == "__main__":
    main()
