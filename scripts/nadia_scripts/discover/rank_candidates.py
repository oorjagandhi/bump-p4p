#!/usr/bin/env python
"""
rank_candidates.py — sort advisory candidates into "can yield a BBC case" vs "cannot".

WHY
---
output/advisory_candidates.json holds 932 (library, fixed-version) pairs across 595
distinct libraries, mined from the OSV Maven feed. Mining one properly costs about a day.
Most are structurally incapable of producing a case, and every reason we have hit is
knowable in advance:

  org-json   the boundary is from 2013 — every mineable client was born past it, so no
             client can have crossed it, however many real adaptations exist.
  snakeyaml  2.0 removed every constructor overload lacking a LoaderOptions, so clients
             crossing the boundary fail at javac and NEVER REACH the behavioural change.
             A compile break shadows the behavioural one.
  json-smart the library is almost always transitive; 89% of its mined commits changed no
             Java at all. Nobody writes code against it, so nobody has code to adapt.

This script encodes the first two as machine checks, ranks what survives, and records a
reason for every rejection so the list is auditable rather than a black box.

STAGES
------
1  metadata only, no network: tier, application-vs-library, boundary release DATE.
2  jars only, no clients and no GitHub: download the boundary version and its immediate
   predecessor, diff their PUBLIC API, and reject the candidate if the boundary REMOVED
   public signatures — that is the snakeyaml trap, and it is visible from two downloads.

Stage 2 is the expensive one, so it runs only on stage-1 survivors and honours --limit.

WHAT THIS IS NOT
----------------
A filter, not a detector. It cannot tell you a library HAS adaptations; it tells you a
library CANNOT have verifiable ones, which is the cheaper half of the problem. Survivors
still need mining. Rejections are kept with their reasons so a wrong call can be revisited
rather than silently lost.

Usage:
  python rank_candidates.py [--tier deserialize] [--limit 40] [--since 2019]
"""

# Scripts live one level down (discover/, mine/, traversal/, screen/, verify/) since
# the 2026-08 reorganisation, but they still import each other by module name and
# resolve data paths (output/, specs/, verified_cases/) against nadia_scripts/.
# This puts that root on sys.path so both keep working from anywhere.
import pathlib as _pl, sys as _sys
_NS_ROOT = _pl.Path(__file__).resolve().parent.parent
for _d in (_NS_ROOT, *(_NS_ROOT / _s for _s in
           ('discover', 'mine', 'traversal', 'screen', 'verify', 'archive', 'ledger', 'agent'))):
    if str(_d) not in _sys.path:
        _sys.path.insert(0, str(_d))

from paths import out, str_out



import argparse
import json
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8")

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / "output"
CAND = out("advisory_candidates.json")
SEARCH = "https://search.maven.org/solrsearch/select"
CENTRAL = "https://repo1.maven.org/maven2"
JARS = HERE / "scratchpad" / "rankjars"


def parse_ver(s):
    nums = re.findall(r"\d+", s or "")
    return tuple(int(n) for n in nums[:4]) if nums else None


def _get(params, tries=3):
    for i in range(tries):
        try:
            r = requests.get(SEARCH, params=params, timeout=60)
            return r.json().get("response", {}).get("docs", [])
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(2 * (i + 1))
    return None


def versions_with_dates(group, artifact):
    """ALL released versions, in Central's own release order.

    NOT the search API. solrsearch silently caps its result set -- asking for rows=400
    returned 20 -- so a predecessor lookup over that window misses the version it is
    looking for entirely (fastjson 1.2.82 was absent, leaving an Android-variant build as
    the nearest match). maven-metadata.xml is authoritative, uncapped, and already ordered
    by release, which removes the need to sort by a parsed version tuple at all.

    Returns [(version, None)] to keep the tuple shape; dates come from the exact-GAV
    lookup, which is reliable.
    """
    url = f"{CENTRAL}/{group.replace('.', '/')}/{artifact}/maven-metadata.xml"
    try:
        r = requests.get(url, timeout=60)
        if r.status_code != 200:
            return []
        return [(v, None) for v in re.findall(r"<version>([^<]+)</version>", r.text)]
    except Exception:
        return []


QUALIFIER = re.compile(r"(?i)(alpha|beta|rc|cr|m\d|snapshot|android|preview|ea|incubat)")


def _same_lineage(v, boundary):
    """Reject versions from a different release LINEAGE than the boundary.

    parse_ver keeps only digits, so `1.1.77.android_noneautotype` reduces to (1,1,77) and
    `4.0.0-beta-1` to (4,0,0,1) -- which sorts BELOW `4.0.0-alpha-2` (4,0,0,2). Both
    produced nonsense predecessors on the first run: fastjson was diffed against an
    Android-stripped build (191 "removed" signatures) and hive-exec against a NEWER alpha
    (4411). Those numbers describe two unrelated jars, not a boundary crossing.

    Rule: if the boundary is a plain release, its predecessor must be one too.
    """
    if QUALIFIER.search(boundary or ""):
        return True          # boundary is itself pre-release; do not over-filter
    return not QUALIFIER.search(v or "")


def predecessor(versions, boundary):
    """The released version immediately BELOW the boundary, same lineage.

    The comparison must be against what clients were actually ON before the boundary --
    the previous RELEASE. An API removal from an unrelated build or two majors back says
    nothing about whether crossing THIS boundary breaks compilation.
    """
    names = [v for v, _ in versions]
    if boundary in names:
        # Central lists versions in RELEASE order, so the predecessor is simply the
        # previous same-lineage entry. This is authoritative and sidesteps version-string
        # parsing entirely -- which is what produced `4.0.0-beta-1` as the predecessor of
        # `4.0.0-alpha-2` when ordering by digits alone.
        idx = names.index(boundary)
        for v in reversed(names[:idx]):
            if _same_lineage(v, boundary):
                return v
        return None
    # Boundary not published under that exact string; fall back to numeric ordering.
    b = parse_ver(boundary)
    if not b:
        return None
    below = [v for v in names
             if parse_ver(v) and parse_ver(v) < b and _same_lineage(v, boundary)]
    return below[-1] if below else None


# Central answers 403 when it is rate-limiting, and download_jar cannot report that
# through its None return -- so a throttled run silently converts every library into
# "jar unavailable on Central", a pre-rejection that looks exactly like a genuine 404.
# That is how a whole ranking pass could be published as measurement when it measured
# nothing. The status of the last attempt is recorded here so the caller can tell the two
# apart, and consecutive 403s abort the run instead of filling a report with pseudo-verdicts.
LAST_HTTP = {"status": None}
CONSECUTIVE_403 = {"n": 0}
MAX_CONSECUTIVE_403 = 5


class CentralThrottled(RuntimeError):
    """Central is refusing downloads; the run cannot produce verdicts."""


def download_jar(group, artifact, version):
    JARS.mkdir(parents=True, exist_ok=True)
    dest = JARS / f"{artifact}-{version}.jar"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    url = f"{CENTRAL}/{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}.jar"
    try:
        r = requests.get(url, timeout=120)
        LAST_HTTP["status"] = r.status_code
        if r.status_code == 403:
            CONSECUTIVE_403["n"] += 1
            if CONSECUTIVE_403["n"] >= MAX_CONSECUTIVE_403:
                raise CentralThrottled(
                    f"{MAX_CONSECUTIVE_403} consecutive 403s from Central — throttled. "
                    f"Stopping: every further row would be recorded as 'jar unavailable', "
                    f"which is not a verdict. Wait for the throttle to clear and resume "
                    f"(the progress file keeps what was already measured).")
            return None
        CONSECUTIVE_403["n"] = 0
        if r.status_code != 200 or not r.content:
            return None
        dest.write_bytes(r.content)
        return dest
    except CentralThrottled:
        raise
    except Exception:
        LAST_HTTP["status"] = None
        return None


def public_api(jar):
    """{fqcn: {signature, ...}} for public members, via one javap per batch of classes.

    javap accepts many class names per invocation, so a whole jar costs a handful of JVM
    starts rather than one per class. Windows caps a command line at ~8k characters, so
    batches are kept small enough to stay under it.
    """
    try:
        with zipfile.ZipFile(jar) as z:
            names = [n[:-6].replace("/", ".") for n in z.namelist()
                     if n.endswith(".class") and "$" not in n]
    except Exception:
        return None
    if not names:
        return None
    api = {}
    batch, size = [], 0
    def flush(bt):
        if not bt:
            return
        r = subprocess.run(["javap", "-cp", str(jar), *bt],
                           capture_output=True, text=True, errors="replace")
        cur = None
        for line in (r.stdout or "").splitlines():
            s = line.strip()
            m = re.match(r"(?:public\s+)?(?:final\s+|abstract\s+)*"
                         r"(?:class|interface|enum)\s+([\w.$]+)", s)
            if m:
                cur = m.group(1)
                api.setdefault(cur, set())
                continue
            if cur and s.startswith("public ") and s.endswith(";"):
                # normalise: drop throws clauses and parameter names
                sig = re.sub(r"\s+throws\s+.*;$", ";", s)
                # Modifiers that cannot break a CALLER's source. snakeyaml 1.32 made seven
                # LoaderOptions getters `final`, which this comparison read as seven
                # removals and rejected the boundary as a compile break -- a boundary whose
                # behavioural change is measured and real. A client calling
                # isAllowDuplicateKeys() compiles identically either way, so the keyword
                # must not count as an API removal.
                #
                # Anywhere in the modifier list, not just straight after `public`:
                # snakeyaml-engine 2.5 turned `public static final ... builder()` into
                # `public static ... builder()`, which the narrower rule read as the removal
                # of the builder entry point every client uses. static/abstract/default are
                # KEPT -- those do change how a caller may invoke the member.
                sig = re.sub(r"\b(?:final|synchronized|native|strictfp)\s+", "", sig)
                api[cur].add(sig)
    for n in names:
        batch.append(n)
        size += len(n) + 1
        if size > 6000:
            flush(batch)
            batch, size = [], 0
    flush(batch)
    return api or None


def api_removals(old_jar, new_jar):
    """(removed_signature_count, removed_class_count, samples) or None if unreadable."""
    a, b = public_api(old_jar), public_api(new_jar)
    if a is None or b is None:
        return None
    gone_classes = [c for c in a if c not in b]
    removed, samples = 0, []
    for c, sigs in a.items():
        if c not in b:
            continue
        lost = sigs - b[c]
        if lost:
            removed += len(lost)
            if len(samples) < 6:
                samples.append(f"{c}: {sorted(lost)[0][:90]}")
    return removed, len(gone_classes), samples


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="deserialize",
                    help="advisory tier to consider (deserialize|limit|validate|all)")
    ap.add_argument("--limit", type=int, default=25, help="stage-2 budget")
    ap.add_argument("--since", type=int, default=2019,
                    help="reject boundaries released before this year")
    ap.add_argument("--out", default="output/CANDIDATE_RANKING.md")
    args = ap.parse_args()

    rows = json.loads(CAND.read_text(encoding="utf-8"))
    print(f"[rank] {len(rows)} advisory rows, "
          f"{len({r['package'] for r in rows})} distinct libraries\n")

    # ── stage 1: metadata only ────────────────────────────────────────────────
    stage1, rejected = [], []
    for r in rows:
        pkg, boundary = r.get("package"), r.get("break_boundary_fixed")
        if r.get("is_app"):
            rejected.append((pkg, boundary, "application, not a library")); continue
        if args.tier != "all" and r.get("tier") != args.tier:
            continue
        if not boundary or ":" not in (pkg or ""):
            rejected.append((pkg, boundary, "no usable package/boundary")); continue
        stage1.append(r)
    # strongest advisory per library — repeated CVEs on one library are one opportunity
    best = {}
    for r in sorted(stage1, key=lambda x: -(x.get("score") or 0)):
        best.setdefault(r["package"], r)
    stage1 = list(best.values())
    print(f"[stage1] {len(stage1)} libraries in tier '{args.tier}' "
          f"(deduped to the highest-scoring advisory each)\n")

    # Append each verdict as it is computed. Stage 2 costs two jar downloads and a full
    # javap pass per candidate, so holding results in memory until the end means a kill
    # discards the whole run -- which happened at row 73 of 120. This is the FOURTH time
    # today the same mistake has cost a pass (commit search, classify loop, and the
    # undecided resolver were each fixed for it), so it is fixed here the same way.
    #
    # The progress file is PER TIER. It was not, and that was a reporting bug waiting to
    # fire: `results` is preloaded from it and then written straight into the report, so
    # running --tier validate after --tier deserialize would have published the 82
    # deserialize verdicts under a validate heading. A tier's report must contain that
    # tier's measurements and nothing else.
    prog = out(f"candidate_ranking_progress_{args.tier}.jsonl")
    legacy = out("candidate_ranking_progress.jsonl")
    if args.tier == "deserialize" and legacy.exists() and not prog.exists():
        legacy.rename(prog)          # the pre-tier run was a deserialize run
    results, done_pkgs = [], set()
    if prog.exists():
        for line in prog.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                prev = json.loads(line)
            except Exception:
                continue
            results.append(prev)
            done_pkgs.add(prev.get("package"))
        if done_pkgs:
            print(f"[rank] resuming: {len(done_pkgs)} package(s) already verdicted\n")
    pf = prog.open("a", encoding="utf-8")
    # Resumed rows count against --limit. They did not, so a resumed run spent the FULL
    # budget again on new libraries -- `checked` started at 0 while the already-done ones
    # were skipped before it incremented. --limit means "stage-2 checks for this tier",
    # not "stage-2 checks since the last kill".
    checked = len(done_pkgs)
    for r in sorted(stage1, key=lambda x: -(x.get("score") or 0)):
        if checked >= args.limit:
            break
        pkg, boundary = r["package"], r["break_boundary_fixed"]
        if pkg in done_pkgs:
            continue
        g, a = pkg.split(":", 1)
        vs = versions_with_dates(g, a)
        # maven-metadata.xml gives order but no dates, so the release date comes from an
        # EXACT-GAV search. Without this the --since filter silently passes everything --
        # which would drop the org-json lesson (a boundary older than the client
        # population yields zero crossings by construction) out of the pipeline entirely.
        docs = _get({"q": f'g:"{g}" AND a:"{a}" AND v:"{boundary}"',
                     "core": "gav", "rows": 1, "wt": "json"}) or []
        ts = docs[0].get("timestamp") if docs else None
        date = time.strftime("%Y-%m", time.gmtime(ts / 1000)) if ts else None
        if date and int(date[:4]) < args.since:
            rejected.append((pkg, boundary, f"boundary too old ({date}) — "
                                            f"clients born past it"))
            continue
        prev = predecessor(vs, boundary)
        if not prev:
            rejected.append((pkg, boundary, "no released predecessor version"))
            continue

        checked += 1
        print(f"[stage2 {checked}/{args.limit}] {pkg}  {prev} -> {boundary} ({date})",
              flush=True)
        oj, nj = download_jar(g, a, prev), download_jar(g, a, boundary)
        if not oj or not nj:
            # 403 is a throttle, not a 404. Recording it as "unavailable" would put a
            # non-measurement in the report under the same wording as a real one.
            why = ("Central returned 403 (rate-limited) — NOT a verdict, re-run"
                   if LAST_HTTP["status"] == 403 else "jar unavailable on Central")
            rejected.append((pkg, boundary, why))
            continue
        diff = api_removals(oj, nj)
        if diff is None:
            rejected.append((pkg, boundary, "jar unreadable by javap"))
            continue
        removed, gone_classes, samples = diff
        verdict = ("REJECT" if (removed or gone_classes) else "MINEABLE")
        rec = {
            "package": pkg, "boundary": boundary, "predecessor": prev,
            "released": date, "score": r.get("score"), "cwes": r.get("cwes"),
            "ghsa": r.get("ghsa"), "summary": (r.get("summary") or "")[:110],
            "removed_signatures": removed, "removed_classes": gone_classes,
            "samples": samples, "verdict": verdict,
        }
        results.append(rec)
        pf.write(json.dumps(rec) + chr(10)); pf.flush()
        print(f"      {verdict}: {removed} removed signature(s), "
              f"{gone_classes} removed class(es)", flush=True)

    pf.close()
    mineable = [x for x in results if x["verdict"] == "MINEABLE"]
    blocked = [x for x in results if x["verdict"] == "REJECT"]

    lines = ["# Candidate ranking — which advisories can yield a BBC case", "",
             f"Generated by `rank_candidates.py` from `advisory_candidates.json` "
             f"({len(rows)} rows, {len({r['package'] for r in rows})} libraries).", "",
             "A break can only produce a verifiable case if the boundary release **does "
             "not remove public API**. If it does, clients crossing it fail at javac and "
             "never reach the behavioural change — the snakeyaml trap, where all three "
             "traversal-confirmed candidates turned out to be compile breaks.", "",
             f"Tier `{args.tier}`, boundaries from {args.since} onward, "
             f"stage-2 budget {args.limit}.", "",
             f"## Mineable ({len(mineable)})", "",
             "| library | transition | released | removed API | advisory |",
             "|---|---|---|---:|---|"]
    for x in sorted(mineable, key=lambda y: -(y["score"] or 0)):
        lines.append(f"| `{x['package']}` | {x['predecessor']} → {x['boundary']} | "
                     f"{x['released']} | **0** | {x['ghsa']} |")
    lines += ["", f"## Rejected: boundary removes public API ({len(blocked)})", "",
              "These crossings break compilation, so any behavioural change is shadowed.",
              "", "| library | transition | removed sigs | removed classes | example |",
              "|---|---|---:|---:|---|"]
    for x in sorted(blocked, key=lambda y: -y["removed_signatures"]):
        eg = (x["samples"] or ["—"])[0]
        lines.append(f"| `{x['package']}` | {x['predecessor']} → {x['boundary']} | "
                     f"{x['removed_signatures']} | {x['removed_classes']} | `{eg}` |")
    lines += ["", f"## Rejected before stage 2 ({len(rejected)})", "",
              "| library | boundary | reason |", "|---|---|---|"]
    for pkg, b, why in rejected[:60]:
        lines.append(f"| `{pkg}` | {b} | {why} |")
    if len(rejected) > 60:
        lines.append(f"| … | | {len(rejected) - 60} more |")

    dest = HERE / args.out
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    # Per tier, for the same reason the progress file is: a validate run must not
    # overwrite the deserialize measurements with a different tier's verdicts.
    ranking_json = (out("candidate_ranking.json") if args.tier == "deserialize"
                    else out(f"candidate_ranking_{args.tier}.json"))
    ranking_json.write_text(
        json.dumps({"mineable": mineable, "blocked": blocked}, indent=2),
        encoding="utf-8")
    print(f"\n[rank] mineable={len(mineable)} blocked={len(blocked)} "
          f"pre-rejected={len(rejected)}")
    print(f"[rank] saved -> {dest}")


if __name__ == "__main__":
    main()
