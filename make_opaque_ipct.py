"""Inverse-%T (opaque) plate - GH130 3196 vs Nat Caready.

Opaque shampoos measured across dilution. Trough 1 = GH130 3196 (Nhance 3196,
DwC control, B-20260723-01408); Trough 2 = GH130 Nat Caready (0.25 Nat Caready,
B-20260728-01980). Plots raw %T vs dilution (1:X) at t=0 and t=15, smoothed.

For an OPAQUE product: %T is very low when concentrated (base opacity) and rises
as dilution clears it. Coacervation shows up as a FEATURE on that rise -
a clarification PEAK (inverse method, coacervate + trapped particles removed) or
a turbidity DIP (direct read, coacervate adds cloudiness). This plot lets us see
which is happening.

Output: Reports/opaque_ipct_gh130.png
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
          "Opaque_GH130_3196_and_Nat_Caready.txt",
          r"raw_data\Opaque_GH130_3196_and_Nat_Caready.txt"]
SRC = next((p for p in _CANDS if os.path.exists(p)), _CANDS[0])
TROUGHS = {1: ("GH130 · Nhance 3196", "#2E75B6"),
           2: ("GH130 · Nat Caready 0.25%", "#c0392b")}
TIMES = [0, 15]
LS = {0: "-", 15: "--"}


def curve(df, trough, tp):
    sel = df[df["trough"] == trough].dropna(subset=["formula_fraction"])
    times = sorted(sel["timepoint_minutes"].unique())
    t = min(times, key=lambda z: abs(z - tp))
    cur = sel[sel["timepoint_minutes"] == t].sort_values("formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(cur["formula_fraction"].to_numpy(float)), float)
    y = cur["transmission_pct"].to_numpy(float)
    o = np.argsort(x)
    return x[o], y[o]


def main():
    df = annotate_concentration(parse_kinetic_plate_file(SRC))
    import coacervation_lasentec as clas
    fig, ax = plt.subplots(figsize=(10, 6))
    xmins, xmaxs = [], []
    for tr, (lab, col) in TROUGHS.items():
        x, y = curve(df, tr, 0)
        cx, cy, _ = clean_curve(x, y)
        xmins.append(cx.min()); xmaxs.append(cx.max())
        fx, fy = smooth_hybrid(cx, cy)
        ax.plot(fx, fy, "-", color=col, lw=2.4, label=lab)
        ax.plot(x, y, "o", color=col, ms=2.4, alpha=0.25)
        fp = clas.inverse_pct_fingerprint(x, y)
        if fp:
            ax.axvline(fp["onset_dilution"], color=col, ls=":", lw=1, alpha=0.7)
            ax.annotate(f"peak 1:{fp['peak_dilution']:g}", (fp["peak_dilution"], fp["peak_pct"]),
                        color=col, fontsize=8, xytext=(4, 6), textcoords="offset points")
    _dil_axis(ax, min(xmins), max(xmaxs), fs=9)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Dilution (1:X)")
    ax.set_ylabel("%T (upper phase)")
    ax.grid(True, which="both", ls=":", alpha=0.5)
    ax.set_title("Inverse-%T (opaque) \u2014 GH130 3196 vs Nat Caready\n"
                 "dotted = onset  \u25bc = clarification peak", fontweight="bold", fontsize=11)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(f"{R}/opaque_ipct_gh130.png", dpi=150)
    plt.close(fig)
    print(f"wrote {R}/opaque_ipct_gh130.png\n")

    print(f"{'sample':22s} {'onset':>7s} {'peak':>10s} {'redis':>7s} {'AUC':>8s}")
    for tr, (lab, _) in TROUGHS.items():
        x, y = curve(df, tr, 0)
        fp = clas.inverse_pct_fingerprint(x, y)
        print(f"{lab:22s} 1:{fp['onset_dilution']:<5g} "
              f"{fp['peak_pct']:>4g}%@1:{fp['peak_dilution']:<4g} "
              f"{str(fp['redissolution_dilution']):>7s} {fp['inverse_auc']:>8.1f}")
        if fp["note"]:
            print(f"   \u26a0 {fp['note']}")


if __name__ == "__main__":
    main()
