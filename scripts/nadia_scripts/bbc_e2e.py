"""
bbc_e2e.py
──────────
End-to-end orchestrator for the BBC → external-production-adaptation workflow we
validated by hand on xstream/TVRenamer. It automates the DETERMINISTIC stages and
leaves clearly-marked seams for the two AI/human JUDGMENT stages.

Flow (each stage a subcommand), driven by specs/bump_breaks_catalog.json:

  characterize <break_id>          [deterministic]  failing test + signal from BUMP
                                                    (delegates to bbc_pipeline.characterize)
  mine-commits <break_id>          [deterministic]  GitHub COMMIT search for adaptation
                                                    commits (the winning tool for
                                                    bump-TRIGGERED fixes), per the
                                                    break's mining.commit_search_terms
  classify <repo> <sha> <break_id> [deterministic]  split a commit's files into
                                                    production (src/main) vs test, read
                                                    the dependency version at the commit
                                                    and its parent (transition), and
                                                    detect the build system. SCOPE: we
                                                    only VERIFY Maven clients (is_maven /
                                                    verifiable) — the harness is Maven, so
                                                    Gradle/sbt candidates are flagged and
                                                    de-prioritised, not verified.
  gen-harness <break_id> --repo --adapt-sha --parent-sha --out
                                   [scaffold]       emit a Maven harness (pom.xml),
                                                    a run_differential.sh, and a TEST
                                                    STUB derived from the BUMP failing
                                                    test — the stub body is the JUDGMENT
                                                    seam an agent/human completes
  run <break_id>                   [orchestration]  characterize -> mine -> classify,
                                                    printing production candidates ready
                                                    for gen-harness + verify

JUDGMENT seams (an AI agent or human supplies these; everything else is plumbing):
  • root_cause / affected_usage         — read from characterize output (spec.*)
  • mining.commit_search_terms          — the adaptation signature to search for
  • the generated test's BODY           — how to exercise the affected production path
                                          (gen-harness emits a stub + the characterization)

Env: GH_TOKEN required for mine-commits / classify (GitHub search + contents API).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

from bbc_pipeline import _clean_log, characterize  # reuse hardened log parsing

try:  # commit messages can contain non-cp1252 chars (e.g. CJK) on Windows
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = Path(__file__).resolve().parent
CATALOG = HERE / "specs" / "bump_breaks_catalog.json"
GH = "https://api.github.com"
_GH_CACHE = {}


# ── catalog helpers ─────────────────────────────────────────────────────────────

def load_catalog():
    return json.loads(CATALOG.read_text(encoding="utf-8"))


def get_break(break_id):
    for b in load_catalog()["breaks"]:
        if b["break_id"] == break_id:
            return b
    sys.exit(f"break_id '{break_id}' not in {CATALOG.name}. "
             f"Known: {[b['break_id'] for b in load_catalog()['breaks']]}")


def _token():
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not tok:
        sys.exit("set GH_TOKEN (GitHub search + contents API need auth)")
    return tok


def _gh(url, token, **params):
    key = (url, tuple(sorted(params.items())))
    if key in _GH_CACHE:
        return _GH_CACHE[key]
    headers = {"Authorization": f"Bearer {token}",
               "Accept": "application/vnd.github+json"}
    data = None
    for attempt in range(5):
        # requests.get was previously UNWRAPPED, so a single transient network error
        # propagated and killed the whole run. A deep mine makes thousands of calls
        # over hours; a connection reset is not exceptional, it is expected. One
        # ConnectionResetError destroyed a full 32-term xstream search this way.
        try:
            r = requests.get(url, headers=headers, params=params, timeout=30)
        except requests.exceptions.RequestException as e:
            if attempt == 4:
                print(f"[github] network error, giving up after {attempt + 1} tries: "
                      f"{type(e).__name__}", file=sys.stderr)
                return None
            wait = min(5 * (2 ** attempt), 60)
            print(f"[github] {type(e).__name__}; retry {attempt + 1}/5 in {wait}s",
                  file=sys.stderr)
            time.sleep(wait)
            continue
        try:
            data = r.json()
        except Exception:
            data = {"message": r.text[:500]}
        # List endpoints (/commits, /compare's commits, /pulls) return a JSON ARRAY,
        # which has no .get() — calling it raised AttributeError on every successful
        # list response. find_boundary_bump swallowed that in a bare `except`, so
        # traversal silently saw zero commits and could never confirm ANY candidate.
        msg = str(data.get("message", "")) if isinstance(data, dict) else ""
        secondary = "secondary rate limit" in msg.lower()
        if r.status_code == 200:
            _GH_CACHE[key] = data
            return data
        if r.status_code in (403, 429) and secondary:
            wait = int(os.environ.get("BBC_GH_SECONDARY_WAIT", "60")) * (attempt + 1)
            print(f"[github] secondary rate limit; sleeping {wait}s before retry", file=sys.stderr)
            time.sleep(wait)
            continue
        if r.status_code in (500, 502, 503, 504):
            wait = min(10 * (attempt + 1), 60)
            print(f"[github] transient {r.status_code}; sleeping {wait}s before retry", file=sys.stderr)
            time.sleep(wait)
            continue
        _GH_CACHE[key] = data
        return data
    _GH_CACHE[key] = data
    return data


def _library_keyword(brk):
    m = brk.get("mining", {})
    if m.get("library_keyword"):
        return m["library_keyword"]
    # default: the artifact id's most distinctive token
    return brk["library"]["artifact_id"].split("-")[0]


def _repo_meta(repo, token):
    d = _gh(f"{GH}/repos/{repo}", token)
    return d if isinstance(d, dict) and "full_name" in d else None


def _prefer_repo(cand, cur, token):
    """Which of two repos holding the SAME commit is the better representative?
    Upstream beats fork, then more stars, then older (the origin, not the mirror)."""
    c, u = _repo_meta(cand, token), _repo_meta(cur, token)
    if not c:
        return False
    if not u:
        return True
    def key(m):
        return (bool(m.get("fork")), -(m.get("stargazers_count") or 0),
                m.get("created_at") or "9999")
    return key(c) < key(u)


def _dedup_by_commit(rows, token):
    """Collapse fork armies: ONE row per commit SHA. The same commit reached through
    N forks/mirrors is one adaptation, not N. Measured on the existing output this
    was 19% of all candidate rows (68% on commons-io, where 32 forks of one repo
    shared a single SHA and consumed the whole classify budget). Repo metadata is
    fetched only for SHAs that actually collide, so the common case costs nothing."""
    counts = {}
    for r in rows:
        counts[r["sha"]] = counts.get(r["sha"], 0) + 1
    out, pos = [], {}
    for r in rows:
        sha = r["sha"]
        if sha not in pos:
            pos[sha] = len(out)
            out.append(r)
            continue
        if counts[sha] > 1 and _prefer_repo(r["repo"], out[pos[sha]]["repo"], token):
            keep = dict(r)
            # keep the better-RANKED source/term of the row we're replacing
            keep["source"] = out[pos[sha]]["source"]
            keep["matched_term"] = out[pos[sha]]["matched_term"]
            out[pos[sha]] = keep
    dropped = len(rows) - len(out)
    if dropped:
        print(f"[mine-commits] fork/mirror dedup: collapsed {dropped} duplicate row(s) "
              f"-> {len(out)} distinct commits")
    return out


# ── stage 2: mine-commits (COMMIT search) ───────────────────────────────────────

# A deep mine is 32 queries over several hours and, before this, held every result
# in memory until the very end. A ConnectionResetError in _dedup_by_commit — which
# runs AFTER all searching is done — threw away a completed 32-term xstream run.
# The retry wrapper in _gh narrows that window but cannot close it: any failure
# downstream of the search loop still costs the whole mine. So the search loop now
# checkpoints to disk as it goes and resumes from where it stopped.

def _checkpoint_path(brk):
    return HERE / "output" / f"{brk['break_id']}_mine_checkpoint.jsonl"


def _load_checkpoint(path):
    """(rows, done_terms, seeds) from an interrupted mine; empties if there is none."""
    if not path.exists():
        return [], set(), []
    rows, done, seeds, seeds_done = [], set(), [], set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue  # a torn final line from a hard kill — drop it, keep the rest
        if "_term_done" in rec:
            done.add(rec["_term_done"])
        elif "_bump_seed" in rec:
            seeds.append(rec["_bump_seed"])
        elif "_seed_done" in rec:
            seeds_done.add(rec["_seed_done"])
        else:
            rows.append(rec)
    return rows, done, [s for s in seeds if s["sha"] not in seeds_done]


def _ck(fh, rec):
    fh.write(json.dumps(rec) + "\n")
    fh.flush()


def gh_commit_search(query, token, max_pages=None):
    """Search commit MESSAGES. This is what surfaces bump-triggered fixes
    ('Fix XStream security exception', 'resolve ForbiddenClassException', …) —
    far better than code search for finding the ADAPTATION rather than mere usage.

    Returns (items, complete). `complete` is False when the term was cut short by a
    network or API failure rather than by running out of results, so the caller can
    avoid checkpointing it as done and retry it on the next resume."""
    max_pages = max_pages or int(os.environ.get("BBC_SEARCH_PAGES", "3"))
    out, page = [], 1
    while page <= max_pages:
        data = _gh(f"{GH}/search/commits", token, q=query, per_page=50, page=page)
        if not isinstance(data, dict):
            # network died on all retries — abandon this term, keep the run alive.
            print(f"[mine-commits] search failed for q='{query}' page {page}; "
                  f"skipping the rest of this term", file=sys.stderr)
            return out, False
        items = data.get("items")
        if items is None:
            print(f"[mine-commits] API: {data.get('message')}", file=sys.stderr)
            return out, False
        out.extend(items)
        if len(items) < 50:
            break
        page += 1
    return out, True


def _row_from_search_item(it, matched_term, source):
    return {"repo": it["repository"]["full_name"],
            "sha": it["sha"],
            "message": it["commit"]["message"].splitlines()[0][:80],
            "matched_term": matched_term,
            "source": source}


def _row_from_commit(repo, commit, matched_term, source):
    return {"repo": repo,
            "sha": commit["sha"],
            "message": commit["commit"]["message"].splitlines()[0][:80],
            "matched_term": matched_term,
            "source": source}


def _forward_commits_from_seed(repo, seed_sha, default_branch, token, limit):
    """Return commits after a direct bump seed on the default branch.
    GitHub compare returns commits oldest-first, which is ideal for finding
    nearby post-merge fixes before wandering too far into unrelated history."""
    if limit <= 0:
        return []
    base = quote(seed_sha, safe="")
    head = quote(default_branch or "HEAD", safe="")
    cmp = _gh(f"{GH}/repos/{repo}/compare/{base}...{head}", token)
    if not isinstance(cmp, dict) or "commits" not in cmp:
        return []
    status = cmp.get("status")
    # 'ahead' = the seed IS an ancestor of the default branch, so the commits that
    # follow it are the client's real history. 'diverged' means the seed never
    # merged (abandoned PR / dependabot branch) — scanning forward from it would
    # attribute unrelated default-branch commits to a bump that never landed.
    if status != "ahead":
        return []
    return cmp.get("commits", [])[:limit]


def mine_commits(brk, token):
    mining = brk.get("mining", {})
    adaptation_terms = mining.get("commit_search_terms") or []
    bump_terms = mining.get("direct_bump_search_terms") or []
    mode = os.environ.get("BBC_SEARCH_MODE", "balanced").lower()
    if mode == "bump":
        terms = bump_terms or adaptation_terms
    elif mode == "adaptation":
        terms = adaptation_terms
    else:
        terms = bump_terms + adaptation_terms
    terms = list(dict.fromkeys(terms))
    term_limit = int(os.environ.get("BBC_TERM_LIMIT", "0"))
    if term_limit > 0:
        terms = terms[:term_limit]
    if not terms:
        sys.exit(f"break '{brk['break_id']}' has no mining terms; fill mining.commit_search_terms or mining.direct_bump_search_terms")
    kw = _library_keyword(brk)
    seen, rows = set(), []
    expand_bumps = os.environ.get("BBC_EXPAND_BUMP_SEEDS", "1").lower() not in ("0", "false", "no")
    bump_seed_limit = int(os.environ.get("BBC_BUMP_SEED_LIMIT", "25"))
    forward_limit = int(os.environ.get("BBC_FORWARD_SCAN_COMMITS", "40"))

    ckpt = _checkpoint_path(brk)
    ckpt.parent.mkdir(exist_ok=True)
    resume = os.environ.get("BBC_RESUME", "1").lower() not in ("0", "false", "no")
    done_terms, bump_seeds = set(), []
    if resume:
        prior, done_terms, bump_seeds = _load_checkpoint(ckpt)
        for r in prior:
            key = (r["repo"], r["sha"])
            if key not in seen:
                seen.add(key)
                rows.append(r)
        if rows or done_terms:
            print(f"[mine-commits] resuming from {ckpt.name}: {len(rows)} row(s), "
                  f"{len(done_terms)}/{len(terms)} term(s) already searched, "
                  f"{len(bump_seeds)} seed(s) still to expand", flush=True)
    # The checkpoint is NEVER auto-deleted: a crash in any later stage (classify,
    # traversal) must not cost the search again. Pass BBC_RESUME=0 to start clean.
    ck = ckpt.open("a" if resume else "w", encoding="utf-8")

    for term in terms:
        q = f"{kw} {term}"
        if term in done_terms:
            print(f"[mine-commits] q='{q}' (checkpointed)", flush=True)
            continue
        print(f"[mine-commits] q='{q}'", flush=True)
        items, complete = gh_commit_search(q, token)
        for it in items:
            repo = it["repository"]["full_name"]
            sha = it["sha"]
            if (repo, sha) in seen:
                continue
            seen.add((repo, sha))
            source = "direct_bump_search" if term in bump_terms else "adaptation_search"
            row = _row_from_search_item(it, term, source)
            rows.append(row)
            _ck(ck, row)
            if expand_bumps and term in bump_terms and len(bump_seeds) < bump_seed_limit:
                seed = {"repo": repo, "sha": sha, "term": term,
                        "branch": it["repository"].get("default_branch") or "HEAD"}
                bump_seeds.append(seed)
                _ck(ck, {"_bump_seed": seed})
        # Only a cleanly-finished term is checkpointed as done. A term cut short by a
        # network failure stays unmarked so the next resume searches it again —
        # marking it would silently bake a partial result into the corpus.
        if complete:
            _ck(ck, {"_term_done": term})
        else:
            print(f"[mine-commits] q='{q}' incomplete; will retry on resume", flush=True)

    if expand_bumps and bump_seeds and mode != "adaptation":
        print(f"[mine-commits] expanding {len(bump_seeds)} bump seed(s), "
              f"{forward_limit} later commit(s) each", flush=True)
        for seed in bump_seeds:
            repo, term = seed["repo"], seed["term"]
            for commit in _forward_commits_from_seed(repo, seed["sha"], seed["branch"],
                                                     token, forward_limit):
                sha = commit["sha"]
                if (repo, sha) in seen:
                    continue
                seen.add((repo, sha))
                row = _row_from_commit(repo, commit, term, "bump_forward_scan")
                rows.append(row)
                _ck(ck, row)
            _ck(ck, {"_seed_done": seed["sha"]})
    ck.close()
    if mode == "bump":
        rank = {"bump_forward_scan": 0, "direct_bump_search": 1, "adaptation_search": 2}
    else:
        rank = {"adaptation_search": 0, "bump_forward_scan": 1, "direct_bump_search": 2}
    rows.sort(key=lambda r: rank.get(r.get("source"), 9))
    if os.environ.get("BBC_DEDUP_FORKS", "1").lower() not in ("0", "false", "no"):
        rows = _dedup_by_commit(rows, token)
    per_repo_cap = int(os.environ.get("BBC_MAX_ROWS_PER_REPO", "6"))
    if per_repo_cap > 0:
        counts, capped = {}, []
        for row in rows:
            repo = row["repo"]
            if counts.get(repo, 0) >= per_repo_cap:
                continue
            counts[repo] = counts.get(repo, 0) + 1
            capped.append(row)
        rows = capped
    print(f"[mine-commits] {len(rows)} distinct commits across {len({r['repo'] for r in rows})} repos")
    return rows


BUILD_FILES = ["pom.xml", "build.gradle", "build.gradle.kts", "build.sbt", "ivy.xml"]

# How many mined commits to classify per break. Each classify is a few GitHub API
# calls, so keep this overridable for rate-limit-sensitive runs.
CLASSIFY_CAP = int(os.environ.get("BBC_CLASSIFY_CAP", "200"))
MAVEN_JAVA_ONLY = os.environ.get("BBC_MAVEN_JAVA_ONLY", "1").lower() not in ("0", "false", "no")
REQUIRE_TRAVERSAL = os.environ.get("BBC_REQUIRE_TRAVERSAL", "1").lower() not in ("0", "false", "no")


def _module_poms(prod_files):
    """Module pom.xml path for each changed production file (the dir just above 'src/').
    'mailextractlib/src/main/java/.../StoreExtractor.java' -> 'mailextractlib/pom.xml'.
    One pom per file (not every ancestor dir — that explodes the GitHub API calls);
    the module root is where a multi-module repo declares its deps. Root 'pom.xml' is
    still tried afterwards via BUILD_FILES. Deduped, order-preserving."""
    out = []
    for fn in prod_files or []:
        parts = fn.split("/")
        if "src" in parts:
            i = parts.index("src")
            cand = ("/".join(parts[:i]) + "/pom.xml") if i > 0 else "pom.xml"
        else:
            cand = (parts[0] + "/pom.xml") if len(parts) > 1 else "pom.xml"
        if cand not in out and cand != "pom.xml":   # root handled by BUILD_FILES
            out.append(cand)
    return out


_SRC_EXT = (".java",)


def _is_test_path(fn):
    return "src/test/" in fn or "/test/" in fn or re.search(r"(Test|IT|Spec)\.java$", fn)


def _is_prod_java(fn):
    return fn.endswith(_SRC_EXT) and not _is_test_path(fn) and (
        "src/main/" in fn or "src/java/" in fn or "src/" not in fn)


def _is_library_source(repo, prod_files, group_id, artifact_id):
    """Distinguish a client CALL from the library's own DEFINITION. Filters the
    'vendored/forked library source' false positive (e.g. apache/poi and its forks
    match a POI-API commit search, but the changed file IS the API, not a use of it)."""
    group_path = group_id.replace(".", "/")               # org.apache.poi -> org/apache/poi
    # (a) a changed file sits in the library's OWN package under src/main -> it's the lib
    if any(f"src/main/java/{group_path}" in f or f"src/java/{group_path}" in f
           for f in prod_files):
        return True
    # (b) the repo itself is (a fork of) the artifact
    base = artifact_id.split("-")[0].lower()               # poi-ooxml -> poi
    leaf = repo.split("/")[-1].lower()
    if leaf == base or leaf.endswith(base) or base in leaf:
        return True
    return False


def _maven_properties(text):
    """Extract <properties> name->value pairs (for resolving ${...} version refs)."""
    props = {}
    for sec in re.findall(r"<properties>(.*?)</properties>", text, re.S):
        for name, val in re.findall(r"<([\w.\-]+)>\s*([^<]+?)\s*</\1>", sec):
            props[name] = val.strip()
    return props


def _resolve_prop(value, props, depth=0):
    """Resolve a Maven ${prop} placeholder against <properties>. Returns a concrete
    version string, or None if it can't be resolved (unknown/derived property).
    ${project.version} & friends are treated as unresolvable (None), not guessed."""
    value = value.strip()
    m = re.fullmatch(r"\$\{([\w.\-]+)\}", value)
    if not m:
        return value if value and value[0].isdigit() else None
    key = m.group(1)
    if key not in props or depth > 4:
        return None          # parent/BOM/derived property -> honestly unconfirmed
    return _resolve_prop(props[key], props, depth + 1)


def dep_version(text, group_id, artifact_id):
    """Best-effort read of the dependency version from pom.xml or gradle text.

    Handles the three shapes that previously returned None on real repos:
    - Maven property versions  <version>${poi.version}</version>  -> resolved via <properties>
    - version-less (parent/BOM-managed) blocks                    -> None (honest 'unconfirmed')
    - avoids cross-dependency bleed by scoping <version> to the artifact's OWN
      <dependency> block, not the nearest following <version> anywhere in the file.
    """
    if text is None:
        return None
    # gradle: 'group:artifact:1.2.3'  or  "group:artifact:1.2.3"
    m = re.search(rf"{re.escape(group_id)}:{re.escape(artifact_id)}:([0-9][\w.\-]*)", text)
    if m:
        return m.group(1)
    # gradle legacy: name: 'artifact', version: '1.2.3'
    m = re.search(rf"name:\s*['\"]{re.escape(artifact_id)}['\"].*?version:\s*['\"]([0-9][\w.\-]*)['\"]",
                  text, re.S)
    if m:
        return m.group(1)
    # maven: scan each <dependency> block so the <version> we read is THIS artifact's,
    # then resolve ${...} against <properties>.
    props = _maven_properties(text)
    for block in re.findall(r"<dependency>(.*?)</dependency>", text, re.S):
        if not re.search(rf"<artifactId>\s*{re.escape(artifact_id)}\s*</artifactId>", block):
            continue
        gid = re.search(r"<groupId>\s*([^<]+?)\s*</groupId>", block)
        if gid and gid.group(1).strip() != group_id:
            continue                                   # same artifactId, different group
        vm = re.search(r"<version>\s*([^<]+?)\s*</version>", block)
        if not vm:
            return None                                # parent/BOM-managed -> unconfirmed
        return _resolve_prop(vm.group(1), props)
    return None


# ── content evidence: does the diff actually TOUCH the library? ─────────────────
#
# Commit-message search already proves an adaptation_search hit is about the library.
# The bump_forward_scan does NOT: it emits every commit in a window after a bump, so
# without this check any production .java change near a bump becomes a "candidate".
# Requiring the ADDED/REMOVED lines to import the library or name one of its API
# symbols is what makes the forward scan usable as a recall path — it finds the
# adaptations whose commit message never mentions the library at all.

_STOP_TERMS = {"bump", "upgrade", "update", "fix", "security", "cve", "dependency"}


def _library_patterns(brk):
    """(import_pattern, symbol_pattern) built from the catalog entry. Package
    prefixes come from mining.package_prefixes if set, else the group id and the
    library keyword (they diverge for e.g. com.h2database -> org.h2). Symbols are
    the Java-identifier-shaped commit_search_terms — 'allowTypes',
    'AnyTypePermission', 'ForbiddenClassException' — not the prose ones."""
    lib, mining = brk["library"], brk.get("mining", {})
    prefixes = mining.get("package_prefixes") or [lib["group_id"], _library_keyword(brk)]
    alts = "|".join(re.escape(p) for p in dict.fromkeys(p for p in prefixes if p))
    imp = re.compile(rf"import\s+(?:static\s+)?[\w.]*\b(?:{alts})\b[\w.]*", re.I)
    syms = mining.get("symbol_terms") or [
        t for t in mining.get("commit_search_terms", [])
        if re.fullmatch(r"[A-Za-z_][\w.]{3,}", t)
        and any(ch.isupper() for ch in t)
        and t.lower() not in _STOP_TERMS]
    sym = re.compile("|".join(re.escape(s) for s in syms)) if syms else None
    return imp, sym


def _changed_lines_only(patch):
    """Strip unified-diff context. Searching the raw patch false-positives on
    unchanged surrounding code that merely happens to mention the library."""
    return "\n".join(ln[1:] for ln in patch.splitlines()
                     if ln[:1] in "+-" and not ln.startswith(("+++", "---")))


def _references_library(patch, pats):
    if not patch:
        return False
    changed = _changed_lines_only(patch)
    imp, sym = pats
    return bool(imp.search(changed) or (sym and sym.search(changed)))


def reachable_from_default(repo, sha, token):
    """The dependabot-branch trap: GitHub commit search returns commits on ANY
    branch, including branches that never merged. Require the commit to be an
    ancestor of (or identical to) the default-branch tip. Returns None when the
    comparison is unavailable — unknown, so never silently rejected."""
    dflt = (_repo_meta(repo, token) or {}).get("default_branch") or "HEAD"
    cmp = _gh(f"{GH}/repos/{repo}/compare/{quote(sha, safe='')}..."
              f"{quote(dflt, safe='')}", token)
    if not isinstance(cmp, dict) or "status" not in cmp:
        return None
    return cmp["status"] in ("ahead", "identical")


def classify_commit(repo, sha, brk, token, source=None):
    commit = _gh(f"{GH}/repos/{repo}/commits/{sha}", token)
    # _gh returns None when the network failed on all 5 attempts. `"files" not in None`
    # raises TypeError, which would kill a whole classify pass over hundreds of
    # candidates for one unreachable commit. Report it as a per-candidate error.
    if not isinstance(commit, dict):
        return {"error": "github unreachable"}
    if "files" not in commit:
        return {"error": commit.get("message", "no files")}
    files = [f["filename"] for f in commit["files"]]
    prod = [f for f in files if _is_prod_java(f)]
    test = [f for f in files if _is_test_path(f)]
    parent = commit["parents"][0]["sha"] if commit.get("parents") else None

    gid, aid = brk["library"]["group_id"], brk["library"]["artifact_id"]
    ver_at = ver_parent = None
    # Search the MODULE pom nearest each changed prod file first (multi-module repos declare
    # the dep in the module, not root), then root build files. First hit wins.
    for bf in _module_poms(prod) + BUILD_FILES:
        at = _gh_file(repo, bf, sha, token)
        v = dep_version(at, gid, aid)
        if v:
            ver_at = v
            if parent:
                ver_parent = dep_version(_gh_file(repo, bf, parent, token), gid, aid)
            break

    lib_source = _is_library_source(repo, prod, gid, aid)
    build_system = _detect_build_system(repo, sha, token)

    # content evidence (P1): which changed prod files actually touch the library
    pats = _library_patterns(brk)
    referencing = {f["filename"] for f in commit["files"]
                   if _references_library(f.get("patch"), pats)}
    ref_prod = [f for f in prod if f in referencing]
    # A commit found by adaptation_search already carries message evidence; one
    # found by a bump forward-scan or a bare bump-term search carries none, so it
    # must show content evidence to count.
    has_message = source in (None, "adaptation_search")
    has_content = bool(ref_prod)
    evidence = ("message+content" if (has_message and has_content)
                else "content" if has_content
                else "message" if has_message else "none")

    # branch reachability (P2) — only worth an API call for real prod candidates
    reach = None
    if prod and not lib_source:
        reach = reachable_from_default(repo, sha, token)

    is_fork = bool((_repo_meta(repo, token) or {}).get("fork")) if prod else False
    return {
        "repo": repo, "sha": sha, "parent": parent,
        "message": commit["commit"]["message"].splitlines()[0][:80],
        "production_files": prod,
        "test_files": test,
        "library_referenced_files": ref_prod,
        "evidence": evidence,                  # message | content | message+content | none
        "source": source,
        "repo_is_fork": is_fork,
        "reachable_from_default": reach,       # True | False | None (unknown)
        "library_source": lib_source,
        "build_system": build_system,          # maven | gradle | sbt | unknown
        "is_maven": build_system == "maven",   # verification scope: Maven only
        "is_production_adaptation": bool(prod) and not lib_source,
        "verifiable": (bool(prod) and not lib_source and build_system == "maven"
                       and evidence != "none" and reach is not False),
        "test_only": bool(test) and not prod,
        "version_at_commit": ver_at,
        "version_at_parent": ver_parent,
        "version_changed_here": bool(ver_at and ver_parent and ver_at != ver_parent),
    }


def _detect_build_system(repo, ref, token):
    """We only VERIFY Maven clients (the harness is Maven). Detect the build system
    so non-Maven candidates (Gradle/sbt) can be flagged and de-prioritised."""
    for fname, system in [("pom.xml", "maven"), ("build.sbt", "sbt"),
                          ("build.gradle", "gradle"), ("build.gradle.kts", "gradle")]:
        if _gh_file(repo, fname, ref, token) is not None:
            return system
    return "unknown"


def _gh_file(repo, path, ref, token):
    import base64
    d = _gh(f"{GH}/repos/{repo}/contents/{path}", token, ref=ref)
    if isinstance(d, dict) and d.get("content"):
        try:
            return base64.b64decode(d["content"]).decode("utf-8", "replace")
        except Exception:
            return None
    return None


def find_dep_version_decl(pom_text, group_id, artifact_id):
    """How is the target dependency's version declared? Returns
    ('property', name) | ('literal', value) | (None, None). Lets the reuse-pom
    harness override ONLY the baseline version, whichever way it's written."""
    if not pom_text:
        return (None, None)
    m = re.search(rf"<groupId>\s*{re.escape(group_id)}\s*</groupId>\s*"
                  rf"<artifactId>\s*{re.escape(artifact_id)}\s*</artifactId>\s*"
                  rf"<version>\s*([^<]+?)\s*</version>", pom_text, re.S)
    if not m:
        return (None, None)
    v = m.group(1).strip()
    pm = re.match(r"\$\{([^}]+)\}", v)
    return ("property", pm.group(1)) if pm else ("literal", v)


def pom_java_release(pom_text):
    """Read the repo's Java level from its pom (release/target/source) -> '8','11','17'."""
    for tag in ("maven.compiler.release", "maven.compiler.target", "maven.compiler.source"):
        m = re.search(rf"<{tag}>\s*([0-9.]+)\s*</{tag}>", pom_text or "")
        if m:
            return m.group(1).split(".")[-1]
    return None


# ── stage 5: gen-harness (Maven pom + differential runner + test STUB) ──────────

POM_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!-- AUTO-GENERATED Maven harness for the {break_id} BBC differential.
     Compiles the target repo's untouched production source and runs ONE authored
     test; the dependency version is parameterised via -D{prop}. -->
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>bbc.harness</groupId>
  <artifactId>{artifact}-bbc-harness</artifactId>
  <version>1.0</version>
  <properties>
    <maven.compiler.release>{java}</maven.compiler.release>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <{prop}>{to_version}</{prop}>
  </properties>
  <dependencies>
    <dependency>
      <groupId>{group_id}</groupId>
      <artifactId>{artifact_id}</artifactId>
      <version>${{{prop}}}</version>
    </dependency>
    <dependency>
      <groupId>junit</groupId><artifactId>junit</artifactId>
      <version>4.13.2</version><scope>test</scope>
    </dependency>
    <!-- TODO(JUDGMENT): add the repo's OTHER compile deps so src/main compiles
         (copy from its pom.xml / build.gradle). -->
  </dependencies>
  <build>
    <sourceDirectory>src/main/java</sourceDirectory>
    <testSourceDirectory>src/test/java</testSourceDirectory>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-surefire-plugin</artifactId><version>3.2.5</version>
        <configuration>
          <includes><include>**/{test_class}.java</include></includes>
          <argLine>{add_opens}</argLine>
        </configuration>
      </plugin>
    </plugins>
  </build>
</project>
"""

TEST_STUB = """package {test_pkg};

import static org.junit.Assert.*;
import org.junit.Test;

/**
 * AUTO-GENERATED STUB for the {break_id} BBC differential.
 *
 * Derived from the BUMP failing test:
 *   {bump_failing_test}
 * Break signal: {signal}
 * What changed: {brief_what_changed}
 * Expected state-2 signal: {brief_expected_signal}
 *
 * JUDGMENT SEAM — an agent/human must complete the body so it exercises the
 * AFFECTED PRODUCTION PATH (not a test-only reimplementation): call the client's
 * real production entry point that triggers the library's changed behaviour, then
 * assert the pre-break outcome. It must PASS on {baseline_version}, FAIL on
 * {to_version} with '{signal}', and PASS again once the production adaptation is
 * present.  Keep ALL library config in production code, never here.
 */
public class {test_class} {{

    @Test
    public void reproducesBbc() throws Exception {{
        // TODO(JUDGMENT): construct realistic input, call the production path
        // (e.g. the client's load()/parse()/deserialize()), assert the survivor value.
        fail("stub not implemented — complete the body from the characterization above");
    }}
}}
"""

RUN_SH = """#!/usr/bin/env bash
# AUTO-GENERATED 3-state differential for {break_id} ({repo}).
set -eu
export JAVA_HOME="${{JAVA_HOME:-{java_home_hint}}}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${{1:-./{artifact}-diff}}"
git clone --quiet https://github.com/{repo}.git "$WORK"
cd "$WORK"
cp "$HERE/pom.xml" ./pom.xml
mkdir -p "$(dirname "src/test/java/{test_path}")"
cp "$HERE/{test_class}.java" "src/test/java/{test_path}"
RPT="target/surefire-reports/{test_fqcn}.txt"
run() {{ mvn clean test -D{prop}="$2" >/tmp/bbc_diff.log 2>&1 || true
        printf '%-38s %s | %s\\n' "$1" \\
          "$(grep -aoE 'Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+' "$RPT" 2>/dev/null | head -1)" \\
          "$(grep -aoE '{signal_grep}' "$RPT" 2>/dev/null | head -1 || echo PASS)"; }}
git checkout --quiet {parent_sha}
run "1: parent + {baseline_version} (PASS)" {baseline_version}
run "2: parent + {to_version} (FAIL)" {to_version}
git stash -u >/dev/null 2>&1 || true; git checkout --quiet {adapt_sha}; git stash pop >/dev/null 2>&1 || true
run "3: adapted + {to_version} (PASS)" {to_version}
"""


SET_BASELINE_PY = '''import re, sys
# Force EVERY dependency under <groupId> to version <newv> in a Maven pom (covers
# multi-artifact libraries, e.g. poi + poi-ooxml + poi-scratchpad). Handles both a
# literal version and a ${property} placeholder in the <version> tag.
pom, group, newv = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(pom, encoding="utf-8").read()
pat = re.compile(r"(<groupId>\\s*" + re.escape(group) +
                 r"\\s*</groupId>\\s*<artifactId>[^<]+</artifactId>\\s*<version>\\s*)([^<]+?)(\\s*</version>)", re.S)
n = len(pat.findall(s))
open(pom, "w", encoding="utf-8").write(pat.sub(lambda m: m.group(1) + newv + m.group(3), s))
print(f"[set-baseline] {group}:* -> {newv} at {n} site(s)" +
      ("" if n else "  (0 sites — versions managed by a parent/BOM or a property block; override manually)"))
'''

RUN_SH_REUSE = """#!/usr/bin/env bash
# AUTO-GENERATED reuse-pom 3-state differential for {break_id} ({repo}).
# Uses the repo's OWN pom (native Maven) — no hand-written dependency list.
# Only the BASELINE version is overridden; states 2 & 3 use the repo's pom as-is.
# Module: '{module}' (multi-module builds with -pl {module} -am).
#   1) parent code + {baseline_version}  -> expect PASS
#   2) parent code + {to_version} (repo)  -> expect FAIL ({signal})
#   3) adapted code + {to_version} (repo) -> expect PASS
set -u
export JAVA_HOME="${{JAVA_HOME:-{java_home_hint}}}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="${{1:-./{artifact}-diff}}"
git clone --quiet https://github.com/{repo}.git "$WORK"; cd "$WORK"
mkdir -p "$(dirname "{test_rel}")"
cp "$HERE/{test_class}.java" "{test_rel}"
MVN='mvn clean test {pl_arg} -Dtest={test_class} -DfailIfNoTests=false -DargLine="{add_opens}"'
report() {{
  local res sig
  res=$(grep -haoE 'Tests run: [0-9]+, Failures: [0-9]+, Errors: [0-9]+' {report_glob} 2>/dev/null | head -1)
  sig=$(grep -haoE '{signal_grep}' {report_glob} 2>/dev/null | head -1)
  printf '%-42s %s | %s\\n' "$1" "$res" "${{sig:-PASS}}"
}}
git checkout --quiet {parent_sha}
python "$HERE/set_baseline_version.py" {pom_rel} {group_id} {baseline_version}
eval "$MVN" >/tmp/bbc_diff.log 2>&1 || true; report "1: parent + {baseline_version} (PASS)"
git checkout -- {pom_rel}
eval "$MVN" >/tmp/bbc_diff.log 2>&1 || true; report "2: parent + {to_version} (FAIL)"
git stash -u >/dev/null 2>&1 || true; git checkout --quiet {adapt_sha}; git stash pop >/dev/null 2>&1 || true
eval "$MVN" >/tmp/bbc_diff.log 2>&1 || true; report "3: adapted + {to_version} (PASS)"
"""


def gen_harness(brk, repo, adapt_sha, parent_sha, out_dir, reuse_pom=False, token=None,
                module="", baseline=None):
    v = brk.get("verify", {})
    lib = brk["library"]
    match_artifact = re.split(r"[/\s]", lib["artifact_id"].strip())[0]  # "poi / poi-ooxml" -> "poi"
    test_class = f"{match_artifact.split('-')[0].capitalize()}BbcTest"
    test_pkg = "bbc"
    java = str(v.get("java", 17))
    to_version = lib.get("to_version") or lib.get("at_version") or "REPLACE"

    # multi-module layout: source + pom live under <module>/ and we build it in-reactor
    mod = module.strip("/")
    mod_dir = f"{mod}/" if mod else ""
    pom_rel = f"{mod}/pom.xml" if mod else "pom.xml"
    pl_arg = f"-pl {mod} -am" if mod else ""

    if reuse_pom:  # read the (module) pom to pick the Java level and warn on managed versions
        if not token:
            token = _token()
        pom_text = _gh_file(repo, pom_rel, adapt_sha, token)
        if pom_text is None:
            sys.exit(f"--reuse-pom: {repo}@{adapt_sha[:8]} has no {pom_rel} — "
                     f"not native-Maven, or wrong --module (scope is Maven only).")
        java = pom_java_release(pom_text) or java
        kind, val = find_dep_version_decl(pom_text, lib["group_id"], match_artifact)
        if kind is None:
            print(f"[gen-harness] WARN: {match_artifact} version not found in {pom_rel}'s "
                  f"dependency block (managed by a parent/BOM?). Baseline override may "
                  f"no-op — check set_baseline_version.py output when you run it.")
        else:
            print(f"[gen-harness] {pom_rel}: {match_artifact} version is a {kind}"
                  + (f" (${{{val}}})" if kind == 'property' else f" ({val})"))

    ctx = dict(
        break_id=brk["break_id"], group_id=lib["group_id"], artifact_id=lib["artifact_id"],
        artifact=match_artifact, match_artifact=match_artifact,
        to_version=to_version,
        # per-client baseline: the version THIS repo was actually on before its bump,
        # which is usually not the catalog's canonical runnable_baseline
        baseline_version=baseline or v.get("runnable_baseline",
                                           lib.get("from_version", "REPLACE")),
        prop="dep.version", java=java,
        add_opens=" ".join(v.get("jvm_add_opens", [])),
        test_class=test_class, test_pkg=test_pkg,
        test_path=f"{test_pkg}/{test_class}.java",
        test_fqcn=f"{test_pkg}.{test_class}",
        module=mod, pom_rel=pom_rel, pl_arg=pl_arg,
        test_rel=f"{mod_dir}src/test/java/{test_pkg}/{test_class}.java",
        report_glob=f"{mod_dir}target/surefire-reports/*{test_class}.txt",
        bump_failing_test="; ".join(brk.get("characterization", {}).get("failing_tests", ["?"])),
        signal=brk.get("characterization", {}).get("signal", "?"),
        brief_what_changed=brk.get("brief", {}).get("what_changed", brk.get("why_it_breaks", "?")),
        brief_expected_signal=brk.get("brief", {}).get("expected_signal_hint", v.get("signal_grep", "Exception")),
        signal_grep=v.get("signal_grep", "Exception"),
        repo=repo, adapt_sha=adapt_sha, parent_sha=parent_sha,
        java_home_hint=v.get("java_home_hint", "/c/Program Files/Java/jdk-17"),
    )
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{test_class}.java").write_text(TEST_STUB.format(**ctx), encoding="utf-8")
    if reuse_pom:
        (out / "set_baseline_version.py").write_text(SET_BASELINE_PY, encoding="utf-8")
        (out / "run_differential.sh").write_text(RUN_SH_REUSE.format(**ctx), encoding="utf-8")
        print(f"[gen-harness] REUSE-POM harness written to {out}/ (uses the repo's own pom):")
        print(f"  - {test_class}.java        (JUDGMENT: complete reproducesBbc())")
        print(f"  - set_baseline_version.py  (baseline dep-version override helper)")
        print(f"  - run_differential.sh      (bash run_differential.sh)")
        return
    (out / "pom.xml").write_text(POM_TEMPLATE.format(**ctx), encoding="utf-8")
    (out / "run_differential.sh").write_text(RUN_SH.format(**ctx), encoding="utf-8")
    print(f"[gen-harness] wrote harness to {out}/")
    print(f"  - pom.xml               (add the repo's other compile deps)")
    print(f"  - {test_class}.java     (JUDGMENT: complete reproducesBbc())")
    print(f"  - run_differential.sh   (bash run_differential.sh)")


# ── orchestration ────────────────────────────────────────────────────────────────

def summarize():
    """Consolidate output/<break>_candidates.jsonl (from `run`) + verified_cases/*.json
    into one dataset table across all catalog breaks."""
    cat = load_catalog()
    cases = {}
    cdir = HERE / "verified_cases"
    for cf in cdir.glob("*.json"):
        try:
            d = json.loads(cf.read_text(encoding="utf-8"))
        except Exception:
            continue
        repo = (d.get("adaptation", {}) or {}).get("repo")
        if repo:
            cases[repo] = (d.get("status", "?"), cf.name)

    lines = ["# BBC adaptation dataset — all breaks\n",
             f"Consolidated from output/<break>_candidates.jsonl + verified_cases/. "
             f"Regenerate: `python bbc_e2e.py summarize`.\n",
             "| Break | signal | candidates | Maven-prod (verifiable) | best candidate | recorded status |",
             "|---|---|---|---|---|---|"]
    detail = ["\n## Verifiable Maven production candidates per break\n"]
    for b in cat["breaks"]:
        bid = b["break_id"]
        sig = b.get("mining", {}).get("signal_quality", "?")
        f = HERE / "output" / f"{bid}_candidates.jsonl"
        if not f.exists():
            lines.append(f"| {bid} | {sig} | _not run_ | – | – | – |")
            continue
        rows = []
        for line_no, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                print(f"[summarize] skip invalid JSON: {f.name}:{line_no}", file=sys.stderr)
                continue
            if not row.get("repo") or not row.get("sha"):
                print(f"[summarize] skip malformed row missing repo/sha: {f.name}:{line_no}", file=sys.stderr)
                continue
            rows.append(row)
        ver = [c for c in rows if c.get("verifiable")]
        best = ver[0] if ver else None
        # recorded status: any case file whose repo appears among this break's candidates
        repos = {c["repo"] for c in rows}
        status = next((f"{st} ({fn})" for r, (st, fn) in cases.items() if r in repos), "—")
        best_s = f"{best['repo']}@{best['sha'][:8]}" if best else "—"
        lines.append(f"| {bid} | {sig} | {len(rows)} | {len(ver)} | {best_s} | {status} |")
        detail.append(f"### {bid}  (signal: {sig})")
        if ver:
            for c in ver[:8]:
                pf = (c.get("production_files") or ["?"])[0]
                detail.append(f"- `{c['repo']}@{c['sha'][:8]}` — {pf} — {c['message'][:60]}")
        else:
            detail.append("- (no native-Maven production candidates)")
        detail.append("")
    out = HERE / "output" / "ALL_candidates_summary.md"
    out.write_text("\n".join(lines + detail), encoding="utf-8")
    print("\n".join(lines))
    print(f"\n[summarize] wrote {out.relative_to(HERE)}")


# ── stage 3.5: verify version traversal (real bump -> break -> fix, not born-on-new) ────
#
# A mined adaptation commit only proves the client USES the fix API. It does NOT prove the
# client CROSSED the break boundary — many clients were already on the new version (the dep
# is transitive, or they were born on it) and hit the restrictive default as a latent bug,
# which is NOT an adaptation to a breaking CHANGE. This stage requires a DIRECT-dependency
# version bump that crosses the break boundary within a commit window of the adaptation.

# Max commits between the boundary-crossing bump and the adaptation commit.
# A distance of 0 is valid: the dependency bump and adaptation can be in the same commit.
MAX_TRAVERSAL_COMMITS = int(os.environ.get("BBC_MAX_TRAVERSAL_COMMITS", "200"))
# How many build-file commits (newest-first from the adapt commit) to scan for the bump.
TRAVERSAL_SCAN = int(os.environ.get("BBC_TRAVERSAL_SCAN", "200"))
# Transitive crossings COUNT (2026-08-04): a client who bumped a framework that moved
# the library across the boundary, then adapted production code, experienced the break
# just as much as one who bumped the library directly. Resolution is a POM walk per
# commit, so it is budgeted separately from the (cheap) declared-version scan.
RESOLVE_TRANSITIVE = os.environ.get("BBC_RESOLVE_TRANSITIVE", "1").lower() not in ("0", "false", "no")
TRANSITIVE_SCAN = int(os.environ.get("BBC_TRANSITIVE_SCAN", "30"))


def _parse_ver(s):
    """'1.33' -> (1,33); '2.15.0' -> (2,15,0); '2.0.RELEASE' -> (2,0). None if no digits."""
    if not s:
        return None
    nums = re.findall(r"\d+", s)
    return tuple(int(n) for n in nums[:4]) if nums else None


def _ver_lt(a, b):
    """tuple < with zero-padding to equal length."""
    n = max(len(a), len(b))
    return a + (0,) * (n - len(a)) < b + (0,) * (n - len(b))


def _crosses_boundary(vold, vnew, boundary):
    """True iff vold < boundary <= vnew (a real crossing of the break boundary)."""
    o, n, b = _parse_ver(vold), _parse_ver(vnew), _parse_ver(boundary)
    if not (o and n and b):
        return False
    return _ver_lt(o, b) and not _ver_lt(n, b)


def _candidate_buildfiles(repo, adapt_sha, token):
    """Module poms nearest the adaptation's production files, then root build files."""
    mods = []
    try:
        commit = _gh(f"{GH}/repos/{repo}/commits/{adapt_sha}", token)
        prod = [f["filename"] for f in commit.get("files", []) if _is_prod_java(f["filename"])]
        mods = _module_poms(prod)
    except Exception:
        pass
    out = []
    for f in mods + BUILD_FILES:
        if f not in out:
            out.append(f)
    return out


def _coord_key(via):
    """'group:artifact' from a resolution-path entry like 'g:a:version'. The VERSION
    is deliberately dropped — the same coordinate at two versions is the same route
    (that is the bump); a different coordinate is a different route (that is not)."""
    if not via:
        return None
    parts = str(via).split(":")
    return ":".join(parts[:2]) if len(parts) >= 2 else str(via)


def find_boundary_bump(repo, brk, token, adapt_sha, max_scan=TRAVERSAL_SCAN):
    """Walk each build file's history (newest-first from adapt_sha) for a commit whose
    RESOLVED target version crosses the break boundary.

    Declared-version first (cheap, exact). But when the library is not declared in the
    client's pom it arrives transitively, and reading the pom text can never see it —
    which is what made every Axon case look like a non-traversal. So fall back to the
    version the build actually resolves to (resolve_version, a Maven Central POM walk).
    That separates the two situations the old verdict conflated:

      transitive crossing  resolved below -> at/above the boundary  -> IS a case
      born past boundary   resolved >= boundary on both sides       -> NOT a case
      unresolvable         -> reported as such, never as "no crossing"

    Returns the bump commit with `kind` (direct|transitive) and `via` (the coordinate
    the crossing came through), or None.
    """
    gid, aid = brk["library"]["group_id"], brk["library"]["artifact_id"]
    boundary = brk["verify"]["break_boundary"]
    budget = TRANSITIVE_SCAN if RESOLVE_TRANSITIVE else 0
    unresolved = 0

    def _resolved(bf_path, sha):
        """(version, kind, via) the build actually gets at this commit."""
        text = _gh_file(repo, bf_path, sha, token)
        if text is None:
            return None, None, None
        try:
            import resolve_version as RV
        except ImportError:
            return None, None, None
        r = RV.resolve_from_client(text, gid, aid)
        via = r["path"][0] if r.get("path") else None
        return r["version"], r["kind"], via

    for bf in _candidate_buildfiles(repo, adapt_sha, token):
        try:
            commits = _gh(f"{GH}/repos/{repo}/commits", token, path=bf, sha=adapt_sha, per_page=max_scan)
        except SystemExit:
            raise
        except Exception as e:
            # never silently: a swallowed error here reads as "no traversal", which
            # is indistinguishable from a genuine negative and hid a real bug once
            print(f"[traversal] {repo} {bf}: commit listing failed "
                  f"({type(e).__name__}: {e})", file=sys.stderr)
            commits = []
        if not isinstance(commits, list):
            continue
        for c in commits:
            parents = c.get("parents", [])
            if not parents:
                continue
            vnew = dep_version(_gh_file(repo, bf, c["sha"], token), gid, aid)
            if vnew:
                vold = dep_version(_gh_file(repo, bf, parents[0]["sha"], token), gid, aid)
                if _crosses_boundary(vold, vnew, boundary):
                    return {"bump_sha": c["sha"], "buildfile": bf,
                            "from": vold, "to": vnew, "kind": "direct", "via": None,
                            "date": c["commit"]["committer"]["date"]}
                continue

            # Not declared here -> the library is transitive. Resolve what the build
            # really gets on each side. Budgeted: each resolution is a POM walk.
            if budget <= 0:
                continue
            budget -= 1
            rnew, knew, via = _resolved(bf, c["sha"])
            if not rnew:
                unresolved += 1
                continue
            rold, _, via_old = _resolved(bf, parents[0]["sha"])
            if not rold:
                unresolved += 1
                continue
            # The two sides must be reached the SAME way. If the winning coordinate
            # differs, the numbers describe different paths through the graph, not a
            # version change — comparing them invents a crossing. This produced a
            # false GOLD on einsteinarbert/axon-saga-example: a "upgrade version of
            # spring boot" commit where Axon never moved (4.6.1 both sides), but the
            # parent resolved xstream 1.4.10 via a different route.
            if via and via_old and _coord_key(via) != _coord_key(via_old):
                unresolved += 1
                continue
            if _crosses_boundary(rold, rnew, boundary):
                return {"bump_sha": c["sha"], "buildfile": bf,
                        "from": rold, "to": rnew, "kind": knew or "transitive",
                        "via": via or via_old, "via_parent": via_old,
                        "date": c["commit"]["committer"]["date"]}
    if unresolved:
        return {"unresolved": unresolved}
    return None


def verify_traversal(repo, adapt_sha, brk, token, max_commits=MAX_TRAVERSAL_COMMITS):
    """Confirm the client crossed the break boundary within max_commits of the adaptation."""
    bump = find_boundary_bump(repo, brk, token, adapt_sha)
    if bump and "bump_sha" not in bump:
        # resolution failed on every transitive candidate — unknown, NOT a negative
        return {"traversal_confirmed": False, "resolution": "unresolved",
                "reason": f"no declared-version crossing, and the transitive version "
                          f"could not be resolved for {bump['unresolved']} commit(s) "
                          f"(BOM/parent-managed or unavailable POM) — undecided, "
                          f"confirm with `mvn dependency:tree`"}
    if not bump:
        return {"traversal_confirmed": False,
                "reason": "no boundary-crossing bump in the adaptation's ancestry, "
                          "declared or resolved (client was born at/above the boundary)"}
    # Commits from the bump to the adaptation. Same commit is valid; otherwise
    # the bump must be an ancestor of the adaptation commit.
    dist = None
    try:
        cmp = _gh(f"{GH}/repos/{repo}/compare/{bump['bump_sha']}...{adapt_sha}", token)
        if isinstance(cmp, dict) and cmp.get("status") in ("ahead", "identical"):
            dist = cmp.get("ahead_by")
        elif isinstance(cmp, dict):
            return {"traversal_confirmed": False, "bump": bump,
                    "reason": f"boundary bump found but is not an ancestor/same commit "
                              f"of the adaptation (compare status: {cmp.get('status')})"}
    except Exception:
        pass
    if dist is None:
        return {"traversal_confirmed": False, "bump": bump,
                "reason": "bump found but could not confirm it precedes the adaptation"}
    ok = 0 <= dist <= max_commits
    shape = "BUNDLED_BUMP_AND_ADAPTATION" if dist == 0 else "POST_MERGE_FIX"
    kind = bump.get("kind", "direct")
    via = f" via {bump['via']}" if bump.get("via") else ""
    return {"traversal_confirmed": ok, "distance_commits": dist, "bump": bump,
            "shape": shape, "traversal_kind": kind,
            "reason": (f"[{kind}] bump {bump['from']}->{bump['to']}{via} in "
                       f"{bump['buildfile']} @{bump['bump_sha'][:8]}, "
                       f"{'same commit as adaptation' if dist == 0 else str(dist) + ' commits before the adaptation'}"
                       if ok else
                       f"bump {bump['from']}->{bump['to']} found but {dist} commits away "
                       f"(> {max_commits})")}


def mine_verify(break_id):
    """mine -> classify (production adaptations) -> REQUIRE a boundary-crossing version bump
    within MAX_TRAVERSAL_COMMITS. Only traversal-confirmed candidates are real (bump->break->fix)
    pairs. Writes output/<break>_traversal_candidates.jsonl."""
    brk = get_break(break_id)
    token = _token()
    print(f"\n=== mine-commits {break_id} ===")
    rows = mine_commits(brk, token)
    print(f"\n=== classify + traversal-verify (max {MAX_TRAVERSAL_COMMITS} commits from a "
          f"boundary-crossing bump) ===")
    gold, other = [], []
    checked = 0
    for r in rows[:CLASSIFY_CAP]:
        c = classify_commit(r["repo"], r["sha"], brk, token, source=r.get("source"))
        if c.get("error") or not c.get("is_production_adaptation") or c.get("library_source"):
            continue
        if c.get("evidence") == "none" or c.get("reachable_from_default") is False:
            continue
        # only production adaptations are worth the (API-costly) traversal check
        t = verify_traversal(r["repo"], r["sha"], brk, token)
        c["traversal"] = t
        c["shape"] = t.get("shape") if t.get("traversal_confirmed") else None
        checked += 1
        (gold if t["traversal_confirmed"] else other).append(c)
        mark = "GOLD" if t["traversal_confirmed"] else "----"
        print(f" [{mark}] {c['repo']}@{c['sha'][:8]}  ({c.get('build_system')})  {t['reason']}")
    out_file = HERE / "output" / f"{break_id}_traversal_candidates.jsonl"
    out_file.parent.mkdir(exist_ok=True)
    with out_file.open("w", encoding="utf-8") as fh:
        for c in gold + other:
            fh.write(json.dumps(c) + "\n")
    print(f"\n[mine-verify] production adaptations checked: {checked}  |  "
          f"GOLD (real bump->break->fix traversal): {len(gold)}")
    for c in gold:
        pf = (c.get("production_files") or ["?"])[0]
        b = c["traversal"]["bump"]
        print(f"  GOLD  {c['repo']}@{c['sha'][:8]}  {b['from']}->{b['to']}  {pf}")
    print(f"[mine-verify] saved -> {out_file.relative_to(HERE)}")
    return gold


def run(break_id):
    brk = get_break(break_id)
    token = _token()
    print(f"\n=== characterize {break_id} ===")
    sha = brk["clients"][0]["breaking_commit"]
    characterize(sha)
    print(f"\n=== mine-commits {break_id} ===")
    rows = mine_commits(brk, token)
    print(f"\n=== classify candidates (production adaptations first) ===")
    results = []
    for r in rows[:CLASSIFY_CAP]:
        c = classify_commit(r["repo"], r["sha"], brk, token, source=r.get("source"))
        if c.get("error"):
            continue
        if MAVEN_JAVA_ONLY and not c["verifiable"]:
            continue
        if REQUIRE_TRAVERSAL and c["verifiable"]:
            t = verify_traversal(r["repo"], r["sha"], brk, token)
            c["traversal"] = t
            if not t.get("traversal_confirmed"):
                print(f"  [skip traversal] {c['repo']}@{c['sha'][:8]}  {t.get('reason')}")
                continue
            c["shape"] = t.get("shape")
        results.append(c)
    # verifiable Maven production adaptations first; then non-Maven prod; then rest
    # when BBC_MAVEN_JAVA_ONLY=0 is used for exploratory broad output.
    # strongest evidence first, upstream repos before forks
    results.sort(key=lambda c: (not c["verifiable"],
                                c.get("evidence") != "message+content",
                                c.get("repo_is_fork", False),
                                c["library_source"],
                                not c["is_production_adaptation"], c["test_only"]))
    for c in results:
        tag = ("LIB-SOURCE" if c["library_source"]
               else "PROD" if c["is_production_adaptation"]
               else "TEST-ONLY" if c["test_only"] else "?")
        bs = c.get("build_system", "unknown")
        star = "*" if c["verifiable"] else " "   # * = Maven prod adaptation = ready to verify
        shape = f" {c.get('shape')}" if c.get("shape") else ""
        ev = f" ev={c.get('evidence')}" + ("/fork" if c.get("repo_is_fork") else "")
        ver = f"{c['version_at_parent']}->{c['version_at_commit']}" if c["version_changed_here"] else f"@{c['version_at_commit']}"
        print(f" {star}[{tag:9}|{bs:6}] {c['repo']}@{c['sha'][:8]}  {ver}{shape}{ev}  {c['message']}")
        for f in c["production_files"][:3]:
            print(f"                     {f}")
    # persist candidates so a run's results are a durable artifact, not just stdout
    out_file = HERE / "output" / f"{break_id}_candidates.jsonl"
    out_file.parent.mkdir(exist_ok=True)
    with out_file.open("w", encoding="utf-8") as fh:
        for c in results:
            fh.write(json.dumps(c) + "\n")
    verifiable = [c for c in results if c["verifiable"]]
    mode = "Maven Java production candidates only" if MAVEN_JAVA_ONLY else "all classified candidates"
    traversal_mode = "requiring direct bump traversal" if REQUIRE_TRAVERSAL else "without traversal requirement"
    print(f"\n{len(verifiable)} Maven production adaptation(s) ready to verify (marked *). "
          f"Output mode: {mode}, {traversal_mode}.")
    print(f"[run] saved {len(results)} candidates -> {out_file.relative_to(HERE)}")
    print(f"Next: pick a * candidate, then:")
    print(f"  python bbc_e2e.py gen-harness {break_id} --repo <r> --adapt-sha <s> --parent-sha <p> --out scratchpad/{break_id}-harness")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("characterize").add_argument("break_id")
    sub.add_parser("mine-commits").add_argument("break_id")
    p = sub.add_parser("classify"); p.add_argument("repo"); p.add_argument("sha"); p.add_argument("break_id")
    p = sub.add_parser("traversal"); p.add_argument("repo"); p.add_argument("sha"); p.add_argument("break_id")
    sub.add_parser("mine-verify").add_argument("break_id")
    p = sub.add_parser("gen-harness")
    p.add_argument("break_id"); p.add_argument("--repo", required=True)
    p.add_argument("--adapt-sha", required=True); p.add_argument("--parent-sha", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--reuse-pom", action="store_true",
                   help="native-Maven repos: reuse the repo's own pom (no hand-written dep list); "
                        "override only the baseline version")
    p.add_argument("--module", default="",
                   help="for multi-module repos: the module dir holding the source "
                        "(e.g. 'core'); builds with -pl <module> -am")
    p.add_argument("--baseline", default=None,
                   help="pre-bump version THIS client was on (state 1). Defaults to the "
                        "catalog's verify.runnable_baseline, which is often not the "
                        "version the specific repo came from")
    sub.add_parser("run").add_argument("break_id")
    sub.add_parser("summarize")
    args = ap.parse_args()

    if args.cmd == "characterize":
        brk = get_break(args.break_id)
        characterize(brk["clients"][0]["breaking_commit"])
    elif args.cmd == "mine-commits":
        for r in mine_commits(get_break(args.break_id), _token()):
            print(f"  {r['repo']}@{r['sha'][:8]}  [{r['matched_term']}]  {r['message']}")
    elif args.cmd == "classify":
        print(json.dumps(classify_commit(args.repo, args.sha, get_break(args.break_id), _token()), indent=2))
    elif args.cmd == "traversal":
        print(json.dumps(verify_traversal(args.repo, args.sha, get_break(args.break_id), _token()), indent=2))
    elif args.cmd == "mine-verify":
        mine_verify(args.break_id)
    elif args.cmd == "gen-harness":
        gen_harness(get_break(args.break_id), args.repo, args.adapt_sha, args.parent_sha,
                    args.out, reuse_pom=args.reuse_pom,
                    token=(_token() if args.reuse_pom else None), module=args.module,
                    baseline=args.baseline)
    elif args.cmd == "run":
        run(args.break_id)
    elif args.cmd == "summarize":
        summarize()


if __name__ == "__main__":
    main()
