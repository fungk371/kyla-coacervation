"""1% (solid) vs 0.4% (dashed) polymer per-chassis grids, at t=0 min.

Same as make_dextran_full_analysis.conc_compare_grids but read at the t=0
timepoint (freshest coacervate) instead of t=3, for all 3 chassis.
AUC in the legend is the 1:1-1:20 consumer window (unchanged), now at t=0.

Output: Reports/dextran_conc_compare_{EED0,LAPB,APG}_t0.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from make_dextran_figs import curve
from make_dextran_chassis_compare import POLYMERS
from make_dextran_full_analysis import (
    curve04, _fit, _auc, _dil_axis, C_ONE, C_04, POLY_ORDER, CHASSIS, R,
)

TP = 0.0


def curve1_t0(pkey, ch):
    if ch not in POLYMERS.get(pkey, {}):
        return None
    path, tr = POLYMERS[pkey][ch]
    path = path if path.startswith("raw_data") else f"raw_data/{path}"
    return curve(path, tr, timepoint=TP)


def main():
    for ch, _ in CHASSIS:
        fig, axes = plt.subplots(2, 4, figsize=(16, 8)); axes = axes.ravel()
        for i, pkey in enumerate(POLY_ORDER):
            ax = axes[i]; xmins, xmaxs = [], []
            xy1 = curve1_t0(pkey, ch)
            xy0 = curve04(pkey, ch, timepoint=TP)
            if xy1 is not None:
                x, y = xy1; xmins.append(x.min()); xmaxs.append(x.max())
                fx, fy = _fit(x, y, mode="fit")
                ax.plot(fx, fy, "-", color=C_ONE, lw=2.1, label=f"1% (AUC {_auc(xy1):.3f})")
                ax.plot(x, y, "o", color=C_ONE, ms=2.8, alpha=0.45)
            if xy0 is not None:
                x, y = xy0; xmins.append(x.min()); xmaxs.append(x.max())
                fx, fy = _fit(x, y, mode="fit")
                ax.plot(fx, fy, "--", color=C_04, lw=2.0, label=f"0.4% (AUC {_auc(xy0):.3f})")
                ax.plot(x, y, "s", color=C_04, ms=2.8, alpha=0.40)
            if xmins:
                _dil_axis(ax, min(xmins), max(xmaxs))
            ax.set_ylim(0, 100); ax.set_title(pkey, fontsize=11.5, fontweight="bold")
            ax.grid(True, ls=":", alpha=0.5); ax.legend(fontsize=7.5, loc="lower right")
            if i % 4 == 0:
                ax.set_ylabel("% Transmittance")
        fig.suptitle(f"{ch} chassis \u2014 1% (solid) vs 0.4% (dashed) polymer @ t=0 min  "
                     "\u2014  smooth best-fit",
                     fontsize=14, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        fig.savefig(f"{R}/dextran_conc_compare_{ch}_t0.png", dpi=150); plt.close(fig)
        print(f"wrote {R}/dextran_conc_compare_{ch}_t0.png")


if __name__ == "__main__":
    main()
