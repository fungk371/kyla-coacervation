"""Figures for the in-market vs competitor coacervation benchmark set.

Six shampoos run as %T dilution series on the Hamilton (2026-08-26), 2 per plate:
  Run1  T1 L'Oreal Hyaluron Pure         T2 Pantene Pro-V Sheer Volume
  Run2  T1 Pantene Keratin Sulfate-Free  T2 L'Oreal EverPure Volume
  Run3  T1 Pantene Complete Curl Care    T2 L'Oreal EverPure Clarify

Produces, in the same style as the Mark-Brown dextran 24-shampoo set:
  * %T-vs-dilution overlay              -> Reports/inmarket_pct.png
  * Absorbance-vs-dilution overlay      -> Reports/inmarket_abs.png  (consumer AUC band)
  * AUC ranking bar (in-market vs comp) -> Reports/inmarket_auc.png
  * Time-course small-multiples grid    -> Reports/inmarket_timecourse.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator, NullFormatter
from matplotlib.patches import Patch
import numpy as np

from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import (
    dilution_ratio, fit_curve, transmittance_to_absorbance, compute_auc,
)
from coacervation_plotting import plot_small_multiples

RAW = "raw_data"
TIMEPOINT = 3.0
TICKS = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500]
# Consumer-relevant rinse window: 1:1 - 1:20 dilution.
AUC_WINDOW = (1.0 / (1 + 20), 1.0 / (1 + 1))

F1 = "InMarket Run1 20260826.txt"
F2 = "InMarket Run2 20260826.txt"
F3 = "InMarket Run3 20260826.txt"

# (label, file, trough, color, category)
IN_MARKET = "in_market"
COMPETITOR = "competitor"
CAT_COLOR = {IN_MARKET: "#2e75b6", COMPETITOR: "#c0392b"}
SAMPLES = [
    ("Pantene Keratin Sulfate-Free", F2, 1, "#1f4e79", IN_MARKET),
    ("Pantene Complete Curl Care",   F3, 1, "#2e75b6", IN_MARKET),
    ("Pantene Pro-V Sheer Volume",   F1, 2, "#7cb5ec", IN_MARKET),
    ("L'Oreal EverPure Volume",      F2, 2, "#c0392b", COMPETITOR),
    ("L'Oreal EverPure Clarify",     F3, 2, "#e67e22", COMPETITOR),
    ("L'Oreal Hyaluron Pure",        F1, 1, "#f0b27a", COMPETITOR),
]


def _sub(path, trough):
    df = annotate_concentration(parse_kinetic_plate_file(path))
    return df[df["trough"] == trough].dropna(subset=["formula_fraction"])


def curve(path, trough, timepoint=TIMEPOINT):
    sub = _sub(path, trough)
    tp = min(sorted(sub["timepoint_minutes"].unique()), key=lambda t: abs(t - timepoint))
    cur = sub[sub["timepoint_minutes"] == tp].sort_values("formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(cur["formula_fraction"].to_numpy()), dtype=float)
    y = cur["transmission_pct"].to_numpy()
    order = np.argsort(x)
    return x[order], y[order]


def series(path, trough):
    sub = _sub(path, trough)
    out = []
    for tp in sorted(sub["timepoint_minutes"].unique()):
        cur = sub[sub["timepoint_minutes"] == tp].sort_values("formula_fraction", ascending=False)
        out.append({"time": float(tp),
                    "concentration": cur["formula_fraction"].to_numpy(),
                    "pct_transmittance": cur["transmission_pct"].to_numpy()})
    return out


def dilution_axis(ax, xmin, xmax):
    ax.set_xscale("log")
    tk = [t for t in TICKS if xmin * 0.9 <= t <= xmax * 1.15]
    ax.set_xticks(tk)
    ax.set_xticklabels([f"1:{t}" for t in tk], rotation=45, ha="right")
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlim(max(xmin * 0.9, 0.9), xmax * 1.15)


def plot_overlay(png, *, mode="pct"):
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    xmins, xmaxs = [], []
    for label, fn, tr, col, cat in SAMPLES:
        x, y = curve(f"{RAW}/{fn}", tr)
        if mode == "abs":
            y = transmittance_to_absorbance(y)
        xmins.append(x.min()); xmaxs.append(x.max())
        lx = np.log10(np.clip(x, 1e-9, None))
        lxd = np.linspace(lx.min(), lx.max(), 400)
        fit = fit_curve(lx, y, kind="lowess", smoothing=0.25)
        yd = np.clip(np.asarray(fit(lxd)), y.min(), y.max())
        ls = "-" if cat == IN_MARKET else "--"
        ax.plot(10 ** lxd, yd, ls, color=col, lw=2.4, label=label, zorder=3)
        ax.plot(x, y, "o", color=col, ms=3, alpha=0.4, zorder=2)
    dilution_axis(ax, min(xmins), max(xmaxs))
    ax.set_xlabel("Dilution (1:X)  —  most → least concentrated")
    if mode == "abs":
        lo, hi = dilution_ratio(max(AUC_WINDOW)), dilution_ratio(min(AUC_WINDOW))
        ax.axvspan(lo, hi, color="#f2d7a0", alpha=0.45, zorder=1,
                   label="Consumer window (1:1–1:20)")
        ax.set_ylabel("Absorbance  (A = 2 − log10 %T)")
        ax.set_ylim(0, 0.9)
        ax.legend(fontsize=8, loc="upper right")
        title = "Absorbance vs. dilution — in-market vs competitor shampoos"
    else:
        ax.set_ylabel("% Transmittance")
        ax.set_ylim(0, 100)
        ax.legend(fontsize=8, loc="lower right")
        title = "%T vs. dilution — in-market vs competitor shampoos"
    ax.set_title(title, fontsize=11.5, fontweight="bold")
    ax.grid(True, which="major", ls=":", alpha=0.55)
    fig.tight_layout()
    fig.savefig(f"Reports/{png}", dpi=160)
    plt.close(fig)
    print("wrote Reports/" + png)


def plot_auc_bars(png):
    rows = []  # (label, color, cat, auc)
    for label, fn, tr, col, cat in SAMPLES:
        x, ypct = curve(f"{RAW}/{fn}", tr)
        conc = 1.0 / (1.0 + x)
        absb = transmittance_to_absorbance(ypct)
        # Same call as the Library builder (default spline fit) so the bar
        # values match the AUC stored in the database.
        auc = compute_auc(conc, absb, window=AUC_WINDOW, use_fit=True)
        rows.append((label, CAT_COLOR[cat], cat, auc["auc"]))
    rows.sort(key=lambda r: r[3])
    labels = [r[0] for r in rows]
    colors = [r[1] for r in rows]
    vals = [r[3] for r in rows]
    fig, ax = plt.subplots(figsize=(9.4, 0.62 * len(rows) + 1.8))
    y = np.arange(len(rows))
    ax.barh(y, vals, color=colors, edgecolor="#33404d", linewidth=0.7)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=10)
    for i, v in enumerate(vals):
        ax.text(v + max(vals) * 0.01, i, f"{v:.3f}", va="center", fontsize=9)
    ax.set_xlabel("Coacervation AUC  (absorbance × decade, consumer window 1:1–1:20)")
    ax.set_title("Coacervation strength (AUC) — in-market vs competitor",
                 fontsize=12.5, fontweight="bold")
    ax.grid(True, axis="x", ls=":", alpha=0.5)
    ax.legend(handles=[Patch(facecolor=CAT_COLOR[IN_MARKET], label="P&G in-market (Pantene)"),
                       Patch(facecolor=CAT_COLOR[COMPETITOR], label="Competitor (L'Oreal)")],
              fontsize=9, loc="lower right")
    fig.tight_layout()
    fig.savefig(f"Reports/{png}", dpi=160)
    plt.close(fig)
    print("wrote Reports/" + png)


def plot_timecourse(png):
    panels = [{"label": label, "series": series(f"{RAW}/{fn}", tr)}
              for label, fn, tr, col, cat in SAMPLES]
    plot_small_multiples(panels, view="pct", auc_window=AUC_WINDOW, ncols=3,
                         title="In-market vs competitor shampoos — %T time-course grid",
                         out_path=f"Reports/{png}")
    print("wrote Reports/" + png)


if __name__ == "__main__":
    plot_overlay("inmarket_pct.png", mode="pct")
    plot_overlay("inmarket_abs.png", mode="abs")
    plot_auc_bars("inmarket_auc.png")
    plot_timecourse("inmarket_timecourse.png")
    print("done")
