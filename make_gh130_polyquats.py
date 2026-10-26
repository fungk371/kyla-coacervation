"""GH130 LT1 polyquats \u2014 inverse %T overlay of Polyquat-6/22/47/53.

Two SoftMax 'matrix' exports (UTF-16, 8x12 blocks per timepoint):
  GH130_PQ6_PQ22.txt   T1 = Polyquat-6,  T2 = Polyquat-22
  GH130_PQ47_PQ53.txt  T1 = Polyquat-47, T2 = Polyquat-53

Reference (centrifuged supernatant) convention: coacervation = %T hump UP
(coacervate captures the opacifier and sediments it, so the supernatant clears).

Output: Reports/gh130_polyquats_ipct.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import coacervation_lasentec as clas
from coacervation_layout import annotate_concentration
from coacervation_analysis import dilution_ratio
from make_dextran_figs import clean_curve
from make_dextran_timepoint_analysis import smooth_hybrid, _dil_axis
from make_gh130_pq_new import parse_softmax_matrix

R = "Reports"
# (label, file, trough, colour)
SAMPLES = [
    ("Polyquat-6", r"raw_data\GH130_PQ6_PQ22.txt", 1, "#2E75B6"),
    ("Polyquat-22", r"raw_data\GH130_PQ6_PQ22.txt", 2, "#c0392b"),
    ("Polyquat-47", r"raw_data\GH130_PQ47_PQ53.txt", 1, "#27ae60"),
    ("Polyquat-53", r"raw_data\GH130_PQ47_PQ53.txt", 2, "#8E44AD"),
]


def curve(path, trough, tp=0):
    df = annotate_concentration(parse_softmax_matrix(path))
    t = min(sorted(df["timepoint_minutes"].unique()), key=lambda z: abs(z - tp))
    sel = df[(df["trough"] == trough) & (df["timepoint_minutes"] == t)].dropna(
        subset=["formula_fraction"]).sort_values("formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(sel["formula_fraction"].to_numpy(float)), float)
    y = sel["transmission_pct"].to_numpy(float)
    o = np.argsort(x)
    return x[o], y[o]


def main():
    fig, ax = plt.subplots(figsize=(11, 6.3))
    lo, hi = [], []
    print(f"{'polymer':13s} {'floor':>5s} {'onset':>7s} {'peak':>12s} "
          f"{'redis':>8s} {'recloud':>7s} {'width':>6s} {'AUC':>6s}")
    for name, path, tr, col in SAMPLES:
        x, y = curve(path, tr)
        cx, cy, _ = clean_curve(x, y)
        fx, fy = smooth_hybrid(cx, cy)
        ax.plot(x, y, "o", color=col, ms=2.6, alpha=0.25)
        ax.plot(fx, fy, "-", color=col, lw=2.4, label=name)
        lo.append(cx.min()); hi.append(cx.max())
        fp = clas.inverse_pct_fingerprint(x, y) or {}
        pk, pkp = fp.get("peak_dilution"), fp.get("peak_pct")
        recloud, redis = 0.0, fp.get("redissolution_dilution")
        if pk and pkp is not None:
            m = fx > pk
            if m.any():
                j = int(np.argmin(fy[m])); recloud = max(0.0, pkp - float(fy[m][j]))
                if redis is None:
                    redis = float(fx[m][j])
        onset = f"1:{fp['onset_dilution']:g}" if fp.get("onset_dilution") else "-"
        peak = f"{pkp:.0f}@1:{pk:.0f}" if pkp else "-"
        rd = f"1:{redis:.0f}" if redis else "none"
        wd = (f"{np.log10(redis / fp['onset_dilution']):.2f}"
              if redis and fp.get("onset_dilution") else "-")
        print(f"{name:13s} {fp.get('baseline_pct', 0):5.0f} {onset:>7s} {peak:>12s} "
              f"{rd:>8s} {recloud:7.0f} {wd:>6s} {fp.get('inverse_auc', 0):6.0f}")
    _dil_axis(ax, min(lo), max(hi), fs=9)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Dilution (Water:Shampoo, 1:X)  \u2014  rinse \u2192")
    ax.set_ylabel("%T (centrifuged supernatant)")
    ax.grid(True, which="both", ls=":", alpha=0.5)
    ax.set_title("GH130 LT1 chassis \u2014 Polyquat-6 / -22 / -47 / -53 inverse %T (t=0)\n"
                 "higher / earlier hump = more coacervate captured earlier in the rinse",
                 fontweight="bold")
    ax.legend(fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{R}/gh130_polyquats_ipct.png", dpi=150)
    plt.close(fig)
    print(f"\nwrote {R}/gh130_polyquats_ipct.png")


if __name__ == "__main__":
    main()
