"""Generate figures for the Tea Saponin coacervation case-study deck.

Produces, for the 3 comparison groups (silicone shift, R2510 dose, N22510S dose):
  * %T-vs-dilution overlays         -> tea_shift.png / tea_R2510.png / tea_N22510S.png
  * Absorbance-vs-dilution overlays -> tea_shift_abs.png / tea_R2510_abs.png / tea_N22510S_abs.png
  * AUC ranking bar chart (all samples, grouped/colored) -> tea_auc.png
  * A Mark-Brown 24-shampoo-style time-course panel grid  -> tea_timecourse.png
    (one panel per sample, 0-15 min curves colored by time, on the 1:X axis).

Uses the improved (noise-based, bimodal-capable) smoothing-spline fit and a
1:X dilution axis (1:1, 1:2, 1:10, 1:100 ...).
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import NullLocator, NullFormatter
import numpy as np

from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import (
    dilution_ratio,
    fit_curve,
    transmittance_to_absorbance,
    compute_auc,
)
from coacervation_plotting import plot_small_multiples

RAW = "raw_data"
TIMEPOINT = 5.0
TICKS = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500]

# ---------------------------------------------------------------- file mapping
# The renamed raw plate files (2 samples / plate, trough 1 = A-D, trough 2 = E-H)
F_SHIFT = "5.8..5.8..2.4 – 2% CAPB_5.8..5.8..2.4 – 0.5% DM5500 with 2.4% CAPB.txt"
F_TEASAP = ("5.8..5.8..1.4 – 0.5% DM5500, 1.0% Tea Sap with 1.4% CAPB--"
            "GH150 16% R2510 + 0% Tea Saponin.txt")
F_R2510_LO = "GH150 16% R2510 + 0.25% Tea Saponin_GH150 16% R2510 + 0.5% Tea Saponin.txt"
F_R2510_HI = "GH150 16% R2510 + 1.0% Tea Saponin--GH150 16% N22510S + 0% Tea Saponin.txt"
F_N22510S = "GH150 16% N22510S + 0.25% Tea Saponin--GH150 16% N22510S + 0.5% Tea Saponin.txt"

# Each group: list of (label, file, trough, color)
GROUP_SHIFT = [
    ("Control (2% CAPB, no silicone)", F_SHIFT, 1, "#8a8f98"),
    ("+0.5% DM5500 (2.4% CAPB)",       F_SHIFT, 2, "#c0392b"),
    ("+0.5% DM5500 +1.0% Tea Saponin", F_TEASAP, 1, "#2e9e5b"),
]
GROUP_R2510 = [
    ("0% Tea Saponin",    F_TEASAP,   2, "#8a8f98"),
    ("0.25% Tea Saponin", F_R2510_LO, 1, "#7cb5ec"),
    ("0.5% Tea Saponin",  F_R2510_LO, 2, "#2e75b6"),
    ("1.0% Tea Saponin",  F_R2510_HI, 1, "#c0392b"),
]
GROUP_N22510S = [
    ("0% Tea Saponin",    F_R2510_HI, 2, "#8a8f98"),
    ("0.25% Tea Saponin", F_N22510S,  1, "#7cb5ec"),
    ("0.5% Tea Saponin",  F_N22510S,  2, "#2e75b6"),
]

# AUC window (formula fraction). 1:2 .. 1:20 spans the coacervate 2-phase region.
AUC_WINDOW = (1.0 / (1 + 2), 1.0 / (1 + 20))


# ---------------------------------------------------------------- data helpers
def _sub(path, trough):
    df = annotate_concentration(parse_kinetic_plate_file(path))
    return df[df["trough"] == trough].dropna(subset=["formula_fraction"])


def curve(path, trough, timepoint=TIMEPOINT):
    """Single-timepoint dilution curve (x sorted ascending), returns (x, %T)."""
    sub = _sub(path, trough)
    avail = sorted(sub["timepoint_minutes"].unique())
    tp = min(avail, key=lambda t: abs(t - timepoint))
    cur = sub[sub["timepoint_minutes"] == tp].sort_values("formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(cur["formula_fraction"].to_numpy()), dtype=float)
    y = cur["transmission_pct"].to_numpy()
    order = np.argsort(x)
    return x[order], y[order]


def series(path, trough):
    """All timepoints for a sample -> list of dicts for plot_small_multiples."""
    sub = _sub(path, trough)
    out = []
    for tp in sorted(sub["timepoint_minutes"].unique()):
        cur = sub[sub["timepoint_minutes"] == tp].sort_values("formula_fraction", ascending=False)
        out.append({
            "time": float(tp),
            "concentration": cur["formula_fraction"].to_numpy(),
            "pct_transmittance": cur["transmission_pct"].to_numpy(),
        })
    return out


# ---------------------------------------------------------------- axis helper
def dilution_axis(ax, xmin, xmax):
    ax.set_xscale("log")
    tk = [t for t in TICKS if xmin * 0.9 <= t <= xmax * 1.15]
    ax.set_xticks(tk)
    ax.set_xticklabels([f"1:{t}" for t in tk], rotation=45, ha="right")
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlim(max(xmin * 0.9, 0.9), xmax * 1.15)


# ---------------------------------------------------------------- overlays
def plot_overlay(items, title, png, *, mode="pct"):
    """Overlay a dose group. mode='pct' (%T) or 'abs' (Absorbance)."""
    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    xmins, xmaxs = [], []
    for label, fn, tr, col in items:
        try:
            x, y = curve(f"{RAW}/{fn}", tr)
        except Exception as e:  # noqa: BLE001
            print("skip", label, e); continue
        if mode == "abs":
            y = transmittance_to_absorbance(y)
        xmins.append(x.min()); xmaxs.append(x.max())
        lx = np.log10(np.clip(x, 1e-9, None))
        lxd = np.linspace(lx.min(), lx.max(), 400)
        fit = fit_curve(lx, y, kind="lowess", smoothing=0.25)
        yd = np.clip(np.asarray(fit(lxd)), y.min(), y.max())
        ax.plot(10 ** lxd, yd, "-", color=col, lw=2.4, label=label, zorder=3)
        ax.plot(x, y, "o", color=col, ms=3, alpha=0.45, zorder=2)
    dilution_axis(ax, min(xmins), max(xmaxs))
    ax.set_xlabel("Dilution (1:X)  —  most -> least concentrated")
    if mode == "abs":
        ax.set_ylabel("Absorbance  (A = 2 - log10 %T)")
        ax.set_ylim(0, 0.6)
        ax.legend(fontsize=8.5, loc="upper right")
    else:
        ax.set_ylabel("% Transmittance")
        ax.set_ylim(0, 100)
        ax.legend(fontsize=8.5, loc="lower right")
    ax.set_title(title, fontsize=11)
    ax.grid(True, which="major", ls=":", alpha=0.55)
    fig.tight_layout()
    fig.savefig(f"Reports/{png}", dpi=160)
    plt.close(fig)
    print("wrote Reports/" + png)


# ---------------------------------------------------------------- AUC bar chart
def plot_auc_bars(groups, png):
    """Ranked AUC (absorbance) bar chart across all samples, colored by group."""
    rows = []  # (group, label, color, auc)
    for gname, items in groups:
        for label, fn, tr, col in items:
            try:
                x, ypct = curve(f"{RAW}/{fn}", tr)
            except Exception as e:  # noqa: BLE001
                print("skip AUC", label, e); continue
            conc = 1.0 / (1.0 + x)  # dilution -> formula fraction
            absb = transmittance_to_absorbance(ypct)
            auc = compute_auc(conc, absb, window=AUC_WINDOW, use_fit=True, kind="lowess")
            rows.append((gname, f"{gname}: {label}", col, auc["auc"]))
    rows.sort(key=lambda r: r[3])
    labels = [r[1] for r in rows]
    vals = [r[3] for r in rows]
    colors = [r[2] for r in rows]
    fig, ax = plt.subplots(figsize=(9.2, max(3.2, 0.42 * len(rows) + 1.4)))
    y = np.arange(len(rows))
    ax.barh(y, vals, color=colors, edgecolor="#33404d", linewidth=0.6)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9)
    for i, v in enumerate(vals):
        ax.text(v + max(vals) * 0.01, i, f"{v:.3f}", va="center", fontsize=8.5)
    ax.set_xlabel("Coacervation AUC  (absorbance x decade, window 1:2 - 1:20)")
    ax.set_title("Coacervation strength (AUC) — Tea Saponin set", fontsize=12, fontweight="bold")
    ax.grid(True, axis="x", ls=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(f"Reports/{png}", dpi=160)
    plt.close(fig)
    print("wrote Reports/" + png)


# ---------------------------------------------------------------- AUC over time
def _auc_series(path, trough):
    """AUC (absorbance window) at every available timepoint -> (times, aucs)."""
    sub = _sub(path, trough)
    times, aucs = [], []
    for tp in sorted(sub["timepoint_minutes"].unique()):
        cur = sub[sub["timepoint_minutes"] == tp].sort_values("formula_fraction", ascending=False)
        conc = cur["formula_fraction"].to_numpy()
        absb = transmittance_to_absorbance(cur["transmission_pct"].to_numpy())
        auc = compute_auc(conc, absb, window=AUC_WINDOW, use_fit=True, kind="lowess")
        times.append(float(tp)); aucs.append(auc["auc"])
    return np.asarray(times), np.asarray(aucs)


def write_auc_values(groups, csv_name="tea_auc_values.csv", tps=(1, 3, 5, 10, 15)):
    """Write a numeric AUC table (per sample x timepoint) + return rows."""
    import csv
    rows = []
    for gname, items in groups:
        for label, fn, tr, col in items:
            t, a = _auc_series(f"{RAW}/{fn}", tr)
            vals = [float(np.interp(tp, t, a)) for tp in tps]
            slope = float(np.polyfit(t, a, 1)[0]) * 10.0  # AUC change per 10 min
            rows.append({"group": gname, "sample": label, **{f"AUC_t{tp}": round(v, 4) for tp, v in zip(tps, vals)},
                         "AUC_peak": round(float(a.max()), 4), "trend_per10min": round(slope, 4),
                         "kinetics": "builds" if slope > 0.002 else ("decays" if slope < -0.002 else "stable")})
    with open(f"Reports/{csv_name}", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    print("wrote Reports/" + csv_name)
    return rows


def plot_auc_time(groups, png):
    """AUC vs time (0-15 min), one panel per comparison group — reveals the
    chassis-dependent kinetics (build vs decay) that a single timepoint hides."""
    n = len(groups)
    fig, axes = plt.subplots(1, n, figsize=(5.0 * n, 4.4), dpi=150, squeeze=False)
    axes = axes[0]
    for ax, (gname, items) in zip(axes, groups):
        for label, fn, tr, col in items:
            t, a = _auc_series(f"{RAW}/{fn}", tr)
            ax.plot(t, a, "-o", color=col, ms=4, lw=2.0, label=label)
        ax.set_title(gname, fontsize=11, fontweight="bold")
        ax.set_xlabel("Time (min)")
        ax.set_ylabel("Coacervation AUC")
        ax.set_ylim(0.045, 0.095)
        ax.grid(True, ls=":", alpha=0.55)
        ax.legend(fontsize=8, loc="best")
    fig.suptitle("Coacervation strength over time (AUC vs time) — Tea Saponin set",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(f"Reports/{png}", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote Reports/" + png)


# ---------------------------------------------------------------- friction / deposition vs AUC
# Measured conditioning data (SLR Table 1, Camille England 15 DEC 2025):
#   GH150 16% full-formula DM5500, Tea Saponin as ADDITIVE. Lower friction = better.
FRICTION_DOSE = [0.0, 0.25, 0.5, 1.0]
FRICTION = {
    "Detangling (dry)":     [122, 93, 73, 62],
    "Total friction (dry)": [95, 76, 62, 47],
    "IFM (dry)":            [144, 130, 121, 128],
}


def _auc_dose(group, tp=5.0):
    """AUC at timepoint tp for each sample in a dose group -> (doses, aucs)."""
    doses, aucs = [], []
    for label, fn, tr, col in group:
        # parse leading numeric dose from the label ("0.25% Tea Saponin" -> 0.25)
        d = 0.0
        for tok in label.replace("%", " ").split():
            try:
                d = float(tok); break
            except ValueError:
                continue
        t, a = _auc_series(f"{RAW}/{fn}", tr)
        doses.append(d); aucs.append(float(np.interp(tp, t, a)))
    order = np.argsort(doses)
    return np.asarray(doses)[order], np.asarray(aucs)[order]


def plot_friction_auc(png, tp=5.0):
    """Compare measured conditioning (friction, SLR Table 1) vs coacervation AUC,
    both as a function of Tea Saponin dose.

    Left  : measured friction/IFM (dry) vs TS dose  -> clear dose response.
    Right : coacervation AUC vs TS dose (R2510, N22510S) -> ~flat with dose.
    The contrast is the scientific point: deposition/conditioning scales with
    dose, but the coacervate SHIFT (AUC) does not — AUC marks the shift, not the
    dose-dependent amount deposited.
    """
    fig, (axf, axa) = plt.subplots(1, 2, figsize=(12.0, 4.8), dpi=150)

    # left: measured friction vs dose
    fcolors = {"Detangling (dry)": "#7B1FA2", "Total friction (dry)": "#C0392B", "IFM (dry)": "#E67E22"}
    for name, vals in FRICTION.items():
        axf.plot(FRICTION_DOSE, vals, "-o", ms=6, lw=2.2, color=fcolors[name], label=name)
        r = np.corrcoef(FRICTION_DOSE, vals)[0, 1]
        axf.annotate(f"r={r:+.2f}", (FRICTION_DOSE[-1], vals[-1]), fontsize=8,
                     color=fcolors[name], xytext=(4, 0), textcoords="offset points", va="center")
    axf.set_xlabel("Tea Saponin dose (%)")
    axf.set_ylabel("Friction / IFM  (lower = better conditioning)")
    axf.set_title("Measured conditioning vs dose\nGH150 16% DM5500 (SLR Table 1)", fontsize=11, fontweight="bold")
    axf.grid(True, ls=":", alpha=0.55)
    axf.legend(fontsize=9, loc="center right")

    # right: AUC vs dose
    for group, name, col in ((GROUP_R2510, "GH150 16% R2510", "#1F4E78"),
                             (GROUP_N22510S, "GH150 16% N22510S", "#2E9E5B")):
        d, a = _auc_dose(group, tp=tp)
        axa.plot(d, a, "-o", ms=6, lw=2.2, color=col, label=name)
    axa.set_xlabel("Tea Saponin dose (%)")
    axa.set_ylabel(f"Coacervation AUC ({tp:g} min)")
    axa.set_title("Coacervation AUC vs dose\n(this platform) — ~flat with dose", fontsize=11, fontweight="bold")
    axa.set_ylim(0.045, 0.095)
    axa.grid(True, ls=":", alpha=0.55)
    axa.legend(fontsize=9, loc="center right")

    fig.suptitle("Conditioning scales with dose — coacervation AUC does not  (dose decouples from the shift)",
                 fontsize=12.5, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(f"Reports/{png}", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote Reports/" + png)


# ---------------------------------------------------------------- time course grid
def plot_timecourse_grid(groups, png, *, view="pct"):
    """Mark-Brown 24-shampoo-style small-multiples grid: one panel per sample,
    0-15 min curves colored by time, shared Time legend."""
    panels = []
    for gname, items in groups:
        for label, fn, tr, col in items:
            try:
                ser = series(f"{RAW}/{fn}", tr)
            except Exception as e:  # noqa: BLE001
                print("skip TC", label, e); continue
            panels.append({"label": f"{gname}\n{label}", "series": ser})
    fig = plot_small_multiples(
        panels, view=view, ncols=4,
        dilution_ticks=(1, 2, 5, 10, 20, 100),
        title="Coacervation time-course (0-15 min) — Tea Saponin set",
    )
    fig.savefig(f"Reports/{png}", dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("wrote Reports/" + png)


# ================================================================ run
ALL_GROUPS = [
    ("5.8/5.8/2.4 GH150 shift", GROUP_SHIFT),
    ("GH150 16% R2510", GROUP_R2510),
    ("GH150 16% N22510S", GROUP_N22510S),
]

# %T overlays
plot_overlay(GROUP_SHIFT, "Coacervate shift with Tea Saponin - 5.8/5.8/2.4 GH150 (5 min)", "tea_shift.png")
plot_overlay(GROUP_R2510, "GH150 16% R2510 - Tea Saponin dose (5 min)", "tea_R2510.png")
plot_overlay(GROUP_N22510S, "GH150 16% N22510S - Tea Saponin dose (5 min)", "tea_N22510S.png")

# Absorbance overlays
plot_overlay(GROUP_SHIFT, "Absorbance — shift with Tea Saponin, 5.8/5.8/2.4 GH150 (5 min)", "tea_shift_abs.png", mode="abs")
plot_overlay(GROUP_R2510, "Absorbance — GH150 16% R2510 Tea Saponin dose (5 min)", "tea_R2510_abs.png", mode="abs")
plot_overlay(GROUP_N22510S, "Absorbance — GH150 16% N22510S Tea Saponin dose (5 min)", "tea_N22510S_abs.png", mode="abs")

# AUC ranking bar chart
plot_auc_bars(ALL_GROUPS, "tea_auc.png")

# AUC over time (kinetics) + numeric values
plot_auc_time(ALL_GROUPS, "tea_auc_time.png")
write_auc_values(ALL_GROUPS, "tea_auc_values.csv")

# Conditioning (friction) vs AUC, both vs Tea Saponin dose
plot_friction_auc("tea_friction_auc.png")

# Mark-Brown-style time-course panel grid
plot_timecourse_grid(ALL_GROUPS, "tea_timecourse.png", view="pct")
