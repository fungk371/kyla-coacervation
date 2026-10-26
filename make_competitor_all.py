"""Unified competitor / in-market %T analysis (clear shampoos).

Combines every competitor & P&G in-market product run as a clear-%T dilution
series into ONE overlay and ONE ranked AUC bar graph (P&G blue vs competitor
red), so the whole benchmarking set is comparable on a single axis.

AUC = consumer rinse window (1:1-1:20), absorbance x decade, spline fit
(matches the Sample library / other decks).

Outputs (Reports/):
  competitor_all_pct.png   %T vs dilution overlay (all products)
  competitor_all_auc.png   ranked coacervation-strength bar (P&G vs competitor)
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np

from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import (
    dilution_ratio, fit_curve, transmittance_to_absorbance, compute_auc,
)

R = "Reports"
RAW = "raw_data"
TIMEPOINT = 3.0
TICKS = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500]
AUC_WINDOW = (1.0 / (1 + 20), 1.0 / (1 + 1))     # consumer window 1:1-1:20
SMOOTH = 0.25

PG = "P&G in-market"
COMP = "Competitor"
CAT_COLOR = {PG: "#2e75b6", COMP: "#c0392b"}

F1 = f"{RAW}/InMarket Run1 20260826.txt"
F2 = f"{RAW}/InMarket Run2 20260826.txt"
F3 = f"{RAW}/InMarket Run3 20260826.txt"
L7 = f"{RAW}/20260904_7_GH150DDU0_LAPB_1percent_NATIVE_DexK.txt"
CROWN = f"{RAW}/Crown_Solu (1).txt"
TSAL = f"{RAW}/TsalandActAcrePLantStemCell.txt"

# (label, file, trough, category, note)  note flags non-coacervation artifacts
SAMPLES = [
    ("Pantene Keratin Sulfate-Free", F2, 1, PG, ""),
    ("Pantene Complete Curl Care", F3, 1, PG, ""),
    ("Pantene Pro-V Sheer Volume", F1, 2, PG, ""),
    ("L'Oreal EverPure Volume", F2, 2, COMP, ""),
    ("L'Oreal EverPure Clarify", F3, 2, COMP, ""),
    ("L'Oreal Hyaluron Pure", F1, 1, COMP, ""),
    ("NATIVE Scalp Detox", L7, 1, COMP, ""),
    ("Crown Volumizing", CROWN, 1, COMP, ""),
    ("Solu Shampoo", CROWN, 2, COMP, ""),
    ("Act+Acre Plant Stem Cell", TSAL, 2, COMP, "opaque/pearlised — %T partly base opacity"),
    ("Neutrogena T/Sal", TSAL, 1, COMP, "salicylic-acid precipitation, not coacervation"),
]


def curve(path, trough, timepoint=TIMEPOINT):
    df = annotate_concentration(parse_kinetic_plate_file(path))
    sub = df[df["trough"] == trough].dropna(subset=["formula_fraction"])
    tp = min(sorted(sub["timepoint_minutes"].unique()), key=lambda t: abs(t - timepoint))
    cur = sub[sub["timepoint_minutes"] == tp].sort_values("formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(cur["formula_fraction"].to_numpy(float)), float)
    y = cur["transmission_pct"].to_numpy(float)
    o = np.argsort(x)
    return x[o], y[o]


def auc_of(x, y):
    conc = 1.0 / (1.0 + x)
    return compute_auc(conc, transmittance_to_absorbance(y),
                       window=AUC_WINDOW, use_fit=True)["auc"]


def fit(x, y):
    lx = np.log10(np.clip(x, 1e-9, None))
    lxd = np.linspace(lx.min(), lx.max(), 400)
    f = fit_curve(lx, y, kind="lowess", smoothing=SMOOTH)
    return 10 ** lxd, np.clip(np.asarray(f(lxd)), y.min(), y.max())


def dil_axis(ax, xmin, xmax):
    ax.set_xscale("log")
    tk = [t for t in TICKS if xmin * 0.9 <= t <= xmax * 1.15]
    ax.set_xticks(tk); ax.set_xticklabels([f"1:{t}" for t in tk], rotation=45, ha="right")
    ax.set_xlim(max(xmin * 0.9, 0.9), xmax * 1.15)


def main():
    rows = []
    # ---- %T overlay ----
    fig, ax = plt.subplots(figsize=(11, 6.4))
    xmins, xmaxs = [], []
    palette = plt.cm.tab20(np.linspace(0, 1, len(SAMPLES)))
    for (label, path, tr, cat, note), col in zip(SAMPLES, palette):
        x, y = curve(path, tr)
        xmins.append(x.min()); xmaxs.append(x.max())
        fx, fy = fit(x, y)
        a = auc_of(x, y)
        rows.append((label, cat, a, note))
        ls = "-" if cat == PG else "--"
        ax.plot(fx, fy, ls, color=col, lw=2.4, label=f"{label} (AUC {a:.3f})")
        ax.plot(x, y, "o", color=col, ms=2.6, alpha=0.3)
    dil_axis(ax, min(xmins), max(xmaxs))
    ax.set_ylim(0, 100); ax.set_ylabel("% Transmittance")
    ax.set_xlabel("Dilution (1:X)  \u2014  most \u2192 least concentrated")
    ax.set_title("Competitor & in-market shampoos \u2014 clear %T vs dilution (t=3 min)\n"
                 "solid = P&G in-market, dashed = competitor",
                 fontsize=12, fontweight="bold")
    ax.grid(True, which="both", ls=":", alpha=0.5)
    ax.legend(fontsize=8, ncol=2, loc="lower right")
    fig.tight_layout()
    fig.savefig(f"{R}/competitor_all_pct.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/competitor_all_pct.png")

    # ---- ranked AUC bar (P&G vs competitor) ----
    rows.sort(key=lambda z: z[2])
    fig, ax = plt.subplots(figsize=(11, 7))
    ypos = np.arange(len(rows))
    for i, (label, cat, a, note) in enumerate(rows):
        ax.barh(i, a, color=CAT_COLOR[cat], edgecolor="white",
                hatch="//" if note else None)
        ax.text(a + 0.006, i, f"{a:.3f}" + ("  \u26a0" if note else ""),
                va="center", fontsize=9)
    ax.set_yticks(ypos); ax.set_yticklabels([r[0] for r in rows], fontsize=9)
    ax.set_xlabel("Coacervation AUC  (absorbance \u00d7 decade, consumer window 1:1-1:20)")
    ax.set_title("Coacervation strength (AUC) \u2014 competitor & in-market benchmark\n"
                 "P&G in-market (blue) vs competitor (red);  \u26a0 hatched = opacity/precipitation artifact",
                 fontsize=12, fontweight="bold")
    ax.legend(handles=[Patch(facecolor=CAT_COLOR[PG], label=PG),
                       Patch(facecolor=CAT_COLOR[COMP], label=COMP)],
              fontsize=10, loc="lower right")
    ax.grid(True, axis="x", ls=":", alpha=0.5)
    ax.set_xlim(0, max(a for _, _, a, _ in rows) * 1.18)
    notes = [f"\u26a0 {label}: {note}" for label, _c, _a, note in rows if note]
    if notes:
        fig.text(0.5, 0.005, "   ".join(notes), ha="center", fontsize=8.5,
                 color="#7a1f1f")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(f"{R}/competitor_all_auc.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/competitor_all_auc.png\n")

    print(f"{'product':32s} {'category':14s} {'AUC':>6s}  note")
    for label, cat, a, note in sorted(rows, key=lambda z: -z[2]):
        print(f"{label:32s} {cat:14s} {a:6.3f}  {note}")


if __name__ == "__main__":
    main()
