"""AUC window sensitivity: does the ranking of the 1% dextran formulations
change with the integration window?

Compares three AUC definitions at t = 3 min for every 1% polymer x chassis:
  * Full AUC            - whole measured dilution range (total optical area)
  * 1:1 -> 1:20 window  - consumer window INCLUDING the concentrated 1:1 end
  * 1:2 -> 1:20 window  - consumer window EXCLUDING the 1:1 (in-bottle) point

Outputs (Reports/):
  dextran_auc_window_compare.png   dot plot of the 3 AUC values + rank slopegraph
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from make_dextran_timepoint_analysis import c1, CHASSIS, CH_FULL
from make_dextran_full_analysis import POLY_ORDER
from coacervation_analysis import transmittance_to_absorbance, compute_auc, compute_fingerprint
R = "Reports"
CHCOL = {"EED0": "#2E75B6", "LAPB": "#2e9e5b", "APG": "#e67e22"}
WINDOWS = [
    ("Full AUC", "#3b3b3b", None),                 # per-sample full range
    ("1:1\u20131:20", "#2E75B6", (1 / 21, 1 / 2)),  # includes 1:1
    ("1:2\u20131:20", "#e67e22", (1 / 21, 1 / 3)),  # excludes 1:1
]


def _auc(xy, window):
    if xy is None:
        return None
    x, y = xy
    conc = 1.0 / (1.0 + x)
    w = window if window is not None else (float(conc.min()), float(conc.max()))
    return float(compute_auc(conc, transmittance_to_absorbance(y),
                             window=w, use_fit=True)["auc"])


def _collect(timepoint=3.0):
    """One record per 1% formulation with the three AUC values + in-situ flag."""
    recs = []
    for ch, _ in CHASSIS:
        for pkey in POLY_ORDER:
            xy = c1(pkey, ch, timepoint)
            if xy is None:
                continue
            vals = [_auc(xy, w) for _, _, w in WINDOWS]
            if vals[0] is None or vals[0] < 0.02:   # skip near-flat / non-coacervating
                continue
            x, y = xy
            fp = compute_fingerprint(1.0 / (1.0 + x), y) or {}
            recs.append({"label": f"{ch}\u00b7{pkey}", "ch": ch,
                         "full": vals[0], "w120": vals[1], "w220": vals[2],
                         "in_situ": bool(fp.get("in_situ"))})
    return recs


def window_compare(timepoint=3.0):
    recs = _collect(timepoint)
    # rank each way (descending AUC)
    keys = ["full", "w120", "w220"]
    order = {k: sorted(recs, key=lambda r: r[k], reverse=True) for k in keys}
    rank = {k: {id(r): i + 1 for i, r in enumerate(order[k])} for k in keys}

    # sort rows for the dot plot by the full-AUC ranking
    rows = order["full"]
    n = len(rows)

    fig, (axL, axR) = plt.subplots(
        1, 2, figsize=(15.5, 0.46 * n + 2.2), gridspec_kw={"width_ratios": [1.35, 1]})

    # ---- left: dot / lollipop plot of the three AUC values ----------------
    yv = np.arange(n)[::-1]
    for y, r in zip(yv, rows):
        xs = [r["full"], r["w120"], r["w220"]]
        axL.plot([min(xs), max(xs)], [y, y], color="#c9ced6", lw=1.4, zorder=1)
        for (name, col, _), v in zip(WINDOWS, xs):
            axL.scatter(v, y, s=64, color=col, edgecolor="#33404d",
                        linewidth=0.6, zorder=3)
        if r["in_situ"]:                              # flag less-preferred in-situ
            axL.scatter(-max(xs) * 0.0 - 0.004, y, marker="X", s=70, color="#b4231f",
                        zorder=4, clip_on=False)
    axL.set_yticks(yv)
    lbls = axL.set_yticklabels(
        [(f"\u2717 {r['label']}" if r["in_situ"] else r["label"]) for r in rows], fontsize=9)
    for t, r in zip(lbls, rows):
        if r["in_situ"]:
            t.set_color("#b4231f")
    axL.set_xlabel("Coacervation AUC (t = 3 min)")
    axL.set_title("AUC value by integration window", fontsize=12.5, fontweight="bold")
    axL.grid(True, axis="x", ls=":", alpha=0.5)
    axL.margins(y=0.01)
    handles = [plt.Line2D([0], [0], marker="o", ls="", mfc=c, mec="#33404d",
                          ms=9, label=nm) for nm, c, _ in WINDOWS]
    handles.append(plt.Line2D([0], [0], marker="x", ls="", mec="#b4231f", mfc="#b4231f",
                              ms=9, label="in-situ (less preferred)"))
    axL.legend(handles=handles, fontsize=8.5, loc="lower right", title="Window / flag")

    # ---- right: rank slopegraph across the three windows ------------------
    xcols = [0, 1, 2]
    for r in rows:
        ranks = [rank["full"][id(r)], rank["w120"][id(r)], rank["w220"][id(r)]]
        ls = "--" if r["in_situ"] else "-"
        mfc = "white" if r["in_situ"] else CHCOL[r["ch"]]
        alpha = 0.55 if r["in_situ"] else 0.9
        axR.plot(xcols, ranks, ls, color=CHCOL[r["ch"]], lw=1.8, alpha=alpha,
                 marker="o", ms=6, mec=CHCOL[r["ch"]], mfc=mfc, mew=1.2)
        col = "#b4231f" if r["in_situ"] else "#33404d"
        tag = f"{ranks[0]}. \u2717{r['label']}" if r["in_situ"] else f"{ranks[0]}. {r['label']}"
        axR.text(-0.06, ranks[0], tag, ha="right", va="center", fontsize=8.5, color=col)
        axR.text(2.06, ranks[2], f"{r['label']} ({ranks[2]})", ha="left",
                 va="center", fontsize=8.5, color=col)
    axR.set_xlim(-1.25, 3.25)
    axR.set_ylim(n + 0.6, 0.4)                       # rank 1 at top
    axR.set_xticks(xcols)
    axR.set_xticklabels([nm for nm, _, _ in WINDOWS], fontsize=10, fontweight="bold")
    axR.set_yticks(range(1, n + 1))
    axR.set_ylabel("Rank (1 = strongest)")
    axR.set_title("Rank order by window \u2014 solid = in-use (preferred), dashed \u2717 = in-situ",
                  fontsize=11.5, fontweight="bold")
    axR.grid(True, axis="y", ls=":", alpha=0.4)
    for sp in ("top", "right"):
        axR.spines[sp].set_visible(False)

    fig.suptitle("1% dextran \u2014 AUC window sensitivity + in-situ vs in-use coacervation",
                 fontsize=14.5, fontweight="bold")
    full_names = "   |   ".join(f"{k} = {v}" for k, v in CH_FULL.items())
    fig.text(0.5, 0.035, "\u2717 in-situ (pre-formed, less preferred) coacervate already turbid at 1:1. "
             "The 1:2\u20131:20 window discounts the in-situ 1:1 end \u2192 promotes in-use (APG) coacervators.",
             ha="center", fontsize=9, style="italic", color="#7a1f16")
    fig.text(0.5, 0.008, "Chassis colour: " + full_names, ha="center",
             fontsize=8.5, style="italic", color="#33404d")
    fig.tight_layout(rect=(0, 0.055, 1, 0.955))
    fig.savefig(f"{R}/dextran_auc_window_compare.png", dpi=155)
    plt.close(fig)
    print(f"wrote {R}/dextran_auc_window_compare.png")

    # ---- console table ----------------------------------------------------
    print("\nAUC by window (t = 3 min), sorted by Full AUC:")
    print(f"{'formulation':16s} {'insitu':>6s} {'Full':>7s} {'1:1-1:20':>9s} {'1:2-1:20':>9s}  "
          f"{'rk_full':>7s} {'rk_120':>6s} {'rk_220':>6s}")
    for r in rows:
        print(f"{r['label']:16s} {('YES' if r['in_situ'] else '-'):>6s} "
              f"{r['full']:7.3f} {r['w120']:9.3f} {r['w220']:9.3f}  "
              f"{rank['full'][id(r)]:7d} {rank['w120'][id(r)]:6d} {rank['w220'][id(r)]:6d}")
    return rows, rank


# The two in-use dilution stages (illustrative dilution ratios 1:X).
APPLIED_WIN = (1.0, 10.0)     # 1st dilution: shampoo massaged onto wet hair
RINSE_WIN = (10.0, 120.0)     # 2nd dilution: rinsing, wash drops toward/below CMC
CMC_X = 120.0                 # approx dilution where system crosses CMC (illustrative)
_TICKS = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500]


def _smooth(x, y):
    from make_dextran_timepoint_analysis import smooth_hybrid
    return smooth_hybrid(x, y)


def use_windows_plot(timepoint=3.0):
    """One explanatory plot: the two in-use dilution stages (apply-to-hair vs
    rinse) shaded differently, with the CMC crossing, on representative curves."""
    # in-use coacervator (APG, delayed onset) vs in-situ (LAPB Dex-J*, turbid at 1:1)
    picks = [("APG", "CD2", "#e67e22", "in-use: APG\u00b7CD2 (dilution-triggered)"),
             ("APG", "Dex-K", "#8e44ad", "in-use: APG\u00b7Dex-K"),
             ("LAPB", "Dex-J*", "#2e9e5b", "in-situ: LAPB\u00b7Dex-J* (turbid at 1:1)")]

    fig, ax = plt.subplots(figsize=(13, 7))
    # shaded stage windows
    ax.axvspan(*APPLIED_WIN, color="#2E75B6", alpha=0.10, zorder=0)
    ax.axvspan(*RINSE_WIN, color="#2e9e5b", alpha=0.10, zorder=0)
    ax.axvline(CMC_X, color="#7a1f16", ls="--", lw=1.6, alpha=0.8, zorder=1)

    xmins, xmaxs = [], []
    for ch, pk, col, lab in picks:
        xy = c1(pk, ch, timepoint)
        if xy is None:
            continue
        x, y = xy
        xmins.append(x.min()); xmaxs.append(x.max())
        fx, fy = _smooth(x, y)
        ls = "--" if "in-situ" in lab else "-"
        ax.plot(fx, fy, ls, color=col, lw=2.4, label=lab, zorder=3)
        ax.plot(x, y, "o", color=col, ms=2.6, alpha=0.30, zorder=2)

    lo = min(xmins) if xmins else 1.0
    hi = max(xmaxs) if xmaxs else 500.0
    ax.set_xscale("log")
    tk = [t for t in _TICKS if lo * 0.9 <= t <= hi * 1.15]
    ax.set_xticks(tk); ax.set_xticklabels([f"1:{t}" for t in tk])
    ax.set_xlim(max(lo * 0.9, 0.9), hi * 1.15)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Dilution ratio (product : water)")
    ax.set_ylabel("% Transmittance   (lower = more coacervate/turbidity)")
    ax.grid(True, ls=":", alpha=0.5, zorder=0)

    # stage annotations
    ymid = 96
    ax.text(np.sqrt(APPLIED_WIN[0] * APPLIED_WIN[1]), ymid,
            "APPLIED TO HAIR\n(1st dilution)\ncoacervate-aided\nSMALL-particle deposition",
            ha="center", va="top", fontsize=10, fontweight="bold", color="#1f4e79",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#2E75B6", alpha=0.85))
    ax.text(np.sqrt(RINSE_WIN[0] * RINSE_WIN[1]), ymid,
            "RINSING\n(2nd dilution)\nfiltration deposition\nof LARGE particles (silicone)",
            ha="center", va="top", fontsize=10, fontweight="bold", color="#1f5c34",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#2e9e5b", alpha=0.85))
    ax.text(CMC_X, 8, "\u2248 CMC\nmicelles\ndisassemble", ha="center", va="bottom",
            fontsize=9, color="#7a1f16", fontweight="bold")

    ax.legend(fontsize=9.5, loc="lower left", framealpha=0.9)
    ax.set_title("The two in-use dilution stages \u2014 where deposition happens (1% dextran, t = 3 min)",
                 fontsize=13.5, fontweight="bold")
    fig.text(0.5, 0.012,
             "Apply-to-hair (~1:1\u20131:10): surfactant well above CMC \u2192 dilution triggers coacervation "
             "\u2192 small-particle (active) deposition.   Rinsing (~1:10\u20131:120): wash falls toward/below CMC "
             "\u2192 micelles break up \u2192 filtration deposits large particles (silicone).   Dashed green = in-situ "
             "(already turbid before use \u2014 less preferred).",
             ha="center", fontsize=8.6, style="italic", color="#33404d", wrap=True)
    fig.tight_layout(rect=(0, 0.045, 1, 1))
    fig.savefig(f"{R}/dextran_use_windows.png", dpi=155)
    plt.close(fig)
    print(f"wrote {R}/dextran_use_windows.png")


if __name__ == "__main__":
    window_compare()
    use_windows_plot()
    print("done")
