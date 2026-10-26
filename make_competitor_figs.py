"""Competitor shampoo %T figures (2026-09-04 batch).

Plates / troughs (user-confirmed):
  20260904_7_..._NATIVE_DexK.txt      T1 = NATIVE Scalp Detox   (T2 = LAPB Dex-K, a dextran)
  Crown_Solu (1).txt                  T1 = Crown Volumizing      T2 = Solu Shampoo
  TsalandActAcrePLantStemCell.txt     T1 = Neutrogena T/Sal      T2 = Act+Acre Plant Stem Cell

Outputs (Reports/):
  competitor_2026090_pct.png   %T vs dilution overlay
  competitor_2026090_auc.png   consumer-window AUC bars
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from make_dextran_figs import curve, SMOOTH, AUC_WINDOW, TICKS, dilution_ratio
from coacervation_analysis import fit_curve, transmittance_to_absorbance, compute_auc

RAW = "raw_data"
L7    = f"{RAW}/20260904_7_GH150DDU0_LAPB_1percent_NATIVE_DexK.txt"
CROWN = f"{RAW}/Crown_Solu (1).txt"
TSAL  = f"{RAW}/TsalandActAcrePLantStemCell.txt"

# (label, file, trough, color)
COMP = [
    ("NATIVE Scalp Detox",       L7,    1, "#c0392b"),
    ("Crown Volumizing",         CROWN, 1, "#8e44ad"),
    ("Solu Shampoo",             CROWN, 2, "#2e9e5b"),
    ("Neutrogena T/Sal",         TSAL,  1, "#1f4e79"),
    ("Act+Acre Plant Stem Cell", TSAL,  2, "#e67e22"),
]


def _auc(x, ypct):
    conc = 1.0 / (1.0 + x)
    return compute_auc(conc, transmittance_to_absorbance(ypct),
                       window=AUC_WINDOW, use_fit=True)["auc"]


def _fit(x, y):
    lx = np.log10(np.clip(x, 1e-9, None))
    lxd = np.linspace(lx.min(), lx.max(), 400)
    f = fit_curve(lx, y, kind="lowess", smoothing=SMOOTH)
    return 10 ** lxd, np.clip(np.asarray(f(lxd)), y.min(), y.max())


def _dil_axis(ax, xmin, xmax):
    ax.set_xscale("log")
    tk = [t for t in TICKS if xmin * 0.9 <= t <= xmax * 1.15]
    ax.set_xticks(tk); ax.set_xticklabels([f"1:{t}" for t in tk], rotation=45, ha="right")
    ax.set_xlim(max(xmin * 0.9, 0.9), xmax * 1.15)


def build():
    rows = []
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    xmins, xmaxs = [], []
    for label, path, tr, col in COMP:
        x, y = curve(path, tr)
        xmins.append(x.min()); xmaxs.append(x.max())
        fx, fy = _fit(x, y)
        a = _auc(x, y)
        rows.append((label, col, a, float(y.min()), float(x[np.argmin(y)])))
        ax.plot(fx, fy, "-", color=col, lw=2.4, label=f"{label} (AUC {a:.3f})")
        ax.plot(x, y, "o", color=col, ms=3, alpha=0.35)
    _dil_axis(ax, min(xmins), max(xmaxs))
    ax.set_ylim(0, 100); ax.set_ylabel("% Transmittance")
    ax.set_xlabel("Dilution (1:X)  \u2014  most \u2192 least concentrated")
    ax.set_title("Competitor shampoos \u2014 %T vs dilution (3 min)", fontsize=12, fontweight="bold")
    ax.grid(True, ls=":", alpha=0.55); ax.legend(fontsize=8.5, loc="lower right")
    fig.tight_layout(); fig.savefig("Reports/competitor_2026090_pct.png", dpi=160); plt.close(fig)
    print("wrote Reports/competitor_2026090_pct.png")

    rows.sort(key=lambda r: r[2])
    fig, ax = plt.subplots(figsize=(9, 0.6 * len(rows) + 1.8))
    yv = np.arange(len(rows))
    ax.barh(yv, [r[2] for r in rows], color=[r[1] for r in rows], edgecolor="#33404d", linewidth=0.7)
    ax.set_yticks(yv); ax.set_yticklabels([r[0] for r in rows], fontsize=10)
    mx = max(r[2] for r in rows) or 1
    for i, r in enumerate(rows):
        ax.text(r[2] + mx * 0.01, i, f"{r[2]:.3f}", va="center", fontsize=9)
    ax.set_xlabel("Coacervation AUC (consumer window 1:1\u20131:20)")
    ax.set_title("Competitor coacervation strength (AUC)", fontsize=12, fontweight="bold")
    ax.grid(True, axis="x", ls=":", alpha=0.5)
    fig.tight_layout(); fig.savefig("Reports/competitor_2026090_auc.png", dpi=160); plt.close(fig)
    print("wrote Reports/competitor_2026090_auc.png")

    print("\nCompetitor summary (t=3, consumer window):")
    for label, col, a, ymin, xdip in sorted(rows, key=lambda r: -r[2]):
        print(f"  {label:26s} AUC={a:.3f}  min%T={ymin:.0f} at 1:{xdip:.0f}")


if __name__ == "__main__":
    build()
