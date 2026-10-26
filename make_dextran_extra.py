"""Extra dextran figures: 0.4% evolution per chassis + t=0 three-chassis overlays.

  dextran_04pct_evolution_{chassis}.png  0-15 min evolution, 0.4% polymer (all 8, incl guar)
  dextran_t0_chassis_overlay.png         guar/CD2/Dex-K/Dex-J/Dex-J* overlaid across 3 chassis at t=0
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from make_dextran_timepoint_analysis import smooth, TIMES, TCOLORS, _dil_axis, c1
from make_dextran_full_analysis import curve04, CHASSIS, POLY_ORDER
from coacervation_analysis import fit_curve

R = "Reports"
CHCOL = {"EED0": "#2E75B6", "LAPB": "#2e9e5b", "APG": "#e67e22"}


def smooth_hybrid(x, y, split=50.0, frac=0.28, k=0.16):
    """Smooth (lowess) below 1:split, through-points (PCHIP) above it.

    Blends a heavier lowess fit (kills jagged concentrated-end noise, 1:1-1:50)
    into a point-faithful PCHIP curve at high dilution (keeps the real troughs).
    """
    lx = np.log10(np.clip(x, 1e-9, None))
    lxd = np.linspace(lx.min(), lx.max(), 600)
    ylo = np.asarray(fit_curve(lx, y, kind="lowess", smoothing=frac)(lxd))
    ypc = np.asarray(fit_curve(lx, y, kind="pchip")(lxd))
    xd = 10 ** lxd
    w = 1.0 / (1.0 + np.exp(-(np.log10(xd) - np.log10(split)) / k))  # 0 conc -> 1 dilute
    yd = (1 - w) * ylo + w * ypc
    yd = np.clip(yd, min(float(y.min()), 0.0), 100.0 if y.max() > 5 else float(y.max()))
    return xd, yd


def evolution_04():
    for ch, _ in CHASSIS:
        fig, axes = plt.subplots(2, 4, figsize=(16, 8)); axes = axes.ravel()
        for i, pkey in enumerate(POLY_ORDER):
            ax = axes[i]; xmins, xmaxs = [], []
            for t in TIMES:
                xy = curve04(pkey, ch, t)
                if xy is None:
                    continue
                x, y = xy; xmins.append(x.min()); xmaxs.append(x.max())
                fx, fy = smooth(x, y)
                ax.plot(fx, fy, "-", color=TCOLORS[t], lw=1.9, label=f"{t} min")
                ax.plot(x, y, "o", color=TCOLORS[t], ms=2.4, alpha=0.35)
            if xmins:
                _dil_axis(ax, min(xmins), max(xmaxs))
            ax.set_ylim(0, 100); ax.set_title(pkey, fontsize=11.5, fontweight="bold")
            ax.grid(True, ls=":", alpha=0.5)
            if i % 4 == 0:
                ax.set_ylabel("% Transmittance")
            if i == 0:
                ax.legend(fontsize=8, loc="lower right")
        fig.suptitle(f"0.4% dextran \u2014 {ch} chassis \u2014 0\u201315 min evolution (all 8 polymers incl. guar)",
                     fontsize=14, fontweight="bold")
        fig.tight_layout(rect=(0, 0, 1, 0.97))
        fig.savefig(f"{R}/dextran_04pct_evolution_{ch}.png", dpi=150); plt.close(fig)
        print(f"wrote {R}/dextran_04pct_evolution_{ch}.png")


def t0_overlay(mode="fit"):
    sfx = "_points" if mode == "points" else ""
    style = ("smooth 1:1-1:50, through-points beyond" if mode == "points" else "smooth fit")
    pols = [("3196", "0.4%"), ("CD2", "1%"), ("Dex-K", "1%"), ("Dex-J", "1%"), ("Dex-J*", "1%")]
    fig, axes = plt.subplots(2, 3, figsize=(15, 8)); axes = axes.ravel()
    for i, (pkey, conc) in enumerate(pols):
        ax = axes[i]; xmins, xmaxs = [], []
        for ch, _ in CHASSIS:
            xy = c1(pkey, ch, 0.0) if conc == "1%" else curve04(pkey, ch, 0.0)
            if xy is None:
                continue
            x, y = xy; xmins.append(x.min()); xmaxs.append(x.max())
            fx, fy = smooth_hybrid(x, y) if mode == "points" else smooth(x, y, mode="fit")
            ax.plot(fx, fy, "-", color=CHCOL[ch], lw=2.0, label=ch)
            ax.plot(x, y, "o", color=CHCOL[ch], ms=2.6, alpha=0.35)
        if xmins:
            _dil_axis(ax, min(xmins), max(xmaxs))
        ax.set_ylim(0, 100); ax.set_title(f"{pkey}   ({conc})", fontsize=12.5, fontweight="bold")
        ax.grid(True, ls=":", alpha=0.5); ax.legend(fontsize=9, loc="lower right")
        if i % 3 == 0:
            ax.set_ylabel("% Transmittance")
    ax = axes[5]; ax.axis("off")
    ax.text(0.5, 0.62, "t = 0 min (freshly mixed)\n3-chassis overlay", ha="center", fontsize=14,
            fontweight="bold", color="#0B1F3A", transform=ax.transAxes)
    ax.text(0.5, 0.34, "guar shown at 0.4% (no 1% yet);\nCD2/Dex-K/Dex-J/Dex-J* at 1%", ha="center",
            fontsize=10.5, style="italic", color="#6b7480", transform=ax.transAxes)
    fig.suptitle(f"Chassis effect at t = 0 min \u2014 guar, CD2, Dex-K, Dex-J, Dex-J*  ({style})",
                 fontsize=14.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(f"{R}/dextran_t0_chassis_overlay{sfx}.png", dpi=155); plt.close(fig)
    print(f"wrote {R}/dextran_t0_chassis_overlay{sfx}.png")


def conc_compare(mode="points"):
    """0.4% (dashed) vs 1% (solid) for polymers that have both, t = 0 min.

    One panel per polymer; three chassis overlaid (colour), concentration by
    line style. Directly shows how raising the polymer to 1% deepens/broadens
    coacervation vs the 0.4% screen.
    """
    sfx = "_points" if mode == "points" else ""
    fx_of = (lambda x, y: smooth_hybrid(x, y)) if mode == "points" else (lambda x, y: smooth(x, y, mode="fit"))
    pols = ["CD2", "Dex-K", "Dex-J", "Dex-J*"]  # have both 0.4% and 1% data
    fig, axes = plt.subplots(2, 2, figsize=(13, 9)); axes = axes.ravel()
    for i, pkey in enumerate(pols):
        ax = axes[i]; xmins, xmaxs = [], []
        for ch, _ in CHASSIS:
            col = CHCOL[ch]
            for conc, lo in (("0.4%", curve04(pkey, ch, 0.0)), ("1%", c1(pkey, ch, 0.0))):
                if lo is None:
                    continue
                x, y = lo; xmins.append(x.min()); xmaxs.append(x.max())
                fx, fy = fx_of(x, y)
                ls = "--" if conc == "0.4%" else "-"
                lw = 1.7 if conc == "0.4%" else 2.3
                ax.plot(fx, fy, ls, color=col, lw=lw, alpha=0.95,
                        label=f"{ch} {conc}")
                ax.plot(x, y, "o", color=col, ms=2.3, alpha=0.28)
        if xmins:
            _dil_axis(ax, min(xmins), max(xmaxs))
        ax.set_ylim(0, 100); ax.set_title(pkey, fontsize=13, fontweight="bold")
        ax.grid(True, ls=":", alpha=0.5); ax.legend(fontsize=8, loc="lower right", ncol=1)
        if i % 2 == 0:
            ax.set_ylabel("% Transmittance")
    fig.suptitle("Concentration effect at t = 0 min \u2014 0.4% (dashed) vs 1% (solid), "
                 "three chassis", fontsize=14.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(f"{R}/dextran_conc_04_vs_1{sfx}.png", dpi=155); plt.close(fig)
    print(f"wrote {R}/dextran_conc_04_vs_1{sfx}.png")


if __name__ == "__main__":
    evolution_04()
    t0_overlay(mode="fit")
    t0_overlay(mode="points")
    conc_compare(mode="points")
    print("done")
