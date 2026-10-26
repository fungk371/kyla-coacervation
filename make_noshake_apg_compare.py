"""Shake vs no-shake %T comparison - GH150 DDU0 + 3.6% APG, 1% CD2 and Dex-K.

Overlays the new no-shake dilution run against the earlier SHAKE-protocol APG
runs (2026-09-03) for the SAME formulations:
  * CD2   : no-shake T1  vs  shake 20260903_APG_CD2_DexB  T1
  * Dex-K : no-shake T2  vs  shake 20260903_APGDexK_LAPBDexK T1 (APG side)

APG is the shear-generated chassis (Mark's hypothesis): if no-shake stays FLAT
while shake dips, the APG signal is collision/mixing-driven rather than a
pre-formed in-bottle coacervate.

Output: Reports/noshake_vs_shake_apg.png
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
_CANDS = [r"C:\Users\fung.k.1\Downloads\noshakeAPG_CD2_Dex_1percent.txt",
          r"raw_data\noshakeAPG_CD2_Dex_1percent.txt",
          "noshakeAPG_CD2_Dex_1percent.txt"]
NOSHAKE = next((p for p in _CANDS if os.path.exists(p)), _CANDS[0])
SHAKE = {
    "CD2":   (r"raw_data\20260903_APG_CD2_DexB_RawData.txt", 1),
    "Dex-K": (r"raw_data\20260903_APGDexK_LAPBDexK_RawData.txt", 1),
}
NOSHAKE_TROUGH = {"CD2": 1, "Dex-K": 2}
TIMES = [0, 3, 15]
TCOL = {0: "#1f2d5a", 3: "#e8892b", 15: "#b4231f"}


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
    x, y, _ = clean_curve(x, y)          # drop isolated bubble/particulate spikes
    return x, y


def _trough_depth(path, trough, tp):
    c = curve(path, trough, tp)
    return float(np.nanmin(c[1])) if c else np.nan


def _smooth(x, y):
    cx, cy, _ = clean_curve(x, y)
    if len(cx) < 5:
        return x, y
    fx, fy = smooth_hybrid(cx, cy)
    return fx, fy


def main():
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2))
    for ax, poly in zip(axes, ["CD2", "Dex-K"]):
        spath, str_ = SHAKE[poly]
        ntr = NOSHAKE_TROUGH[poly]
        xmins, xmaxs = [], []
        for t in TIMES:
            cs = curve(spath, str_, t)      # SHAKE = solid
            if cs and len(cs[0]) >= 5:
                xmins.append(cs[0].min()); xmaxs.append(cs[0].max())
                fx, fy = _smooth(cs[0], cs[1])
                ax.plot(fx, fy, "-", color=TCOL[t], lw=2.2, label=f"shake {t} min")
            cn = curve(NOSHAKE, ntr, t)     # NO-SHAKE = dashed
            if cn and len(cn[0]) >= 5:
                xmins.append(cn[0].min()); xmaxs.append(cn[0].max())
                fx, fy = _smooth(cn[0], cn[1])
                ax.plot(fx, fy, "--", color=TCOL[t], lw=2.2, label=f"no-shake {t} min")
        if xmins:
            _dil_axis(ax, min(xmins), max(xmaxs), fs=9)
        ax.set_ylim(0, 100)
        ax.set_xlabel("Dilution (1:X)")
        ax.set_ylabel("%T")
        ax.grid(True, which="both", ls=":", alpha=0.5)
        ax.set_title(f"GH150 + 3.6% APG + 1% {poly}", fontweight="bold")
        ax.legend(fontsize=8, ncol=2)
    fig.suptitle("Shake (solid) vs no-shake (dashed) \u2014 GH150 + 3.6% APG, 1% CD2 & Dex-K",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{R}/noshake_vs_shake_apg.png", dpi=150)
    plt.close(fig)
    print(f"wrote {R}/noshake_vs_shake_apg.png\n")

    print(f"{'poly':7s} {'shake t3':>9s} {'noshake t0':>11s} {'noshake t3':>11s} {'noshake t15':>12s}")
    for poly in ["CD2", "Dex-K"]:
        spath, str_ = SHAKE[poly]
        ntr = NOSHAKE_TROUGH[poly]
        print(f"{poly:7s} {_trough_depth(spath, str_, 3):9.1f} "
              f"{_trough_depth(NOSHAKE, ntr, 0):11.1f} "
              f"{_trough_depth(NOSHAKE, ntr, 3):11.1f} "
              f"{_trough_depth(NOSHAKE, ntr, 15):12.1f}")
    print("\n(lower %T = more turbidity = more coacervation)")


if __name__ == "__main__":
    main()
