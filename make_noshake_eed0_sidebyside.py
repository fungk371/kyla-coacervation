"""Shake vs no-shake, SIDE-BY-SIDE (not overlaid) - GH150 EED0, 1% CD2 & Dex-K.

2 rows (CD2, Dex-K) x 2 cols (shake | no-shake). Each panel shows the full
0-15 min time course (every minute), coloured blue->red, so the two protocols
can be compared panel-to-panel without overlaying.

Output: Reports/noshake_vs_shake_eed0_sidebyside.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import numpy as np
import os

from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import dilution_ratio
from make_dextran_figs import clean_curve
from make_dextran_timepoint_analysis import smooth_hybrid, _dil_axis

R = "Reports"
_CANDS = [r"C:\Users\fung.k.1\Downloads\noshake_GH150DDU0_1percentCD2andDexK.txt",
          "noshake_GH150DDU0_1percentCD2andDexK.txt",
          r"raw_data\noshake_GH150DDU0_1percentCD2andDexK.txt"]
NOSHAKE = next((p for p in _CANDS if os.path.exists(p)), _CANDS[0])
SHAKE = {
    "CD2":   (r"raw_data\20260904_1_GH150EED0_CD2_DexB_1percent.txt", 1),
    "Dex-K": (r"raw_data\20260904_7_GH150DDU0_LAPB_1percent_NATIVE_DexK.txt", 2),
}
NOSHAKE_TROUGH = {"CD2": 1, "Dex-K": 2}


def all_times(path, trough):
    df = annotate_concentration(parse_kinetic_plate_file(path))
    sel = df[df["trough"] == trough].dropna(subset=["formula_fraction"])
    return sorted(sel["timepoint_minutes"].unique())


def curve(path, trough, tp):
    df = annotate_concentration(parse_kinetic_plate_file(path))
    sel = df[df["trough"] == trough].dropna(subset=["formula_fraction"])
    if sel.empty:
        return None
    times = sorted(sel["timepoint_minutes"].unique())
    t = min(times, key=lambda z: abs(z - tp))
    cur = sel[sel["timepoint_minutes"] == t].sort_values("formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(cur["formula_fraction"].to_numpy(float)), float)
    y = cur["transmission_pct"].to_numpy(float)
    order = np.argsort(x)
    x, y = x[order], y[order]
    x, y, _ = clean_curve(x, y)
    return x, y


def _smooth(x, y):
    cx, cy, _ = clean_curve(x, y)
    if len(cx) < 5:
        return x, y
    return smooth_hybrid(cx, cy)


def draw(ax, path, trough, title):
    times = [t for t in all_times(path, trough) if t <= 15]
    norm = mcolors.Normalize(vmin=0, vmax=15)
    cmap = plt.get_cmap("turbo")
    xmins, xmaxs = [], []
    for t in times:
        c = curve(path, trough, t)
        if not c or len(c[0]) < 5:
            continue
        xmins.append(c[0].min()); xmaxs.append(c[0].max())
        fx, fy = _smooth(c[0], c[1])
        ax.plot(fx, fy, "-", color=cmap(norm(t)), lw=1.8, alpha=0.9)
    if xmins:
        _dil_axis(ax, min(xmins), max(xmaxs), fs=9)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Dilution (1:X)")
    ax.set_ylabel("%T")
    ax.grid(True, which="both", ls=":", alpha=0.5)
    ax.set_title(title, fontweight="bold", fontsize=12)
    return cmap, norm


def main():
    fig, axes = plt.subplots(2, 2, figsize=(15, 10.5), constrained_layout=True)
    cmap = norm = None
    for row, poly in enumerate(["CD2", "Dex-K"]):
        spath, str_ = SHAKE[poly]
        ntr = NOSHAKE_TROUGH[poly]
        cmap, norm = draw(axes[row, 0], spath, str_, f"SHAKE \u2014 1% {poly}")
        draw(axes[row, 1], NOSHAKE, ntr, f"NO-SHAKE \u2014 1% {poly}")
    sm = cm.ScalarMappable(cmap=cmap, norm=norm); sm.set_array([])
    cbar = fig.colorbar(sm, ax=axes, fraction=0.025, pad=0.02)
    cbar.set_label("time (min)", fontsize=11)
    fig.suptitle("GH150 EED0, 1% CD2 & Dex-K \u2014 shake vs no-shake, 0\u201315 min time course",
                 fontsize=14, fontweight="bold")
    fig.savefig(f"{R}/noshake_vs_shake_eed0_sidebyside.png", dpi=150)
    plt.close(fig)
    print(f"wrote {R}/noshake_vs_shake_eed0_sidebyside.png")


if __name__ == "__main__":
    main()
