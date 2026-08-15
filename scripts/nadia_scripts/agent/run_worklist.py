#!/usr/bin/env python3
"""
Run a fan-out worklist through the verification agent, one candidate at a time.

WHY THIS EXISTS. fanout.py produces the queue and orchestrator.py knows how to verify
ONE candidate, but nothing joined them: every corpus so far was driven by a hand-written
acceptance_*.py per repo. That does not scale past a couple of cases, and it loses the
per-candidate outcome unless someone remembers to write it down.

Two things this adds over calling orchestrator.verify_candidate directly:

  1. A PROBE-ONLY pass. The version-knob probe (orchestrator P3) is the cheapest stage
     that can reject a candidate outright -- ua-parser/uap-java died there, on a build
     that resolves snakeyaml 1.33 no matter what -D you hand it -- and it needs no test
     to have been written. Running it across the whole worklist first means driver-test
     effort is only spent on candidates whose differential can actually be controlled.

  2. A PATH-B SEAM. seams.py answers SEAM_A by calling the Anthropic API, which needs a
     credential this machine does not have. The seam is a JUDGEMENT, not an API call:
     an agent reads the adaptation diff and writes a driver that exercises the client's
     real production path. `--driver <file.java>` accepts that judgement from a file, so
     the deterministic stages run identically whichever way the driver was authored.
     Drivers live in verified_cases/drivers/ alongside the three already there.

Disk is the other constraint (this box runs at ~4 GB free): each candidate is cloned
blob-filtered, verified, and deleted before the next one starts, unless --keep.

Usage:
  python run_worklist.py <worklist.json> --probe-only
  python run_worklist.py <worklist.json> --repo owner/name --driver <BbcTest.java> [--jdk 17]
  python run_worklist.py <worklist.json> --repo owner/name --probe-only --keep
"""
from __future__ import annotations
import argparse, json, os, re, shutil, stat, subprocess, sys, tempfile, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import orchestrator as O

OUT = os.path.join(O.NADIA, "output")
DRIVERS = os.path.join(O.NADIA, "verified_cases", "drivers")


def force_rmtree(path):
    """Windows locks .git pack files read-only; plain rmtree fails on them."""
    def onerror(func, fpath, _exc):
        try:
            os.chmod(fpath, stat.S_IWRITE)
            func(fpath)
        except Exception:
            pass
    shutil.rmtree(path, onerror=onerror)


def ledger_path(worklist_path: str) -> str:
    """output/_<lib>_differential.jsonl, matching the corpus files already in output/."""
    base = os.path.basename(worklist_path)
    lib = "snakeyaml" if "snakeyaml" in base else base.replace("worklist_", "").split("-")[0]
    return os.path.join(OUT, f"_{lib}_differential.jsonl")


def already_done(ledger: str) -> dict:
    done = {}
    if os.path.exists(ledger):
        for line in open(ledger, encoding="utf-8"):
            if line.strip():
                d = json.loads(line)
                done[(d.get("repo"), d.get("break_id"))] = d
    return done


def append(ledger: str, row: dict):
    with open(ledger, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def _vt(s):
    """Leading dotted-numeric tuple, e.g. '1.30.1' -> (1,30,1); None on garbage."""
    if not s:
        return None
    parts = []
    for tok in str(s).split("."):
        num = ""
        for ch in tok:
            if ch.isdigit():
                num += ch
            else:
                break
        if not num:
            break
        parts.append(int(num))
    return tuple(parts) or None


def baseline_for(brk: dict, item: dict) -> tuple[str, str]:
    """(version, provenance) to run state 1 at.

    Prefer the version the client ACTUALLY came from, read off its own crossing, over the
    catalog's generic runnable_baseline -- that is the difference between the worldedit
    case (state 1 is the version they were really on) and infoarchive (a baseline we
    assembled). Falls back to the catalog when the crossing's `from` is missing or is not
    provably below the boundary.
    """
    cat = brk.get("verify", {}).get("runnable_baseline")
    boundary = brk.get("verify", {}).get("break_boundary")
    frm = (item.get("crossing") or {}).get("from")
    if _vt(frm) and _vt(boundary) and _vt(frm) < _vt(boundary):
        return frm, "crossing.from (the client's own previous version)"
    return cat, "catalog runnable_baseline"


def probe(item: dict, brk: dict, repo_dir: str, jdk: str, baseline: str) -> dict:
    lib = brk["library"]
    props = O.probe_version_props(
        repo_dir, jdk, item.get("module", ""), lib["group_id"], lib["artifact_id"],
        brk.get("verify", {}).get("version_property", ""),
        lib["artifact_id"].split("-")[0].lower(), baseline)
    return props


def pin_version_property(repo_dir: str, group_id: str, artifact_id: str, prop: str) -> list:
    """Rewrite the library's hardcoded <version> literal into ${prop}, in every POM declaring it.

    WHY. The probe's honest answer for onthegomap/planetiler is "there is no knob": the
    version lives in the root POM's dependencyManagement as a bare `<version>2.8</version>`,
    named by no property, so no -D can move it. That is a fact about the CLIENT'S BUILD, not
    about the break -- and planetiler is otherwise the cleanest adaptation in the corpus (one
    production entry point, limit raised to Integer.MAX_VALUE). Refusing it would discard a
    real case over a build-file convention.

    This is the same rewrite `gen-harness --reuse-pom` performs, and it is safe for the same
    reason the property GUESSES are safe: it is followed by the probe, which MEASURES whether
    the version actually moves. A rewrite that misses (wrong POM, version inherited from a
    BOM we did not touch) shows up as a failed probe, not as a silently wrong differential.

    Returns the POMs changed, so the intervention appears in the ledger instead of nowhere.
    """
    dep_re = re.compile(
        r"(<dependency>(?:(?!</dependency>).)*?"
        r"<groupId>\s*" + re.escape(group_id) + r"\s*</groupId>"
        r"(?:(?!</dependency>).)*?"
        r"<artifactId>\s*" + re.escape(artifact_id) + r"\s*</artifactId>"
        r"(?:(?!</dependency>).)*?)"
        r"<version>\s*[^<${][^<]*</version>", re.S)
    changed = []
    for dirpath, _dirs, files in os.walk(repo_dir):
        if ".git" in dirpath or "pom.xml" not in files:
            continue
        path = os.path.join(dirpath, "pom.xml")
        text = open(path, encoding="utf-8", errors="replace").read()
        new, n = dep_re.subn(r"\1<version>${" + prop + "}</version>", text)
        if n:
            open(path, "w", encoding="utf-8").write(new)
            changed.append(os.path.relpath(path, repo_dir))
    return changed


def inject_library_dep(repo_dir: str, module: str, group_id: str, artifact_id: str,
                       prop: str) -> str | None:
    """Declare the library as a DIRECT dependency at ${prop}, for clients that get it
    transitively.

    A -D property only moves a version the build actually names. When the library arrives
    through someone else's dependency tree there is nothing to name and nothing to pin:
    artshishkin/art-kargopolov-cqrs-saga-axon-microservices gets xstream via Axon, so the
    probe measured 1.4.19 no matter what was asked for, and the run died at `setup:` — on a
    case verified by hand long ago. The original acceptance harness for it did exactly what
    this does, by hand.

    Adding a depth-1 declaration is version-neutral in the sense that matters: Maven's
    nearest-wins rule then lets the property decide, and every state gets the same treatment.
    It DOES change the dependency graph, so it is recorded in the ledger, and the probe still
    measures the result rather than assuming it.
    """
    pom = os.path.join(repo_dir, module or "", "pom.xml")
    if not os.path.exists(pom):
        return None
    text = open(pom, encoding="utf-8", errors="replace").read()
    if f"<artifactId>{artifact_id}</artifactId>" in text:
        return None                      # already declared; pinning was the right tool
    i = text.find("<dependencies>")
    if i < 0:
        return None
    i += len("<dependencies>")
    dep = (f"\n        <dependency>\n"
           f"            <groupId>{group_id}</groupId>\n"
           f"            <artifactId>{artifact_id}</artifactId>\n"
           f"            <version>${{{prop}}}</version>\n"
           f"        </dependency>")
    open(pom, "w", encoding="utf-8", newline="").write(text[:i] + dep + text[i:])
    return os.path.relpath(pom, repo_dir)


JUNIT4_DEP = """
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.13.2</version>
            <scope>test</scope>
        </dependency>"""


def inject_test_dep(pom_path: str) -> bool:
    """Add a test-scoped JUnit 4 dependency to a POM that declares no test framework.

    Some clients have no tests at all -- Brokkonaut/GlobalConnectionServer declares log4j,
    jline, semver4j, mariadb and snakeyaml, and nothing else. Surefire then runs nothing, and
    a differential that runs nothing proves nothing. Injecting a test framework is the same
    class of intervention as injecting the driver .java itself: it is version-neutral with
    respect to the library under test, it is applied identically to all three states, and it
    is recorded in the ledger (`test_dep_injected`) rather than done quietly.

    JUnit 4 specifically, not Jupiter: Maven's super-POM binds maven-surefire-plugin 2.12.4,
    which cannot run Jupiter tests, and pinning a newer surefire is a much larger change to
    the client's build than adding one test-scoped jar.
    """
    text = open(pom_path, encoding="utf-8").read()
    if "<artifactId>junit</artifactId>" in text or "junit-jupiter" in text:
        return False
    i = text.find("<dependencies>")
    if i < 0:
        return False
    i += len("<dependencies>")
    open(pom_path, "w", encoding="utf-8").write(text[:i] + JUNIT4_DEP + text[i:])
    return True


def why_unresolvable(repo_dir: str, jdk: str, module: str, group_id: str, artifact_id: str) -> str:
    """Separate 'the build never ran' from 'the library is genuinely not in this build'.

    probe_version_props reports `resolved None` for BOTH, and they mean opposite things: the
    first is a harness problem (a missing parent artifact, an unreachable repository, a
    goal that needs generated sources), the second is a real answer -- the candidate does
    not depend on the library where we looked. Left conflated, a broken clone reads as
    'not a case'. So when resolution comes back None, ask Maven once more and quote what it
    actually said.
    """
    cmd = O.mvn_base() + ["-B", "-U", "dependency:list", f"-DincludeGroupIds={group_id}",
                          f"-DincludeArtifactIds={artifact_id}"] + (["-pl", module] if module else [])
    p = subprocess.run(cmd, cwd=repo_dir, capture_output=True, text=True,
                       env=dict(os.environ, JAVA_HOME=jdk))
    if p.returncode == 0:
        return (f"build SUCCEEDED but lists no {group_id}:{artifact_id} — the library is not a "
                f"dependency of this reactor (wrong module, shaded, or provided elsewhere)")
    errs = [l.strip() for l in (p.stdout + p.stderr).splitlines() if "[ERROR]" in l][:4]
    return "build FAILED, so the probe measured nothing: " + " | ".join(errs or ["(no [ERROR] lines)"])


def run_one(item: dict, args, ledger: str) -> dict:
    if args.module:
        item = dict(item, module=args.module)
    brk = O.load_break(item["break_id"])
    baseline, baseline_why = baseline_for(brk, item)
    jdk_key = args.jdk or str(brk.get("verify", {}).get("java", "17"))
    jdk = O.JDKS.get(jdk_key)
    if not jdk or not os.path.exists(os.path.join(jdk, "bin", "java.exe")):
        return {"repo": item["repo"], "break_id": item["break_id"], "outcome": O.OUTCOME_FAILED,
                "reason": f"JDK {jdk_key} not installed"}

    workdir = args.workdir or tempfile.mkdtemp(prefix="bbc_")
    repo_dir = os.path.join(workdir, item["repo"].replace("/", "_"))
    row = {"repo": item["repo"], "break_id": item["break_id"],
           "adapt_sha": item["adapt_sha"], "parent_sha": item["parent_sha"],
           "crossing": item.get("crossing"), "jdk": jdk_key,
           "baseline": baseline, "baseline_provenance": baseline_why,
           "test_dep_injected": bool(args.add_test_dep),
           "module": item.get("module", "") or None,
           "mvn_args": args.mvn_arg or None,
           "build_env": dict(args.env or []) or None}
    # Re-verification rows carry the answer they are being checked against, so the ledger
    # scores itself instead of needing the case files opened alongside it.
    if item.get("known_outcome"):
        row["known_outcome"] = item["known_outcome"]
        row["case_file"] = item.get("case_file")
    t0 = time.time()
    try:
        if not os.path.exists(repo_dir):
            print(f"  [clone] {item['repo']} @ {item['adapt_sha'][:10]}", flush=True)
            O.clone(item["repo"], item["adapt_sha"], repo_dir)

        pin_prop = brk.get("verify", {}).get("version_property", "") or "bbc.lib.version"
        if args.pin_version:
            lib = brk["library"]
            pinned = pin_version_property(repo_dir, lib["group_id"], lib["artifact_id"], pin_prop)
            row["version_pinned"] = pinned
            print(f"  [pin  ] {lib['artifact_id']} version -> ${{{pin_prop}}} in {pinned}", flush=True)

        print(f"  [probe] version knob for {brk['library']['artifact_id']}={baseline}", flush=True)
        try:
            props = probe(item, brk, repo_dir, jdk, baseline)
        except Exception as first_e:
            # No property controls the version. Before giving up, try rewriting the hardcoded
            # <version> literal to one and probing again — a client that names the version
            # with no property is a fact about its POM, not about the break.
            #
            # This was --pin-version, opt-in, and that was wrong: it needs the operator to
            # already know why the probe failed. On marklogic/marklogic-contentpump — a case
            # verified by hand long ago — the agent refused a known-good client because its
            # pom pins xstream twice as a literal. On a NEW candidate that refusal would have
            # read as "not verifiable" and nobody would have looked further.
            #
            # Safe to attempt unconditionally because the probe still MEASURES the result: a
            # rewrite that does not move the version fails exactly as before.
            if not args.pin_version:
                lib = brk["library"]
                pinned = pin_version_property(repo_dir, lib["group_id"], lib["artifact_id"],
                                              pin_prop)
                if pinned:
                    print(f"  [probe] no property controls the version; pinned literal -> "
                          f"${{{pin_prop}}} in {pinned}, re-probing", flush=True)
                    try:
                        props = probe(item, brk, repo_dir, jdk, baseline)
                        row["version_pinned"] = pinned
                        row["version_pinned_auto"] = True
                        args.pin_version = True     # keep it applied after every checkout
                    except Exception as e:
                        raise e from first_e
                else:
                    # Nothing to pin means the client never names the library: it arrives
                    # transitively. Declare it at depth 1 so the property has something to
                    # control, then measure again.
                    injected = inject_library_dep(repo_dir, item.get("module", ""),
                                                  lib["group_id"], lib["artifact_id"], pin_prop)
                    if not injected:
                        raise first_e
                    print(f"  [probe] library is transitive; declared it directly in "
                          f"{injected} at ${{{pin_prop}}}, re-probing", flush=True)
                    try:
                        props = probe(item, brk, repo_dir, jdk, baseline)
                        row["library_dep_injected"] = injected
                        args.inject_library_dep = True   # re-apply after every checkout
                    except Exception as e:
                        raise e from first_e
            else:
                raise first_e
        except Exception as e:
            reason = f"version knob probe: {e}"
            if "resolved None" in reason:
                lib = brk["library"]
                reason += " DIAGNOSIS: " + why_unresolvable(
                    repo_dir, jdk, item.get("module", ""), lib["group_id"], lib["artifact_id"])
            row.update(outcome=O.OUTCOME_FAILED, reason=reason, states=[])
            return row
        row["version_props"] = sorted(props)
        print(f"  [probe] OK -> {sorted(props)}", flush=True)

        if args.probe_only:
            row.update(outcome="probe_ok", reason="version knob works; differential not run")
            return row

        cand = O.Candidate(item["repo"], item["adapt_sha"], item["parent_sha"],
                           item.get("build_system", "maven"), item.get("module", ""),
                           item.get("production_files", []))

        if args.seam_a:
            # PATH A: the driver is written by the model, headless, from the adaptation diff
            # and the break spec -- no hand-authored answer anywhere in the loop. Credentials
            # come from the zero-arg anthropic.Anthropic() client, which resolves an
            # `ant auth login` profile as readily as ANTHROPIC_API_KEY; see seams.py.
            import seams
            # --add-test-dep means WE put the framework on the classpath, so we name it;
            # otherwise seams detects what the client declares.
            fw = "junit4" if args.add_test_dep else None
            print(f"  [SEAM_A] generating driver via {seams.MODEL}"
                  f"{' (framework: ' + fw + ', harness-supplied)' if fw else ''}", flush=True)
            driver_src = seams.generate_test(brk, cand, repo_dir, framework=fw)
            row["seam_a"] = f"path_a ({seams.MODEL})"
            drivers_dir = os.path.join(O.NADIA, "verified_cases", "drivers")
            os.makedirs(drivers_dir, exist_ok=True)
            gen_path = os.path.join(drivers_dir,
                                    f"{item['repo'].split('/')[-1]}_PathA_BbcTest.java")
            with open(gen_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(driver_src)
            row["driver"] = os.path.relpath(gen_path, O.NADIA)
            args._driver_path = gen_path       # so SEAM_B revisions overwrite the same file
            print(f"  [SEAM_A] {len(driver_src)} chars -> {row['driver']}", flush=True)
        else:
            driver_src = open(args.driver, encoding="utf-8").read()
            row["seam_a"] = f"path_b (file: {os.path.basename(args.driver)})"
        res = differential(brk, cand, repo_dir, jdk, props, baseline, driver_src, args,
                           pin_prop, jdk_key)
        row.update(res)
        return row
    except Exception as e:
        row.update(outcome=O.OUTCOME_FAILED, reason=f"setup: {e}")
        return row
    finally:
        row["seconds"] = round(time.time() - t0)
        if not args.keep and os.path.exists(repo_dir):
            force_rmtree(repo_dir)


def is_shape_b(driver_src: str) -> bool:
    """Does this driver use the two-method born-past-boundary shape?

    seam_a_testgen.md mandates the exact method names `preAdaptation` and `adapted` for
    Shape B precisely so the harness can recognise it, so matching on the @Test declarations
    is reading a contract rather than guessing. A driver with only one of the two names (a
    field called `adapted`, say) is not Shape B.
    """
    return all(re.search(rf"@Test\s+(?:public\s+)?\w[\w<>\[\], .]*\s+{name}\s*\(", driver_src)
               for name in ("preAdaptation", "adapted"))


def differential(brk, cand, repo_dir, jdk, props, baseline, driver_src, args, pin_prop="",
                 jdk_key="") -> dict:
    """The 3-state oracle, with the driver supplied rather than generated (Path B seam).

    States are the same ones orchestrator.verify_candidate runs; this copy exists so the
    driver comes from a file and so each state's log is written to _runlogs/ for reading
    afterwards -- a non-trip is only diagnosable if its output survived.
    """
    v = brk.get("verify", {})
    to_version = v.get("break_boundary") or brk["library"]["to_version"]

    # State 3 normally runs at the boundary too, so states 2 and 3 differ ONLY in code. Some
    # adaptations cannot be read that way, because the fix was written against a later
    # release and does not work at the boundary at all. Brokkonaut/GlobalConnectionServer is
    # the case: it sets setCodePointLimit(MAX_VALUE) on a LoaderOptions handed to
    # `new Yaml(new SafeConstructor(options))`, and at 1.32 that Yaml constructor builds its
    # own default LoaderOptions for the reader, so the limit set on the constructor is
    # ignored and the document still throws. The same code works at 2.x, which is what the
    # adaptation commit actually bumped to. Running state 3 at their real version measures
    # the adaptation they shipped; running it at the boundary measures one they never had.
    state3_version = getattr(args, "state3_version", None) or to_version
    signal = v.get("signal_grep", "")

    # jvm_add_opens is a JDK 9+ module-system flag. The catalog sets it for the JDK the break
    # is normally verified on (17 for xstream), but some clients only build on 8 — and there
    # `--add-opens` is not "ignored", it kills the forked JVM outright: surefire reports "The
    # forked VM terminated without properly saying goodbye", Tests run: 0, BUILD FAILURE. On
    # marklogic/marklogic-contentpump that looked exactly like a client whose tests cannot run.
    add_opens = v.get("jvm_add_opens")
    if add_opens and str(jdk_key) == "8":
        print(f"  [note] dropping {len(add_opens)} --add-opens flag(s): JDK 8 predates them",
              flush=True)
        add_opens = None
    test_class = args.test or "bbc.BbcTest"
    O.write_test(repo_dir, cand.module, driver_src, test_class.split(".")[-1])

    at = lambda ver: {k: ver for k in props}
    logs = os.path.join(O.NADIA, "_runlogs")
    os.makedirs(logs, exist_ok=True)
    slug = cand.repo.replace("/", "_")

    def state(name, sha, version):
        if sha:
            subprocess.run([O.GIT, "-C", repo_dir, "checkout", "-q", "-f", sha], check=True)
            O.write_test(repo_dir, cand.module, driver_src, test_class.split(".")[-1])
        if sha:
            # Re-apply every POM intervention: the checkout just restored the client's own
            # build files, so anything the probe stage rewrote is gone again.
            if args.pin_version:
                lib = brk["library"]
                pin_version_property(repo_dir, lib["group_id"], lib["artifact_id"], pin_prop)
            if getattr(args, "inject_library_dep", False):
                lib = brk["library"]
                inject_library_dep(repo_dir, cand.module, lib["group_id"], lib["artifact_id"],
                                   pin_prop)
        if args.add_test_dep:
            inject_test_dep(os.path.join(repo_dir, cand.module or "", "pom.xml"))
        print(f"  [state {name}] {brk['library']['artifact_id']}={version}", flush=True)
        s = O.run_state(repo_dir, jdk, test_class, at(version), add_opens=add_opens,
                        extra_args=args.mvn_arg, extra_env=dict(args.env or []))
        with open(os.path.join(logs, f"{slug}_{name}.log"), "w", encoding="utf-8") as f:
            f.write(s["log"])
        # Which test METHODS failed, not just how many. A driver with more than one @Test
        # cannot be scored in aggregate: SEAM_A sometimes emits the two-method "Shape B"
        # driver (a plain pre-adaptation stand-in beside the real production config), where
        # the stand-in is MEANT to keep failing at state 3. Counting that as a failed state
        # marks the whole case signature_confirmed -- which is exactly how openmrs/openmrs-core,
        # verified_bbc by hand, came back as a disagreement.
        s["failed_tests"] = sorted(set(re.findall(r"BbcTest\.(\w+)", s["log"])) - {"java"})
        print(f"  [state {name}] run={s['run']} fail={s['fail']} err={s['err']}", flush=True)
        return s

    s3 = state("3_adapted", cand.adapt_sha, state3_version)
    s2 = state("2_newlib_oldcode", cand.parent_sha, to_version)

    # SEAM_B: state 2 was supposed to fail and didn't. Under Path A the model gets the state-2
    # log back and adjusts the FIXTURE (bigger document, different entry point), bounded by
    # --seam-b-retries. Under Path B there is nobody to ask, so a non-trip is simply reported.
    attempt = 0
    while args.seam_a and not (s2["fail"] or s2["err"]) and attempt < args.seam_b_retries:
        attempt += 1
        import seams
        print(f"  [SEAM_B] state 2 did not trip; diagnosis attempt "
              f"{attempt}/{args.seam_b_retries}", flush=True)
        new_src = seams.diagnose_nontrip(brk, cand, driver_src, s2["log"],
                                         attempt, args.seam_b_retries)
        if not new_src:
            print("  [SEAM_B] gave up: not standalone-reproducible", flush=True)
            break
        driver_src = new_src
        # Persist the REVISION, not just SEAM_A's first draft. The driver is the evidence for
        # a verified case, and until this line the saved copy was whatever SEAM_A produced
        # before SEAM_B corrected it — so a green oracle pointed at a file that had never
        # passed. The working copy lives in a temp clone that is deleted on the way out.
        if args.seam_a and getattr(args, "_driver_path", None):
            with open(args._driver_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(driver_src)
        s2 = state("2_newlib_oldcode", cand.parent_sha, to_version)
    if attempt:
        # A revised fixture is a different test; state 3 must be re-run against the same source
        # or the three states are no longer comparable.
        s3 = state("3_adapted", cand.adapt_sha, state3_version)

    # Check the parent out EXPLICITLY rather than relying on the tree still sitting where
    # state 2 left it. It does not after a SEAM_B revision: the state-3 re-run above moves
    # the tree to adapt_sha, so a state 1 that passed sha=None compiled the ADAPTED sources
    # against the baseline library. On Brokkonaut/GlobalConnectionServer that surfaced as
    # `cannot find symbol: setCodePointLimit` in GlobalServer.java — the adaptation's own
    # call, against snakeyaml 1.30 where it does not exist yet — and the oracle read it as
    # "baseline did not pass cleanly", i.e. blamed the client for a bug in this function.
    s1 = state("1_baseline", cand.parent_sha, baseline)

    summary = [{"name": n, "run": s["run"], "fail": s["fail"], "err": s["err"],
                "failed_tests": s.get("failed_tests") or []}
               for n, s in (("1_baseline", s1), ("2_newlib_oldcode", s2), ("3_adapted", s3))]

    # DID THE TEST ACTUALLY RUN? A state that executed no tests is not evidence of
    # anything, and the oracle below cannot tell it apart from a state that ran and
    # passed -- both have fail=0, err=0. oracle/weblogic-deploy-tooling is the case
    # that proved it: its build enforces a `unit-test-wlst-dir` property pointing at an
    # Oracle Home, so maven-enforcer failed before compiling, every state reported
    # run=0, and the ledger recorded "signature_confirmed / state 2 did not trip" -- a
    # missing Oracle install rendered as a finding about the client's code. Same shape
    # as a dead GH_TOKEN scoring candidates `no_call_in_diff`.
    if s1["run"] == 0 or s2["run"] == 0 or s3["run"] == 0:
        dead = [n for n, s in (("1_baseline", s1), ("2_newlib_oldcode", s2),
                               ("3_adapted", s3)) if s["run"] == 0]
        errs = [l.strip() for l in s2["log"].splitlines() if "[ERROR]" in l][:3]
        return {"outcome": O.OUTCOME_FAILED, "states": summary,
                "reason": f"no tests executed in {dead} — the differential is void, not "
                          f"negative. Maven said: " + " | ".join(errs or ["(no [ERROR] lines)"])}

    # SHAPE B is scored per METHOD, because a state-level verdict cannot express it.
    #
    # A Shape B driver (born-past-boundary clients — see prompts/seam_a_testgen.md) carries
    # exactly two @Tests: `preAdaptation()`, a stand-in for the library's default behaviour
    # built from API common to both versions, and `adapted()`, the client's real configured
    # path. The contract is:
    #
    #     preAdaptation @ from -> PASS      preAdaptation @ to -> FAIL+signal
    #     adapted       @ to   -> PASS      (preAdaptation @ to STAYS FAILING — that is the point)
    #
    # The stand-in never recovers; demonstrating that only the production config fixes it IS
    # the evidence. Scored in aggregate, that deliberate control sinks state 3 and the case
    # comes back signature_confirmed. openmrs/openmrs-core — verified_bbc by hand — did
    # exactly that: the break reproduced, the fix worked, and the verdict was still wrong.
    #
    # This is the only defect found on 2026-08-15 that manufactures a FALSE verdict rather
    # than refusing to give one, which is why it is worth a separate branch: on a fresh
    # candidate nothing downstream would contradict it.
    if is_shape_b(driver_src):
        pre_at = lambda s: "preAdaptation" in (s.get("failed_tests") or [])
        adapted_failed = lambda s: "adapted" in (s.get("failed_tests") or [])
        detail = {n: sorted(s.get("failed_tests") or [])
                  for n, s in (("1", s1), ("2", s2), ("3", s3))}
        if pre_at(s1):
            return {"outcome": O.OUTCOME_FAILED, "states": summary,
                    "reason": f"Shape B: preAdaptation already fails at the baseline "
                              f"({baseline}), so the stand-in does not reconstruct "
                              f"pre-break behaviour. failed={detail}"}
        if not pre_at(s2):
            return {"outcome": O.OUTCOME_SIGNATURE, "states": summary,
                    "reason": f"Shape B: preAdaptation did not trip at {to_version}. "
                              f"failed={detail}"}
        if not O.matches_signal(s2["log"], signal):
            return {"outcome": O.OUTCOME_SIGNATURE, "states": summary,
                    "reason": f"Shape B: preAdaptation failed at {to_version} but not with "
                              f"the signal /{signal}/"}
        if adapted_failed(s3):
            return {"outcome": O.OUTCOME_SIGNATURE, "states": summary,
                    "reason": f"Shape B: the client's configured path still fails at "
                              f"{state3_version}. failed={detail}"}
        return {"outcome": O.OUTCOME_VERIFIED, "states": summary,
                "reason": f"oracle satisfied (Shape B, per-method): preAdaptation PASS@"
                          f"{baseline} / FAIL+signal@{to_version} / adapted PASS@"
                          f"{state3_version}. preAdaptation still failing at state 3 is "
                          f"expected — it is the control. failed={detail}. NOTE: confirm "
                          f"`adapted()` calls the client's REAL production method rather "
                          f"than reimplementing the fix in the test; a synthetic adapted() "
                          f"weakens the case even when the oracle is green."}

    tripped = bool(s2["fail"] or s2["err"])
    signalled = tripped and O.matches_signal(s2["log"], signal)

    if not tripped:
        return {"outcome": O.OUTCOME_SIGNATURE, "states": summary,
                "reason": "state 2 did not trip (SEAM_B: read _runlogs and adjust the fixture)"}
    if not signalled:
        return {"outcome": O.OUTCOME_SIGNATURE, "states": summary,
                "reason": f"state 2 failed but not with the signal /{signal}/"}
    if s1["run"] == 0 or s1["fail"] or s1["err"]:
        return {"outcome": O.OUTCOME_FAILED, "states": summary,
                "reason": "baseline did not pass cleanly"}
    if s3["run"] == 0 or s3["fail"] or s3["err"]:
        # Distinguish the two ways an adapted state fails, because they mean opposite things.
        # If state 3 fails with the SAME signal, the adaptation did not restore the default
        # path: it EXPOSED the limit as a caller-supplied knob and left the default at
        # snakeyaml's 3 MiB (swagger-parser's maxYamlCodePoints defaults to 3*1024*1024;
        # weblogic-deploy-tooling's yaml.max.file.size defaults to '0' = leave it alone;
        # CommandHelper's runtime setting is unset unless a script sets it). That is a real
        # adaptation to a real break, but it is not a recovery, and calling it "coupling"
        # would hide the distinction the corpus is actually here to measure.
        if O.matches_signal(s3["log"], signal):
            same = sorted(set(s3.get("failed_tests") or []) & set(s2.get("failed_tests") or []))
            multi = (s3["run"] or 0) > 1
            return {"outcome": O.OUTCOME_SIGNATURE, "states": summary,
                    "reason":
                        (f"state 3 still shows the signal in {same}, but the driver has "
                         f"{s3['run']} tests — if one is a deliberate pre-adaptation control "
                         f"(Shape B), this aggregate verdict is WRONG and the case needs "
                         f"per-test scoring"
                         if multi else
                         "adaptation did not restore the default path: state 3 reproduces the "
                         "same signal as state 2 on the unconfigured production path (e.g. a "
                         "knob exposed with its default left unchanged)")}
        return {"outcome": O.OUTCOME_SIGNATURE, "states": summary,
                "reason": "adapted state did not pass (coupling?)"}
    return {"outcome": O.OUTCOME_VERIFIED, "states": summary,
            "reason": "oracle satisfied: 1 PASS / 2 FAIL+signal / 3 PASS"}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("worklist")
    ap.add_argument("--repo", help="only this repo (default: every pending entry)")
    ap.add_argument("--probe-only", action="store_true", help="stop after the version-knob probe")
    ap.add_argument("--driver", help="JUnit source for the driver test (SEAM_A, Path B)")
    ap.add_argument("--seam-a", action="store_true",
                    help="PATH A: generate the driver headlessly via seams.py instead of "
                         "--driver, and answer non-trips with SEAM_B")
    ap.add_argument("--env", action="append", type=lambda kv: tuple(kv.split("=", 1)),
                    metavar="KEY=VALUE",
                    help="environment variable the client's build requires, e.g. "
                         "--env CSPACE_INSTANCE_ID=_default; applied to every state")
    ap.add_argument("--seam-b-retries", type=int, default=3,
                    help="max SEAM_B fixture revisions when state 2 does not trip (Path A only)")
    ap.add_argument("--test", default="bbc.BbcTest")
    ap.add_argument("--jdk", help="override the catalog's java version, e.g. 17")
    ap.add_argument("--module", help="module the driver belongs in, e.g. planetiler-core")
    ap.add_argument("--state3-version",
                    help="run state 3 at this version instead of the boundary, for adaptations "
                         "written against a later release (see differential())")
    ap.add_argument("--pin-version", action="store_true",
                    help="rewrite the library's hardcoded <version> literal to the catalog's "
                         "version property, for clients that name it with no property at all")
    ap.add_argument("--add-test-dep", action="store_true",
                    help="inject a test-scoped JUnit 4 dep for clients that declare no test "
                         "framework (recorded in the ledger)")
    ap.add_argument("--mvn-arg", action="append", default=[],
                    help="extra Maven arg for every state, e.g. --mvn-arg=-pl --mvn-arg=core")
    ap.add_argument("--workdir", help="clone here instead of a temp dir")
    ap.add_argument("--keep", action="store_true", help="do not delete the clone afterwards")
    ap.add_argument("--redo", action="store_true", help="re-run entries already in the ledger")
    args = ap.parse_args()

    items = json.load(open(args.worklist, encoding="utf-8"))
    ledger = ledger_path(args.worklist)
    done = already_done(ledger)

    todo = [i for i in items if not args.repo or i["repo"] == args.repo]
    if not args.redo:
        skipped = [i for i in todo if (i["repo"], i["break_id"]) in done
                   and done[(i["repo"], i["break_id"])].get("outcome") != "probe_ok"]
        for i in skipped:
            d = done[(i["repo"], i["break_id"])]
            print(f"[skip] {i['repo']}: already {d['outcome']} -- {d.get('reason','')[:80]}")
        todo = [i for i in todo if i not in skipped]

    if args.driver and len(todo) > 1:
        ap.error("--driver applies to one candidate; pass --repo too")
    if args.driver and args.seam_a:
        ap.error("--driver and --seam-a are the two SEAM_A routes; pick one")

    for i in todo:
        print(f"\n=== {i['repo']} @ {i['adapt_sha'][:10]} ({i['break_id']}) ===", flush=True)
        row = run_one(i, args, ledger)
        append(ledger, row)
        verdict = ""
        if row.get("known_outcome"):
            verdict = ("  [AGREES with the recorded case]"
                       if row["outcome"] == row["known_outcome"]
                       else f"  [DISAGREES — case says {row['known_outcome']}]")
        print(f"  -> {row['outcome']}: {row.get('reason','')[:160]}{verdict}", flush=True)

    print(f"\nledger: {ledger}")


if __name__ == "__main__":
    main()
