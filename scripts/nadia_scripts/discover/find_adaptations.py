#!/usr/bin/env python
"""
find_adaptations.py — which commits RECOVER from a break, rather than merely mention it.

WHY THIS EXISTS
---------------
Every verified case on the snakeyaml code-point limit was found by hand, this way: search
commits for the adaptation identifier, fetch each diff, and read the VALUE the project
chose. The bump-axis mine, run over the same break, checked 105 rows and produced four
candidates -- all false on reading -- while one afternoon of this produced six genuine
ones, three of which verified.

The value is the whole game, because a project touching `setCodePointLimit` is doing one
of three quite different things:

    RAISE     Integer.MAX_VALUE, 64 MB, 50 MB, `length + 10000`
              -> the limit is lifted, previous behaviour restored. A CANDIDATE.
    LOWER     8192, 64 KB, 1 MB
              -> tightening it further. Security hardening, not a recovery.
    KNOB      exposes a setter but leaves the default at the library's own (3 MB)
              -> behaves identically before and after for EVERY input size, so it can
                 never produce a pass/fail/pass differential.

That split is not incidental. Measured five for five on snakeyaml, it follows what the
project IS: applications raise the limit (WorldEdit 64 MB, infoarchive 10 MB, bioformats
sized to the file); libraries and plugins expose a knob and pass the decision downstream
(swagger-parser, bspfsystems, both Jenkins plugins). Only the first kind verifies.

WHAT IT IS NOT
--------------
Not a replacement for mining. This only finds commits whose DIFF touches the identifier.
ome/bioformats hid a genuine recovery inside a commit called "Miscellaneous fixes" and
would still be found here (its diff has the call), but a project that adapted by, say,
deleting a call or changing config would not be. Use it as a fast first pass, and let the
mine cover what messages and identifiers miss.

Usage:
  python find_adaptations.py <break_id> --identifier setCodePointLimit
  python find_adaptations.py <break_id> --identifier setMaxAliasesForCollections --pages 3
  python find_adaptations.py <break_id> --identifier allowTypes --default-value 0
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


import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

import requests

import bbc_e2e as B
from probe_population import is_library_repo, keyword_for

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent.parent
OUT = HERE / "output"

# Sizes written as expressions rather than literals; evaluated so 64 * 1024 * 1024 and
# 67108864 compare equal.
_SIZE = re.compile(r"^[\d_\s*+()]+$")


def literal_value(expr):
    """The numeric value of a simple size expression, or None if it is not one.

    Returns None for anything referring to a variable (`codePointLimit`, `length + 10000`,
    `Integer.getInteger(...)`) -- those need the surrounding lines to interpret, which is
    what `evidence` is for.
    """
    e = expr.strip().rstrip(";")
    if e in ("Integer.MAX_VALUE", "Integer .MAX_VALUE"):
        return 2 ** 31 - 1
    if not _SIZE.match(e):
        return None
    try:
        v = eval(e, {"__builtins__": {}}, {})  # digits and * + ( ) only, per _SIZE
        return int(v) if isinstance(v, (int, float)) else None
    except Exception:
        return None


def resolve_variable(name, added_lines):
    """Value of a variable assigned in the same diff, or None.

    The strongest adaptations pass a variable, not a literal: WorldEdit writes
    `setCodePointLimit(yamlCodePointLimit)` and assigns that from
    `Integer.getInteger("worldedit.yaml.codePointLimit", 64 * 1024 * 1024)`. Without
    resolving it, WorldEdit and infoarchive (both genuine raises) land in the same bucket
    as bspfsystems, whose variable resolves to the library's own 3 MB and is therefore a
    knob. Resolving is what separates them.
    """
    bare = name.split(".")[-1].strip()
    if not re.match(r"^\w+$", bare):
        return None
    for line in added_lines:
        # `TYPE name = <expr>;` or `this.name = <expr>;`
        m = re.search(re.escape(bare) + r"\s*=\s*([^;]+);", line)
        if not m:
            continue
        expr = m.group(1).strip()
        # Integer.getInteger(key, DEFAULT) / getProperty(...) == null ? DEFAULT : ...
        g = re.search(r"getInteger\s*\([^,]+,\s*([^)]+)\)", expr)
        if g:
            expr = g.group(1)
        t = re.search(r"==\s*null\s*\?\s*([^:]+):", expr)
        if t:
            expr = t.group(1)
        v = literal_value(expr)
        if v is not None:
            return v
    return None


def classify(added_lines, identifier, default_value, library_class=None):
    """(verdict, value, evidence) for one commit's added lines.

    `library_class` names the class holding the library's own default constants, e.g.
    "StreamReadConstraints". Passing an argument that IS one of those constants is a knob
    by definition, whatever the number behind it happens to be, and this is the dominant
    false positive on every break mined so far: CloudSlang/score writes

        Integer.getInteger("jackson.core.maxStringLen", StreamReadConstraints.DEFAULT_MAX_STRING_LEN)

    which is a property an operator MAY raise, defaulting to the library's own value, so
    out of the box it changes nothing. It must not be counted with the raises. Matching on
    the library's class name rather than the constant's name is what keeps this from
    swallowing a client's own DEFAULT_-named constant -- AthenZ's
    Config.DEFAULT_JSON_MAX_STRING_LENGTH is a genuine 200 MB raise.
    """
    calls = [l for l in added_lines if identifier in l]
    if not calls:
        return "no_call", None, None
    if library_class:
        lib_default = re.compile(re.escape(library_class) + r"\s*\.\s*DEFAULT_\w+")
        for line in calls:
            if lib_default.search(line):
                return "knob_at_default", None, line.strip()[:110]
        # the call may pass a variable that is itself assigned the library's default
        for line in calls:
            m = re.search(re.escape(identifier) + r"\s*\(([^;]*?)\)", line)
            if not m:
                continue
            bare = m.group(1).strip().split(".")[-1]
            if re.match(r"^\w+$", bare):
                for a in added_lines:
                    if re.search(re.escape(bare) + r"\s*=", a) and lib_default.search(a):
                        return "knob_at_default", None, a.strip()[:110]
    for line in calls:
        # NON-GREEDY. Greedy `([^;]*)` ran to the LAST paren on the line, so the fluent
        # builder form `maxStringLength(20000000).build()` captured `20000000).build(`,
        # which is not a size expression -- 19 of the first 55 jackson rows landed in
        # needs_reading for that reason alone. Nested-call arguments still fall through to
        # resolve_variable exactly as before.
        m = re.search(re.escape(identifier) + r"\s*\(([^;]*?)\)", line)
        if not m:
            continue
        arg = m.group(1).strip()
        v = literal_value(arg)
        if v is None:
            v = resolve_variable(arg, added_lines)
        if v is None:
            # A variable or expression. If the same diff sets a default anywhere, the
            # DEFAULT is what decides -- a knob whose default equals the library's own
            # changes nothing. Surface it for reading rather than guessing.
            defaults = [l for l in added_lines
                        if re.search(r"(MAX_VALUE|getInteger|getProperty|=\s*[\d_\s*+]+;)", l)
                        and identifier not in l]
            return "needs_reading", arg, (defaults[:3] or [line.strip()[:100]])
        if v > default_value:
            return "raise", v, line.strip()[:110]
        if v < default_value:
            return "lower", v, line.strip()[:110]
        return "knob_at_default", v, line.strip()[:110]
    return "needs_reading", None, [c.strip()[:100] for c in calls[:2]]


def library_in_diff(added_lines, group_id):
    """Confirm from the DIFF alone. Weak: only sees added lines."""
    root = group_id.split(".")[0] + "." + group_id.split(".")[-1] if "." in group_id else group_id
    hay = "\n".join(added_lines)
    if group_id.replace(":", ".") in hay or root in hay:
        return True
    return None


def library_in_file(repo, sha, path, group_id, other_group, token):
    """Confirm from the FILE'S IMPORTS which library the call belongs to.

    The diff is not enough. `setCodePointLimit` is spelled identically in
    org.yaml:snakeyaml and org.snakeyaml:snakeyaml-engine -- two different artifacts with
    the same 3 MiB break -- and a commit that only adds the call, leaving an import that
    was already there, gives the diff nothing to match on. fglock/PerlOnJava is exactly
    that: a genuine engine adaptation that the diff-only check cannot attribute, and which
    would otherwise be counted against the wrong break.

    Returns True (this library), False (the other one), or None (could not tell).
    """
    text = B._gh_file(repo, path, sha, token)
    if text is None:
        return None
    mine = group_id.replace(":", ".")
    theirs = (other_group or "").replace(":", ".")
    # engine classes live under org.snakeyaml.engine, snakeyaml's under org.yaml.snakeyaml
    has_mine = mine in text
    has_theirs = bool(theirs) and theirs in text
    if has_mine and not has_theirs:
        return True
    if has_theirs and not has_mine:
        return False
    return None


def code_search_files(query, token, pages=3):
    """(repo, path) for every file whose CURRENT content matches. Keeps the PATH.

    A different index from commit search, and the difference is not cosmetic. Commit
    search could not see AthenZ/athenz at all -- a repo-scoped commit search for
    setStreamReadConstraints returns zero, because GitHub does not index that repository's
    commit history -- while code search returned it immediately. On jackson-core, code
    search found 241 repos of which 238 were unseen by commit search; on snakeyaml, 160 of
    which 155 were unseen.

    This keeps the file PATH, not just the repo name, because the history walk below needs
    it. (A repo-name-only version lived in mine/bbc_pipeline.py until that file was deleted
    on 2026-08-13.)

    Code search is rate-limited to ~10 requests/minute and capped at 1000 results.
    """
    out, page = [], 1
    while page <= pages:
        r = requests.get("https://api.github.com/search/code",
                         headers={"Authorization": f"Bearer {token}",
                                  "Accept": "application/vnd.github+json"},
                         params={"q": query, "per_page": 100, "page": page}, timeout=30)
        try:
            d = r.json()
        except Exception:
            print(f"[code] non-JSON response on page {page}", file=sys.stderr)
            break
        if "items" not in d:
            print(f"[code] API: {d.get('message')}", file=sys.stderr)
            break
        out += [(it["repository"]["full_name"], it["path"]) for it in d["items"]]
        if len(d["items"]) < 100:
            break
        page += 1
        time.sleep(7)          # ~10 req/min
    return out


def introducing_commit(repo, path, identifier, token):
    """The oldest commit at `path` whose content contains `identifier`, or None.

    Code search says a file contains the call TODAY; this dates it. The commits API is
    complete per path and carries none of commit search's recency bias, which is the whole
    point of routing through it.

    Renames end the walk early -- git follows content, this follows a path -- so a commit
    returned here is the introduction WITHIN THIS PATH'S history, not necessarily the
    library-wide first use. karatelabs/karate hits exactly that: its oldest hit is the
    commit that renamed the file.
    """
    commits = B._gh(f"{B.GH}/repos/{repo}/commits", token, path=path, per_page=100)
    if not isinstance(commits, list) or not commits:
        return None
    for c in reversed(commits):            # oldest first
        text = B._gh_file(repo, path, c["sha"], token)
        if text and identifier in text:
            return c
    return None


def report_date_distribution(rows, boundary_year=None):
    """Print adaptations per year, and warn when the crossing window looks under-sampled.

    On jackson-core the distribution was 2021:1, 2023:2, 2025:13, 2026:83 -- 83 of 99 from
    the current year, three years after the boundary. That is an index artefact, not
    behaviour, and it cost 99 rows of triage to notice. Cases cluster NEAR the boundary, so
    a distribution skewed away from it means the search is looking in the wrong place.
    """
    years = Counter((r.get("date") or "?")[:4] for r in rows if r.get("date"))
    if not years:
        return
    print("\n[dates] adaptations by year: "
          + ", ".join(f"{y}:{n}" for y, n in sorted(years.items())))
    if boundary_year:
        near = sum(n for y, n in years.items()
                   if y.isdigit() and 0 <= int(y) - int(boundary_year) <= 1)
        total = sum(years.values())
        pct = 100 * near // max(total, 1)
        print(f"[dates] within a year of the {boundary_year} boundary: {near}/{total} ({pct}%)")
        if pct < 25:
            print("[dates] WARNING: the crossing window is under-sampled. Commit search "
                  "skews recent and cannot index some repositories at all -- try "
                  "--via code-search before concluding there are no cases.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("break_id")
    ap.add_argument("--identifier", required=True,
                    help="the adaptation API, e.g. setCodePointLimit")
    ap.add_argument("--default-value", type=int, default=3 * 1024 * 1024,
                    help="the library's own default; a call setting exactly this is a knob")
    ap.add_argument("--pages", type=int, default=3, help="search pages per query (50 each)")
    ap.add_argument("--via", choices=["commit-search", "code-search"],
                    default="commit-search",
                    help="commit-search (default) reads commit messages and diffs; it is "
                         "recency-biased and cannot index some repositories at all. "
                         "code-search finds files containing the identifier TODAY and dates "
                         "each by walking that file's history -- slower, ~10 req/min, but it "
                         "reaches repos commit search cannot see. AthenZ was found this way.")
    ap.add_argument("--other-group", default="",
                    help="sibling library whose API is spelled the same, e.g. org.yaml "
                         "when mining org.snakeyaml. Used to ATTRIBUTE a commit to one "
                         "break or the other from the changed file's imports.")
    ap.add_argument("--out")
    args = ap.parse_args()

    brk = B.get_break(args.break_id)
    lib = brk["library"]
    gid, aid = lib["group_id"], lib["artifact_id"]
    token = B._token()
    kw = keyword_for(aid)

    # GitHub commit search is NOT stable between runs: the same query returned 52
    # distinct commits by hand this morning and 16 an hour later, both reported
    # complete, and the second set was missing WorldEdit and infoarchive -- two
    # commits we have verified by hand. So cast several nets, and note that the
    # checkpoint ACCUMULATES: re-running adds whatever the index surfaces this time
    # rather than starting over.
    stem = re.sub(r"^(set|get|add|with)", "", args.identifier)
    stem = stem[0].lower() + stem[1:] if stem else args.identifier
    queries = [args.identifier,
               f"{kw} {args.identifier}",
               f"{stem} {kw}",
               f"{kw} {stem}",
               stem]
    queries = list(dict.fromkeys(q for q in queries if q.strip()))
    seen = {}
    if args.via == "commit-search":
        for q in queries:
            items, complete = B.gh_commit_search(q, token, max_pages=args.pages)
            for it in items:
                seen[(it["repository"]["full_name"], it["sha"])] = it
            print(f"[search] q='{q}' -> {len(items)} hit(s)"
                  f"{'' if complete else '  (cut short)'}", flush=True)
        print(f"[search] {len(seen)} distinct commit(s)\n")
    else:
        # Code search finds files containing the identifier TODAY; the introducing commit
        # then comes from walking that file's history. Slower and rate-limited, but it
        # reaches repositories commit search cannot index at all -- which is how AthenZ was
        # found after a repo-scoped commit search for the identifier returned zero.
        hits = []
        for q in (f'"{args.identifier}" language:java',
                  f'"{args.identifier}" "{gid}" language:java'):
            got = code_search_files(q, token, pages=args.pages)
            print(f"[code] q={q[:52]!r} -> {len(got)} file hit(s)", flush=True)
            hits += got
            time.sleep(7)
        by_repo = {}
        for repo, path in hits:
            if is_library_repo(repo, gid, aid):
                continue
            by_repo.setdefault(repo, path)      # one file per repo is enough to date it
        print(f"[code] {len(by_repo)} candidate repo(s); dating each by file history\n")
        for i, (repo, path) in enumerate(sorted(by_repo.items()), 1):
            c = introducing_commit(repo, path, args.identifier, token)
            if c is None:
                continue
            seen[(repo, c["sha"])] = c
            print(f"  [{i}/{len(by_repo)}] {repo[:44]:46} "
                  f"{c['commit']['author']['date'][:10]}  {c['sha'][:8]}", flush=True)
        print(f"\n[code] dated {len(seen)} introducing commit(s)\n")

    # Checkpoint per commit: each row is a diff fetch, and a kill must not discard the
    # pass. Same lesson as the mine, the classify loop and the undecided resolver.
    ck = OUT / f"{args.break_id}_ADAPTATIONS.jsonl"
    done = set()
    if ck.exists():
        for line in ck.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    done.add(tuple(json.loads(line)["key"]))
                except Exception:
                    pass
        if done:
            print(f"[resume] {len(done)} commit(s) already read\n")
    fh = ck.open("a" if done else "w", encoding="utf-8")

    # Collapse forks: one commit SHA copied across many repos is one adaptation. The
    # WorldEdit fix appears in ~15 forks.
    by_sha = {}
    for (repo, sha), it in seen.items():
        by_sha.setdefault(sha, []).append((repo, it))

    results = []
    for sha, repos in by_sha.items():
        repos.sort(key=lambda ri: (is_library_repo(ri[0], gid, aid), len(ri[0])))
        repo, it = repos[0]
        if (repo, sha) in done:
            continue
        c = B._gh(f"{B.GH}/repos/{repo}/commits/{sha}", token)
        if not isinstance(c, dict) or "files" not in c:
            # A failed fetch is UNKNOWN, never "not a candidate". Recording it as a
            # negative is how a throttle becomes a finding.
            rec = {"key": [repo, sha], "verdict": "unreadable", "repo": repo, "sha": sha}
            fh.write(json.dumps(rec) + "\n"); fh.flush(); results.append(rec)
            continue
        added = []
        files = []
        for f in c.get("files", []):
            for line in (f.get("patch") or "").splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    added.append(line[1:])
            if any(args.identifier in (l or "") for l in (f.get("patch") or "").splitlines()):
                files.append(f["filename"])
        verdict, value, evidence = classify(added, args.identifier, args.default_value)
        rec = {"key": [repo, sha], "repo": repo, "sha": sha,
               "date": (c["commit"]["author"]["date"] or "")[:10],
               "message": (c["commit"]["message"] or "").splitlines()[0][:90],
               "verdict": verdict, "value": value, "evidence": evidence,
               "files": files[:3], "forks": len(repos) - 1,
               "library_confirmed": (
                   library_in_diff(added, gid)
                   if library_in_diff(added, gid) is not None else
                   (library_in_file(repo, sha, files[0], gid, args.other_group, token)
                    if files else None)),
               "files_changed": len(c.get("files", []))}
        fh.write(json.dumps(rec) + "\n"); fh.flush()
        results.append(rec)
        print(f"  [{verdict:15}] {repo[:40]:40} {rec['message'][:44]}", flush=True)
    fh.close()

    # Surface the date skew before the shortlist, not after 99 rows of triage.
    boundary_year = None
    bdate = (brk.get("verify") or {}).get("boundary_released") or ""
    if not bdate:
        import re as _re
        m = _re.search(r"(20\d\d)", str((brk.get("library") or {}).get("to_version", "")))
        bdate = m.group(1) if m else ""
    if bdate[:4].isdigit():
        boundary_year = bdate[:4]
    report_date_distribution(results, boundary_year)

    order = {"raise": 0, "needs_reading": 1, "knob_at_default": 2, "lower": 3,
             "no_call": 4, "unreadable": 5}
    results.sort(key=lambda r: (order.get(r["verdict"], 9), -(r.get("forks") or 0)))
    cand = [r for r in results if r["verdict"] in ("raise", "needs_reading")]

    lines = [f"# Adaptations to `{args.break_id}`", "",
             f"Commits touching `{args.identifier}`, classified by the VALUE they set. "
             f"The library's own default is taken as {args.default_value:,}.", "",
             "**RAISE is the only verdict that can yield a case.** A knob left at the "
             "library's default behaves identically before and after for every input size, "
             "so it cannot produce a pass/fail/pass differential; LOWER is security "
             "hardening. Measured five for five on snakeyaml, the split follows what the "
             "project is: applications raise, libraries and plugins expose a knob.", "",
             f"{len(results)} distinct commit(s) after fork collapse; "
             f"**{len(cand)} worth reading**.", "",
             "| verdict | value | repo | date | commit | forks |",
             "|---|---:|---|---|---|---:|"]
    for r in results:
        v = r.get("value")
        vs = f"{v:,}" if isinstance(v, int) else (str(v) if v else "—")
        lines.append(f"| {r['verdict']} | {vs} | `{r['repo']}` | {r.get('date','—')} "
                     f"| {r.get('message','')[:52]} | {r.get('forks') or ''} |")
    lines += ["", "## Worth reading", ""]
    for r in cand:
        lines.append(f"- **{r['repo']}@{r['sha'][:8]}** — {r.get('message','')}")
        lines.append(f"  - value: `{r.get('value')}`  files changed: {r.get('files_changed')}"
                     f"  library confirmed: {r.get('library_confirmed')}")
        if r.get("evidence"):
            ev = r["evidence"] if isinstance(r["evidence"], str) else "; ".join(r["evidence"])
            lines.append(f"  - `{ev[:150]}`")

    dest = HERE / (args.out or f"output/ADAPTATIONS_{args.break_id}.md")
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n[find] raise={sum(1 for r in results if r['verdict']=='raise')} "
          f"needs_reading={sum(1 for r in results if r['verdict']=='needs_reading')} "
          f"knob={sum(1 for r in results if r['verdict']=='knob_at_default')} "
          f"lower={sum(1 for r in results if r['verdict']=='lower')} "
          f"unreadable={sum(1 for r in results if r['verdict']=='unreadable')}")
    print(f"[find] saved -> {dest}")


if __name__ == "__main__":
    main()
