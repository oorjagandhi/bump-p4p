#!/usr/bin/env python
"""
probe_population.py — does anyone PUBLICLY commit the adaptation to this break?

WHY
---
Every screen the project has measures the LIBRARY: does the boundary remove public API
(rank_candidates.py), is the new restriction active by default (sources diff), is the
boundary old enough (boundary_dates.py). None measures the POPULATION. commons-net proved
that gap expensive: it passed every library-side screen, had the best shape since xstream,
and yielded zero — because of 519 mined commits, ZERO named the fix. FTP-behind-NAT is
enterprise integration code and it is not on GitHub.

That is knowable in minutes instead of a day.

HOW IT DERIVES ITS OWN SEARCH TERMS
-----------------------------------
The thing worth searching for is the ADAPTATION, not the upgrade — bump commits are
abundant for every library and discriminate nothing. But the adaptation signature is
usually a method the maintainers ADDED at the boundary so broken clients could opt back
out of the new behaviour:

    commons-net 3.9.0   setIpAddressFromPasvResponse   <- did not exist in 3.8.0
    xstream 1.4.18      allowTypes                      <- the one that produced 7 cases

That is rank_candidates.api_removals run in reverse: public signatures present in the NEW
jar and absent from the OLD one. So the probe needs no hand-written per-library knowledge.

Method names are ranked by how much they look like an opt-back-out — setters and
enable/allow/with/configure/trust verbs first — because those are what a client calls when
the new default breaks it.

WHAT A RESULT MEANS
-------------------
  client_hits high   people publicly commit this identifier -> a population exists to mine
  client_hits ZERO   nobody does -> mining will cost a day and return zero, as commons-net did
  no_new_api         the boundary added no opt-back-out at all. Weaker signal, not fatal:
                     the adaptation may be a config change or a call the client removes.

This is a NEGATIVE screen. High hits do not promise cases — the hits may be exploit demos
(fastjson, commons-text/Text4Shell) or people adopting the API rather than adapting to the
break. It tells you where NOT to spend a day.

Usage:
  python probe_population.py --tier validate
  python probe_population.py --tier validate --limit 10 --terms 4
  python probe_population.py --package org.apache.commons:commons-text
"""

import argparse
import json
import re
import sys
from pathlib import Path

import bbc_e2e as B
import rank_candidates as R

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
OUT = HERE / "output"

# Verbs a maintainer reaches for when adding an escape hatch. Ranked, most telling first.
OPT_OUT_HINTS = ("setallow", "allow", "settrust", "trust", "enable", "setenable",
                 "permit", "setlegacy", "legacy", "compat", "with", "configure",
                 "set", "add", "register")

# Members that are never a client-facing escape hatch.
NOISE = re.compile(r"^(get|is|to|hash|equals|clone|main|read|write|close|iterator|"
                   r"compare|accept|apply|test|run|call|value|values|of|from)", re.I)


def added_api(old_jar, new_jar):
    """Public members present in NEW and absent from OLD — the reverse of api_removals."""
    a, b = R.public_api(old_jar), R.public_api(new_jar)
    if a is None or b is None:
        return None
    added = []
    for cls, sigs in b.items():
        gained = sigs - a.get(cls, set())
        for s in gained:
            added.append((cls, s))
    return added


# Verbs strong enough to identify an escape hatch on their own, without the member also
# having to be NEW at the boundary. Deliberately excludes set/add/with/configure, which
# name half the members of any library.
STRONG_HINTS = ("allow", "trust", "permit", "enable", "legacy", "compat", "unsafe",
                "insecure", "disablecheck", "skipvalidation")


def _rank(n):
    low = n.lower()
    for i, h in enumerate(OPT_OUT_HINTS):
        if low.startswith(h):
            return (i, len(n))
    return (len(OPT_OUT_HINTS), len(n))


def _idents(pairs):
    names = {}
    for cls, sig in pairs:
        for m in re.finditer(r"\b([a-z][A-Za-z0-9_]{4,})\s*\(", sig):
            n = m.group(1)
            if NOISE.match(n):
                continue
            names.setdefault(n, cls)
    return names


def method_names(added, new_api=None):
    """Identifiers to search for, ranked opt-out-first.

    Primary source is API ADDED at the boundary — the escape hatch a maintainer wrote for
    the clients the change broke (commons-net's setIpAddressFromPasvResponse ranks #3 of 6
    here).

    But the escape hatch does not have to be new, and assuming it is would have rejected
    the ONE library that ever produced cases: xstream 1.4.17 -> 1.4.18 adds ZERO public
    members. `allowTypes` shipped back in 1.4.7; 1.4.18 only flipped the DEFAULT to deny.
    So when the added-API set yields nothing, fall back to opt-out-shaped members of the
    NEW jar whatever their vintage — restricted to STRONG_HINTS, because falling back on
    every setter would drown the signal.
    """
    names = _idents(added)
    if names:
        return sorted(names, key=_rank)
    if not new_api:
        return []
    flat = [(cls, s) for cls, sigs in new_api.items() for s in sigs]
    fallback = {n: c for n, c in _idents(flat).items()
                if n.lower().startswith(STRONG_HINTS)}
    return sorted(fallback, key=_rank)


def keyword_for(artifact_id):
    """The token a client's commit message would use for the library."""
    return artifact_id.split("-")[0] if "-" not in artifact_id else artifact_id


def is_library_repo(repo, group_id, artifact_id):
    """Drop the library's own repo, its forks and mirrors — they are not clients."""
    r = repo.lower()
    tail = group_id.lower().split(".")[-1]
    return artifact_id.lower() in r or (len(tail) > 3 and tail in r)


def probe(pkg, boundary, predecessor, token, max_terms):
    g, a = pkg.split(":", 1)
    old_jar = R.download_jar(g, a, predecessor)
    new_jar = R.download_jar(g, a, boundary)
    if not old_jar or not new_jar:
        return {"package": pkg, "status": "jars unavailable", "client_hits": None}
    added = added_api(old_jar, new_jar)
    if added is None:
        return {"package": pkg, "status": "jar unreadable", "client_hits": None}
    names = method_names(added, new_api=R.public_api(new_jar))
    if not names:
        return {"package": pkg, "status": "no_new_api", "added_members": len(added),
                "client_hits": None, "terms": []}

    kw = keyword_for(a)
    hits, per_term, examples = 0, [], []
    for name in names[:max_terms]:
        q = f"{kw} {name}"
        items, complete = B.gh_commit_search(q, token, max_pages=1)
        client = [it for it in items
                  if not is_library_repo(it["repository"]["full_name"], g, a)]
        per_term.append({"term": q, "hits": len(items), "client_hits": len(client),
                         "complete": complete})
        hits += len(client)
        for it in client[:2]:
            examples.append({"repo": it["repository"]["full_name"],
                             "message": (it["commit"]["message"] or "").splitlines()[0][:80]})
    # The AGGREGATE across identifiers is misleading on its own: commons-net scores 3 only
    # because an unrelated setDataTimeout deprecation cleanup is in the corpus, while the
    # actual escape hatch (setIpAddressFromPasvResponse) scores ZERO. Report the best
    # single identifier too -- one live identifier is the signal, a sum is not.
    best = max(per_term, key=lambda t: t["client_hits"]) if per_term else None
    return {"package": pkg, "status": "probed", "added_members": len(added),
            "terms": per_term, "client_hits": hits,
            "best_term": best["term"] if best else None,
            "best_hits": best["client_hits"] if best else 0,
            "examples": examples[:4], "top_names": names[:max_terms]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="validate")
    ap.add_argument("--limit", type=int, default=0, help="0 = every mineable row")
    ap.add_argument("--terms", type=int, default=3, help="identifiers probed per library")
    ap.add_argument("--package", help="probe one package instead of a whole tier")
    ap.add_argument("--out")
    args = ap.parse_args()

    src = (OUT / "candidate_ranking.json" if args.tier == "deserialize"
           else OUT / f"candidate_ranking_{args.tier}.json")
    if not src.exists():
        sys.exit(f"no ranking at {src} — run rank_candidates.py --tier {args.tier} first")
    rows = json.loads(src.read_text(encoding="utf-8"))["mineable"]
    if args.package:
        rows = [r for r in rows if r["package"] == args.package]
        if not rows:
            sys.exit(f"{args.package} is not in the mineable list for tier {args.tier}")
    if args.limit:
        rows = rows[:args.limit]

    token = B._token()
    # Checkpoint per library. Each row costs jar downloads plus several rate-limited
    # GitHub searches, so a kill must not discard the whole pass -- the same lesson the
    # search loop, classify loop, undecided resolver and ranking stage each paid for.
    ck = OUT / f"population_probe_progress_{args.tier}.jsonl"
    done, results = set(), []
    if ck.exists():
        for line in ck.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                prev = json.loads(line)
            except Exception:
                continue
            results.append(prev)
            done.add(prev["package"])
        if done:
            print(f"[probe] resuming: {len(done)} package(s) already probed\n")
    fh = ck.open("a", encoding="utf-8")

    print(f"[probe] {len(rows)} mineable row(s) in tier '{args.tier}', "
          f"{args.terms} identifier(s) each\n")
    for i, r in enumerate(rows, 1):
        if r["package"] in done:
            continue
        res = probe(r["package"], r["boundary"], r["predecessor"], token, args.terms)
        res["boundary"] = r["boundary"]
        res["predecessor"] = r["predecessor"]
        res["ghsa"] = r.get("ghsa")
        results.append(res)
        fh.write(json.dumps(res) + "\n")
        fh.flush()
        ch = res.get("client_hits")
        print(f"[{i}/{len(rows)}] {r['package'][:46]:46} "
              f"{res['status']:16} client_hits="
              f"{'--' if ch is None else ch}", flush=True)
        if res.get("top_names"):
            print(f"          probed: {', '.join(res['top_names'])}", flush=True)
    fh.close()

    probed = [x for x in results if x["status"] == "probed"]
    dead = [x for x in probed if x["client_hits"] == 0]
    live = sorted([x for x in probed if (x["client_hits"] or 0) > 0],
                  key=lambda x: -x["client_hits"])
    no_api = [x for x in results if x["status"] == "no_new_api"]

    lines = ["# Population probe — does anyone publicly commit the adaptation?",
             "",
             "Every other screen measures the LIBRARY. This measures the POPULATION: are there "
             "public commits calling the escape-hatch API the boundary added? commons-net "
             "passed every library-side screen and still yielded zero, because **0 of 519** "
             "mined commits named its fix.", "",
             "Search terms are derived, not hand-written: public members present in the "
             "boundary jar and absent from its predecessor — `api_removals` in reverse — "
             "ranked so opt-back-out verbs (`allow`, `trust`, `enable`, `set…`) come first.",
             "",
             "**A negative screen.** High hits do not promise cases: they may be exploit demos "
             "(fastjson, Text4Shell) or people adopting the API rather than adapting to the "
             "break. It tells you where NOT to spend a day.", "",
             f"Tier `{args.tier}`, {args.terms} identifiers per library. "
             f"{len(live)} with a population, {len(dead)} with none, "
             f"{len(no_api)} added no new API.", "",
             "## Has a public population", "",
             "| library | transition | total | best single identifier | hits |",
             "|---|---|---:|---|---:|"]
    for x in live:
        bt = (x.get("best_term") or "—").split(" ", 1)[-1]
        lines.append(f"| `{x['package']}` | {x['predecessor']} → {x['boundary']} "
                     f"| {x['client_hits']} | `{bt}` | **{x.get('best_hits', 0)}** |")
    lines += ["", "## No public population — do not mine", "",
              "| library | transition | identifiers probed |", "|---|---|---|"]
    for x in dead:
        lines.append(f"| `{x['package']}` | {x['predecessor']} → {x['boundary']} "
                     f"| `{'`, `'.join(x.get('top_names', []))}` |")
    lines += ["", "Read the per-identifier hits, not the total. commons-net scores 3 in "
              "aggregate purely from an unrelated `setDataTimeout` cleanup, while its real "
              "escape hatch `setIpAddressFromPasvResponse` scores **0** — and commons-net "
              "did in fact yield nothing after a full day of mining."]
    if no_api:
        lines += ["", "## Added no new public API", "",
                  "No escape hatch was added, so there is no derived identifier to search. "
                  "Not fatal — the adaptation may be a config change or a call the client "
                  "deletes — but there is nothing for this screen to measure.", "",
                  "| library | transition |", "|---|---|"]
        for x in no_api:
            lines.append(f"| `{x['package']}` | {x['predecessor']} → {x['boundary']} |")

    dest = HERE / (args.out or f"output/POPULATION_PROBE_{args.tier.upper()}.md")
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / f"population_probe_{args.tier}.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8")
    print(f"\n[probe] population={len(live)} none={len(dead)} no_new_api={len(no_api)}")
    print(f"[probe] saved -> {dest}")


if __name__ == "__main__":
    main()
