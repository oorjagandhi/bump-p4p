#!/usr/bin/env python3
"""
resolve_version.py — what version of the target library does a client's build
ACTUALLY resolve to, including through transitive dependencies?

Why: verify_traversal reads the <version> declared in the client's own pom. If the
library arrives transitively there is nothing to read, so the candidate is rejected
with "no boundary-crossing DIRECT-dep bump ... (transitive dependency, or born on the
new version)" — which conflates two opposite situations:

  transitive crossing  was below the boundary, ended up at/above it   -> IS a case
  born past boundary   first resolved version was already >= boundary -> is NOT

Worked example (artshishkin/art-kargopolov-cqrs-saga-axon-microservices, the fixture):
  client bumped  axon-spring-boot-starter 4.5 -> 4.5.14   in core/pom.xml
  axon 4.5     -> xstream 1.4.16   (below 1.4.18)
  axon 4.5.14  -> xstream 1.4.19   (at/above)
  => a real boundary crossing, invisible to declared-version traversal, followed by
     a production adaptation in XStreamConfig.java.

Method: resolve against Maven Central POMs — no clone, no build.
  1. direct declaration in the client pom wins (cheap, exact)
  2. otherwise walk each declared dependency's POM breadth-first to MAX_DEPTH,
     resolving ${properties} and <parent> chains, looking for the target g:a
  3. dependencyManagement is consulted for version-less declarations

This APPROXIMATES Maven. It does not implement nearest-wins conflict mediation,
version ranges, exclusions, or profile activation. It is deliberately biased toward
returning None over returning a guess: an unresolvable chain must surface as
`unknown`, never as "no crossing" — that conflation is what hid the Axon cases.
For candidates that survive screening, confirm with `mvn dependency:tree`.
"""

from __future__ import annotations

import re
import sys
from functools import lru_cache

import requests

CENTRAL = "https://repo1.maven.org/maven2"
MAX_DEPTH = 3
_SESSION = requests.Session()


@lru_cache(maxsize=4096)
def fetch_pom(group_id: str, artifact_id: str, version: str):
    """POM text from Maven Central, or None. Cached — dependency graphs revisit
    the same coordinates constantly."""
    path = f"{group_id.replace('.', '/')}/{artifact_id}/{version}/{artifact_id}-{version}.pom"
    try:
        r = _SESSION.get(f"{CENTRAL}/{path}", timeout=30)
    except requests.RequestException:
        return None
    return r.text if r.status_code == 200 else None


def _strip_comments(text):
    return re.sub(r"<!--.*?-->", "", text or "", flags=re.S)


def parent_of(text):
    m = re.search(r"<parent>(.*?)</parent>", text or "", re.S)
    if not m:
        return None
    blk = m.group(1)
    g = re.search(r"<groupId>\s*([^<]+?)\s*</groupId>", blk)
    a = re.search(r"<artifactId>\s*([^<]+?)\s*</artifactId>", blk)
    v = re.search(r"<version>\s*([^<]+?)\s*</version>", blk)
    return (g.group(1), a.group(1), v.group(1)) if (g and a and v) else None


def properties(text, own_version=None, depth=0):
    """<properties> for this POM plus its parent chain, with project.version bound.
    Child properties win over the parent's."""
    text = _strip_comments(text)
    props = {}
    par = parent_of(text)
    if par and depth < MAX_DEPTH:
        ptext = fetch_pom(*par)
        if ptext:
            props.update(properties(ptext, par[2], depth + 1))
    for sec in re.findall(r"<properties>(.*?)</properties>", text, re.S):
        for name, val in re.findall(r"<([\w.\-]+)>\s*([^<]*?)\s*</\1>", sec):
            props[name] = val.strip()
    # project.version MUST come from the coordinate we actually fetched. Inferring
    # it from the text is wrong whenever a POM inherits from an unrelated parent:
    # axon-spring-boot-starter:4.5's parent is spring-boot-starters:2.2.13.RELEASE,
    # so guessing gave ${project.version}=2.2.13.RELEASE and sent the walk chasing
    # axon artifacts at Spring Boot's version, which do not exist.
    own = own_version
    if own is None:
        m = re.search(r"</parent>\s*(?:<(?!version)[^>]+>[^<]*</[^>]+>\s*)*?"
                      r"<version>\s*([^<]+?)\s*</version>", text, re.S)
        own = m.group(1) if m else (par[2] if par else None)
    if par:
        props.setdefault("project.parent.version", par[2])
    if own:
        props["project.version"] = own
        props["project.parent.version"] = props.get("project.parent.version", own)
    return props


def expand(value, props, depth=0):
    """Resolve ${...} placeholders. None when unresolvable — never a guess."""
    if value is None:
        return None
    value = value.strip()
    if "${" not in value:
        return value or None
    if depth > 6:
        return None
    def sub(m):
        return props.get(m.group(1), m.group(0))
    out = re.sub(r"\$\{([\w.\-]+)\}", sub, value)
    if out == value:
        return None
    return expand(out, props, depth + 1) if "${" in out else (out or None)


def _dep_blocks(text, section=None):
    body = text
    if section:
        m = re.search(rf"<{section}>(.*?)</{section}>", text, re.S)
        if not m:
            return []
        body = m.group(1)
    return re.findall(r"<dependency>(.*?)</dependency>", body, re.S)


def _coords(blk):
    g = re.search(r"<groupId>\s*([^<]+?)\s*</groupId>", blk)
    a = re.search(r"<artifactId>\s*([^<]+?)\s*</artifactId>", blk)
    v = re.search(r"<version>\s*([^<]+?)\s*</version>", blk)
    scope = re.search(r"<scope>\s*([^<]+?)\s*</scope>", blk)
    return (g.group(1) if g else None, a.group(1) if a else None,
            v.group(1) if v else None, scope.group(1) if scope else "compile")


def declared_version(text, target_g, target_a, props=None):
    """Target version declared directly in this POM (or its dependencyManagement)."""
    text = _strip_comments(text)
    props = props if props is not None else properties(text)
    for section in (None, "dependencyManagement"):
        for blk in _dep_blocks(text, section):
            g, a, v, _ = _coords(blk)
            if a == target_a and (g is None or g == target_g):
                return expand(v, props)
    return None


def resolve(text, target_g, target_a, depth=0, seen=None, own_version=None):
    """Version of target_g:target_a this POM resolves to. Returns (version, path).

    Breadth-first, and deliberately LEVEL-COMPLETE: it does not return on the first
    hit, it finishes the whole depth level and requires every occurrence at that
    level to agree. Returning the first hit produced a false positive on
    einsteinarbert/axon-saga-example — a "upgrade version of spring boot" commit
    where Axon did not change at all (4.6.1 on both sides), but the parent side
    happened to reach xstream 1.4.10 by a different path. The resolved version had
    not moved; the path my search took had. Disagreement at the shallowest level
    now yields (None, []) => unknown, never a version.
    """
    if text is None:
        return None, []
    level = [(text, own_version, [])]
    seen = seen if seen is not None else set()
    for d in range(MAX_DEPTH + 1):
        hits, nxt = [], []
        for cur, cur_v, path in level:
            if cur is None:
                continue
            cur = _strip_comments(cur)
            props = properties(cur, cur_v)

            direct = declared_version(cur, target_g, target_a, props)
            if direct:
                hits.append((direct, path + [f"{target_g}:{target_a} (declared)"]))
                continue

            par = parent_of(cur)
            if par:
                ptext = fetch_pom(*par)
                if ptext:
                    v = declared_version(ptext, target_g, target_a,
                                         properties(ptext, par[2]))
                    if v:
                        hits.append((v, path + [f"parent {par[0]}:{par[1]}:{par[2]}",
                                                f"{target_g}:{target_a}"]))
                        continue

            if d == MAX_DEPTH:
                continue
            for blk in _dep_blocks(cur):
                g, a, v, scope = _coords(blk)
                if not g or not a or scope in ("test", "provided", "system"):
                    continue
                cv = expand(v, props)
                if not cv:
                    continue
                key = (g, a, cv)
                if key in seen:
                    continue
                seen.add(key)
                child = fetch_pom(g, a, cv)
                if child:
                    nxt.append((child, cv, path + [f"{g}:{a}:{cv}"]))

        if hits:
            versions = {v for v, _ in hits}
            if len(versions) > 1:
                # genuinely ambiguous at this depth: Maven would mediate, we will not guess
                return None, []
            return hits[0]
        if not nxt:
            break
        level = nxt
    return None, []


def resolve_from_client(pom_text, target_g, target_a, client_version=None):
    """Entry point for a client pom. Returns
    {version, kind: direct|transitive|unresolved, path}."""
    props = properties(pom_text or "", client_version)
    direct = declared_version(pom_text or "", target_g, target_a, props)
    if direct:
        return {"version": direct, "kind": "direct", "path": ["declared in client pom"]}
    v, path = resolve(pom_text, target_g, target_a, own_version=client_version)
    if v:
        return {"version": v, "kind": "transitive", "path": path}
    return {"version": None, "kind": "unresolved", "path": []}


if __name__ == "__main__":
    # Fixture: the Axon chain that declared-version traversal cannot see.
    print("fixture: artshishkin — xstream via axon-spring-boot-starter\n")
    ok = True
    for axon_v, expect in (("4.5", "1.4.16"), ("4.5.14", "1.4.19")):
        pom = f"""<project><modelVersion>4.0.0</modelVersion>
          <groupId>x</groupId><artifactId>y</artifactId><version>1</version>
          <properties><axon.version>{axon_v}</axon.version></properties>
          <dependencies><dependency>
            <groupId>org.axonframework</groupId>
            <artifactId>axon-spring-boot-starter</artifactId>
            <version>${{axon.version}}</version>
          </dependency></dependencies></project>"""
        r = resolve_from_client(pom, "com.thoughtworks.xstream", "xstream")
        good = r["version"] == expect
        ok &= good
        print(f"  [{'PASS' if good else 'FAIL'}] axon {axon_v:<7} -> xstream "
              f"{r['version']} (expected {expect}, kind={r['kind']})")
        if r["path"]:
            print(f"          via {' -> '.join(r['path'])}")
    print("\n1.4.16 < 1.4.18 <= 1.4.19  =>  a real transitive boundary crossing"
          if ok else "\nFIXTURE FAILED")
    sys.exit(0 if ok else 1)
