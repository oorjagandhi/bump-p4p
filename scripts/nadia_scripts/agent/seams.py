#!/usr/bin/env python3
"""
Live implementations of the two LLM-judgment seams, calling Claude via the Anthropic SDK.

SEAM_A (generate_test)      -> writes a JUnit driver that drives the client's real production path.
SEAM_B (diagnose_nontrip)   -> when state 2 doesn't fail, adjusts the FIXTURE (or gives up).

Auth: uses the zero-arg anthropic.Anthropic() client, which resolves credentials from
ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / an `ant auth login` profile. No key is hard-coded.
Model defaults to claude-opus-4-8 (override with BBC_AGENT_MODEL). anthropic is imported
lazily so this module imports even when the SDK/key are absent (the orchestrator stays runnable).
"""
from __future__ import annotations
import os, re, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
PROMPTS = os.path.join(HERE, "prompts")
MODEL = os.environ.get("BBC_AGENT_MODEL", "claude-opus-4-8")


def _client():
    import anthropic  # lazy: keeps this module importable without the SDK installed
    return anthropic.Anthropic()


def _ask(system: str, user: str, max_tokens: int = 8000) -> str:
    """One Claude turn. Adaptive thinking + high effort for code-generation quality."""
    resp = _client().messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def _strip_fences(s: str) -> str:
    m = re.search(r"```(?:java)?\s*(.*?)```", s, re.S)
    return (m.group(1) if m else s).strip() + "\n"


def _load(name: str) -> str:
    return open(os.path.join(PROMPTS, name), encoding="utf-8").read()


# ---- input gathering (deterministic) --------------------------------------

def _git(args, cwd) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True).stdout


def _detect_framework(repo_dir: str) -> str:
    out = subprocess.run(["git", "grep", "-l", "junit-jupiter"], cwd=repo_dir,
                         capture_output=True, text=True).stdout
    return "jupiter (JUnit5)" if out.strip() else "junit4"


def _gather(cand, repo_dir: str) -> dict:
    diff = _git(["show", cand.adapt_sha, "--", *(cand.production_files or [])], repo_dir)
    prod = ""
    for f in (cand.production_files or [])[:2]:
        p = os.path.join(repo_dir, f)
        if os.path.exists(p):
            prod += f"// {f}\n" + open(p, encoding="utf-8", errors="ignore").read()[:4000] + "\n\n"
    return {"diff": diff[:6000], "prod": prod[:6000], "framework": _detect_framework(repo_dir)}


# ---- the seams ------------------------------------------------------------

def generate_test(brk: dict, cand, repo_dir: str) -> str:
    """SEAM_A: return compilable JUnit source for bbc.BbcTest driving the real production path."""
    inp = _gather(cand, repo_dir)
    lib, v = brk["library"], brk.get("verify", {})
    user = (
        f"BREAK: {lib['group_id']}:{lib['artifact_id']} "
        f"{lib.get('from_version')} -> {lib.get('to_version')}, boundary {v.get('break_boundary')}\n"
        f"SIGNAL that state 2 must produce: {v.get('signal_grep')}\n"
        f"BUMP failing tests (shape only, do NOT copy): "
        f"{brk.get('characterization', {}).get('failing_tests')}\n"
        f"TEST FRAMEWORK ON CLASSPATH: {inp['framework']}\n\n"
        f"ADAPTATION DIFF:\n{inp['diff']}\n\n"
        f"ADAPTED PRODUCTION CODE:\n{inp['prod']}\n\n"
        "Output ONLY the .java source for a class bbc.BbcTest (package bbc)."
    )
    return _strip_fences(_ask(_load("seam_a_testgen.md"), user))


def diagnose_nontrip(brk: dict, cand, current_test: str, state2_log: str,
                     attempt: int, max_retries: int) -> str | None:
    """SEAM_B: state 2 passed unexpectedly. Return an adjusted fixture, or None to give up."""
    v = brk.get("verify", {})
    user = (
        f"SIGNAL wanted on state 2: {v.get('signal_grep')}\n"
        f"Attempt {attempt} of {max_retries}\n\n"
        f"CURRENT TEST:\n{current_test}\n\n"
        f"STATE 2 OUTPUT (it PASSED; expected FAIL):\n{state2_log[-3000:]}\n\n"
        "Return an adjusted .java fixture (same rules as SEAM A), "
        "or the literal token 'GIVE_UP: <reason>' if not standalone-reproducible."
    )
    out = _ask(_load("seam_b_diagnose.md"), user)
    if out.strip().startswith("GIVE_UP"):
        return None
    return _strip_fences(out)
