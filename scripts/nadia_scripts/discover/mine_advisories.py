#!/usr/bin/env python3
"""
Steps 1-3 of external break mining: discover NEW behavioural breaks from security
advisories instead of from BUMP.

Rationale: the two clean verified breaks (xstream default-deny, json-smart max-depth)
were both SECURITY hardenings -- the library got stricter and now THROWS on input it
used to accept. That is exactly the production-forcing behavioural-break shape. So we
mine the Maven security-advisory stream for that shape.

  1. Download  -> OSV Maven feed (all Maven advisories, OSV JSON).
  2. Filter    -> keep advisories whose fix is a runtime tightening (deserialization,
                  parsing/entity limits, input validation, injection) AND that have a
                  fixed version (= the break boundary). Drop pure API-removal noise.
  3. Extract   -> library (group:artifact), version boundary (fixed = where stricter
                  behaviour lands), CWE, GHSA id, one-line summary; rank by how closely
                  the fix matches the "throws on previously-accepted input" pattern.

Output: prints a ranked table; writes output/advisory_candidates.json (full) and
output/ADVISORY_SHORTLIST.md (human-readable). Feed a chosen row into the existing
pipeline by hand-writing its catalog entry, then `bbc_e2e.py run <break_id>`.
"""

# Scripts live one level down (discover/, mine/, traversal/, screen/, verify/) since
# the 2026-08 reorganisation, but they still import each other by module name and
# resolve data paths (output/, specs/, verified_cases/) against nadia_scripts/.
# This puts that root on sys.path so both keep working from anywhere.
import pathlib as _pl, sys as _sys
_NS_ROOT = _pl.Path(__file__).resolve().parent.parent
for _d in (_NS_ROOT, *(_NS_ROOT / _s for _s in
           ('discover', 'mine', 'traversal', 'screen', 'verify'))):
    if str(_d) not in _sys.path:
        _sys.path.insert(0, str(_d))

import json
import os
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRATCH = os.environ.get(
    "MINE_SCRATCH",
    os.path.join(HERE, "scratchpad", "advisories"),
)
OUT_DIR = os.path.join(HERE, "output")
OSV_MAVEN_URL = "https://osv-vulnerabilities.storage.googleapis.com/Maven/all.zip"

# CWE classes that correlate with "library added a guard and now throws on input it
# used to accept" -- i.e. a production-forcing behavioural break. Weight = how clean
# the match to the xstream/json-smart pattern is.
CWE_WEIGHTS = {
    "CWE-502": 10,   # deserialization of untrusted data  (xstream, jackson, snakeyaml)
    "CWE-770": 9,    # resource allocation w/o limits -> depth/size guard added (json-smart)
    "CWE-776": 9,    # XML entity expansion (billion laughs) -> parser now rejects
    "CWE-400": 8,    # uncontrolled resource consumption -> limit added, now throws
    "CWE-611": 7,    # XXE -> secure-processing default, now rejects external entities
    "CWE-827": 7,    # improper control of doc type definition (XXE-adjacent)
    "CWE-1321": 6,   # prototype pollution -> setter now rejected
    "CWE-20": 6,     # improper input validation -> stricter validation added
    "CWE-91": 5,     # XML injection
    "CWE-74": 5,     # injection (generic)
    "CWE-94": 5,     # code injection (e.g. commons-text interpolation)
    "CWE-1336": 5,   # template injection (commons-text StringSubstitutor)
}

# --- Step-4 refinement: adaptation-API tier ------------------------------------
# Rank by WHAT the client must do to re-permit the input it used to accept. Only the
# first two tiers leave a distinctive, mineable API a client changes in production.
DESERIALIZE_CWES = {"CWE-502"}                                  # -> allowlist/validator API (xstream, jackson, snakeyaml)
LIMIT_CWES = {"CWE-770", "CWE-776", "CWE-400", "CWE-611", "CWE-827"}  # -> depth/size/XXE config (json-smart)
WEAK_CWES = {"CWE-20", "CWE-1321", "CWE-91", "CWE-74", "CWE-94", "CWE-1336"}  # injection/validation: usually no re-permit API (Log4Shell)
TIER_BASE = {"deserialize": 12, "limit": 8, "validate": 3}
TIER_RANK = {"deserialize": 0, "limit": 1, "validate": 2}

# Phrases that the fix is a *default behaviour tightening* a client adapts around.
GOOD_PHRASES = [
    "by default", "no longer", "now throws", "now rejects", "disallow", "disabled by default",
    "allowlist", "whitelist", "safe", "depth", "nesting", "limit", "restrict", "forbidden",
    "deserial", "polymorphic", "entity expansion", "billion laughs", "untrusted",
]
BAD_PHRASES = ["denial of service only", "memory leak", "timing attack"]

# --- Step-4 refinement: drop end-applications (not libraries clients import) -----
# Conservative product denylist -- tokens that almost always mean a runnable app/server,
# never an embeddable library a client calls. (netty/jetty/tomcat are embeddable -> kept.)
APP_TOKENS = {
    "geoserver", "geowebcache", "openam", "opensso", "opendj", "powernukkit", "uima",
    "uimaj", "flume", "james", "nifi", "jenkins", "keycloak", "liferay", "xwiki",
    "dspace", "alfresco", "gitea", "sonarqube", "graylog", "thingsboard", "guacamole",
    "syncope", "ambari", "zeppelin", "ranger", "knox", "hazelcast-jet", "webgoat",
    "roller", "archiva", "dolphinscheduler", "inlong", "seatunnel", "streampark",
    "hertzbeat", "openmeetings", "cloudstack", "shopizer", "jspwiki", "dependency-track",
    "-webapp", "-standalone", "showcase", "-web-app",
}


def looks_like_app(package):
    p = package.lower()
    return any(tok in p for tok in APP_TOKENS)


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def download():
    os.makedirs(SCRATCH, exist_ok=True)
    zpath = os.path.join(SCRATCH, "maven_all.zip")
    if os.path.exists(zpath) and os.path.getsize(zpath) > 100_000:
        log(f"[1] using cached {zpath} ({os.path.getsize(zpath)//1024} KB)")
        return zpath
    log(f"[1] downloading {OSV_MAVEN_URL} ...")
    req = urllib.request.Request(OSV_MAVEN_URL, headers={"User-Agent": "bbc-miner/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(zpath, "wb") as f:
        f.write(r.read())
    log(f"[1] saved {zpath} ({os.path.getsize(zpath)//1024} KB)")
    return zpath


def iter_advisories(zpath):
    with zipfile.ZipFile(zpath) as z:
        for name in z.namelist():
            if not name.endswith(".json"):
                continue
            try:
                yield json.loads(z.read(name))
            except Exception:
                continue


def fixed_boundary(affected):
    """Return (introduced, fixed) for the first Maven range that has a fixed event."""
    for aff in affected:
        pkg = aff.get("package", {})
        if pkg.get("ecosystem") != "Maven":
            continue
        for rng in aff.get("ranges", []):
            intro, fixed = None, None
            for ev in rng.get("events", []):
                if "introduced" in ev and ev["introduced"] != "0":
                    intro = ev["introduced"]
                if "fixed" in ev:
                    fixed = ev["fixed"]
            if fixed:
                return pkg.get("name"), intro, fixed
    # no fixed version anywhere
    for aff in affected:
        pkg = aff.get("package", {})
        if pkg.get("ecosystem") == "Maven":
            return pkg.get("name"), None, None
    return None, None, None


def score(cwes, text):
    """Return (score, tier, matched_cwes). tier = adaptation-API class (None if no match)."""
    matched_cwes = [c for c in cwes if c in CWE_WEIGHTS]
    if any(c in DESERIALIZE_CWES for c in matched_cwes):
        tier = "deserialize"
    elif any(c in LIMIT_CWES for c in matched_cwes):
        tier = "limit"
    elif any(c in WEAK_CWES for c in matched_cwes):
        tier = "validate"
    else:
        return 0, None, matched_cwes
    s = TIER_BASE[tier]
    tl = text.lower()
    s += sum(1 for p in GOOD_PHRASES if p in tl)   # small nudge, not the dominant term
    s -= sum(3 for p in BAD_PHRASES if p in tl)
    return s, tier, matched_cwes


def main():
    zpath = download()
    log("[2] filtering advisories ...")
    rows = []
    total = 0
    for adv in iter_advisories(zpath):
        total += 1
        db = adv.get("database_specific", {}) or {}
        cwes = db.get("cwe_ids") or []
        summary = adv.get("summary", "") or ""
        details = adv.get("details", "") or ""
        text = summary + " " + details
        sc, tier, matched = score(cwes, text)
        if sc <= 0 or not tier:
            continue  # not a stricter-parsing/validation shape
        name, intro, fixed = fixed_boundary(adv.get("affected", []))
        if not name or not fixed:
            continue  # need a concrete break boundary
        rows.append({
            "package": name,
            "introduced": intro,
            "break_boundary_fixed": fixed,
            "cwes": matched,
            "tier": tier,
            "is_app": looks_like_app(name),
            "score": sc,
            "ghsa": adv.get("id"),
            "aliases": [a for a in adv.get("aliases", []) if a.startswith("CVE")][:3],
            "summary": summary.strip()[:140],
        })

    log(f"[2] scanned {total} Maven advisories -> {len(rows)} stricter-behaviour candidates")

    # keep the highest-scoring advisory per (package, fixed-boundary)
    best = {}
    for r in rows:
        key = (r["package"], r["break_boundary_fixed"])
        if key not in best or r["score"] > best[key]["score"]:
            best[key] = r
    all_deduped = sorted(best.values(), key=lambda r: (TIER_RANK[r["tier"]], -r["score"], r["package"]))
    n_apps = sum(1 for r in all_deduped if r["is_app"])
    # step-4 clean shortlist: libraries only, ranked by adaptation-API tier then score
    deduped = [r for r in all_deduped if not r["is_app"]]
    log(f"[3] refined: dropped {n_apps} application/product rows -> {len(deduped)} library candidates")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "advisory_candidates.json"), "w", encoding="utf-8") as f:
        json.dump(deduped, f, indent=1)

    # markdown shortlist (top 40)
    top = deduped[:40]
    lines = [
        "# External break candidates — mined from Maven security advisories",
        "",
        f"Source: OSV Maven feed. Scanned {total} advisories; {len(deduped)} distinct "
        "(package, fixed-version) candidates whose fix is a stricter-parsing / validation / "
        "deserialization tightening (the xstream/json-smart shape).",
        "",
        "`break_boundary` = the FIXED (patched) version — where the stricter behaviour lands. "
        "Baseline to reproduce the old lenient behaviour = any version below it.",
        "",
        "`tier` = adaptation-API class: **deserialize** (allowlist/validator API — cleanest, "
        "xstream shape) > **limit** (depth/size/XXE config — json-smart shape) > **validate** "
        "(generic — often no distinctive client API). Applications/products filtered out.",
        "",
        "| # | tier | score | package | boundary (fixed) | CWE | GHSA / CVE | summary |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(top, 1):
        cve = (r["aliases"] or [r["ghsa"]])[0]
        lines.append(
            f"| {i} | {r['tier']} | {r['score']} | `{r['package']}` | {r['break_boundary_fixed']} | "
            f"{','.join(r['cwes'])} | {cve} | {r['summary'].replace('|','/')} |"
        )
    with open(os.path.join(OUT_DIR, "ADVISORY_SHORTLIST.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # console: top 25 libraries, tier-ranked
    print("\n=== TOP 25 EXTERNAL BREAK CANDIDATES (libraries, tier-ranked) ===\n")
    print(f"{'#':>2}  {'tier':11s} {'score':>5}  {'package':42s} {'->fixed':14s} {'CWE':9s} ref")
    for i, r in enumerate(deduped[:25], 1):
        cve = (r["aliases"] or [r["ghsa"]])[0]
        print(f"{i:>2}  {r['tier']:11s} {r['score']:>5}  {r['package']:42.42s} {r['break_boundary_fixed']:14.14s} "
              f"{r['cwes'][0]:9s} {cve}")
    print(f"\nFull list: output/advisory_candidates.json  |  table: output/ADVISORY_SHORTLIST.md")
    print(f"Library candidates: {len(deduped)}  (deserialize tier: "
          f"{sum(1 for r in deduped if r['tier']=='deserialize')})")


if __name__ == "__main__":
    main()
