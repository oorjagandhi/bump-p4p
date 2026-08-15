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


def _ask(system: str, user: str, max_tokens: int = 32000) -> str:
    """One Claude turn. Adaptive thinking + high effort for code-generation quality.

    STREAMED, and with a much larger budget than the 8000 this used to carry, because
    `max_tokens` caps thinking AND response text together. On the first real Path A run
    (oracle/weblogic-deploy-tooling, 2026-08-15) adaptive thinking consumed most of an
    8000-token budget and the Java came back cut off mid-comment. The truncated source
    was written to disk and handed to Maven, which of course failed to compile it — so a
    token-budget mistake presented as a candidate that "does not build". Streaming keeps
    a budget this size from tripping the SDK's non-streaming HTTP timeout.

    A `max_tokens` stop is now an ERROR rather than a shorter string: half a driver is
    never the right answer, and letting it through turns a harness fault into a finding
    about the client.
    """
    with _client().messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=system,
        messages=[{"role": "user", "content": user}],
    ) as stream:
        resp = stream.get_final_message()
    if resp.stop_reason == "max_tokens":
        raise RuntimeError(
            f"SEAM output truncated at max_tokens={max_tokens} (model={MODEL}). "
            f"Raise the budget; do not use the partial result.")
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"SEAM refused: {getattr(resp, 'stop_details', None)}")
    return "".join(b.text for b in resp.content if b.type == "text")


def _strip_fences(s: str) -> str:
    """Unwrap a ```java fence. Tolerates a missing CLOSING fence.

    The old pattern required both fences, so an unterminated one fell through to `else s`
    and the literal ```java line was written into the .java file — the second half of the
    truncation failure above. Now the opening fence is stripped whether or not it closes,
    and a leading fence that survives is treated as a bug rather than as source.
    """
    m = re.search(r"```(?:java)?\s*(.*?)```", s, re.S)      # fenced, properly closed
    if not m:
        m = re.search(r"```(?:java)?\s*(.*)\Z", s, re.S)    # fence opened, never closed
    out = (m.group(1) if m else s).strip() + "\n"
    if out.lstrip().startswith("```"):
        raise RuntimeError("SEAM output still starts with a code fence after stripping")
    return out


def _load(name: str) -> str:
    return open(os.path.join(PROMPTS, name), encoding="utf-8").read()


# ---- input gathering (deterministic) --------------------------------------

def _git(args, cwd) -> str:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True).stdout


def _detect_framework(repo_dir: str) -> str:
    """Detect JUnit4 vs Jupiter on the module's classpath.

    Robust to Jupiter arriving TRANSITIVELY: Spring Boot's spring-boot-starter-test
    (2.2+) pulls junit-jupiter with no literal 'junit-jupiter' string in the repo, which
    the old literal grep missed -> it wrongly reported junit4 and the generated JUnit4
    test failed to compile against a Jupiter-only classpath.
    """
    def grep(pat: str) -> str:
        return subprocess.run(["git", "grep", "-lE", pat], cwd=repo_dir,
                              capture_output=True, text=True).stdout.strip()
    jupiter = grep(r"junit-jupiter|org\.junit\.jupiter|spring-boot-starter-test")
    junit4 = grep(r"import +org\.junit\.Test;|<artifactId>junit</artifactId>|org\.junit\.runner")
    if jupiter:
        return "jupiter (JUnit5)"
    if junit4:
        return "junit4"
    return "jupiter (JUnit5)"   # modern-Maven default when neither signal is present


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
