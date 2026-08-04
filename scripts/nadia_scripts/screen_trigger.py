#!/usr/bin/env python3
"""
screen_trigger.py — does the client actually EXERCISE the broken behaviour?

The gate every other gate assumes. All the existing checks ask about the client's
CODE: is it a production adaptation, does the diff reference the library, is it on
the default branch, did it cross the boundary, does it compile across it. None asks
whether the client's DATA or USAGE ever reaches the path whose behaviour changed.

A candidate can pass all five and still have no behavioural break. Verified on
adityajoy-1902/Dashboard-V-2: traversal-confirmed (snakeyaml 1.29->2.0, same
commit), Maven, on the default branch — but it loads YAML with a root-type
Constructor(Application.class) and NO global tags anywhere in its resources.
snakeyaml 2.0's TagInspector rejects global tags; this client has none, so nothing
can throw. Its whole change was a compile migration.

Trigger definitions live in the catalog per break, because each break denies a
different thing:

  "trigger": {
    "kind": "resource_pattern",
    "resource_suffixes": [".yml", ".yaml"],
    "pattern": "!!\\s*[A-Za-z_]\\w*(?:\\.\\w+)+"
  }

Verdicts:
  triggers     a matching construct is present -> the break can fire here
  no_trigger   resources were found and searched, nothing matched -> cannot fire
  unknown      nothing to search, scan cap hit, or no trigger defined for the break
               (notably: YAML supplied at runtime is undecidable from source)

`no_trigger` is a real negative and is safe to exclude. `unknown` is NOT — it means
the question could not be answered and the candidate needs a human look.

Usage:
  python screen_trigger.py <break_id> --in <jsonl> [--limit N] [--behavioural-only]
  python screen_trigger.py <break_id> --repo R --sha S
"""

import argparse
import json
import re
import sys
from pathlib import Path

import bbc_e2e as B

HERE = Path(__file__).resolve().parent
# Per repo. Beyond this the gate declines to claim a clean negative rather than
# guessing — but the cap is a COST limit, not evidence, so a large repo landing in
# `unknown` says nothing about the library. Raise it (--max-resources) and re-run the
# unknowns before treating an all-negative tally as final.
MAX_RESOURCES = 40


def get_trigger(brk):
    t = brk.get("trigger")
    if not t or t.get("kind") != "resource_pattern":
        return None
    return {"suffixes": tuple(t.get("resource_suffixes") or []),
            "regex": re.compile(t["pattern"]),
            "description": t.get("description", "")}


def parent_of(repo, sha, token):
    c = B._gh(f"{B.GH}/repos/{repo}/commits/{sha}", token)
    if not isinstance(c, dict) or not c.get("parents"):
        return None
    return c["parents"][0]["sha"]


def list_resources(repo, ref, suffixes, token):
    """Repo-tree paths with a matching suffix. Skips build output (target/, build/)
    which mirrors src resources and would double-count."""
    t = B._gh(f"{B.GH}/repos/{repo}/git/trees/{ref}", token, recursive=1)
    if not isinstance(t, dict) or "tree" not in t:
        return None, False
    paths = [x["path"] for x in t["tree"]
             if x.get("type") == "blob" and x["path"].endswith(suffixes)
             and not re.match(r"(^|.*/)(target|build|out|node_modules)/", x["path"])]
    return paths, bool(t.get("truncated"))


def screen_trigger(repo, sha, brk, token, max_resources=MAX_RESOURCES):
    trig = get_trigger(brk)
    if not trig:
        return {"verdict": "unknown", "reason": "no trigger defined for this break"}
    parent = parent_of(repo, sha, token)
    if not parent:
        return {"verdict": "unknown", "reason": "parent commit unavailable"}

    paths, truncated = list_resources(repo, parent, trig["suffixes"], token)
    if paths is None:
        return {"verdict": "unknown", "reason": "repo tree unavailable"}
    if not paths:
        return {"verdict": "unknown",
                "reason": f"no {'/'.join(trig['suffixes'])} resources in the repo "
                          f"(data likely supplied at runtime -> undecidable)"}
    if len(paths) > max_resources:
        return {"verdict": "unknown", "resources_found": len(paths),
                "reason": f"{len(paths)} resources exceeds the {max_resources} scan cap; "
                          f"cannot claim a clean negative"}

    hits, scanned = [], 0
    for p in paths:
        text = B._gh_file(repo, p, parent, token)
        if text is None:
            continue
        scanned += 1
        m = trig["regex"].search(text)
        if m:
            hits.append({"file": p, "match": m.group(0)[:60]})
    if hits:
        return {"verdict": "triggers", "hits": hits, "scanned": scanned,
                "reason": f"{len(hits)} resource(s) contain the trigger construct "
                          f"(e.g. {hits[0]['file']}: '{hits[0]['match']}')"}
    if truncated:
        return {"verdict": "unknown", "scanned": scanned,
                "reason": "repo tree was truncated; some resources unseen"}
    return {"verdict": "no_trigger", "scanned": scanned,
            "reason": f"scanned {scanned} resource(s), none contain the trigger "
                      f"construct -> the break cannot fire in this client"}


def _self_test(brk):
    """Validate the PATTERN itself offline. This does not prove the pipeline works,
    only that the regex distinguishes global tags from the constructs that must not
    match — the standard YAML tags and local tags."""
    trig = get_trigger(brk)
    if not trig:
        print("no trigger defined; skipping pattern self-test")
        return 0
    cases = [
        ("items:\n  - !!com.example.MyNode\n    name: a", True, "global tag, FQN"),
        ("a: !!org.yaml.Foo {}", True, "global tag, short package"),
        ("count: !!int 3", False, "standard YAML tag (no dot)"),
        ("s: !!str hello", False, "standard YAML tag"),
        ("m: !!map {}", False, "standard YAML tag"),
        ("x: !property FOO", False, "LOCAL tag — resolved from yamlConstructors, "
                                    "never reaches the TagInspector"),
        ("y: !instance com.foo.Bar", False, "local tag whose VALUE is dotted"),
        ("applications:\n  - name: ExampleApp\n    env: prod", False,
         "Dashboard-V-2 shape: plain properties, no tags"),
    ]
    fails = 0
    print("pattern self-test:")
    for text, expect, label in cases:
        got = bool(trig["regex"].search(text))
        ok = got == expect
        fails += not ok
        print(f"  [{'PASS' if ok else 'FAIL'}] expect={expect!s:<5} got={got!s:<5} {label}")
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("break_id")
    ap.add_argument("--in", dest="infile")
    ap.add_argument("--repo")
    ap.add_argument("--sha")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--behavioural-only", action="store_true",
                    help="only rows whose compile screen said 'behavioural'")
    ap.add_argument("--max-resources", type=int, default=MAX_RESOURCES,
                    help="per-repo resource scan cap; raise it to resolve `unknown` "
                         "rows caused by the cap rather than by real ambiguity")
    ap.add_argument("--unknown-only", action="store_true",
                    help="only rows whose previous trigger screen was `unknown`")
    ap.add_argument("--self-test", action="store_true",
                    help="validate the trigger regex offline and exit")
    args = ap.parse_args()

    brk = B.get_break(args.break_id)
    if args.self_test:
        sys.exit(1 if _self_test(brk) else 0)
    if _self_test(brk):
        sys.exit("pattern self-test failed; fix the catalog regex before screening")
    print()

    token = B._token()
    if args.repo and args.sha:
        rows = [{"repo": args.repo, "sha": args.sha}]
    else:
        src = Path(args.infile)
        rows = [json.loads(l) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()]
        if args.behavioural_only:
            rows = [r for r in rows
                    if (r.get("compile_screen") or {}).get("verdict") == "behavioural"]
        if args.unknown_only:
            rows = [r for r in rows
                    if (r.get("trigger_screen") or {}).get("verdict") == "unknown"]
        if args.limit:
            rows = rows[:args.limit]

    tally, out = {}, []
    for i, r in enumerate(rows, 1):
        res = screen_trigger(r["repo"], r["sha"], brk, token, args.max_resources)
        tally[res["verdict"]] = tally.get(res["verdict"], 0) + 1
        r["trigger_screen"] = res
        out.append(r)
        tag = {"triggers": "FIRES", "no_trigger": "NOFIRE", "unknown": "  ?   "}[res["verdict"]]
        print(f"[{i}/{len(rows)}] [{tag}] {r['repo']}@{r['sha'][:8]}  {res['reason'][:88]}",
              flush=True)

    print(f"\n[trigger] {tally}")
    fires = [r for r in out if r["trigger_screen"]["verdict"] == "triggers"]
    if fires:
        print("\nCandidates where the break CAN fire:")
        for r in fires:
            h = r["trigger_screen"]["hits"][0]
            print(f"  {r['repo']}@{r['sha'][:8]}  {h['file']}  '{h['match']}'")
    if args.infile:
        dst = Path(args.infile).with_name(Path(args.infile).stem + "_TRIGGER.jsonl")
        with dst.open("w", encoding="utf-8") as fh:
            for r in out:
                fh.write(json.dumps(r) + "\n")
        print(f"[trigger] saved -> {dst}")


if __name__ == "__main__":
    main()
