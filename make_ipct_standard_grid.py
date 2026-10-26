"""Converted STANDARD %T profiles for ALL Brandon samples (small multiples).

Each inverse-%T curve is flipped to the equivalent standard %T reading
(coacervation = a turbidity DIP): std %T = 100 - normalised clearing signal,
in the coacervation window (1:1-1:100). Samples that form coacervate and then
rinse it out show a clean dip-and-recover; samples that clear monotonically
(coacervate persists, OR the signal is just trivial dilution) show a dip that
never recovers -> flagged 'persists / ambiguous'.

Output: Reports/ipct_standard_grid.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import make_brandon_ipct_fingerprints as B
import make_brandon_ipct_method as M

R = "Reports"


def main():
    order = sorted(B.SAMPLES, key=lambda s: (s[1], B.POLY_ORDER.index(s[0])))
    ncol, nrow = 4, 4
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.3 * ncol, 3.3 * nrow),
                             squeeze=False, constrained_layout=True)
    for idx, (poly, ch, path, tr) in enumerate(order):
        ax = axes[idx // ncol][idx % ncol]
        x, y = B.curve(path, tr)
        cx, cy, _ = B.clean_curve(x, y)
        fx, fy = B.smooth_hybrid(cx, cy)
        floor = float(np.min(fy[:max(3, len(fy) // 10)]))
        m = fx <= 100.0
        fxw, fyw = fx[m], fy[m]
        h = M.first_hump(fxw, fyw, floor)
        sig = np.clip(fyw - floor, 0, None)
        std = 100.0 - 100.0 * sig / (sig.max() or 1.0)
        col = B.POLY_COL[poly]
        # phase shading (light): forming (onset->peak), rinse-out (peak->offset)
        off = h["offset"] if not h["censored"] else 100
        ax.axvspan(h["onset"], h["peak_dil"], color="#cfe3f7", alpha=0.55, zorder=0)
        if not h["censored"]:
            ax.axvspan(h["peak_dil"], off, color="#fde3b3", alpha=0.55, zorder=0)
        ax.axvline(h["peak_dil"], color="#16a085", ls="--", lw=1.3, zorder=1)
        ax.plot(fxw, std, "-", lw=2.3, color=col, zorder=3)
        B._dil_axis(ax, 1, 100, fs=7)
        ax.set_xlim(1, 100); ax.set_ylim(0, 100)
        flag = "  \u2014 persists/ambiguous" if h["censored"] else ""
        ax.set_title(f"{poly} ({ch.split()[0]}){flag}", fontsize=9,
                     fontweight="bold", color=col)
        ax.grid(True, which="both", ls=":", alpha=0.35)
        ax.tick_params(labelsize=6)
        if idx % ncol == 0:
            ax.set_ylabel("std %T (equiv.)", fontsize=7.5)
        if idx // ncol == nrow - 1:
            ax.set_xlabel("dilution 1:X  (rinse \u2192)", fontsize=7.5)
    for j in range(len(order), nrow * ncol):
        axes[j // ncol][j % ncol].axis("off")
    fig.suptitle("Inverse %T \u2192 standard %T profile (coacervation = dip) \u2014 all samples\n"
                 "blue = coacervation forming, amber = rinse-out;  green dashed = peak (max deposition).  "
                 "'persists/ambiguous' = no rinse-out in range",
                 fontsize=13, fontweight="bold")
    fig.savefig(f"{R}/ipct_standard_grid.png", dpi=150)
    plt.close(fig)
    print(f"wrote {R}/ipct_standard_grid.png")


if __name__ == "__main__":
    main()
