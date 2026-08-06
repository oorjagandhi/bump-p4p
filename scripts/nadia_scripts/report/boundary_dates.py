#!/usr/bin/env python
"""
boundary_dates.py — resolve each break's boundary version to its RELEASE DATE.

WHY
---
org-json taught this the expensive way. Its break is real, 31 real production
adaptations were mined for it, and it can NEVER yield a witnessed crossing — because
the boundary is 20131018 (October 2013) and every mineable client was born after it.
A break is only mineable for crossings if the boundary is recent enough that clients
still cross it. That is a property of the boundary's DATE, and it is knowable before
spending an eight-hour mine.

This writes output/boundary_dates.json, which report/census.py reads to show, per
break, when the boundary landed and how much of the corpus sits below it.

Maven Central's search API returns a release timestamp per exact GAV. Boundaries
recorded as prefixes ("2.0.x") resolve to the EARLIEST release matching that prefix,
since that is the first version at which the new behaviour is present.
"""

import json
import sys
import time
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent
NADIA = HERE.parent
CATALOG = NADIA / "specs" / "bump_breaks_catalog.json"
OUT = NADIA / "output" / "boundary_dates.json"

SEARCH = "https://search.maven.org/solrsearch/select"


def parse_ver(s):
    import re
    nums = re.findall(r"\d+", s or "")
    return tuple(int(n) for n in nums[:4]) if nums else None


def _get(params, tries=3):
    for i in range(tries):
        try:
            r = requests.get(SEARCH, params=params, timeout=60)
            return r.json().get("response", {}).get("docs", [])
        except Exception as e:
            if i == tries - 1:
                print(f"  [warn] lookup failed after {tries}: {type(e).__name__}",
                      file=sys.stderr)
                return None
            time.sleep(3 * (i + 1))
    return None


def fetch_exact(group, artifact, version):
    """Timestamp for one exact GAV, or None if that version does not exist.

    This is the ONLY reliable path. Listing an artifact's versions caps at the most
    recent N and silently drops older ones, so a prefix/nearest match over that window
    can resolve to a version years off -- the first version of this script resolved
    logback 1.4.0 to 1.5.0 and org-json 20131018 to 20160810 that way.
    """
    docs = _get({"q": f'g:"{group}" AND a:"{artifact}" AND v:"{version}"',
                 "core": "gav", "rows": 1, "wt": "json"})
    if not docs:
        return None
    return docs[0].get("timestamp")


def fetch_versions(group, artifact):
    """[(version, epoch_ms)] within the API's most-recent window. APPROXIMATE."""
    docs = _get({"q": f'g:"{group}" AND a:"{artifact}"',
                 "core": "gav", "rows": 400, "wt": "json"})
    if docs is None:
        return None
    return [(d.get("v"), d.get("timestamp")) for d in docs if d.get("v")]


def resolve(group, artifact, boundary):
    """(version, epoch_ms, exact?). Exact GAV lookup first; prefix search only if the
    declared boundary is not itself a released version (e.g. h2's '2.0.x')."""
    ts = fetch_exact(group, artifact, boundary)
    if ts:
        return boundary, ts, True

    versions = fetch_versions(group, artifact) or []
    # Progressively shorter stems. A declared boundary is often a version that was never
    # released -- h2's "2.0.x" by notation, and jsoup's "1.15.0" by accident (jsoup went
    # 1.14.3 -> 1.15.1, so there is no 1.15.0). Matching "1.15.0" exactly finds nothing;
    # falling back to the "1.15" series finds 1.15.1, the first release carrying the new
    # behaviour, which is what the boundary actually means.
    stem = boundary.rstrip(".x").rstrip(".")
    parts = stem.split(".")
    for depth in range(len(parts), 0, -1):
        probe = ".".join(parts[:depth])
        matches = [(v, t) for v, t in versions
                   if v == probe or v.startswith(probe + ".")]
        if matches:
            matches.sort(key=lambda t: (t[1] or 0))
            return matches[0][0], matches[0][1], False
    return None, None, False


def main():
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    out = {}
    for brk in catalog["breaks"]:
        bid = brk["break_id"]
        lib = brk.get("library") or {}
        g, a = lib.get("group_id"), lib.get("artifact_id")
        boundary = (brk.get("verify") or {}).get("break_boundary")
        if not (g and a and boundary):
            print(f"[skip] {bid}: no group/artifact/boundary")
            continue
        v, ts, exact = resolve(g, a, boundary)
        date = (time.strftime("%Y-%m", time.gmtime(ts / 1000)) if ts else None)
        out[bid] = {"boundary_declared": boundary, "boundary_resolved": v,
                    "release_date": date, "epoch_ms": ts, "exact": exact}
        tag = "" if exact else ("  ~approx (declared boundary is not a released "
                                "version)" if v else "  UNRESOLVED")
        print(f"[ok] {bid:45} {boundary:>10} -> {str(v):>10}  {date}{tag}")
        time.sleep(0.4)  # be polite to Central

    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\nsaved -> {OUT}")


if __name__ == "__main__":
    main()
