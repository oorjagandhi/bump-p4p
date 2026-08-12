#!/usr/bin/env python3
"""
screen_compile_break.py — separate BEHAVIOURAL breaks from COMPILE breaks.

The gate the pipeline was missing. A candidate can be a real production adaptation,
carry content evidence, sit on the default branch, AND have a confirmed boundary
traversal — and still not be a BBC, because the client's pre-adaptation code does not
COMPILE against the new version. Then the adaptation is fixing a signature break, and
the 3-state differential can never show the runtime signal (state 2 fails at javac).

Caught in the wild: snork-alt/beanszoo (snakeyaml 1.16->2.2, traversal-confirmed GOLD)
subclasses `Constructor` with an implicit `super()`. snakeyaml 2.0 removed the no-arg
`Constructor()`, so its parent code fails with "no suitable constructor found". Its
`setTagInspector(tag -> true)` is a behavioural fix bundled into a compile fix.

Method (deterministic, no client build required):
  1. fetch the PARENT revision of each production file that references the library
  2. parse the library API constructs it uses — `new LibClass(...)` and
     `class X extends LibClass` + the super(...) arity actually invoked
  3. ask javap what constructor arities the library REALLY offers at from_version
     and at to_version
  4. an arity present at from_version and absent at to_version => COMPILE break

Verdicts:
  behavioural   parent usage still compiles at to_version -> real BBC candidate
  compile_break an arity it needs was removed -> adaptation is (also) a signature fix
  unknown       jar/class/usage not resolvable -> never silently pass or fail

Scope: constructor arity only. That is what the observed breaks turn on; removed or
re-signatured METHODS are not yet covered, so `behavioural` means "no constructor-level
compile break found", not "provably compiles". Wildcard imports yield `unknown`.

Usage:
  python screen_compile_break.py <break_id> --in output/<f>.jsonl [--limit N]
  python screen_compile_break.py <break_id> --repo R --sha S
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
import os
import re
import subprocess
import sys
from pathlib import Path

import bbc_e2e as B

HERE = Path(__file__).resolve().parent.parent
M2 = Path(os.environ.get("M2_REPO", Path.home() / ".m2" / "repository"))


# ── library jar resolution ──────────────────────────────────────────────────────

def resolve_jar(group_id, artifact_id, version):
    """Local ~/.m2 first; fall back to `mvn dependency:get`. None if unobtainable."""
    p = M2.joinpath(*group_id.split("."), artifact_id, version,
                    f"{artifact_id}-{version}.jar")
    if p.is_file():
        return p
    coords = f"{group_id}:{artifact_id}:{version}"
    r = subprocess.run(["mvn", "-q", "-B", "dependency:get", f"-Dartifact={coords}"],
                       capture_output=True, text=True, errors="replace", shell=True)
    if r.returncode == 0 and p.is_file():
        return p
    print(f"    [jar] could not obtain {coords}", file=sys.stderr)
    return None


_CTOR_CACHE = {}


def _erase(t):
    """Erase generics/varargs from a javap parameter type: 'java.lang.Class<? extends
    Object>' -> 'java.lang.Class', 'String...' -> 'String[]'."""
    t = re.sub(r"<[^<>]*(?:<[^<>]*>[^<>]*)*>", "", t).strip()
    return (t[:-3] + "[]") if t.endswith("...") else t


def ctor_signatures(jar, fqcn):
    """[(param type, ...)] for each public constructor, generics erased. None if the
    class is absent from the jar.

    Arity alone is NOT enough: snakeyaml 2.0 kept an arity-1 Constructor but narrowed
    it from Constructor(Class) to Constructor(LoaderOptions), so `new
    Constructor(Foo.class)` is an arity-1 call that no longer compiles.
    """
    key = (str(jar), fqcn)
    if key in _CTOR_CACHE:
        return _CTOR_CACHE[key]
    r = subprocess.run(["javap", "-cp", str(jar), fqcn],
                       capture_output=True, text=True, errors="replace")
    if r.returncode != 0 or "Error" in r.stdout:
        _CTOR_CACHE[key] = None
        return None
    simple = fqcn.split(".")[-1]
    sigs = []
    for line in r.stdout.splitlines():
        line = line.strip()
        m = re.match(rf"public\s+{re.escape(fqcn)}\((.*?)\)\s*(?:throws.*)?;", line) or \
            re.match(rf"public\s+{re.escape(simple)}\((.*?)\)\s*(?:throws.*)?;", line)
        if not m:
            continue
        body = m.group(1).strip()
        sigs.append(tuple(_erase(p) for p in _split_top_level(body)) if body else ())
    _CTOR_CACHE[key] = sigs or None
    return _CTOR_CACHE[key]


def ctor_arities(jar, fqcn):
    sigs = ctor_signatures(jar, fqcn)
    return {len(s) for s in sigs} if sigs is not None else None


_SUPER_CACHE = {}


def supertypes(jar, fqcn, _depth=0):
    """Transitive superclasses + interfaces of fqcn, read from the jar.

    Needed because a declared parameter type is almost never the argument's own
    class: `new XStream(new DomDriver())` passes a DomDriver to a constructor
    declaring HierarchicalStreamDriver. Comparing the two names directly reports a
    signature mismatch on code that compiles perfectly well, which is a FALSE
    compile_break — and a false compile_break silently deletes a real candidate.
    """
    if not jar or _depth > 8:
        return set()
    key = (str(jar), fqcn)
    if key in _SUPER_CACHE:
        return _SUPER_CACHE[key]
    _SUPER_CACHE[key] = set()          # guard against cycles while recursing
    r = subprocess.run(["javap", "-cp", str(jar), fqcn],
                       capture_output=True, text=True, errors="replace")
    out = set()
    if r.returncode == 0 and "Error" not in r.stdout:
        head = ""
        for line in r.stdout.splitlines():
            if re.search(r"\b(class|interface)\s", line) and "{" in line:
                head = line
                break
        head = re.sub(r"<[^<>]*(?:<[^<>]*>[^<>]*)*>", "", head)  # drop generics
        names = []
        ext = re.search(r"\bextends\s+([\w.$,\s]+?)(?:\bimplements\b|\{)", head)
        impl = re.search(r"\bimplements\s+([\w.$,\s]+?)\{", head)
        for grp in (ext, impl):
            if grp:
                names += [n.strip() for n in grp.group(1).split(",") if n.strip()]
        for n in names:
            out.add(n)
            out |= supertypes(jar, n, _depth + 1)
    _SUPER_CACHE[key] = out
    return out


# Argument-expression -> Java type, for the forms that can be classified without real
# type inference. Anything else stays None (unknown) and is treated permissively, so
# the screen never claims a compile break it cannot justify.
def classify_arg(expr, imports):
    e = expr.strip()
    if not e:
        return None
    if re.fullmatch(r"[\w.]+\s*\.\s*class", e):
        return "java.lang.Class"
    if e.startswith('"'):
        return "java.lang.String"
    if e.startswith("'"):
        return "char"
    if e == "null":
        return "NULL"
    if e in ("true", "false"):
        return "boolean"
    if re.fullmatch(r"-?\d+[lL]", e):
        return "long"
    if re.fullmatch(r"-?\d+", e):
        return "int"
    if re.fullmatch(r"-?\d*\.\d+[fFdD]?", e):
        return "double"
    m = re.match(r"new\s+([\w.]+)\s*[(\[]", e)
    if m:
        n = m.group(1)
        return imports.get(n, n)
    return None


def _type_matches(param, arg, jar=None):
    """Permissive erased-type comparison. Unknown args and null match anything;
    Object accepts any reference type; and an argument whose class extends or
    implements the declared parameter type matches (normal Java assignability —
    without this, every polymorphic call reads as a signature mismatch)."""
    if arg is None or arg == "NULL":
        return True
    if param in ("java.lang.Object", "Object"):
        return True
    if param == arg or param.split(".")[-1] == arg.split(".")[-1]:
        return True
    if jar:
        sup = supertypes(jar, arg)
        if param in sup or any(param.split(".")[-1] == s.split(".")[-1] for s in sup):
            return True
    return False


def _split_top_level(s):
    """Split a parameter/argument list on top-level commas only."""
    out, depth, cur, i = [], 0, "", 0
    while i < len(s):
        ch = s[i]
        if ch in "\"'":
            q, cur, i = ch, cur + ch, i + 1
            while i < len(s) and s[i] != q:
                cur += s[i]
                i += 2 if s[i] == "\\" else 1
                continue
            if i < len(s):
                cur += s[i]
        elif ch in "(<[":
            depth += 1
            cur += ch
        elif ch in ")>]":
            depth -= 1
            cur += ch
        elif ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    if cur.strip():
        out.append(cur)
    return [x.strip() for x in out]


# ── Java source parsing ─────────────────────────────────────────────────────────

def split_args_arity(argstr):
    """Arity of an argument list, respecting nesting in (), <>, [], and string/char
    literals — a naive comma count miscounts `new Foo(a, Map<K, V> b)` and `f(g(x, y))`."""
    s = argstr.strip()
    if not s:
        return 0
    depth = n = 0
    i = 0
    while i < len(s):
        ch = s[i]
        if ch in "\"'":
            q = ch
            i += 1
            while i < len(s) and s[i] != q:
                i += 2 if s[i] == "\\" else 1
        elif ch in "(<[":
            depth += 1
        elif ch in ")>]":
            depth -= 1
        elif ch == "," and depth == 0:
            n += 1
        i += 1
    return n + 1


def import_map(src, lib_prefixes):
    """simple name -> FQCN for library imports. Wildcards are recorded separately
    because they make a simple name unresolvable."""
    names, wildcard = {}, False
    for m in re.finditer(r"^\s*import\s+(?:static\s+)?([\w.]+)\s*;", src, re.M):
        fq = m.group(1)
        if not any(p and (fq.startswith(p + ".") or f".{p}." in fq or p in fq)
                   for p in lib_prefixes):
            continue
        if fq.endswith(".*"):
            wildcard = True
            continue
        names[fq.split(".")[-1]] = fq
    return names, wildcard


def find_usages(src, names):
    """[(fqcn, arity, kind)] for library constructors the source actually invokes.

    kind='new'    : `new LibClass(args)`
    kind='extends': `class X extends LibClass` -> the super(...) arity X really calls
                    (explicit `super(...)`, else implicit `super()` = arity 0)
    """
    out = []
    for simple, fq in names.items():
        for m in re.finditer(rf"\bnew\s+{re.escape(simple)}\s*\(", src):
            args = _balanced(src, m.end() - 1)
            if args is not None:
                out.append((fq, split_args_arity(args), "new", args))
        for m in re.finditer(
                rf"\bclass\s+(\w+)[^{{]*?\bextends\s+{re.escape(simple)}\b", src):
            sub = m.group(1)
            body = _class_body(src, m.end())
            if body is None:
                continue
            ctors = list(re.finditer(rf"\b{re.escape(sub)}\s*\(([^)]*)\)\s*(?:throws[^{{]*)?{{",
                                     body))
            if not ctors:
                out.append((fq, 0, "extends", ""))   # implicit default ctor -> super()
                continue
            for cm in ctors:
                tail = body[cm.end():cm.end() + 400]
                sm = re.match(r"\s*super\s*\(", tail)
                if sm:
                    args = _balanced(tail, sm.end() - 1) or ""
                    out.append((fq, split_args_arity(args), "extends", args))
                else:
                    out.append((fq, 0, "extends", ""))   # implicit super()
    return out


def _balanced(s, open_idx):
    """Text inside the parens starting at s[open_idx] == '('. None if unbalanced."""
    if open_idx >= len(s) or s[open_idx] != "(":
        return None
    depth, i = 0, open_idx
    while i < len(s):
        if s[i] == "(":
            depth += 1
        elif s[i] == ")":
            depth -= 1
            if depth == 0:
                return s[open_idx + 1:i]
        i += 1
    return None


def _class_body(s, from_idx):
    i = s.find("{", from_idx)
    if i < 0:
        return None
    depth, j = 0, i
    while j < len(s):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j]
        j += 1
    return s[i + 1:]


# ── the screen ──────────────────────────────────────────────────────────────────

def screen(repo, sha, brk, token, from_jar, to_jar,
           _screened_from=None, _screened_to=None):
    lib = brk["library"]
    prefixes = (brk.get("mining", {}).get("package_prefixes")
                or [lib["group_id"], B._library_keyword(brk)])
    commit = B._gh(f"{B.GH}/repos/{repo}/commits/{sha}", token)
    if not isinstance(commit, dict) or "files" not in commit:
        return {"verdict": "unknown", "reason": "commit unavailable"}
    parent = commit["parents"][0]["sha"] if commit.get("parents") else None
    if not parent:
        return {"verdict": "unknown", "reason": "no parent commit"}

    pats = B._library_patterns(brk)
    files = [f["filename"] for f in commit["files"]
             if B._is_prod_java(f["filename"]) and B._references_library(f.get("patch"), pats)]
    if not files:
        return {"verdict": "unknown", "reason": "no library-referencing production files"}

    findings, wildcard_seen = [], False
    for fn in files:
        src = B._gh_file(repo, fn, parent, token)
        if not src:
            continue
        names, wc = import_map(src, prefixes)
        wildcard_seen |= wc
        for fq, arity, kind, argtext in find_usages(src, names):
            sigs_to = ctor_signatures(to_jar, fq) if to_jar else None
            sigs_from = ctor_signatures(from_jar, fq) if from_jar else None
            have_to = ({len(s) for s in sigs_to} if sigs_to is not None else None)
            have_from = ({len(s) for s in sigs_from} if sigs_from is not None else None)
            argtypes = [classify_arg(a, names) for a in _split_top_level(argtext)] \
                if argtext.strip() else []
            if have_to is None:
                # Absent at to_version but present at from_version = the class itself was
                # REMOVED, which is a compile break just as surely as a removed arity.
                # Only "missing from both" is genuinely unresolvable (wrong artifact,
                # over-broad package prefix, javap failure).
                findings.append({"file": fn, "class": fq, "arity": arity, "kind": kind,
                                 "status": ("class_removed_at_to_version"
                                            if have_from is not None
                                            else "unknown_class_at_to_version")})
            elif arity not in have_to:
                # no overload of this arity at all -> broken regardless of arg types
                findings.append({"file": fn, "class": fq, "arity": arity, "kind": kind,
                                 "status": "removed_at_to_version",
                                 "arities_from": sorted(have_from or []),
                                 "arities_to": sorted(have_to)})
            else:
                cands = [s for s in sigs_to if len(s) == arity]
                if any(all(_type_matches(p, a, to_jar) for p, a in zip(s, argtypes))
                       for s in cands):
                    findings.append({"file": fn, "class": fq, "arity": arity,
                                     "kind": kind, "status": "ok"})
                elif all(a is not None for a in argtypes):
                    # every argument type is known and NO overload accepts them:
                    # a definite signature narrowing (snakeyaml 2.0 turned
                    # Constructor(Class) into Constructor(LoaderOptions))
                    findings.append({"file": fn, "class": fq, "arity": arity,
                                     "kind": kind, "status": "signature_mismatch_at_to_version",
                                     "arg_types": argtypes,
                                     "overloads_to": [list(s) for s in cands]})
                else:
                    findings.append({"file": fn, "class": fq, "arity": arity,
                                     "kind": kind, "status": "inconclusive_arg_types",
                                     "arg_types": argtypes,
                                     "overloads_to": [list(s) for s in cands]})

    # Report the versions actually SCREENED, not the catalogue's defaults. --from-version
    # / --to-version override which jars are inspected, but the reason strings used to
    # quote the catalogue regardless, so screening beanszoo's real 1.16 -> 2.2 transition
    # emitted "exists at 1.33 but not at 2.0". The analysis was right and the sentence
    # describing it was wrong -- which is how a correct tool ends up supporting a false
    # claim in a writeup.
    fv = _screened_from or lib.get("from_version")
    tv = _screened_to or lib.get("to_version")
    gone = [f for f in findings if f["status"] == "class_removed_at_to_version"]
    if gone:
        g = gone[0]
        return {"verdict": "compile_break", "findings": findings,
                "reason": f"class {g['class']} exists at {fv} but is absent at {tv} "
                          f"(removed/relocated)"}
    broken = [f for f in findings if f["status"] == "removed_at_to_version"]
    if broken:
        b = broken[0]
        return {"verdict": "compile_break", "findings": findings,
                "reason": f"{b['class'].split('.')[-1]}({b['arity']} args) via {b['kind']} "
                          f"exists at {fv} but not at {tv} "
                          f"(available arities {b['arities_to']})"}
    mism = [f for f in findings if f["status"] == "signature_mismatch_at_to_version"]
    if mism:
        b = mism[0]
        return {"verdict": "compile_break", "findings": findings,
                "reason": f"{b['class'].split('.')[-1]}({', '.join(str(a) for a in b['arg_types'])}) "
                          f"has no matching overload at {tv} "
                          f"(overloads: {b['overloads_to']})"}
    if any(f["status"] == "inconclusive_arg_types" for f in findings):
        return {"verdict": "unknown", "findings": findings,
                "reason": "argument types unresolvable; arity matches but overload "
                          "compatibility cannot be proven"}
    if not findings:
        return {"verdict": "unknown", "findings": findings,
                "reason": "no resolvable library constructor usage in parent source"
                          + (" (wildcard import)" if wildcard_seen else "")}
    if any(f["status"] == "unknown_class_at_to_version" for f in findings):
        return {"verdict": "unknown", "findings": findings,
                "reason": "some library classes not resolvable in the to_version jar"}
    return {"verdict": "behavioural", "findings": findings,
            "reason": f"all {len(findings)} library constructor usage(s) in the parent "
                      f"source still exist at {brk['library'].get('to_version')}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("break_id")
    ap.add_argument("--in", dest="infile")
    ap.add_argument("--repo")
    ap.add_argument("--sha")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--gold-only", action="store_true",
                    help="only rows whose traversal was confirmed")
    ap.add_argument("--from-version", default=None)
    ap.add_argument("--to-version", default=None)
    args = ap.parse_args()

    brk = B.get_break(args.break_id)
    token = B._token()
    lib = brk["library"]
    fv = args.from_version or lib.get("from_version")
    tv = args.to_version or lib.get("to_version")
    from_jar = resolve_jar(lib["group_id"], lib["artifact_id"], fv)
    to_jar = resolve_jar(lib["group_id"], lib["artifact_id"], tv)
    print(f"[screen] {lib['artifact_id']} {fv} -> {tv}")
    print(f"[screen] from_jar={from_jar}\n[screen] to_jar={to_jar}\n")
    if not to_jar:
        sys.exit("cannot screen without the to_version jar")

    if args.repo and args.sha:
        rows = [{"repo": args.repo, "sha": args.sha}]
    else:
        src = Path(args.infile)
        rows = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
        if args.gold_only:
            rows = [r for r in rows if (r.get("traversal") or {}).get("traversal_confirmed")]
        if args.limit:
            rows = rows[:args.limit]

    tally = {}
    out = []
    for i, r in enumerate(rows, 1):
        res = screen(r["repo"], r["sha"], brk, token, from_jar, to_jar, fv, tv)
        tally[res["verdict"]] = tally.get(res["verdict"], 0) + 1
        r["compile_screen"] = res
        out.append(r)
        tag = {"behavioural": "BEHAV", "compile_break": "CMPLE",
               "unknown": "  ?  "}[res["verdict"]]
        print(f"[{i}/{len(rows)}] [{tag}] {r['repo']}@{r['sha'][:8]}  {res['reason'][:96]}",
              flush=True)

    print(f"\n[screen] {tally}")
    if args.infile:
        dst = Path(args.infile).with_name(
            Path(args.infile).stem + "_SCREENED.jsonl")
        with dst.open("w", encoding="utf-8") as fh:
            for r in out:
                fh.write(json.dumps(r) + "\n")
        print(f"[screen] saved -> {dst}")


if __name__ == "__main__":
    main()
