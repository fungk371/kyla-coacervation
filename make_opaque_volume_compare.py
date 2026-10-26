"""Inverse-%T volume comparison: 100 uL vs 200 uL upper-phase read.

Same formulas (GH130, 1% ... T1=Nhance 3196, T2=Nat Caready 0.25%) read at two
aspiration/read volumes. Overlays 100 uL (solid) vs 200 uL (dashed), t=0, with
raw points + smooth curve, and prints the inverse-%T fingerprint for each so we
can judge which volume gives a cleaner coacervation signal.

Output: Reports/opaque_ipct_volume_compare.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os

import coacervation_lasentec as clas
from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import dilution_ratio
from make_dextran_figs import clean_curve
from make_dextran_timepoint_analysis import smooth_hybrid, _dil_axis

R = "Reports"


def _find(cands):
    return next((p for p in cands if os.path.exists(p)), cands[0])


RUNS = {
    "100 uL": (_find([r"C:\Users\fung.k.1\Downloads\GH130_3196andNatCaready_100uL.txt",
                      r"raw_data\GH130_3196andNatCaready_100uL.txt"]), "-"),
    "200 uL": (_find([r"raw_data\Opaque_GH130_3196_and_Nat_Caready.txt",
                      r"C:\Users\fung.k.1\Downloads\Opaque_GH130_3196_and_Nat_Caready.txt"]), "--"),
}
TROUGHS = {1: ("GH130 · Nhance 3196", "#2E75B6"), 2: ("GH130 · Nat Caready 0.25%", "#c0392b")}


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


def main():
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2))
    print(f"{'run':7s} {'poly':10s} {'floor':>6s} {'onset':>7s} {'peak':>13s} {'redis':>7s} {'AUC':>7s}")
    for ax, (tr, (lab, col)) in zip(axes, TROUGHS.items()):
        xmins, xmaxs = [], []
        for run, (path, ls) in RUNS.items():
            x, y = curve(path, tr)
            cx, cy, _ = clean_curve(x, y)
            xmins.append(cx.min()); xmaxs.append(cx.max())
            fx, fy = smooth_hybrid(cx, cy)
            ax.plot(fx, fy, ls, color=col, lw=2.2, label=f"{run}")
            ax.plot(x, y, "o", color=col, ms=2.4, alpha=0.25)
            fp = clas.inverse_pct_fingerprint(x, y)
            if fp:
                print(f"{run:7s} {lab.split('·')[1].strip()[:10]:10s} "
                      f"{fp['baseline_pct']:6.1f} 1:{fp['onset_dilution']:<5g} "
                      f"{fp['peak_pct']:>4g}%@1:{fp['peak_dilution']:<5g} "
                      f"{str(fp['redissolution_dilution']):>7s} {fp['inverse_auc']:>7.1f}")
        _dil_axis(ax, min(xmins), max(xmaxs), fs=9)
        ax.set_ylim(0, 100)
        ax.set_xlabel("Dilution (1:X)")
        ax.set_ylabel("%T (upper phase)")
        ax.grid(True, which="both", ls=":", alpha=0.5)
        ax.set_title(lab, fontweight="bold")
    fig.suptitle("Inverse %T \u2014 100 \u00b5L (solid) vs 200 \u00b5L (dashed) read \u2014 GH130",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{R}/opaque_ipct_volume_compare.png", dpi=150)
    plt.close(fig)
    print(f"\nwrote {R}/opaque_ipct_volume_compare.png")


if __name__ == "__main__":
    main()
