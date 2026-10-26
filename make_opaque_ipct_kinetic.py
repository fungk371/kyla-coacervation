"""Kinetic time-course of the opaque inverse-%T GH130 run (0-15 min).

The plate was read every minute AFTER centrifugation/transfer. This shows
whether the transferred supernatant is STABLE over the read or still evolving
(re-settling, re-mixing, or coacervate re-forming). Two panels: 3196 | Nat Caready.

Output: Reports/opaque_ipct_gh130_kinetic.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os

from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import dilution_ratio
from make_dextran_figs import clean_curve
from make_dextran_timepoint_analysis import smooth_hybrid, _dil_axis

R = "Reports"
_CANDS = [r"C:\Users\fung.k.1\Downloads\Opaque_GH130_3196_and_Nat_Caready.txt",
          r"raw_data\Opaque_GH130_3196_and_Nat_Caready.txt"]
SRC = next((p for p in _CANDS if os.path.exists(p)), _CANDS[0])
TROUGHS = {1: "GH130 · Nhance 3196", 2: "GH130 · Nat Caready 0.25%"}


def curve(df, trough, t):
    sel = df[(df["trough"] == trough) & (df["timepoint_minutes"] == t)].dropna(
        subset=["formula_fraction"]).sort_values("formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(sel["formula_fraction"].to_numpy(float)), float)
    y = sel["transmission_pct"].to_numpy(float)
    o = np.argsort(x)
    return x[o], y[o]


def main():
    df = annotate_concentration(parse_kinetic_plate_file(SRC))
    times = sorted(df["timepoint_minutes"].unique())
    cmap = plt.cm.turbo
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2))
    for ax, (tr, lab) in zip(axes, TROUGHS.items()):
        xmins, xmaxs = [], []
        for t in times:
            x, y = curve(df, tr, t)
            cx, cy, _ = clean_curve(x, y)
            if len(cx) < 5:
                continue
            xmins.append(cx.min()); xmaxs.append(cx.max())
            fx, fy = smooth_hybrid(cx, cy)
            ax.plot(fx, fy, "-", color=cmap(t / max(times)), lw=1.6)
        _dil_axis(ax, min(xmins), max(xmaxs), fs=9)
        ax.set_ylim(0, 100)
        ax.set_xlabel("Dilution (1:X)")
        ax.set_ylabel("%T (upper phase)")
        ax.grid(True, which="both", ls=":", alpha=0.5)
        ax.set_title(lab, fontweight="bold")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, max(times)))
    fig.colorbar(sm, ax=axes, label="read time (min)", fraction=0.025)
    fig.suptitle("Opaque inverse-%T kinetics (post-centrifuge read, 0\u201315 min) \u2014 GH130",
                 fontsize=13, fontweight="bold")
    fig.savefig(f"{R}/opaque_ipct_gh130_kinetic.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {R}/opaque_ipct_gh130_kinetic.png\n")

    # how much does %T drift over 0->15 at key dilutions?
    for tr, lab in TROUGHS.items():
        print(lab)
        for target in (5, 10, 20, 50):
            vals = []
            for t in times:
                x, y = curve(df, tr, t)
                if target < x.min() or target > x.max():
                    continue
                vals.append(float(np.interp(target, x, y)))
            if len(vals) >= 2:
                print(f"  1:{target:<3d}  %T 0min={vals[0]:5.1f}  15min={vals[-1]:5.1f}  "
                      f"drift={vals[-1]-vals[0]:+5.1f}")


if __name__ == "__main__":
    main()
