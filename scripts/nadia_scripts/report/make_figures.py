#!/usr/bin/env python3
"""Generate the mid-year report figures from the study's own numbers."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from pathlib import Path

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)

INK = "#1b2430"
ACC = "#2f6f8f"
ACC2 = "#c65b3c"
MUT = "#8a94a3"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.edgecolor": INK})


# ── Fig 1: the BUMP filtering funnel ────────────────────────────────────────────
def funnel():
    # left-anchored horizontal funnel; labels sit to the RIGHT of every bar so the
    # narrow stages (n=17, n=18) stay legible.
    stages = [
        ("Breaking-update benchmarks", 571, ACC),
        ("Test-failure category (incl. test errors)", 188, ACC),
        ("Adaptations merged to main (of the 188)", 18, MUT),
        ("Test assertion failures (strict BBC signal)", 17, ACC2),
    ]
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    maxw = 571.0
    ys = list(range(len(stages)))[::-1]
    for y, (label, val, col) in zip(ys, stages):
        w = val / maxw
        ax.add_patch(FancyBboxPatch((0, y - 0.34), max(w, 0.006), 0.68,
                     boxstyle="round,pad=0.002,rounding_size=0.015",
                     linewidth=0, facecolor=col))
        ax.text(w + 0.02, y, f"{label}   (n = {val})", ha="left", va="center",
                color=INK, fontsize=9.6, weight="bold")
    ax.set_xlim(0, 1.0); ax.set_ylim(-0.6, len(stages) - 0.3)
    ax.axis("off")
    ax.set_title("Filtering the BUMP corpus for behavioural-break signals",
                 fontsize=11.5, weight="bold", color=INK, pad=10, loc="left")
    fig.tight_layout()
    fig.savefig(OUT / "fig1_funnel.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ── Fig 2: xstream candidate taxonomy (12 verifiable candidates -> outcomes) ─────
def taxonomy():
    cats = [
        "Direct bump + fix\n(same commit)",
        "Direct bump +\nseparate fix",
        "Transitive bump\ncrossing boundary",
        "Born past boundary\n(no bump commit)",
        "Too coupled\nto isolate",
    ]
    counts = [1, 1, 1, 2, 2]
    examples = ["logging-chainsaw", "TVRenamer", "artshishkin", "amirsnw / einsteinarbert", "Spark / drools"]
    cols = [ACC, ACC, ACC2, ACC2, MUT]
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    bars = ax.bar(range(len(cats)), counts, color=cols, width=0.62)
    for i, (b, ex) in enumerate(zip(bars, examples)):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.05, ex,
                ha="center", va="bottom", fontsize=7.6, color=INK, style="italic")
    ax.set_xticks(range(len(cats)))
    ax.set_xticklabels(cats, fontsize=8.2)
    ax.set_ylabel("verified cases")
    ax.set_ylim(0, 2.7)
    ax.set_title("XStream 1.4.18 default-deny: adaptation taxonomy across mined clients",
                 fontsize=11, weight="bold", color=INK, pad=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "fig2_xstream_taxonomy.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ── Fig 3: mine_major_bumps snakeyaml smoke result (yield funnel) ────────────────
def smoke():
    stages = [
        ("Commit-search hits\n('snakeyaml' + bump/upgrade/migrate)", 385, ACC),
        ("Classified (cap = 25)", 25, ACC),
        ("Boundary-crossing bumps found", 10, ACC2),
        ("Naked bumps\n(build-file only, no code)", 10, MUT),
        ("Real code adaptations", 0, "#b23b3b"),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    labels = [s[0] for s in stages]
    vals = [s[1] for s in stages]
    cols = [s[2] for s in stages]
    ypos = range(len(stages))[::-1]
    ax.barh(list(ypos), vals, color=cols, height=0.6)
    for y, v in zip(ypos, vals):
        ax.text(v + 5, y, str(v), va="center", fontsize=9, color=INK, weight="bold")
    ax.set_yticks(list(ypos)); ax.set_yticklabels(labels, fontsize=8.3)
    ax.set_xlim(0, 420); ax.set_xlabel("commits")
    ax.set_title("mine_major_bumps.py — snakeyaml 1.x→2.0 smoke run yield",
                 fontsize=11, weight="bold", color=INK, pad=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "fig3_smoke_yield.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


# ── Fig 4: full failure-category flowchart from the 571 benchmarks ───────────────
def flowchart():
    from matplotlib.patches import FancyBboxPatch
    GREY = "#8a94a3"; BLUE = ACC; BEH = ACC2; ASRT = "#4a8c7a"
    fig, ax = plt.subplots(figsize=(9.2, 11.4))
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

    def box(cx, cy, w, h, text, fc, tc="white", fs=9, weight="bold"):
        ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                     boxstyle="round,pad=0.3,rounding_size=1.2",
                     linewidth=0, facecolor=fc))
        ax.text(cx, cy, text, ha="center", va="center", color=tc,
                fontsize=fs, weight=weight, linespacing=1.15)
        return (cx, cy, w, h)

    def arrow(x0, y0, x1, y1, col=INK):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color=col, lw=1.3,
                                    shrinkA=1, shrinkB=1))

    # root
    root = box(50, 95.5, 40, 5.6, "571 breaking-update benchmarks", INK, fs=12)

    # level 1: the six failure categories
    cats = [
        ("COMPILATION\nFAILURE", 235, GREY),
        ("TEST\nFAILURE", 188, BLUE),
        ("ENFORCER\nFAILURE", 121, GREY),
        ("DEP-LOCK\nFAILURE", 14, GREY),
        ("WERROR\nFAILURE", 8, GREY),
        ("DEP-RESOLVE\nFAILURE", 5, GREY),
    ]
    xs = [9.5, 26, 42.5, 59, 75.5, 92]
    l1 = {}
    for (label, n, col), x in zip(cats, xs):
        b = box(x, 83, 14.5, 7.2, f"{label}\nn = {n}", col, fs=7.6)
        l1[label] = b
        arrow(50, root[1] - root[3] / 2, x, b[1] + b[3] / 2)
    tf = l1["TEST\nFAILURE"]

    ax.text(50, 74.5, "TEST_FAILURE breaks down by JUnit outcome  (188 = 158 errors + 30 assertion failures)",
            ha="center", fontsize=9.2, style="italic", color=INK)

    # level 2: errors vs assertion failures
    err = box(31, 68, 26, 6.2, "Errors\n(uncaught exceptions)   n = 158", BLUE, fs=8.6)
    asr = box(73, 68, 34, 6.2, "Assertion failures  (n = 30)\nAssertionError / ComparisonFailure", ASRT, fs=8.1)
    arrow(tf[0] - 2, tf[1] - tf[3] / 2, err[0], err[1] + err[3] / 2)
    arrow(tf[0] + 2, tf[1] - tf[3] / 2, asr[0], asr[1] + asr[3] / 2)
    box(72, 59.5, 30, 5.4, "behavioural output change,\nbut adapted in TEST code → excluded", "#dfe7e4",
        tc=INK, fs=7.6, weight="normal")
    arrow(asr[0], asr[1] - asr[3] / 2, 72, 62.3, col=ASRT)

    # level 3: the error sub-categories (spine from 'Errors')
    buckets = [
        ("missing_class", 69, "ClassNotFound / NoClassDefFound — relocation / Jakarta / classpath", GREY),
        ("syntactic", 34, "NoSuchMethod/Field/AbstractMethod, InvalidClass — API / serialization", GREY),
        ("binding_init", 21, "ClassCast / ExceptionInInitializer — logger/provider init", GREY),
        ("jvm_version", 11, "UnsupportedClassVersionError — needs newer JVM", GREY),
        ("semantic", 14, "", BEH),
        ("semantic?", 6, "", BEH),
        ("other", 3, "unclassified", GREY),
    ]
    top_y = 51.5
    dy = 6.6
    spine_x = 12
    ys = [top_y - i * dy for i in range(len(buckets))]
    arrow(err[0], err[1] - err[3] / 2, spine_x, ys[0] + 2.6)  # into the spine
    ax.plot([spine_x, spine_x], [ys[0] + 2.6, ys[-1]], color=INK, lw=1.2, zorder=0)
    for (name, n, desc, col), y in zip(buckets, ys):
        ax.plot([spine_x, spine_x + 3], [y, y], color=INK, lw=1.2, zorder=0)
        box(spine_x + 3 + 15, y, 30, 5.2, f"{name}   n = {n}", col, fs=8)
        ax.text(spine_x + 3 + 32, y, desc, ha="left", va="center", fontsize=7.4,
                color=INK, style="italic")

    # behavioural callout
    ymid = (ys[4] + ys[5]) / 2
    box(83, ymid, 24, 8.4,
        "≈ 20 behavioural\n(production-forcing)\n— the mining target",
        BEH, fs=8.4)
    ax.annotate("", xy=(71, ymid), xytext=(spine_x + 3 + 30, ys[4]),
                arrowprops=dict(arrowstyle="-|>", color=BEH, lw=1.4))
    ax.annotate("", xy=(71, ymid), xytext=(spine_x + 3 + 30, ys[5]),
                arrowprops=dict(arrowstyle="-|>", color=BEH, lw=1.4))

    # footnote
    ax.text(50, 2.2,
            "Grey = syntactic / classpath / JVM / config (not behavioural).  "
            "~72% of TEST_FAILURE is syntactic in disguise; only ~11% is behavioural.\n"
            "Source: data/benchmark/ failureCategory field (571) + dominant-exception "
            "classification of reproduction logs (bump_semantic_sweep.py).",
            ha="center", va="bottom", fontsize=7.3, color=MUT)

    ax.set_title("BUMP corpus: failure-category decomposition of the 571 breaking updates",
                 fontsize=12.5, weight="bold", color=INK, pad=6)
    fig.tight_layout()
    fig.savefig(OUT / "fig4_failure_flowchart.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


funnel(); taxonomy(); smoke(); flowchart()
print("wrote:", *[p.name for p in sorted(OUT.glob('*.png'))])
