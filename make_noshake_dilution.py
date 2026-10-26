"""No-shake DILUTION series (neat -> ~1:500) vs the shaken run.

This plate is a dilution series (first well most concentrated, down to ~1:500),
read WITHOUT shaking between reads. Plotting %T vs dilution and overlaying the
earlier SHAKEN APG curves tests Mark's hypothesis: does not-shaking lessen the
observed %T reduction (i.e. is the coacervation signal partly collision/shear-
driven when particles mix)?

Sample: GH150 DDU0 + 3.6% APG, 1% CD2 (Trough 1) / 1% Dex-K (Trough 2).
x-axis: standard 48-point plate layout (most concentrated 1:1 -> 1:539). If the
first well was truly NEAT (1:0), send the exact dilution table and I'll remap.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import sys

from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import dilution_ratio
from make_dextran_timepoint_analysis import c1, smooth_hybrid, _dil_axis

R = "Reports"
SRC = r"C:\Users\fung.k.1\Downloads\TestFileforXML_2026. 09. 10_10.31.46.txt"
TROUGHS = {1: ("APG\u00b71% CD2", "#e67e22"), 2: ("APG\u00b71% Dex-K", "#8e44ad")}
TIMES = [0, 3, 15]
TCOL = {0: "#1f2d5a", 3: "#e8892b", 15: "#b4231f"}


def _curve(df, trough, tp):
    sel = df[(df["trough"] == trough)].dropna(subset=["formula_fraction"])
    times = sorted(sel["timepoint_minutes"].unique())
    t = min(times, key=lambda z: abs(z - tp))
    cur = sel[sel["timepoint_minutes"] == t].sort_values("formula_fraction", ascending=False)
    ff = cur["formula_fraction"].to_numpy(float)
    y = cur["transmission_pct"].to_numpy(float)
    x = np.asarray(dilution_ratio(ff), float)
    return x, y


def main(src=SRC):
    df = annotate_concentration(parse_kinetic_plate_file(src))
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2))
    for ax, (tr, (lab, col)) in zip(axes, TROUGHS.items()):
        xmins, xmaxs = [], []
        # no-shake: 0 / 3 / 15 min
        for t in TIMES:
            x, y = _curve(df, tr, t)
            if len(x) < 5:
                continue
            xmins.append(x.min()); xmaxs.append(x.max())
            fx, fy = smooth_hybrid(x, y)
            ax.plot(fx, fy, "-", color=TCOL[t], lw=2.0, label=f"no-shake {t} min")
            ax.plot(x, y, "o", color=TCOL[t], ms=2.6, alpha=0.30)
        # shaken reference (3 min) for the same formulation
        pk = "CD2" if tr == 1 else "Dex-K"
        sxy = c1(pk, "APG", 3.0)
        if sxy is not None:
            sx, sy = sxy
            xmins.append(sx.min()); xmaxs.append(sx.max())
            fx, fy = smooth_hybrid(sx, sy)
            ax.plot(fx, fy, "--", color="#555e6b", lw=2.2, label="SHAKEN 3 min (ref)")
        if xmins:
            _dil_axis(ax, min(xmins), max(xmaxs))
        ax.set_ylim(0, 100)
        ax.set_title(f"{lab}", fontsize=13, fontweight="bold")
        ax.set_xlabel("Dilution ratio (1:X)")
        ax.set_ylabel("% Transmittance")
        ax.grid(True, ls=":", alpha=0.5)
        ax.legend(fontsize=9, loc="lower right")
        # report the deepest dip each way
        print(f"\nTrough {tr} {lab}:")
        for t in TIMES:
            x, y = _curve(df, tr, t)
            if len(y):
                print(f"  no-shake {t:2d} min: min %T = {y.min():.1f}  (at 1:{x[int(np.argmin(y))]:.0f})")
        if sxy is not None:
            print(f"  SHAKEN    3 min: min %T = {sy.min():.1f}  (at 1:{sx[int(np.argmin(sy))]:.0f})")

    fig.suptitle("NO-shake dilution series vs SHAKEN \u2014 GH150 DDU0 + 3.6% APG, 1% CD2 / 1% Dex-K",
                 fontsize=13.5, fontweight="bold")
    fig.text(0.5, 0.012, "If the no-shake curve stays HIGH (flat) where the shaken curve dips, the %T reduction is "
             "partly driven by shaking/collision (coacervate coarsening on mixing) \u2014 supporting the rheology factor. "
             "x-axis = standard plate layout (1:1\u21921:539); send the neat-start table to remap to 1:0\u21921:500.",
             ha="center", fontsize=8.6, style="italic", color="#33404d", wrap=True)
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fig.savefig(f"{R}/dextran_noshake_dilution_APG.png", dpi=155)
    plt.close(fig)
    print(f"\nwrote {R}/dextran_noshake_dilution_APG.png")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else SRC)
