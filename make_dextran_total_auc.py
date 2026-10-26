"""WHOLE-curve (total) coacervation AUC - 0.4% vs 1% polymer, by chassis.

The concentration-response bars (dextran_conc_response.png) integrate only the
1:1-1:20 consumer window, so they MISS the late high-dilution trough. This
version integrates turbidity (absorbance) over LOG-dilution across the ENTIRE
curve, so every decade (incl. 1:30-1:500) is weighted equally and the latter
trough is captured - the metric to correlate against PTL product performance.

Output: Reports/dextran_total_auc.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from make_dextran_full_analysis import curve04, curve1, POLY_ORDER, CHASSIS, R
from coacervation_analysis import transmittance_to_absorbance

_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))


def total_auc(xy):
    """Total turbidity area = integral of absorbance over log10(dilution).

    Captures ALL troughs (early + late) with equal per-decade weighting.
    """
    if xy is None:
        return None
    x, y = xy
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    if x.size < 3:
        return None
    absb = transmittance_to_absorbance(y)
    lx = np.log10(np.clip(x, 1e-9, None))
    o = np.argsort(lx)
    return float(_trapz(absb[o], lx[o]))


def main():
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
    print(f"{'chassis':7s} {'polymer':8s} {'0.4%':>7s} {'1%':>7s}")
    for k, (ch, ccol) in enumerate(CHASSIS):
        ax = axes[k]
        xpos = np.arange(len(POLY_ORDER)); w = 0.38
        v04 = [total_auc(curve04(p, ch)) or 0.0 for p in POLY_ORDER]
        v1 = [total_auc(curve1(p, ch)) or 0.0 for p in POLY_ORDER]
        ax.bar(xpos - w / 2, v04, w, color="#e67e22", edgecolor="#33404d", lw=0.5, label="0.4%")
        ax.bar(xpos + w / 2, v1, w, color="#1f4e79", edgecolor="#33404d", lw=0.5, label="1%")
        ax.set_xticks(xpos); ax.set_xticklabels(POLY_ORDER, rotation=45, ha="right", fontsize=8.5)
        ax.set_title(f"{ch} chassis", fontsize=12, fontweight="bold", color=ccol)
        ax.grid(True, axis="y", ls=":", alpha=0.5)
        if k == 0:
            ax.set_ylabel("TOTAL turbidity AUC\n(absorbance \u00d7 log-dilution, whole curve)")
        ax.legend(fontsize=9)
        for p, a, b in zip(POLY_ORDER, v04, v1):
            print(f"{ch:7s} {p:8s} {a:7.3f} {b:7.3f}")
    fig.suptitle("TOTAL coacervation AUC (whole curve, incl. late trough): "
                 "0.4% vs 1% polymer, by chassis  (guar 1% awaiting)",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(f"{R}/dextran_total_auc.png", dpi=155); plt.close(fig)
    print(f"\nwrote {R}/dextran_total_auc.png")


if __name__ == "__main__":
    main()
