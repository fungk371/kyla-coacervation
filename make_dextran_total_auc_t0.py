"""WHOLE-curve (total) coacervation AUC at t=0 min - 0.4% vs 1%, by chassis.

Same as make_dextran_total_auc but read at the freshest (t=0) timepoint.
Output: Reports/dextran_total_auc_t0.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from make_dextran_figs import curve
from make_dextran_chassis_compare import POLYMERS
from make_dextran_full_analysis import curve04, POLY_ORDER, CHASSIS, R
from make_dextran_total_auc import total_auc

TP = 0.0


def curve1_t0(pkey, ch):
    if ch not in POLYMERS.get(pkey, {}):
        return None
    path, tr = POLYMERS[pkey][ch]
    path = path if path.startswith("raw_data") else f"raw_data/{path}"
    return curve(path, tr, timepoint=TP)


def main():
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
    print(f"{'chassis':7s} {'polymer':8s} {'0.4%':>7s} {'1%':>7s}")
    for k, (ch, ccol) in enumerate(CHASSIS):
        ax = axes[k]
        xpos = np.arange(len(POLY_ORDER)); w = 0.38
        v04 = [total_auc(curve04(p, ch, timepoint=TP)) or 0.0 for p in POLY_ORDER]
        v1 = [total_auc(curve1_t0(p, ch)) or 0.0 for p in POLY_ORDER]
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
    fig.suptitle("TOTAL coacervation AUC (whole curve, incl. late trough) @ t=0 min: "
                 "0.4% vs 1% polymer, by chassis  (guar 1% awaiting)",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(f"{R}/dextran_total_auc_t0.png", dpi=155); plt.close(fig)
    print(f"\nwrote {R}/dextran_total_auc_t0.png")


if __name__ == "__main__":
    main()
