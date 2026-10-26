"""Build the 'How to read the inverse %T' teaching + data deck (16:9).

Generates three new figures from Kyla's GH130 data:
  * Reports/ipct_howto_annotated.png  - Cassia curve annotated with floor,
    clarification, peak, DEPTH, WIDTH, dip position, redissolution.
  * Reports/ipct_formula_overlay.png  - all GH130 troughs run so far on one axis.
  * Reports/ipct_metrics_bars.png     - the compare-across-formula metrics
    (dip depth, dip dilution, width).
Then assembles Reports/Inverse_PctT_Guide.pptx, reusing the existing
opaque_ipct_*.png figures and leaving OPEN placeholder slides for the rest of
Brandon's samples.
"""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import coacervation_lasentec as clas
from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import dilution_ratio
from make_dextran_figs import clean_curve
from make_dextran_timepoint_analysis import smooth_hybrid, _dil_axis

R = "Reports"

# ---------------------------------------------------------------- data sources
GH_2NC = "raw_data/Opaque_GH130_3196_and_Nat_Caready.txt"   # T1=3196, T2=Nat Caready
GH_CNC = "raw_data/GH130_Cassia_NatClear_200uL.txt"          # T1=Cassia, T2=Nat Clear

FORMULAS = [
    ("Nhance 3196",  GH_2NC, 1, "#2E75B6"),
    ("Nat Caready",  GH_2NC, 2, "#c0392b"),
    ("Cassia",       GH_CNC, 1, "#8e44ad"),
    ("Nat Clear",    GH_CNC, 2, "#1f9e5b"),
]


def curve(path, trough, tp=0):
    df = annotate_concentration(parse_kinetic_plate_file(path))
    times = sorted(df["timepoint_minutes"].unique())
    t = min(times, key=lambda z: abs(z - tp))
    sel = df[(df["trough"] == trough) & (df["timepoint_minutes"] == t)].dropna(
        subset=["formula_fraction"]).sort_values("formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(sel["formula_fraction"].to_numpy(float)), float)
    y = sel["transmission_pct"].to_numpy(float)
    o = np.argsort(x)
    return x[o], y[o]


def fingerprint(path, trough):
    """Return dict: floor, onset, peak(%,1:X), dip(%,1:X), depth, width_dec, auc."""
    x, y = curve(path, trough)
    cx, cy, _ = clean_curve(x, y)
    fx, fy = smooth_hybrid(cx, cy)
    fp = clas.inverse_pct_fingerprint(x, y) or {}
    peak_dil = fp.get("peak_dilution", fx[np.argmax(fy)])
    peak_pct = fp.get("peak_pct", float(np.max(fy)))
    # deepest post-peak dip on the smoothed curve
    m = fx > peak_dil
    if m.any():
        di = np.argmin(fy[m])
        dip_dil = float(fx[m][di]); dip_pct = float(fy[m][di])
    else:
        dip_dil, dip_pct = peak_dil, peak_pct
    depth = max(0.0, peak_pct - dip_pct)
    # width = decades where curve sits below the half-depth threshold around dip
    thr = dip_pct + 0.5 * depth
    width_dec, wl, wr = 0.0, dip_dil, dip_dil
    if depth > 3:
        below = fx[(fy <= thr)]
        near = below[(below >= peak_dil)]
        if near.size:
            wl, wr = float(near.min()), float(near.max())
            width_dec = np.log10(wr / max(wl, 1e-9))
    return dict(x=x, y=y, fx=fx, fy=fy, cx=cx,
                floor=fp.get("baseline_pct", float(np.min(cy))),
                onset=fp.get("onset_dilution", np.nan),
                peak_pct=peak_pct, peak_dil=peak_dil,
                dip_pct=dip_pct, dip_dil=dip_dil, depth=depth,
                width_dec=width_dec, wl=wl, wr=wr,
                auc=fp.get("inverse_auc", np.nan),
                redis=fp.get("redissolution_dilution"))


# =============================================================== 1) annotated
def make_howto():
    fp = fingerprint(GH_CNC, 1)  # Cassia = clean teaching example
    fx, fy = fp["fx"], fp["fy"]
    fig, ax = plt.subplots(figsize=(11.5, 6.4))
    ax.plot(fp["x"], fp["y"], "o", color="#8e44ad", ms=3.2, alpha=0.22, zorder=2)
    ax.plot(fx, fy, "-", color="#8e44ad", lw=3.0, zorder=3, label="Cassia (upper-phase %T)")

    pk, pkp = fp["peak_dil"], fp["peak_pct"]
    dp, dpp = fp["dip_dil"], fp["dip_pct"]

    # guide lines
    ax.axvline(pk, color="#7f8c8d", ls=":", lw=1.2, zorder=1)
    ax.axvline(dp, color="#7f8c8d", ls=":", lw=1.2, zorder=1)

    # DEPTH double arrow
    ax.annotate("", xy=(dp, pkp), xytext=(dp, dpp),
                arrowprops=dict(arrowstyle="<->", color="#c0392b", lw=2.4))
    ax.text(dp * 1.28, (pkp + dpp) / 2 - 4,
            f"DEPTH\n\u2248 {fp['depth']:.0f} %T\n= coacervate amount",
            color="#c0392b", fontsize=11, fontweight="bold", va="center", ha="left")

    # WIDTH double arrow at half-depth
    thr = dpp + 0.5 * fp["depth"]
    ax.annotate("", xy=(fp["wl"], thr), xytext=(fp["wr"], thr),
                arrowprops=dict(arrowstyle="<->", color="#B97700", lw=2.2))
    ax.text(np.sqrt(fp["wl"] * fp["wr"]), thr - 8,
            f"WIDTH \u2248 {fp['width_dec']:.2f} decades\n= rinse robustness",
            color="#8a6d00", fontsize=10.5, fontweight="bold", ha="center", va="top")

    # region callouts
    ax.annotate("Opaque floor\n(formula base)", xy=(fp["cx"].min(), fp["floor"]),
                xytext=(fp["cx"].min() * 1.05, 22), fontsize=10.5, color="#5A6470",
                arrowprops=dict(arrowstyle="->", color="#5A6470"))
    ax.annotate("Clarification\n(base dilutes out)", xy=(pk / 3, 60),
                xytext=(pk / 5.5, 30), fontsize=10.5, color="#5A6470",
                arrowprops=dict(arrowstyle="->", color="#5A6470"))
    ax.text(pk, min(99, pkp + 3.5), "Peak clarity\n(pre-coacervation)",
            color="#16a085", fontsize=10.5, fontweight="bold", ha="center")
    ax.annotate("Coacervation dip\n(max coacervate)", xy=(dp, dpp),
                xytext=(dp / 2.2, dpp - 18), fontsize=11, color="#c0392b",
                fontweight="bold",
                arrowprops=dict(arrowstyle="->", color="#c0392b"))
    if fp["fx"].max() > dp:
        ax.annotate("Redissolution\n(over-dilution)", xy=(fp["fx"].max(), fy[-1]),
                    xytext=(fp["fx"].max() * 0.30, min(99, fy[-1] + 4)),
                    fontsize=10.5, color="#5A6470",
                    arrowprops=dict(arrowstyle="->", color="#5A6470"))

    _dil_axis(ax, fp["cx"].min(), fp["cx"].max(), fs=10)
    ax.set_ylim(0, 105)
    ax.set_xlabel("Dilution (1:X)   \u2014   rinse timeline \u2192", fontsize=11)
    ax.set_ylabel("%T of well  (\u2193 = more turbid = more coacervate)", fontsize=11)
    ax.set_title("How to read an inverse %T curve  \u2014  GH130 Cassia (200 \u00b5L, t=0)",
                 fontsize=13, fontweight="bold")
    ax.grid(True, which="both", ls=":", alpha=0.45)
    fig.tight_layout()
    fig.savefig(f"{R}/ipct_howto_annotated.png", dpi=150)
    plt.close(fig)
    print("wrote ipct_howto_annotated.png")


# =============================================================== 2) overlay
def make_overlay():
    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    xs_lo, xs_hi = [], []
    for lab, path, tr, col in FORMULAS:
        fp = fingerprint(path, tr)
        ax.plot(fp["fx"], fp["fy"], "-", color=col, lw=2.6, label=lab)
        ax.plot(fp["dip_dil"], fp["dip_pct"], "v", color=col, ms=10)
        xs_lo.append(fp["cx"].min()); xs_hi.append(fp["cx"].max())
    _dil_axis(ax, min(xs_lo), max(xs_hi), fs=10)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Dilution (1:X)   \u2014   rinse timeline \u2192", fontsize=11)
    ax.set_ylabel("%T (upper phase)", fontsize=11)
    ax.set_title("Inverse %T across formulas \u2014 GH130 (200 \u00b5L, t=0)\n"
                 "deeper / broader dip = more coacervate; \u25bc marks the coacervation dip",
                 fontsize=12.5, fontweight="bold")
    ax.grid(True, which="both", ls=":", alpha=0.45)
    ax.legend(loc="lower right", fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{R}/ipct_formula_overlay.png", dpi=150)
    plt.close(fig)
    print("wrote ipct_formula_overlay.png")


# =============================================================== 3) metric bars
def make_metrics():
    labs, cols, depth, dipdil, width = [], [], [], [], []
    for lab, path, tr, col in FORMULAS:
        fp = fingerprint(path, tr)
        labs.append(lab); cols.append(col)
        depth.append(fp["depth"]); dipdil.append(fp["dip_dil"]); width.append(fp["width_dec"])
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 5.0))
    xs = np.arange(len(labs))

    def _bars(ax, vals, title, ylab, fmt="{:.0f}"):
        ax.bar(xs, vals, color=cols, edgecolor="white")
        for i, v in enumerate(vals):
            ax.text(i, v + max(vals) * 0.02 if max(vals) else v, fmt.format(v),
                    ha="center", va="bottom", fontsize=10, fontweight="bold")
        ax.set_xticks(xs); ax.set_xticklabels(labs, rotation=20, ha="right", fontsize=9)
        ax.set_title(title, fontsize=12, fontweight="bold")
        ax.set_ylabel(ylab, fontsize=10)
        ax.grid(True, axis="y", ls=":", alpha=0.4)

    _bars(axes[0], depth, "Dip DEPTH\n(coacervate amount)", "%T drop")
    axes[1].bar(xs, dipdil, color=cols, edgecolor="white")
    for i, v in enumerate(dipdil):
        axes[1].text(i, v + max(dipdil) * 0.02, f"1:{v:.0f}", ha="center",
                     va="bottom", fontsize=10, fontweight="bold")
    axes[1].set_xticks(xs); axes[1].set_xticklabels(labs, rotation=20, ha="right", fontsize=9)
    axes[1].set_title("Dip POSITION\n(when in rinse)", fontsize=12, fontweight="bold")
    axes[1].set_ylabel("Dilution at dip (1:X)", fontsize=10)
    axes[1].grid(True, axis="y", ls=":", alpha=0.4)
    _bars(axes[2], width, "Dip WIDTH\n(rinse robustness)", "decades", fmt="{:.2f}")

    fig.suptitle("Metrics to compare across formulas", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(f"{R}/ipct_metrics_bars.png", dpi=150)
    plt.close(fig)
    print("wrote ipct_metrics_bars.png")


if __name__ == "__main__":
    os.makedirs(R, exist_ok=True)
    make_howto()
    make_overlay()
    make_metrics()
    print("\nfigures done \u2014 building deck")
    import build_ipct_deck  # noqa: F401  (assembles the pptx)
