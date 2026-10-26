"""Brandon inverse-%T TIME COURSE small-multiples (like the dextran program).

One panel per sample (16 = 8 BC128o + 8 GH130), each showing the inverse-%T
clearing curve at several timepoints (0-15 min) coloured by time, so you can
see how the coacervation hump develops / coarsens over the read.

Output: Reports/brandon_ipct_timecourse.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import make_brandon_ipct_fingerprints as B
from make_dextran_figs import clean_curve
from make_dextran_timepoint_analysis import smooth_hybrid, _dil_axis
from coacervation_analysis import dilution_ratio

R = "Reports"
TPS = [0, 1, 2, 3, 5, 7, 10, 15]     # minutes to overlay
_cache = {}


def load_df(path):
    if path not in _cache:
        _cache[path] = B._load_df(path)
    return _cache[path]


def curve_at(path, trough, tp):
    df = load_df(path)
    times = sorted(df["timepoint_minutes"].unique())
    t = min(times, key=lambda z: abs(z - tp))
    sel = df[(df["trough"] == trough) & (df["timepoint_minutes"] == t)].dropna(
        subset=["formula_fraction"]).sort_values("formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(sel["formula_fraction"].to_numpy(float)), float)
    y = sel["transmission_pct"].to_numpy(float)
    o = np.argsort(x)
    return x[o], y[o]


def main():
    order = sorted(B.SAMPLES, key=lambda s: (s[1], B.POLY_ORDER.index(s[0])))
    ncol, nrow = 4, 4
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.3 * ncol, 3.2 * nrow),
                             squeeze=False, constrained_layout=True)
    cmap = plt.get_cmap("turbo")
    for idx, (poly, ch, path, tr) in enumerate(order):
        ax = axes[idx // ncol][idx % ncol]
        df = load_df(path)
        times = sorted(df["timepoint_minutes"].unique())
        tps = [t for t in TPS if any(abs(t - a) < 0.6 for a in times)]
        lo, hi = [], []
        for tp in tps:
            x, y = curve_at(path, tr, tp)
            try:
                cx, cy, _ = clean_curve(x, y)
                fx, fy = smooth_hybrid(cx, cy)
            except Exception:  # noqa: BLE001
                cx, fx, fy = x, x, y
            ax.plot(fx, fy, "-", color=cmap(tp / 15.0), lw=1.7, alpha=0.9)
            lo.append(cx.min()); hi.append(cx.max())
        _dil_axis(ax, min(lo), max(hi), fs=7)
        ax.set_ylim(0, 100)
        ax.set_title(f"{poly}  ({ch.split()[0]})", fontsize=9.5, fontweight="bold",
                     color=B.POLY_COL.get(poly, "#333"))
        ax.grid(True, which="both", ls=":", alpha=0.4)
        ax.tick_params(labelsize=6)
        if idx % ncol == 0:
            ax.set_ylabel("%T (supernatant)", fontsize=7.5)
        if idx // ncol == nrow - 1:
            ax.set_xlabel("Dilution (1:X)  \u2014 rinse \u2192", fontsize=7.5)
    for j in range(len(order), nrow * ncol):
        axes[j // ncol][j % ncol].axis("off")
    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(0, 15))
    cbar = fig.colorbar(sm, ax=axes.ravel().tolist(), shrink=0.55, pad=0.01)
    cbar.set_label("time (min)")
    fig.suptitle("Brandon inverse %T \u2014 time course by sample (0\u201315 min, coloured by time)",
                 fontsize=14, fontweight="bold")
    fig.savefig(f"{R}/brandon_ipct_timecourse.png", dpi=150)
    plt.close(fig)
    print(f"wrote {R}/brandon_ipct_timecourse.png")


if __name__ == "__main__":
    main()
