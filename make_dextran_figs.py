"""Figures for the 2026-09-03 biodegradable dextran screen (Dow collaboration).

APG chassis, 1% polymer. 2 samples/plate (trough 1 = A-D, trough 2 = E-H):
  CD2_DexB    T1 CD2 (Dexcare CD-2)      T2 Dex-B
  DexBstar_DexJ  T1 Dex-B*               T2 Dex-J
  DexJstar_DexA  T1 Dex-J*               T2 Dex-A
  NoSalt_PTLWater T1 No-salt control     T2 PTL water (blank)

Outputs (Mark-Brown dextran style):
  Reports/dextran_1pct_pct.png         %T-vs-dilution overlay
  Reports/dextran_1pct_abs.png         Absorbance-vs-dilution overlay (consumer AUC band)
  Reports/dextran_1pct_auc.png         AUC ranking bar
  Reports/dextran_1pct_timecourse.png  Time-course small-multiples grid
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator, NullFormatter
import numpy as np
import pandas as pd

from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import (
    dilution_ratio, fit_curve, transmittance_to_absorbance, compute_auc,
)
from coacervation_plotting import plot_small_multiples

RAW = "raw_data"
TIMEPOINT = 3.0
CHASSIS = "GH150 DDU0 + 3.6% APG"
TICKS = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500]
AUC_WINDOW = (1.0 / (1 + 20), 1.0 / (1 + 1))  # consumer window 1:1-1:20
SMOOTH = 0.25  # lowess fraction: smooth (not jagged) yet resolves APG bimodal 2nd trough

F_CD2B = "20260903_APG_CD2_DexB_RawData.txt"
F_BJ = "20260903_DexBstar_DexJ_RawData.txt"
F_JA = "20260903_DexJstar_DexA_RawData.txt"
F_CTRL = "20260903_NoSalt_PTLWater_RawData.txt"
F_DEXK = "20260903_APGDexK_LAPBDexK_RawData.txt"

# (label, file, trough, color, is_control)
SAMPLES = [
    ("CD2 (Dexcare CD-2)", F_CD2B, 1, "#c0392b", False),
    ("Dex-K",              F_DEXK, 1, "#8e44ad", False),
    ("Dex-A",              F_JA,   2, "#1f4e79", False),
    ("Dex-J",              F_BJ,   2, "#2e9e5b", False),
    ("Dex-J*",             F_JA,   1, "#17a2b8", False),
    ("Dex-B",              F_CD2B, 2, "#e67e22", False),
    ("Dex-B*",             F_BJ,   1, "#7a5c00", False),
    ("No-salt control",    F_CTRL, 1, "#8a8f98", True),
    ("PTL water (blank)",  F_CTRL, 2, "#c8ccd1", True),
]

# 1% Dex-K in two chassis (same plate: T1 APG, T2 LAPB)
DEXK_CHASSIS = [
    ("Dex-K in GH150 DDU0 + 3.6% APG",  F_DEXK, 1, "#8e44ad"),
    ("Dex-K in GH150 DDU0 + 3.6% LAPB", F_DEXK, 2, "#c0392b"),
]

# 0.4% polymer dataset (Dow share folder) - same GH150 DDu0 + 3.6% APG chassis.
CONC_CSV = r"C:\VScode_Projects\Dextran_Project_Share\data\all_time_formula_fraction_curves.csv"

# 1% (file, trough) vs 0.4% (csv polymer name), APG chassis - matched polymers.
# (display, file, trough, csv_polymer, color)
COMPARE = [
    ("CD2",    F_CD2B, 1, "0.4% CD2",    "#c0392b"),
    ("Dex-K",  F_DEXK, 1, "0.4% Dex K",  "#8e44ad"),
    ("Dex-A",  F_JA,   2, "0.4% Dex A",  "#1f4e79"),
    ("Dex-J",  F_BJ,   2, "0.4% Dex J",  "#2e9e5b"),
    ("Dex-B",  F_CD2B, 2, "0.4% Dex B",  "#e67e22"),
    ("Dex-J*", F_JA,   1, "0.4% Dex J*", "#17a2b8"),
    ("Dex-B*", F_BJ,   1, "0.4% Dex B*", "#7a5c00"),
]


def _sub(path, trough):
    df = annotate_concentration(parse_kinetic_plate_file(path))
    return df[df["trough"] == trough].dropna(subset=["formula_fraction"])


def clean_curve(x, y, k=4.5, floor=6.0, win=5):
    """Remove ONLY isolated bubble/particulate artifacts from a dilution curve.

    Conservative on purpose: compares each point to a local rolling median and
    drops a point only if its residual exceeds max(k*robust-sigma, floor %T).
    A real coacervation trough - including the APG SECOND trough at high dilution
    - spans several contiguous wells, so the rolling median follows it and it is
    KEPT; only single-well spikes (bubbles) are removed. Returns (x, y, n_removed).
    """
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    n = len(y)
    if n < 7:
        return x, y, 0
    half = win // 2
    med = np.empty(n)
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        med[i] = np.median(y[lo:hi])
    resid = y - med
    mad = np.median(np.abs(resid - np.median(resid)))
    sigma = 1.4826 * mad if mad > 0 else 1e-9
    thr = max(k * sigma, floor)
    keep = np.abs(resid) <= thr
    return x[keep], y[keep], int((~keep).sum())


def curve(path, trough, timepoint=TIMEPOINT):
    sub = _sub(path, trough)
    tp = min(sorted(sub["timepoint_minutes"].unique()), key=lambda t: abs(t - timepoint))
    cur = sub[sub["timepoint_minutes"] == tp].sort_values("formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(cur["formula_fraction"].to_numpy()), dtype=float)
    y = cur["transmission_pct"].to_numpy()
    order = np.argsort(x)
    x, y = x[order], y[order]
    x, y, _ = clean_curve(x, y)
    return x, y


_CONC_DF = None


def _load_conc_df():
    global _CONC_DF
    if _CONC_DF is None:
        _CONC_DF = pd.read_csv(CONC_CSV)
    return _CONC_DF


def curve_04(csv_polymer, timepoint=TIMEPOINT):
    """0.4% %T-vs-dilution curve for a polymer in the APG chassis (cleaned)."""
    d = _load_conc_df()
    sub = d[(d["Chassis"].str.contains("APG")) & (d["Polymer"] == csv_polymer)]
    tps = sorted(sub["Time_min"].unique())
    tp = min(tps, key=lambda t: abs(t - timepoint))
    cur = sub[sub["Time_min"] == tp].sort_values("Formula_fraction", ascending=False)
    x = cur["Diluent_ratio"].to_numpy(float)
    y = cur["%T"].to_numpy(float)
    order = np.argsort(x)
    x, y, _ = clean_curve(x[order], y[order])
    return x, y


def _fit_line(x, y):
    lx = np.log10(np.clip(x, 1e-9, None))
    lxd = np.linspace(lx.min(), lx.max(), 400)
    fit = fit_curve(lx, y, kind="lowess", smoothing=SMOOTH)
    yd = np.clip(np.asarray(fit(lxd)), y.min(), y.max())
    return 10 ** lxd, yd


def _auc_pct(x, ypct):
    conc = 1.0 / (1.0 + x)
    return compute_auc(conc, transmittance_to_absorbance(ypct),
                       window=AUC_WINDOW, use_fit=True)["auc"]


def series(path, trough):
    sub = _sub(path, trough)
    out = []
    for tp in sorted(sub["timepoint_minutes"].unique()):
        cur = sub[sub["timepoint_minutes"] == tp].sort_values("formula_fraction", ascending=False)
        x = np.asarray(dilution_ratio(cur["formula_fraction"].to_numpy()), float)
        y = cur["transmission_pct"].to_numpy()
        order = np.argsort(x)
        xc, yc, _ = clean_curve(x[order], y[order])
        # back to concentration for plot_small_multiples
        conc = 1.0 / (1.0 + xc)
        out.append({"time": float(tp), "concentration": conc, "pct_transmittance": yc})
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
    fig, ax = plt.subplots(figsize=(7.8, 5.0))
    xmins, xmaxs = [], []
    for label, fn, tr, col, ctrl in SAMPLES:
        x, y = curve(f"{RAW}/{fn}", tr)
        if mode == "abs":
            y = transmittance_to_absorbance(y)
        xmins.append(x.min()); xmaxs.append(x.max())
        lx = np.log10(np.clip(x, 1e-9, None))
        lxd = np.linspace(lx.min(), lx.max(), 400)
        fit = fit_curve(lx, y, kind="lowess", smoothing=SMOOTH)
        yd = np.clip(np.asarray(fit(lxd)), y.min(), y.max())
        ls = ":" if ctrl else "-"
        lw = 1.8 if ctrl else 2.5
        ax.plot(10 ** lxd, yd, ls, color=col, lw=lw, label=label, zorder=3)
        ax.plot(x, y, "o", color=col, ms=3, alpha=0.4, zorder=2)
    dilution_axis(ax, min(xmins), max(xmaxs))
    ax.set_xlabel("Dilution (1:X)  —  most → least concentrated")
    if mode == "abs":
        lo, hi = dilution_ratio(max(AUC_WINDOW)), dilution_ratio(min(AUC_WINDOW))
        ax.axvspan(lo, hi, color="#f2d7a0", alpha=0.45, zorder=1, label="Consumer window (1:1–1:20)")
        ax.set_ylabel("Absorbance  (A = 2 − log10 %T)")
        ax.set_ylim(0, 0.6)
        ax.legend(fontsize=8, loc="upper right")
        title = f"Absorbance vs. dilution — {CHASSIS} + polymer (1%)"
    else:
        ax.set_ylabel("% Transmittance")
        ax.set_ylim(0, 100)
        ax.legend(fontsize=8, loc="lower right")
        title = f"%T vs. dilution — {CHASSIS} + polymer (1%)"
    ax.set_title(title, fontsize=11.5, fontweight="bold")
    ax.grid(True, which="major", ls=":", alpha=0.55)
    fig.tight_layout()
    fig.savefig(f"Reports/{png}", dpi=160)
    plt.close(fig)
    print("wrote Reports/" + png)


def plot_auc_bars(png):
    rows = []
    for label, fn, tr, col, ctrl in SAMPLES:
        x, ypct = curve(f"{RAW}/{fn}", tr)
        conc = 1.0 / (1.0 + x)
        absb = transmittance_to_absorbance(ypct)
        auc = compute_auc(conc, absb, window=AUC_WINDOW, use_fit=True)  # spline (matches library)
        rows.append((label, col, auc["auc"]))
    rows.sort(key=lambda r: r[2])
    fig, ax = plt.subplots(figsize=(9.0, 0.55 * len(rows) + 1.8))
    y = np.arange(len(rows))
    ax.barh(y, [r[2] for r in rows], color=[r[1] for r in rows],
            edgecolor="#33404d", linewidth=0.7)
    ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rows], fontsize=10)
    mx = max(r[2] for r in rows) or 1
    for i, r in enumerate(rows):
        ax.text(r[2] + mx * 0.01, i, f"{r[2]:.3f}", va="center", fontsize=9)
    ax.set_xlabel("Coacervation AUC  (absorbance × decade, consumer window 1:1–1:20)")
    ax.set_title(f"Coacervation strength (AUC) — {CHASSIS} + polymer (1%)",
                 fontsize=12, fontweight="bold")
    ax.grid(True, axis="x", ls=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(f"Reports/{png}", dpi=160)
    plt.close(fig)
    print("wrote Reports/" + png)


def plot_timecourse(png):
    panels = [{"label": label, "series": series(f"{RAW}/{fn}", tr)}
              for label, fn, tr, col, ctrl in SAMPLES]
    plot_small_multiples(panels, view="pct", auc_window=AUC_WINDOW, ncols=4,
                         frac=SMOOTH,
                         title=f"{CHASSIS} + polymer (1%) — %T time-course grid",
                         out_path=f"Reports/{png}")
    print("wrote Reports/" + png)


def plot_chassis_compare(png):
    """1% Dex-K: APG vs LAPB chassis (%T + absorbance with consumer AUC window)."""
    fig, (axp, axa) = plt.subplots(1, 2, figsize=(13, 5.2))
    xmins, xmaxs = [], []
    for label, fn, tr, col in DEXK_CHASSIS:
        x, y = curve(f"{RAW}/{fn}", tr)  # cleaned
        xmins.append(x.min()); xmaxs.append(x.max())
        lx = np.log10(np.clip(x, 1e-9, None))
        lxd = np.linspace(lx.min(), lx.max(), 400)
        fitp = fit_curve(lx, y, kind="lowess", smoothing=SMOOTH)
        yp = np.clip(np.asarray(fitp(lxd)), y.min(), y.max())
        axp.plot(10 ** lxd, yp, "-", color=col, lw=2.5, label=label)
        axp.plot(x, y, "o", color=col, ms=3, alpha=0.4)
        ya = transmittance_to_absorbance(y)
        fita = fit_curve(lx, ya, kind="lowess", smoothing=SMOOTH)
        yad = np.clip(np.asarray(fita(lxd)), ya.min(), ya.max())
        conc = 1.0 / (1.0 + x)
        auc = compute_auc(conc, transmittance_to_absorbance(y), window=AUC_WINDOW, use_fit=True)
        axa.plot(10 ** lxd, yad, "-", color=col, lw=2.5,
                 label=f"{label}  (AUC={auc['auc']:.3f})")
        axa.plot(x, ya, "o", color=col, ms=3, alpha=0.4)
    for ax in (axp, axa):
        dilution_axis(ax, min(xmins), max(xmaxs))
        ax.grid(True, ls=":", alpha=0.55)
        ax.set_xlabel("Dilution (1:X)  —  most → least concentrated")
    axp.set_ylabel("% Transmittance"); axp.set_ylim(0, 100)
    axp.legend(fontsize=8.5, loc="lower right"); axp.set_title("%T vs. dilution", fontsize=11)
    lo, hi = dilution_ratio(max(AUC_WINDOW)), dilution_ratio(min(AUC_WINDOW))
    axa.axvspan(lo, hi, color="#f2d7a0", alpha=0.45, label="Consumer window (1:1–1:20)")
    axa.set_ylabel("Absorbance  (A = 2 − log10 %T)"); axa.set_ylim(0, 0.9)
    axa.legend(fontsize=8.5, loc="upper right"); axa.set_title("Absorbance + consumer AUC window", fontsize=11)
    fig.suptitle("1% Dex-K — chassis effect: APG vs LAPB (GH150 DDU0)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(f"Reports/{png}", dpi=160)
    plt.close(fig)
    print("wrote Reports/" + png)


def plot_conc_compare(png):
    """1% vs 0.4% polymer overlay (GH150 DDu0 + 3.6% APG), one panel per polymer.

    Solid = 1% (this study's raw plates), dashed = 0.4% (Dow share dataset).
    Both fitted with the same smooth lowess (SMOOTH). Bottom-right panel = AUC bars.
    """
    ncols = 4
    nrows = 2
    fig, axes = plt.subplots(nrows, ncols, figsize=(15.5, 7.6))
    axes = axes.ravel()
    xmins, xmaxs = [], []
    auc_rows = []  # (display, auc1, auc04, color)
    for i, (disp, fn, tr, csvname, col) in enumerate(COMPARE):
        ax = axes[i]
        x1, y1 = curve(f"{RAW}/{fn}", tr)            # 1%
        x0, y0 = curve_04(csvname)                   # 0.4%
        xmins += [x1.min(), x0.min()]; xmaxs += [x1.max(), x0.max()]
        fx1, fy1 = _fit_line(x1, y1)
        fx0, fy0 = _fit_line(x0, y0)
        a1, a0 = _auc_pct(x1, y1), _auc_pct(x0, y0)
        auc_rows.append((disp, a1, a0, col))
        ax.plot(fx1, fy1, "-", color=col, lw=2.5, label=f"1%  (AUC {a1:.3f})")
        ax.plot(x1, y1, "o", color=col, ms=2.5, alpha=0.35)
        ax.plot(fx0, fy0, "--", color=col, lw=2.2, label=f"0.4%  (AUC {a0:.3f})")
        ax.plot(x0, y0, "s", color=col, ms=2.5, alpha=0.30)
        dilution_axis(ax, min(xmins), max(xmaxs))
        ax.set_ylim(0, 100)
        ax.set_title(disp, fontsize=11, fontweight="bold")
        ax.grid(True, ls=":", alpha=0.5)
        ax.legend(fontsize=7.5, loc="lower right")
        if i % ncols == 0:
            ax.set_ylabel("% Transmittance")

    # summary AUC bars in the last cell
    axb = axes[len(COMPARE)]
    labels = [r[0] for r in auc_rows]
    xpos = np.arange(len(labels))
    w = 0.38
    axb.bar(xpos - w / 2, [r[1] for r in auc_rows], w, color=[r[3] for r in auc_rows],
            edgecolor="#33404d", linewidth=0.6, label="1%")
    axb.bar(xpos + w / 2, [r[2] for r in auc_rows], w, color=[r[3] for r in auc_rows],
            alpha=0.5, hatch="//", edgecolor="#33404d", linewidth=0.6, label="0.4%")
    axb.set_xticks(xpos); axb.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    axb.set_ylabel("AUC (1:1–1:20)")
    axb.set_title("Consumer-window AUC: 1% (solid) vs 0.4% (hatched)",
                  fontsize=9.5, fontweight="bold")
    axb.grid(True, axis="y", ls=":", alpha=0.5)
    axb.legend(fontsize=8, loc="upper right")

    fig.suptitle(f"1% vs 0.4% polymer — {CHASSIS}  (solid = 1%, dashed = 0.4%, {TIMEPOINT:.0f} min)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(f"Reports/{png}", dpi=160)
    plt.close(fig)
    print("wrote Reports/" + png)
    print("  AUC 1% vs 0.4% (consumer window):")
    for disp, a1, a0, _ in auc_rows:
        ratio = (a1 / a0) if a0 > 1e-6 else float("nan")
        print(f"    {disp:6s}  1%={a1:.3f}  0.4%={a0:.3f}  ratio={ratio:.2f}")


if __name__ == "__main__":
    # cleaning report (t=3 curve per sample)
    print("Artifact cleaning (points removed @ t=3):")
    for label, fn, tr, col, ctrl in SAMPLES:
        sub = _sub(f"{RAW}/{fn}", tr)
        tp = min(sorted(sub["timepoint_minutes"].unique()), key=lambda t: abs(t - TIMEPOINT))
        cc = sub[sub["timepoint_minutes"] == tp].sort_values("formula_fraction", ascending=False)
        xx = np.asarray(dilution_ratio(cc["formula_fraction"].to_numpy()), float)
        yy = cc["transmission_pct"].to_numpy()
        o = np.argsort(xx)
        _, _, nrem = clean_curve(xx[o], yy[o])
        print(f"  {label:20s} removed {nrem}")
    plot_overlay("dextran_1pct_pct.png", mode="pct")
    plot_overlay("dextran_1pct_abs.png", mode="abs")
    plot_auc_bars("dextran_1pct_auc.png")
    plot_timecourse("dextran_1pct_timecourse.png")
    plot_chassis_compare("dextran_dexk_chassis.png")
    plot_conc_compare("dextran_1pct_vs_04pct.png")
    print("done")
