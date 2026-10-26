"""Timepoint, absorbance & AUC-ranking suite for the dextran screen.

Uses a TROUGH-PRESERVING smooth (lowess frac 0.15): smooth but keeps the real
late-dilution / second troughs. Timepoints of interest: 0, 3, 5, 15 min.

Outputs (Reports/):
  dextran_1pct_timepts_{chassis}.png     all polymers overlaid, one panel per t (0/3/5/15)
  dextran_1pct_evolution_{chassis}.png   one panel per polymer, 0/3/5/15 min overlaid
  dextran_1pct_absorbance_{chassis}.png  absorbance vs concentration, 0/3/5/15, AUC band
  dextran_auc_ranking_all.png            ranked AUC bar across ALL formulations
  dextran_auc_over_time.png              AUC(t) decay for the top formulations
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from make_dextran_chassis_compare import POLYMERS
from make_dextran_full_analysis import curve04, CH_CSV, POLY_ORDER, CHASSIS
from make_dextran_figs import curve, AUC_WINDOW, TICKS
from coacervation_analysis import fit_curve, transmittance_to_absorbance, compute_auc

R = "Reports"
TROUGH_SMOOTH = 0.20  # smooth but keeps multi-well troughs (incl. APG 2nd trough)
TIMES = [0, 3, 5, 15]
TCOLORS = {0: "#1f2d5a", 3: "#2e9e5b", 5: "#e8892b", 15: "#b4231f"}
POLY_COLORS = {
    "CD2": "#c0392b", "Dex-K": "#8e44ad", "3196": "#555e6b", "Dex-A": "#1f4e79",
    "Dex-B": "#e67e22", "Dex-B*": "#7a5c00", "Dex-J": "#2e9e5b", "Dex-J*": "#17a2b8",
}
POLY_1PCT = [p for p in POLY_ORDER if p != "3196"]  # guar 1% awaiting

CH_FULL = {
    "EED0": "Base: GH150 EED0 (5/5/2 AOS/SLS/CAPB)",
    "LAPB": "70% base + LAPB (3.5/3.5/1.4/3.6 AOS/SLS/CAPB/LAPB)",
    "APG":  "70% base + APG (3.5/3.5/1.4/3.6 AOS/SLS/CAPB/APG)",
}

OBS_TIMEPTS = {
    "EED0": "Observation: CD2 leads; Dex-K moderate; other dextrans stay ~clear. Troughs are deepest at 0 min and shallow by 15 min (coacervate coarsens).",
    "LAPB": "Observation: CD2, Dex-K AND Dex-J* coacervate strongly at the CONCENTRATED end (1:1-1:5) then clear on dilution - the LAPB 'in-bottle' signature.",
    "APG": "Observation: coacervation is DELAYED to ~1:5 (rinse-relevant) and weaker; a real SECOND trough appears at high dilution (~1:80-1:100).",
}
OBS_EVO = {
    "EED0": "Observation: concentrated-end troughs fade over 0->15 min (coalescence/ripening - NOT settling; the plate is shaken between every read).",
    "LAPB": "Observation: strongest, in-bottle troughs that shallow over 15 min as droplets coarsen. Dex-J* switches on ONLY here (and only at 1%).",
    "APG": "Observation: delayed primary trough (~1:5) PLUS a preserved second trough at high dilution; both fade with time.",
}
OBS_ABS = "Observation: absorbance PEAK height ~ coacervate amount, AREA ~ total deposition potential; peaks decay 0->15 min. Shaded band = consumer window."


def c1(pkey, ch, t=3.0):
    if ch not in POLYMERS.get(pkey, {}):
        return None
    path, tr = POLYMERS[pkey][ch]
    if not path.startswith("raw_data"):
        path = f"raw_data/{path}"
    return curve(path, tr, timepoint=t)


def smooth(x, y, frac=TROUGH_SMOOTH, mode="fit"):
    lx = np.log10(np.clip(x, 1e-9, None))
    lxd = np.linspace(lx.min(), lx.max(), 500)
    if mode == "points":
        return smooth_hybrid(x, y)                     # smooth 1:1-1:50, through-points beyond
    else:
        f = fit_curve(lx, y, kind="lowess", smoothing=frac)
    yd = np.clip(np.asarray(f(lxd)), min(y.min(), 0), max(y.max(), 100) if y.max() > 5 else y.max())
    return 10 ** lxd, yd


def smooth_hybrid(x, y, split=50.0, frac=0.28, k=0.16):
    """Hybrid: heavy lowess below 1:split (kills jagged concentrated-end noise,
    1:1-1:50), blended into a point-faithful PCHIP curve beyond 1:split (keeps
    the real late-dilution troughs). Sigmoid weight in log-dilution space."""
    lx = np.log10(np.clip(x, 1e-9, None))
    lxd = np.linspace(lx.min(), lx.max(), 600)
    ylo = np.asarray(fit_curve(lx, y, kind="lowess", smoothing=frac)(lxd))
    ypc = np.asarray(fit_curve(lx, y, kind="pchip")(lxd))
    xd = 10 ** lxd
    w = 1.0 / (1.0 + np.exp(-(np.log10(xd) - np.log10(split)) / k))  # 0 conc -> 1 dilute
    yd = (1 - w) * ylo + w * ypc
    yd = np.clip(yd, min(float(y.min()), 0.0), 100.0 if y.max() > 5 else float(y.max()))
    return xd, yd


def _auc(xy):
    if xy is None:
        return None
    x, y = xy
    return compute_auc(1.0 / (1.0 + x), transmittance_to_absorbance(y),
                       window=AUC_WINDOW, use_fit=True)["auc"]


def _dil_axis(ax, xmin, xmax, fs=7.5):
    ax.set_xscale("log")
    tk = [t for t in TICKS if xmin * 0.9 <= t <= xmax * 1.15]
    ax.set_xticks(tk); ax.set_xticklabels([f"1:{t}" for t in tk], rotation=45, ha="right", fontsize=fs)
    ax.set_xlim(max(xmin * 0.9, 0.9), xmax * 1.15)


# ---------------------------------------------- 1) timepoint overlays (all polymers)
def timepts_grids():
    for ch, _ in CHASSIS:
        fig, axes = plt.subplots(2, 2, figsize=(13, 8)); axes = axes.ravel()
        for k, t in enumerate(TIMES):
            ax = axes[k]; xmins, xmaxs = [], []
            for pkey in POLY_1PCT:
                xy = c1(pkey, ch, t)
                if xy is None:
                    continue
                x, y = xy; xmins.append(x.min()); xmaxs.append(x.max())
                fx, fy = smooth(x, y)
                ax.plot(fx, fy, "-", color=POLY_COLORS[pkey], lw=2.1, label=pkey)
                ax.plot(x, y, "o", color=POLY_COLORS[pkey], ms=2.1, alpha=0.22)
            if xmins:
                _dil_axis(ax, min(xmins), max(xmaxs))
            ax.set_ylim(0, 100); ax.set_title(f"{t} min", fontsize=12, fontweight="bold")
            ax.grid(True, ls=":", alpha=0.5); ax.set_ylabel("% Transmittance")
            if k == 0:
                ax.legend(fontsize=8, loc="lower right", ncol=2)
        fig.suptitle(f"1% dextran \u2014 {CH_FULL[ch]} \u2014 all polymers at 0 / 3 / 5 / 15 min (trough-preserving smooth + raw points)",
                     fontsize=13, fontweight="bold")
        fig.text(0.5, 0.012, OBS_TIMEPTS[ch], ha="center", fontsize=9.5, style="italic", color="#33404d")
        fig.tight_layout(rect=(0, 0.035, 1, 0.96))
        fig.savefig(f"{R}/dextran_1pct_timepts_{ch}.png", dpi=150); plt.close(fig)
        print(f"wrote {R}/dextran_1pct_timepts_{ch}.png")


# ---------------------------------------------- 2) evolution (per polymer, times overlaid)
def evolution_grids(mode="fit"):
    sfx = "points" if mode == "points" else "fit"
    style = "smooth 1:1-1:50, through-points beyond" if mode == "points" else "trough-preserving smooth"
    for ch, _ in CHASSIS:
        fig, axes = plt.subplots(2, 4, figsize=(16, 8)); axes = axes.ravel()
        for i, pkey in enumerate(POLY_1PCT):
            ax = axes[i]; xmins, xmaxs = [], []
            for t in TIMES:
                xy = c1(pkey, ch, t)
                if xy is None:
                    continue
                x, y = xy; xmins.append(x.min()); xmaxs.append(x.max())
                # LAPB Dex-A: draw through every data point (pure PCHIP), no hybrid smoothing
                if mode == "points" and ch == "LAPB" and pkey == "Dex-A":
                    lx = np.log10(np.clip(x, 1e-9, None))
                    lxd = np.linspace(lx.min(), lx.max(), 500)
                    fx, fy = 10 ** lxd, np.asarray(fit_curve(lx, y, kind="pchip")(lxd))
                else:
                    fx, fy = smooth(x, y, mode=mode)
                ax.plot(fx, fy, "-", color=TCOLORS[t], lw=1.9, label=f"{t} min")
                ax.plot(x, y, "o", color=TCOLORS[t], ms=2.6, alpha=0.38)
            if xmins:
                _dil_axis(ax, min(xmins), max(xmaxs))
            ax.set_ylim(0, 100); ax.set_title(pkey, fontsize=11.5, fontweight="bold")
            ax.grid(True, ls=":", alpha=0.5)
            if i % 4 == 0:
                ax.set_ylabel("% Transmittance")
            if i == 0:
                ax.legend(fontsize=8, loc="lower right")
        axes[7].axis("off")
        fig.suptitle(f"1% dextran \u2014 {CH_FULL[ch]} \u2014 0\u201315 min evolution ({style} + raw points)",
                     fontsize=13, fontweight="bold")
        fig.text(0.5, 0.012, OBS_EVO[ch], ha="center", fontsize=9.5, style="italic", color="#33404d")
        fig.tight_layout(rect=(0, 0.035, 1, 0.97))
        fig.savefig(f"{R}/dextran_1pct_evolution_{ch}_{sfx}.png", dpi=150); plt.close(fig)
        print(f"wrote {R}/dextran_1pct_evolution_{ch}_{sfx}.png")


# ---------------------------------------------- 3) absorbance vs concentration
def absorbance_grids():
    lo, hi = min(AUC_WINDOW), max(AUC_WINDOW)
    for ch, _ in CHASSIS:
        fig, axes = plt.subplots(2, 4, figsize=(16, 8)); axes = axes.ravel()
        for i, pkey in enumerate(POLY_1PCT):
            ax = axes[i]
            for t in TIMES:
                xy = c1(pkey, ch, t)
                if xy is None:
                    continue
                x, y = xy
                a = transmittance_to_absorbance(y)
                lx = np.log10(np.clip(x, 1e-9, None)); lxd = np.linspace(lx.min(), lx.max(), 500)
                f = fit_curve(lx, a, kind="lowess", smoothing=TROUGH_SMOOTH)
                ad = np.clip(np.asarray(f(lxd)), a.min(), a.max())
                conc = 1.0 / (1.0 + 10 ** lxd)
                ax.plot(conc, ad, "-", color=TCOLORS[t], lw=2.0, label=f"{t} min")
                ax.plot(1.0 / (1.0 + x), a, "o", color=TCOLORS[t], ms=2.2, alpha=0.28)
            ax.axvspan(lo, hi, color="#f2d7a0", alpha=0.4)
            ax.set_xlim(0.5, 0.0); ax.set_ylim(0, 0.6)
            ax.set_title(pkey, fontsize=11.5, fontweight="bold")
            ax.grid(True, ls=":", alpha=0.5)
            if i % 4 == 0:
                ax.set_ylabel("Absorbance (A = 2 \u2212 log10 %T)")
            if i >= 4:
                ax.set_xlabel("Concentration (formula fraction)")
            if i == 0:
                ax.legend(fontsize=8, loc="upper right")
        axes[7].axis("off")
        fig.suptitle(f"1% dextran \u2014 {CH_FULL[ch]} \u2014 absorbance vs concentration (0/3/5/15 min; band = consumer window)",
                     fontsize=12.5, fontweight="bold")
        fig.text(0.5, 0.012, OBS_ABS, ha="center", fontsize=9.5, style="italic", color="#33404d")
        fig.tight_layout(rect=(0, 0.035, 1, 0.97))
        fig.savefig(f"{R}/dextran_1pct_absorbance_{ch}.png", dpi=150); plt.close(fig)
        print(f"wrote {R}/dextran_1pct_absorbance_{ch}.png")


# ---------------------------------------------- 4) AUC ranking across ALL formulations
def auc_ranking():
    rows = []  # (label, chassis, conc, auc)
    for ch, _ in CHASSIS:
        for pkey in POLY_ORDER:
            a1 = _auc(c1(pkey, ch, 3.0))
            a0 = _auc(curve04(pkey, ch, 3.0))
            if a1 is not None:
                rows.append((f"{ch} \u00b7 {pkey} \u00b7 1%", ch, "1%", a1))
            if a0 is not None:
                rows.append((f"{ch} \u00b7 {pkey} \u00b7 0.4%", ch, "0.4%", a0))
    rows.sort(key=lambda r: r[3], reverse=True)
    # print full ranked table
    print("\nRANKED AUC (consumer window, 3 min) \u2014 all formulations:")
    for rk, (lab, ch, conc, a) in enumerate(rows, 1):
        print(f"  {rk:2d}. {lab:24s} {a:.3f}")
    # bar of the meaningful ones (>= 0.025)
    top = [r for r in rows if r[3] >= 0.025]
    chcol = {"EED0": "#2E75B6", "LAPB": "#2e9e5b", "APG": "#e67e22"}
    fig, ax = plt.subplots(figsize=(9.5, 0.42 * len(top) + 1.5))
    yv = np.arange(len(top))[::-1]
    ax.barh(yv, [r[3] for r in top], color=[chcol[r[1]] for r in top],
            hatch=["//" if r[2] == "0.4%" else "" for r in top],
            edgecolor="#33404d", linewidth=0.6)
    ax.set_yticks(yv); ax.set_yticklabels([r[0] for r in top], fontsize=8.5)
    mx = max(r[3] for r in top)
    for y, r in zip(yv, top):
        ax.text(r[3] + mx * 0.01, y, f"{r[3]:.3f}", va="center", fontsize=8)
    from matplotlib.patches import Patch
    leg = [Patch(fc="#2E75B6", label="EED0"), Patch(fc="#2e9e5b", label="LAPB"),
           Patch(fc="#e67e22", label="APG"), Patch(fc="#ccc", hatch="//", label="0.4% (hatched)")]
    ax.legend(handles=leg, fontsize=8.5, loc="lower right")
    ax.set_xlabel("Coacervation AUC (consumer window 1:1\u20131:20, 3 min)")
    ax.set_title("Coacervation strength ranked \u2014 all formulations (AUC \u2265 0.025 shown)",
                 fontsize=12.5, fontweight="bold")
    ax.grid(True, axis="x", ls=":", alpha=0.5)
    fig.text(0.5, 0.012, "Observation: LAPB 1% sweeps the podium (CD2 > Dex-J* > Dex-K). EED0-CD2 saturates by 0.4%; APG weakest. "
             "Lead dextrans reach ~80% of CD2 (benchmark) in LAPB.", ha="center", fontsize=9, style="italic", color="#33404d")
    fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(f"{R}/dextran_auc_ranking_all.png", dpi=155); plt.close(fig)
    print(f"wrote {R}/dextran_auc_ranking_all.png")
    return [r for r in rows if r[3] >= 0.04][:8]


# ---------------------------------------------- 5) AUC over time (decay) for top formulations
def auc_over_time(top):
    ts = [0, 1, 3, 5, 10, 15]
    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    chls = {"EED0": "-", "LAPB": "--", "APG": ":"}
    for lab, ch, conc, _ in top:
        pkey = lab.split(" \u00b7 ")[1]
        vals = []
        for t in ts:
            xy = c1(pkey, ch, t) if conc == "1%" else curve04(pkey, ch, t)
            vals.append(_auc(xy) or 0.0)
        ax.plot(ts, vals, chls.get(ch, "-"), marker="o", lw=2, label=lab)
    ax.set_xlabel("Time (min)"); ax.set_ylabel("Coacervation AUC")
    ax.set_title("Coacervation AUC over time \u2014 top formulations (kinetic stability)",
                 fontsize=12.5, fontweight="bold")
    ax.grid(True, ls=":", alpha=0.55); ax.legend(fontsize=8.5, loc="upper right")
    fig.text(0.5, 0.01, "Observation: every leader LOSES AUC over 0->15 min (coacervate coarsening/coalescence). The decay slope itself "
             "is a 'kinetic-stability' attribute worth ranking.", ha="center", fontsize=9, style="italic", color="#33404d")
    fig.tight_layout(rect=(0, 0.04, 1, 1)); fig.savefig(f"{R}/dextran_auc_over_time.png", dpi=155); plt.close(fig)
    print(f"wrote {R}/dextran_auc_over_time.png")


if __name__ == "__main__":
    timepts_grids()
    evolution_grids(mode="fit")
    evolution_grids(mode="points")
    absorbance_grids()
    top = auc_ranking()
    auc_over_time(top)
    print("done")
