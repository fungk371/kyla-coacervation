"""Full dextran visualization suite: 3 chassis x 8 polymers, 0.4% vs 1%, 0-15 min.

Produces (Reports/):
  dextran_1pct_timecourse_{EED0,LAPB,APG}.png   0-15 min %T overlay grids at 1%
  dextran_conc_compare_{EED0,LAPB,APG}.png       1% (solid) vs 0.4% (dashed) per polymer
  dextran_master_heatmap.png                     AUC: polymer x (chassis x concentration)
  dextran_conc_response.png                      per-chassis 0.4% vs 1% AUC bars

1% curves come from my raw plates (via make_dextran_chassis_compare.POLYMERS);
0.4% curves come from the Dow share CSV. Guar (3196) has no 1% data yet.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from make_dextran_figs import (
    series, curve, clean_curve, SMOOTH, AUC_WINDOW, TICKS, _load_conc_df,
)
from make_dextran_chassis_compare import POLYMERS
from coacervation_analysis import (
    fit_curve, transmittance_to_absorbance, compute_auc, dilution_ratio,
)
from coacervation_plotting import plot_small_multiples

R = "Reports"
KEY_TIMES = {0, 1, 3, 5, 10, 15}
CH_CSV = {"EED0": "GH150 EED0", "LAPB": "GH150 DDu0, 3.6% LAPB", "APG": "GH150 DDu0, 3.6% APG"}
CHASSIS = [("EED0", "#2E75B6"), ("LAPB", "#2e9e5b"), ("APG", "#e67e22")]
POLY_ORDER = ["CD2", "Dex-K", "3196", "Dex-A", "Dex-B", "Dex-B*", "Dex-J", "Dex-J*"]
C_ONE, C_04 = "#1f4e79", "#e67e22"


def _keytimes(ser):
    return [d for d in ser if round(d["time"]) in KEY_TIMES]


def series_04(pkey, chassis):
    """0.4% time-series (list of {time, concentration, pct_transmittance})."""
    d = _load_conc_df()
    cname = "0.4% " + pkey.replace("-", " ")
    sub = d[(d["Chassis"] == CH_CSV[chassis]) & (d["Polymer"] == cname)]
    if sub.empty:
        return None
    out = []
    for tp in sorted(sub["Time_min"].unique()):
        if round(float(tp)) not in KEY_TIMES:
            continue
        cur = sub[sub["Time_min"] == tp].sort_values("Formula_fraction", ascending=False)
        conc = cur["Formula_fraction"].to_numpy(float)
        y = cur["%T"].to_numpy(float)
        out.append({"time": float(tp), "concentration": conc, "pct_transmittance": y})
    return out


def curve04(pkey, chassis, timepoint=3.0):
    d = _load_conc_df()
    cname = "0.4% " + pkey.replace("-", " ")
    sub = d[(d["Chassis"] == CH_CSV[chassis]) & (d["Polymer"] == cname)]
    if sub.empty:
        return None
    tps = sorted(sub["Time_min"].unique())
    tp = min(tps, key=lambda t: abs(t - timepoint))
    cur = sub[sub["Time_min"] == tp].sort_values("Formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(cur["Formula_fraction"].to_numpy()), float)
    y = cur["%T"].to_numpy(float)
    o = np.argsort(x); x, y, _ = clean_curve(x[o], y[o])
    return x, y


def curve1(pkey, chassis):
    if chassis not in POLYMERS.get(pkey, {}):
        return None
    path, tr = POLYMERS[pkey][chassis]
    if not path.startswith("raw_data"):
        path = f"raw_data/{path}"
    return curve(path, tr)


def _auc(xy):
    if xy is None:
        return None
    x, y = xy
    conc = 1.0 / (1.0 + x)
    return compute_auc(conc, transmittance_to_absorbance(y), window=AUC_WINDOW, use_fit=True)["auc"]


def _fit(x, y, mode="fit"):
    lx = np.log10(np.clip(x, 1e-9, None))
    lxd = np.linspace(lx.min(), lx.max(), 500)
    if mode == "points":
        f = fit_curve(lx, y, kind="pchip")           # passes through every point
    else:
        f = fit_curve(lx, y, kind="lowess", smoothing=SMOOTH)
    return 10 ** lxd, np.clip(np.asarray(f(lxd)), y.min(), y.max())


def _dil_axis(ax, xmin, xmax):
    ax.set_xscale("log")
    tk = [t for t in TICKS if xmin * 0.9 <= t <= xmax * 1.15]
    ax.set_xticks(tk); ax.set_xticklabels([f"1:{t}" for t in tk], rotation=45, ha="right", fontsize=7.5)
    ax.set_xlim(max(xmin * 0.9, 0.9), xmax * 1.15)


# --------------------------------------------------------------- 1) timecourse grids (1%)
def timecourse_grids():
    for ch, _ in CHASSIS:
        panels = []
        for pkey in POLY_ORDER:
            if pkey == "3196" or ch not in POLYMERS.get(pkey, {}):
                continue
            path, tr = POLYMERS[pkey][ch]
            path = path if path.startswith("raw_data") else f"raw_data/{path}"
            panels.append({"label": pkey, "series": _keytimes(series(path, tr))})
        plot_small_multiples(panels, view="pct", auc_window=AUC_WINDOW, ncols=4, frac=SMOOTH,
                             title=f"1% dextran \u2014 {ch} chassis \u2014 %T time-course (0\u201315 min)  [guar awaiting]",
                             out_path=f"{R}/dextran_1pct_timecourse_{ch}.png")
        print(f"wrote {R}/dextran_1pct_timecourse_{ch}.png")


# --------------------------------------------------------------- 2) 0.4% vs 1% grids per chassis
def conc_compare_grids(mode="fit"):
    subtitle = "line through every data point (PCHIP)" if mode == "points" else "smooth best-fit"
    for ch, _ in CHASSIS:
        fig, axes = plt.subplots(2, 4, figsize=(16, 8)); axes = axes.ravel()
        for i, pkey in enumerate(POLY_ORDER):
            ax = axes[i]; xmins, xmaxs = [], []
            xy1 = curve1(pkey, ch); xy0 = curve04(pkey, ch)
            if xy1 is not None:
                x, y = xy1; xmins.append(x.min()); xmaxs.append(x.max())
                fx, fy = _fit(x, y, mode=mode)
                ax.plot(fx, fy, "-", color=C_ONE, lw=2.1, label=f"1% (AUC {_auc(xy1):.3f})")
                ax.plot(x, y, "o", color=C_ONE, ms=2.8, alpha=0.45)
            if xy0 is not None:
                x, y = xy0; xmins.append(x.min()); xmaxs.append(x.max())
                fx, fy = _fit(x, y, mode=mode)
                ax.plot(fx, fy, "--", color=C_04, lw=2.0, label=f"0.4% (AUC {_auc(xy0):.3f})")
                ax.plot(x, y, "s", color=C_04, ms=2.8, alpha=0.40)
            if xmins:
                _dil_axis(ax, min(xmins), max(xmaxs))
            ax.set_ylim(0, 100); ax.set_title(pkey, fontsize=11.5, fontweight="bold")
            ax.grid(True, ls=":", alpha=0.5); ax.legend(fontsize=7.5, loc="lower right")
            if i % 4 == 0:
                ax.set_ylabel("% Transmittance")
        fig.suptitle(f"{ch} chassis \u2014 1% (solid) vs 0.4% (dashed) polymer @ 3 min  \u2014  {subtitle}",
                     fontsize=14, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        tag = "points" if mode == "points" else "fit"
        fig.savefig(f"{R}/dextran_conc_compare_{ch}_{tag}.png", dpi=150); plt.close(fig)
        print(f"wrote {R}/dextran_conc_compare_{ch}_{tag}.png")


# --------------------------------------------------------------- 3) master heatmap
def master_heatmap():
    cols = []
    for ch, _ in CHASSIS:
        cols += [(ch, "0.4%"), (ch, "1%")]
    M = np.full((len(POLY_ORDER), len(cols)), np.nan)
    for r, pkey in enumerate(POLY_ORDER):
        for c, (ch, conc) in enumerate(cols):
            a = _auc(curve04(pkey, ch)) if conc == "0.4%" else _auc(curve1(pkey, ch))
            if a is not None:
                M[r, c] = a
    fig, ax = plt.subplots(figsize=(9.2, 6.6))
    im = ax.imshow(M, cmap="YlGnBu", aspect="auto", vmin=0, vmax=np.nanmax(M))
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([f"{ch}\n{conc}" for ch, conc in cols], fontsize=10)
    ax.set_yticks(range(len(POLY_ORDER))); ax.set_yticklabels(POLY_ORDER)
    for r in range(len(POLY_ORDER)):
        for c in range(len(cols)):
            v = M[r, c]
            ax.text(c, r, "n/a" if np.isnan(v) else f"{v:.3f}", ha="center", va="center",
                    fontsize=9, color=("#999" if np.isnan(v) else
                                       ("white" if v > 0.5 * np.nanmax(M) else "#123")),
                    fontweight="bold")
    # chassis separators
    for x in (1.5, 3.5):
        ax.axvline(x, color="white", lw=3)
    ax.set_title("Dextran coacervation AUC \u2014 polymer \u00d7 (chassis \u00d7 concentration)\nconsumer window 1:1\u20131:20, 3 min",
                 fontsize=12.5, fontweight="bold")
    fig.colorbar(im, ax=ax, label="Absorbance AUC")
    fig.tight_layout(); fig.savefig(f"{R}/dextran_master_heatmap.png", dpi=155); plt.close(fig)
    print(f"wrote {R}/dextran_master_heatmap.png")
    # text table
    print("\nAUC  polymer x chassis x conc:")
    print("polymer".ljust(8), "  ".join(f"{ch}{c[0]}".rjust(7) for ch, c in cols))
    for r, pkey in enumerate(POLY_ORDER):
        print(pkey.ljust(8), "  ".join(("n/a" if np.isnan(M[r, c]) else f"{M[r,c]:.3f}").rjust(7)
                                       for c in range(len(cols))))


# --------------------------------------------------------------- 4) concentration-response bars
def conc_response():
    fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)
    for k, (ch, ccol) in enumerate(CHASSIS):
        ax = axes[k]; xpos = np.arange(len(POLY_ORDER)); w = 0.38
        v04 = [_auc(curve04(p, ch)) or 0.0 for p in POLY_ORDER]
        v1 = [(_auc(curve1(p, ch)) or 0.0) for p in POLY_ORDER]
        ax.bar(xpos - w / 2, v04, w, color="#e67e22", edgecolor="#33404d", lw=0.5, label="0.4%")
        ax.bar(xpos + w / 2, v1, w, color="#1f4e79", edgecolor="#33404d", lw=0.5, label="1%")
        ax.set_xticks(xpos); ax.set_xticklabels(POLY_ORDER, rotation=45, ha="right", fontsize=8.5)
        ax.set_title(f"{ch} chassis", fontsize=12, fontweight="bold", color=ccol)
        ax.grid(True, axis="y", ls=":", alpha=0.5)
        if k == 0:
            ax.set_ylabel("Coacervation AUC (1:1\u20131:20)")
        ax.legend(fontsize=9)
    fig.suptitle("Concentration response: 0.4% vs 1% polymer, by chassis  (guar 1% awaiting)",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(f"{R}/dextran_conc_response.png", dpi=155); plt.close(fig)
    print(f"wrote {R}/dextran_conc_response.png")


if __name__ == "__main__":
    timecourse_grids()
    conc_compare_grids(mode="fit")
    conc_compare_grids(mode="points")
    master_heatmap()
    conc_response()
    print("done")
