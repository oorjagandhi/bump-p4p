#!/usr/bin/env python3
"""
Did this repository CROSS the break boundary, and when?

The code-search route (discover/date_hits.py -> discover/screen_dated.py) finds clients
that call the adaptation API and dates them, but calling it proves nothing on its own:
Azure/azure-sdk-for-java added a full reflective StreamReadConstraints adaptation while
pinned to jackson 2.13.5, because azure-core supports users who bring their own newer
jackson. It never crossed. That is an adaptation without a crossing, and it is not a case.

Bisects a build file's history for the first commit whose declared version is at or past
the boundary. Bisection assumes the version only moves forward, which is true of ordinary
upgrade history and false across a repo restructure -- see `undecided` below.

Reports the three-valued outcome the census depends on, and they are NOT interchangeable:

  confirmed        the version went from below the boundary to at/past it, in this file's
                   own history. The previous value is reported so the transition can be read.
  genuine_negative the file's history never reaches the boundary, or starts already past it
                   -- the client was born beyond it and cannot have crossed.
  undecided        the version is absent at the transition (managed by a parent POM or BOM,
                   or the history is broken by a repo merge). An UNKNOWN, not a negative.
                   ICIJ/datashare lands here: jackson.version simply appears in 2024-06 when
                   datashare-api was pulled back into the repo, so the crossing, if any,
                   happened in the predecessor repository.

That last distinction earned its keep. ICIJ/datashare DID cross -- 2.12.2 -> 2.15.1 at
2368659234e2 on 2024-05-14 -- in the standalone ICIJ/datashare-api repo, whose history is
reachable only as the SECOND parent of merge 6efdf79d. This bisect walks one file on the
first-parent lineage, where the property has no history before 2024-06 and starts already
past the boundary: the exact signature of a client born past it. Reporting that as a
negative would have discarded a case that is now verified (verified_cases/jackson-core/
jackson-streamreadconstraints-datashare.json). `undecided` kept it alive for a human.

So: undecided is not a soft negative and must never be counted as one. Resolving it means
looking for a predecessor repository or a parent POM by hand.
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

import argparse, json, os, re, sys

import bbc_e2e as B


def vtuple(v):
    """'2.15.1' -> (2, 15, 1). Non-numeric suffixes are dropped, which is enough to order
    releases either side of a boundary."""
    if not v:
        return None
    nums = re.findall(r"\d+", v)
    return tuple(int(x) for x in nums[:3]) if nums else None


_XML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def strip_comments(text):
    """Remove XML comments before any regex reads a version out of a POM.

    Not cosmetic. A commented-out property is extremely common in real build files --
    someone pins a version, then comments it out and puts the live one below it -- and
    reading the dead one as live makes the version look OLDER than it is. In a boundary
    bisect that is the worst possible error: a pre-boundary version read at a post-boundary
    commit places the crossing later than it happened, or hides it entirely.
    """
    return _XML_COMMENT.sub("", text or "")


def declared_version(text, prop, artifact, keyword=None, group=None):
    """The version this build file declares, from a <property> or a direct <dependency>.

    `prop='auto'` finds the property by keyword instead of by exact name, because every
    project spells it differently -- jackson.version, jackson-core.version,
    jackson-bom.version, version.jackson. Batch runs are unusable without this.

    NOTE this is deliberately a REGEX read of one file, not a POM resolve. It answers
    "what does this file literally declare", which is what a history bisect needs, and it
    returns None rather than guessing when the value is a ${...} reference it cannot see
    through -- that None is what surfaces as `undecided`. For the full resolve, including
    parent/BOM walking, see traversal/resolve_version.py, which is a different question and
    a different function of the same name.
    """
    if not text:
        return None
    text = strip_comments(text)
    if prop == "auto":
        kw = (keyword or "jackson").lower()
        # Prefer the property the target dependency ACTUALLY references. Picking by name
        # length instead ("most specific") silently loses whenever a project keeps a legacy
        # property whose name happens to be longer than the live one -- e.g. a live
        # <jackson.version> beside a dead <jackson-bom-legacy.version>.
        referenced = set()
        for blk in re.findall(r"<dependency>(.*?)</dependency>", text, re.S):
            if artifact and not re.search(r"<artifactId>\s*" + re.escape(artifact) + r"\s*</artifactId>", blk):
                continue
            referenced.update(re.findall(r"<version>\s*\$\{([\w.\-]+)\}\s*</version>", blk))
        best = None
        for name, val in re.findall(r"<([\w.\-]+)>\s*([^<\s]+)\s*</\1>", text):
            n = name.lower()
            if kw in n and "version" in n and not val.startswith("${"):
                rank = (1 if name in referenced else 0, len(name))
                if best is None or rank > best[0]:
                    best = (rank, val)
        if best:
            return best[1]
    elif prop:
        m = re.search(r"<" + re.escape(prop) + r">\s*([^<]+?)\s*</", text)
        if m and not m.group(1).startswith("${"):
            return m.group(1)
    if artifact:
        # Match inside a single <dependency> block so the groupId can be checked. Matching
        # artifactId alone attributes a repackaged fork's version to the real library.
        for blk in re.findall(r"<dependency>(.*?)</dependency>", text, re.S):
            if not re.search(r"<artifactId>\s*" + re.escape(artifact) + r"\s*</artifactId>", blk):
                continue
            if group:
                g = re.search(r"<groupId>\s*([^<]+?)\s*</groupId>", blk)
                if g and g.group(1) != group:
                    continue
            v = re.search(r"<version>\s*([^<$][^<]*?)\s*</version>", blk)
            if v:
                return v.group(1)
        if group:
            # A groupId was demanded and no <dependency> block satisfied it. Falling back
            # to the loose scan below would re-admit exactly what the check just rejected.
            return None
        m = re.search(r"<artifactId>\s*" + re.escape(artifact) +
                      r"\s*</artifactId>\s*<version>\s*([^<$][^<]*?)\s*</version>", text)
        if m:
            return m.group(1)
    return None


def path_commits(repo, path, token, max_pages=8):
    out, page = [], 1
    while True:
        b = B._gh(f"{B.GH}/repos/{repo}/commits", token, path=path, per_page=100, page=page)
        if not isinstance(b, list) or not b:
            break
        out += b
        if len(b) < 100 or page >= max_pages:
            break
        page += 1
    return list(reversed(out))          # oldest first


def find_crossing(repo, path, prop, artifact, boundary, token, keyword=None, group=None):
    commits = path_commits(repo, path, token)
    if not commits:
        return {"repo": repo, "outcome": "undecided", "why": f"no commits at {path}"}

    bt = vtuple(boundary)
    at = lambda c: vtuple(declared_version(
        B._gh_file(repo, path, c["sha"], token), prop, artifact, keyword, group))

    lo, hi, first = 0, len(commits) - 1, None
    while lo <= hi:                     # first commit at/past the boundary
        mid = (lo + hi) // 2
        v = at(commits[mid])
        if v and v >= bt:
            first, hi = mid, mid - 1
        else:
            lo = mid + 1

    res = {"repo": repo, "path": path, "commits_at_path": len(commits)}
    if first is None:
        # "never reaches the boundary" and "never declares a version here at all" look
        # identical to the bisection and are NOT the same finding. Azure declares jackson
        # in eng/versioning/external_dependencies.txt, not the root pom; Confluent projects
        # inherit it from a parent. Calling that a measured negative is precisely the error
        # the census exists to prevent, so sample the ends before deciding.
        seen = [declared_version(B._gh_file(repo, path, c["sha"], token),
                                 prop, artifact, keyword, group)
                for c in (commits[-1], commits[len(commits) // 2], commits[0])]
        latest = seen[0]        # commits is oldest-first, so commits[-1] is the newest
        if latest is None:
            # Either never declared here, or declared once and since moved to a parent/BOM.
            # Both mean this file cannot answer the question.
            ever = next((s for s in seen if s), None)
            res.update(outcome="undecided",
                       why=(f"no version declared in {path} at the latest commit "
                            + (f"(seen {ever} earlier) " if ever else "or at any point ")
                            + "-- parent/BOM-managed or declared in another file. "
                              "An UNKNOWN, not a negative."))
        else:
            res.update(outcome="genuine_negative",
                       why=f"declared here (latest: {latest}) but never reaches the boundary")
        return res

    c = commits[first]
    res["crossed_at"] = {"sha": c["sha"][:12],
                         "date": c["commit"]["author"]["date"][:10],
                         "message": c["commit"]["message"].splitlines()[0][:100],
                         "version": declared_version(
                             B._gh_file(repo, path, c["sha"], token), prop, artifact,
                             keyword, group)}
    if first == 0:
        res.update(outcome="genuine_negative",
                   why="the file's oldest commit is already past the boundary "
                       "(client born beyond it)")
        return res

    prev_raw = declared_version(B._gh_file(repo, path, commits[first - 1]["sha"], token),
                               prop, artifact, keyword, group)
    res["previous_version"] = prev_raw
    if prev_raw is None:
        res.update(outcome="undecided",
                   why="no version declared just before the transition -- parent/BOM-managed, "
                       "or the history is broken by a repo merge. An UNKNOWN, not a negative.")
    else:
        res.update(outcome="confirmed",
                   why=f"{prev_raw} -> {res['crossed_at']['version']} crosses {boundary}")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repos", nargs="+", help="owner/name, repeatable")
    ap.add_argument("--path", default="pom.xml", help="build file to walk")
    ap.add_argument("--property", dest="prop", help="version property, e.g. jackson.version")
    ap.add_argument("--artifact", help="artifactId, for a directly-declared version")
    ap.add_argument("--group", help="groupId; with --artifact, rejects a repackaged "
                                    "fork that reuses the artifactId")
    ap.add_argument("--keyword", help="with --property auto, the library keyword to look "
                                      "for in property names (default: jackson)")
    ap.add_argument("--boundary", required=True, help="e.g. 2.15.0")
    ap.add_argument("--out", help="append results as JSONL")
    args = ap.parse_args()

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GH_TOKEN required")
    if not (args.prop or args.artifact):
        sys.exit("give --property or --artifact")

    results = []
    for repo in args.repos:
        try:
            r = find_crossing(repo, args.path, args.prop, args.artifact,
                              args.boundary, token, args.keyword, args.group)
        except Exception as e:
            r = {"repo": repo, "outcome": "error", "why": f"{type(e).__name__}: {e}"[:200]}
        results.append(r)
        print(f"\n{repo}  ->  {r['outcome'].upper()}")
        print(f"   {r.get('why','')}")
        if r.get("crossed_at"):
            c = r["crossed_at"]
            print(f"   at {c['sha']} {c['date']}  version={c['version']} "
                  f"(was {r.get('previous_version')})")
            print(f"   msg: {c['message']}")
        sys.stdout.flush()

    if args.out:
        with open(args.out, "a", encoding="utf-8") as fh:
            for r in results:
                fh.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
