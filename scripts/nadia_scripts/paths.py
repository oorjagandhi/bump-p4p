"""Where pipeline output goes — the ONE place that knows the layout.

Every script used to write into a single flat `output/` folder, so 115 files from nine
different scripts sat side by side with nothing to say which stage produced what. Now
output is split by PIPELINE STAGE, and `out(name)` routes a filename to its folder.

    output/
      01_discover/   who might have adapted?      rank_candidates, mine_advisories,
                                                  find_adaptations, probe_population
      02_mine/       which commits are they?      bbc_e2e mine-commits / classify
      03_screen/     which are real candidates?   screen_compile_break, screen_trigger
      04_traversal/  did they cross the boundary? find_crossing
      05_verify/     did the break reproduce?     run_worklist, 02_verify_bbc
      reports/       human-readable summaries     every .md

Call `out("some_file.jsonl")` instead of building a path by hand. Adding a rule here is
what moves a file class; no caller changes.

Why routing by FILENAME and not by caller: several files are written by one script and
read by another (fanout reads bbc_e2e's `<break>_candidates.jsonl`), so the name is the
contract both sides already agree on. Keeping the rule in one table means producer and
consumer cannot drift apart.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"

DISCOVER = OUTPUT / "01_discover"
MINE = OUTPUT / "02_mine"
SCREEN = OUTPUT / "03_screen"
TRAVERSAL = OUTPUT / "04_traversal"
VERIFY = OUTPUT / "05_verify"
REPORTS = OUTPUT / "reports"

STAGES = (DISCOVER, MINE, SCREEN, TRAVERSAL, VERIFY, REPORTS)

# (substring, folder) — FIRST match wins, so order is significant. A file that is a
# SCREEN of traversal output ("..._traversal_RECHECK_SCREENED.jsonl") belongs to the
# screening stage, so screening is tested before traversal.
_RULES = (
    (".md",                REPORTS),
    ("ADAPTATIONS",        DISCOVER),
    ("candidate_ranking",  DISCOVER),
    ("advisory_candidates", DISCOVER),
    ("population_probe",   DISCOVER),
    ("boundary_dates",     DISCOVER),
    ("major_screen",       DISCOVER),
    ("major_bumps",        DISCOVER),
    ("bump_semantic",      DISCOVER),
    ("_dated",             DISCOVER),
    ("codesearch",         DISCOVER),
    ("SCREENED",           SCREEN),
    ("_screened",          SCREEN),
    ("TRIGGER",            SCREEN),
    ("differential",       VERIFY),
    ("_verified",          VERIFY),
    ("_verify_input",      VERIFY),
    ("_all_results",       VERIFY),
    ("traversal",          TRAVERSAL),
    ("UNDECIDED",          TRAVERSAL),
    ("MVNRECHECK",         TRAVERSAL),
    ("CLOSEOUT",           TRAVERSAL),
    ("crossings",          TRAVERSAL),
    ("checkpoint",         MINE),
    ("_candidates",        MINE),
    ("PRODONLY",           MINE),
    ("bumpaxis",           MINE),
    ("characterize",       MINE),
)


def stage_for(name: str) -> Path:
    """The folder a file of this name belongs in. Unmatched names go to output/ itself,
    which is deliberate: an unrouted file is visible rather than silently filed wrong."""
    base = Path(name).name
    for token, folder in _RULES:
        if token in base:
            return folder
    return OUTPUT


def out(name: str) -> Path:
    """Full path for an output file, with its folder created.

    Also migrates transparently: if the file does not exist at its routed location but
    DOES still sit in the old flat output/, the old path is returned so a half-migrated
    tree keeps working instead of silently starting an empty file next to a full one.
    """
    routed = stage_for(name) / Path(name).name
    if not routed.exists():
        legacy = OUTPUT / Path(name).name
        if legacy.exists():
            return legacy
    routed.parent.mkdir(parents=True, exist_ok=True)
    return routed


def str_out(name: str) -> str:
    """`out()` as a plain string, for the callers still using os.path.join."""
    return str(out(name))
