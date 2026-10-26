"""1% dextran screen across 3 surfactant chassis (EED0 / LAPB / APG).

Completes the 3-chassis x polymer matrix at 1% using my own plates:
  - APG   plates: 20260903_* (already used in make_dextran_figs.py)
  - EED0  plates: 20260904_1..3 (this batch)
  - LAPB  plates: 20260904_4..6 (this batch)  + LAPB Dex-K from 20260903_APGDexK_LAPBDexK

Outputs (Reports/):
  dextran_1pct_chassis_grid.png     per-polymer %T overlay across 3 chassis
  dextran_1pct_chassis_heatmap.png  consumer-window AUC heatmap (polymer x chassis)
  dextran_1pct_chassis_bars.png     grouped AUC bars (polymer x chassis)
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from make_dextran_figs import curve, SMOOTH, AUC_WINDOW, TICKS, dilution_ratio
from coacervation_analysis import fit_curve, transmittance_to_absorbance, compute_auc

RAW = "raw_data"
TIMEPOINT = 3.0
FIT_SMOOTH = 0.18  # lowess fraction for the best-fit version (hugs points, still smooth)

# chassis display order + color
CHASSIS = [("EED0", "#2E75B6"), ("LAPB", "#2e9e5b"), ("APG", "#e67e22")]

# raw plate files
APG_CD2B = f"{RAW}/20260903_APG_CD2_DexB_RawData.txt"
APG_BJ   = f"{RAW}/20260903_DexBstar_DexJ_RawData.txt"
APG_JA   = f"{RAW}/20260903_DexJstar_DexA_RawData.txt"
APG_DEXK = f"{RAW}/20260903_APGDexK_LAPBDexK_RawData.txt"
E1 = f"{RAW}/20260904_1_GH150EED0_CD2_DexB_1percent.txt"
E2 = f"{RAW}/20260904_2_GH150EED0_DexBstar_DexJ_1percent.txt"
E3 = f"{RAW}/20260904_3_GH150EED0_Dexjstar_DexA_1percent.txt"
L4 = f"{RAW}/20260904_4_GH150DDU0_LAPB_1percent_DexBstar_DexJ.txt"
L5 = f"{RAW}/20260904_5_GH150DDU0_LAPB_1percent_CD2_DexB.txt"
L6 = f"{RAW}/20260904_6_GH150DDU0_LAPB_1percent_DexJstar_DexA.txt"
L7 = f"{RAW}/20260904_7_GH150DDU0_LAPB_1percent_NATIVE_DexK.txt"  # T1=NATIVE(competitor), T2=Dex-K in EED0 base

# polymer -> {chassis: (file, trough)}
POLYMERS = {
    "CD2":    {"EED0": (E1, 1), "LAPB": (L5, 1), "APG": (APG_CD2B, 1)},
    "Dex-K":  {"EED0": (L7, 2), "LAPB": (APG_DEXK, 2), "APG": (APG_DEXK, 1)},  # EED0 = file7 T2 (base)
    "Dex-B":  {"EED0": (E1, 2), "LAPB": (L5, 2), "APG": (APG_CD2B, 2)},
    "Dex-B*": {"EED0": (E2, 1), "LAPB": (L4, 1), "APG": (APG_BJ, 1)},
    "Dex-J":  {"EED0": (E2, 2), "LAPB": (L4, 2), "APG": (APG_BJ, 2)},
    "Dex-J*": {"EED0": (E3, 1), "LAPB": (L6, 1), "APG": (APG_JA, 1)},
    "Dex-A":  {"EED0": (E3, 2), "LAPB": (L6, 2), "APG": (APG_JA, 2)},
}
COLORS = dict(CHASSIS)


def _auc(x, ypct):
    conc = 1.0 / (1.0 + x)
    return compute_auc(conc, transmittance_to_absorbance(ypct),
                       window=AUC_WINDOW, use_fit=True)["auc"]


def _fit(x, y, mode="fit"):
    """Return (x_dense, y_dense) for one of two curve styles.

    mode='points' -> monotone PCHIP interpolation that passes through EVERY
                     (cleaned) data point.
    mode='fit'    -> smooth lowess best-fit curve.
    """
    lx = np.log10(np.clip(x, 1e-9, None))
    lxd = np.linspace(lx.min(), lx.max(), 500)
    if mode == "points":
        f = fit_curve(lx, y, kind="pchip")
    else:
        f = fit_curve(lx, y, kind="lowess", smoothing=FIT_SMOOTH)
    return 10 ** lxd, np.clip(np.asarray(f(lxd)), y.min(), y.max())


def _dil_axis(ax, xmin, xmax):
    ax.set_xscale("log")
    tk = [t for t in TICKS if xmin * 0.9 <= t <= xmax * 1.15]
    ax.set_xticks(tk); ax.set_xticklabels([f"1:{t}" for t in tk], rotation=45, ha="right", fontsize=7.5)
    ax.set_xlim(max(xmin * 0.9, 0.9), xmax * 1.15)


def build():
    # collect AUC table once (independent of display style)
    auc_tab = {p: {} for p in POLYMERS}
    for pname, chdict in POLYMERS.items():
        for ch, _ in CHASSIS:
            if ch not in chdict:
                continue
            path, tr = chdict[ch]
            x, y = curve(path, tr)
            auc_tab[pname][ch] = _auc(x, y)

    # two grid versions: through-every-point (pchip) and smooth best-fit (lowess)
    for mode, tag, subtitle in [
        ("points", "points", "curve through EVERY data point (PCHIP interpolation)"),
        ("fit", "fit", "smooth best-fit (lowess)"),
    ]:
        fig, axes = plt.subplots(2, 4, figsize=(16, 8))
        axes = axes.ravel()
        for i, (pname, chdict) in enumerate(POLYMERS.items()):
            ax = axes[i]
            xmins, xmaxs = [], []
            for ch, col in CHASSIS:
                if ch not in chdict:
                    continue
                path, tr = chdict[ch]
                x, y = curve(path, tr)  # cleaned, t=3
                xmins.append(x.min()); xmaxs.append(x.max())
                fx, fy = _fit(x, y, mode=mode)
                a = auc_tab[pname][ch]
                lw = 1.9 if mode == "points" else 2.4
                ax.plot(fx, fy, "-", color=col, lw=lw, label=f"{ch} (AUC {a:.3f})")
                ax.plot(x, y, "o", color=col, ms=3.2, alpha=0.55 if mode == "points" else 0.30)
            _dil_axis(ax, min(xmins), max(xmaxs))
            ax.set_ylim(0, 100)
            ax.set_title(pname, fontsize=11.5, fontweight="bold")
            ax.grid(True, ls=":", alpha=0.5)
            ax.legend(fontsize=7.5, loc="lower right")
            if i % 4 == 0:
                ax.set_ylabel("% Transmittance")
        # 8th panel: grouped AUC bars
        axb = axes[7]
        pol = list(POLYMERS.keys())
        xpos = np.arange(len(pol)); w = 0.26
        for j, (ch, col) in enumerate(CHASSIS):
            vals = [auc_tab[p].get(ch, 0.0) for p in pol]
            axb.bar(xpos + (j - 1) * w, vals, w, color=col, edgecolor="#33404d",
                    linewidth=0.5, label=ch)
        axb.set_xticks(xpos); axb.set_xticklabels(pol, rotation=45, ha="right", fontsize=8)
        axb.set_ylabel("AUC (1:1\u20131:20)"); axb.set_title("Consumer-window AUC", fontsize=10.5, fontweight="bold")
        axb.grid(True, axis="y", ls=":", alpha=0.5); axb.legend(fontsize=8)
        fig.suptitle(f"1% dextran screen \u2014 3 chassis (EED0 / LAPB / APG), %T @ 3 min  \u2014  {subtitle}",
                     fontsize=13.5, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        out = f"Reports/dextran_1pct_chassis_grid_{tag}.png"
        fig.savefig(out, dpi=155)
        plt.close(fig)
        print("wrote", out)

    # heatmap
    pol = list(POLYMERS.keys())
    chs = [c for c, _ in CHASSIS]
    M = np.array([[auc_tab[p].get(c, np.nan) for c in chs] for p in pol])
    fig, ax = plt.subplots(figsize=(6.2, 6.8))
    im = ax.imshow(M, cmap="YlGnBu", aspect="auto", vmin=0, vmax=np.nanmax(M))
    ax.set_xticks(range(len(chs))); ax.set_xticklabels(chs)
    ax.set_yticks(range(len(pol))); ax.set_yticklabels(pol)
    for r in range(len(pol)):
        for c in range(len(chs)):
            v = M[r, c]
            if np.isnan(v):
                ax.text(c, r, "n/a", ha="center", va="center", fontsize=9, color="#999")
            else:
                ax.text(c, r, f"{v:.3f}", ha="center", va="center", fontsize=9.5,
                        color="white" if v > 0.5 * np.nanmax(M) else "#123",
                        fontweight="bold")
    ax.set_title("1% dextran \u2014 coacervation AUC\n(polymer \u00d7 chassis, consumer window)",
                 fontsize=12, fontweight="bold")
    fig.colorbar(im, ax=ax, label="Absorbance AUC")
    fig.tight_layout()
    fig.savefig("Reports/dextran_1pct_chassis_heatmap.png", dpi=155)
    plt.close(fig)
    print("wrote Reports/dextran_1pct_chassis_heatmap.png")

    # print table
    print("\n1% AUC (consumer window 1:1-1:20):")
    print("polymer".ljust(8), "  ".join(c.rjust(6) for c in chs))
    for p in pol:
        print(p.ljust(8), "  ".join((f"{auc_tab[p][c]:.3f}" if c in auc_tab[p] else "  n/a").rjust(6) for c in chs))


if __name__ == "__main__":
    build()
