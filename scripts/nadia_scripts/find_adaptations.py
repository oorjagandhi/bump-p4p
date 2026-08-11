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

import argparse
import json
import re
import sys
from pathlib import Path

import bbc_e2e as B
from probe_population import is_library_repo, keyword_for

sys.stdout.reconfigure(encoding="utf-8")
HERE = Path(__file__).resolve().parent
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


def classify(added_lines, identifier, default_value):
    """(verdict, value, evidence) for one commit's added lines."""
    calls = [l for l in added_lines if identifier in l]
    if not calls:
        return "no_call", None, None
    for line in calls:
        m = re.search(re.escape(identifier) + r"\s*\(([^;]*)\)", line)
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
    """Confirm the diff touches THIS library.

    PerlOnJava calls setCodePointLimit too -- on org.snakeyaml:snakeyaml-engine, a
    different artifact with an analogous break. Without this check it reads as a case for
    a break it has nothing to do with.
    """
    root = group_id.split(".")[0] + "." + group_id.split(".")[-1] if "." in group_id else group_id
    hay = "\n".join(added_lines)
    if group_id.replace(":", ".") in hay or root in hay:
        return True
    return None  # unknown: the call may be in a file whose imports are unchanged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("break_id")
    ap.add_argument("--identifier", required=True,
                    help="the adaptation API, e.g. setCodePointLimit")
    ap.add_argument("--default-value", type=int, default=3 * 1024 * 1024,
                    help="the library's own default; a call setting exactly this is a knob")
    ap.add_argument("--pages", type=int, default=3, help="search pages per query (50 each)")
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
    for q in queries:
        items, complete = B.gh_commit_search(q, token, max_pages=args.pages)
        for it in items:
            seen[(it["repository"]["full_name"], it["sha"])] = it
        print(f"[search] q='{q}' -> {len(items)} hit(s)"
              f"{'' if complete else '  (cut short)'}", flush=True)
    print(f"[search] {len(seen)} distinct commit(s)\n")

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
               "library_confirmed": library_in_diff(added, gid),
               "files_changed": len(c.get("files", []))}
        fh.write(json.dumps(rec) + "\n"); fh.flush()
        results.append(rec)
        print(f"  [{verdict:15}] {repo[:40]:40} {rec['message'][:44]}", flush=True)
    fh.close()

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
