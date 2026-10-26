"""
Plotting for coacervation absorbance / AUC analysis.

Produces the capability-deck style graph:
  - Absorbance (y) vs. Concentration / formula fraction (x)
  - x-axis oriented MOST concentrated (left) -> LEAST concentrated (right)
  - raw points + smooth best-fit curve
  - shaded, annotated AUC window
"""

from __future__ import annotations

import textwrap
from typing import Optional

import numpy as np
import matplotlib

matplotlib.use("Agg")  # headless / server-safe
import matplotlib.pyplot as plt  # noqa: E402

from coacervation_analysis import (  # noqa: E402
    transmittance_to_absorbance,
    dilution_ratio,
    fit_curve,
    compute_auc,
)


_DEPO_CLASS_COLORS = {
    "~2x": "#e07a5f", "~1.5x": "#f2a65a", "~1x": "#8ecae6",
    "sub-baseline": "#adb5bd", "": "#adb5bd",
}


def _depo_label(r: dict) -> str:
    name = r.get("component") or r.get("polymer") or r.get("surfactant") or "?"
    conc = r.get("concentration") or ""
    run = r.get("run") or ""
    return f"{name} {conc}".strip() + (f" [{run}]" if run else "")


def plot_deposition(rows, models, *, kind="ranking", outcome_label="PO deposition"):
    """Visualize predicted deposition across the sample library.

    kind:
      'ranking'   - horizontal bar of predicted depo per sample (sorted), with
                    the chassis baseline line, colored by 1x/1.5x/2x class.
      'mwcd'      - scatter of MW x CD vs predicted depo with the model fit line.
      'structure' - MW (x) vs charge density (y), bubble size ~ predicted depo.
    """
    mw_cd_model = next((m for m in models if m.get("predictor") == "mw_cd"), None)
    baseline = None
    for m in models:
        if m.get("baseline") is not None:
            baseline = float(m["baseline"])
            break

    have = [r for r in rows if r.get("pred_depo") is not None]

    if kind == "ranking":
        fig, ax = plt.subplots(figsize=(9, max(3, 0.42 * len(have) + 1.5)))
        if not have:
            ax.text(0.5, 0.5, "No predicted deposition yet.\nAdd MW/CD (or coacervate size) "
                    "via the intake workbook.", ha="center", va="center")
            ax.axis("off")
            return fig
        have.sort(key=lambda r: r["pred_depo"])
        labels = [_depo_label(r) for r in have]
        vals = [r["pred_depo"] for r in have]
        colors = [_DEPO_CLASS_COLORS.get(r.get("depo_class", ""), "#8ecae6") for r in have]
        y = np.arange(len(have))
        ax.barh(y, vals, color=colors, edgecolor="#33404d", linewidth=0.5)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8)
        for i, v in enumerate(vals):
            ax.text(v + 0.02, i, f"{v:.2f}", va="center", fontsize=8)
        if baseline is not None:
            ax.axvline(baseline, color="#6c757d", ls="--", lw=1)
            ax.text(baseline, len(have) - 0.3, f" chassis baseline ~{baseline:g}",
                    color="#6c757d", fontsize=8, va="top")
        ax.set_xlabel(f"Predicted {outcome_label} (ug/cm2)")
        ax.set_title(f"Predicted {outcome_label} - ranked")
        # legend for classes
        from matplotlib.patches import Patch
        handles = [Patch(facecolor=c, edgecolor="#33404d", label=k)
                   for k, c in (("~2x", "#e07a5f"), ("~1.5x", "#f2a65a"),
                                ("~1x", "#8ecae6"), ("sub-baseline", "#adb5bd"))]
        ax.legend(handles=handles, fontsize=8, loc="lower right", title="Depo class")
        fig.tight_layout()
        return fig

    if kind == "mwcd":
        fig, ax = plt.subplots(figsize=(8, 6))
        pts = [r for r in have if r.get("mw_kda") not in (None, "") and r.get("charge") not in (None, "")]
        xs = [float(r["mw_kda"]) * float(r["charge"]) for r in pts]
        ys = [r["pred_depo"] for r in pts]
        colors = [_DEPO_CLASS_COLORS.get(r.get("depo_class", ""), "#8ecae6") for r in pts]
        ax.scatter(xs, ys, c=colors, s=70, edgecolor="#33404d", zorder=3)
        for r, x, yv in zip(pts, xs, ys):
            ax.annotate(_depo_label(r), (x, yv), fontsize=7, xytext=(4, 4),
                        textcoords="offset points")
        if mw_cd_model and xs:
            xline = np.linspace(0, max(xs) * 1.1 + 1, 100)
            yline = float(mw_cd_model["slope"]) * xline + float(mw_cd_model["intercept"])
            ax.plot(xline, yline, color="#1f4e78", lw=1.8,
                    label=f"{mw_cd_model.get('name', 'fit')}"
                          + (f"  (R2={mw_cd_model.get('r2')})" if mw_cd_model.get("r2") else ""))
            ax.legend(fontsize=8, loc="upper left")
        ax.set_xlabel("MW (kDa) x charge density (meq/g)")
        ax.set_ylabel(f"Predicted {outcome_label} (ug/cm2)")
        ax.set_title(f"{outcome_label} vs. polymer MW x charge density")
        ax.grid(True, alpha=0.25)
        fig.tight_layout()
        return fig

    # structure map: MW vs CD, bubble size ~ predicted depo
    fig, ax = plt.subplots(figsize=(8, 6))
    pts = [r for r in have if r.get("mw_kda") not in (None, "") and r.get("charge") not in (None, "")]
    if not pts:
        ax.text(0.5, 0.5, "Need MW and charge density (intake workbook) to map structure.",
                ha="center", va="center")
        ax.axis("off")
        return fig
    xs = [float(r["mw_kda"]) for r in pts]
    ys = [float(r["charge"]) for r in pts]
    sizes = [max(30, (r["pred_depo"] ** 2) * 120) for r in pts]
    colors = [_DEPO_CLASS_COLORS.get(r.get("depo_class", ""), "#8ecae6") for r in pts]
    ax.scatter(xs, ys, s=sizes, c=colors, alpha=0.8, edgecolor="#33404d", zorder=3)
    for r, x, yv in zip(pts, xs, ys):
        ax.annotate(f"{_depo_label(r)}\n{r['pred_depo']:.2f}", (x, yv), fontsize=7,
                    xytext=(5, 5), textcoords="offset points")
    ax.set_xlabel("Polymer MW (kDa)")
    ax.set_ylabel("Charge density (meq/g)")
    ax.set_title(f"Structure map - bubble size ~ predicted {outcome_label}")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    return fig


def plot_absorbance_vs_concentration(
    concentration: np.ndarray,
    pct_transmittance: np.ndarray,
    *,
    sample_label: str = "Sample",
    auc_window: Optional[tuple[float, float]] = None,
    kind: str = "spline",
    smoothing: Optional[float] = None,
    out_path: Optional[str] = None,
    ax: Optional[plt.Axes] = None,
):
    """Create the absorbance-vs-concentration plot with best fit and AUC.

    Args:
        concentration: formula-fraction values.
        pct_transmittance: %T values aligned with concentration.
        sample_label: legend/title label for the series.
        auc_window: (low, high) concentration window to shade and integrate.
        kind: curve-fit type ('spline', 'pchip', 'akima', 'poly').
        smoothing: spline smoothing factor (None = auto).
        out_path: if given, save the figure to this path.
        ax: optional existing axis to draw on.

    Returns:
        (fig, ax, auc_result)
    """
    conc = np.asarray(concentration, dtype=float)
    absb = transmittance_to_absorbance(np.asarray(pct_transmittance, dtype=float))

    fit = fit_curve(conc, absb, kind=kind, smoothing=smoothing)
    xs, ys = fit.dense(400)

    auc_result = compute_auc(
        conc, absb, window=auc_window, use_fit=True, kind=kind, smoothing=smoothing
    )

    if ax is None:
        fig, ax = plt.subplots(figsize=(8.5, 5.5), dpi=120)
    else:
        fig = ax.figure

    # best-fit curve
    ax.plot(xs, ys, "-", color="#1F4E78", lw=2.2, zorder=3,
            label=f"{sample_label} (best fit)")
    # raw points
    ax.plot(conc, absb, "o", color="#C00000", ms=6, mec="white", mew=0.7,
            zorder=4, label="Measured")

    # AUC shaded window
    lo, hi = auc_result["low"], auc_result["high"]
    wmask = (xs >= lo) & (xs <= hi)
    ax.fill_between(xs[wmask], 0, ys[wmask], color="#9DC3E6", alpha=0.45,
                    zorder=2, label=f"AUC window [{hi:.3f} -> {lo:.3f}]")

    # AUC annotation
    ax.annotate(
        f"AUC = {auc_result['auc']:.4f}\n(mean A = {auc_result['mean_absorbance']:.3f})",
        xy=(0.5 * (lo + hi), max(ys[wmask]) if wmask.any() else ys.max()),
        xytext=(0.55, 0.9), textcoords="axes fraction",
        ha="left", va="top",
        fontsize=11, fontweight="bold", color="#1F4E78",
        bbox=dict(boxstyle="round,pad=0.4", fc="#EAF1FB", ec="#1F4E78", lw=1.2),
    )

    # x-axis: most concentrated LEFT -> least concentrated RIGHT
    ax.set_xlim(conc.max() * 1.02, conc.min() - conc.max() * 0.02)
    ax.set_xlabel("Concentration (formula fraction)  —  most → least concentrated")
    ax.set_ylabel("Absorbance  (A = 2 − log₁₀ %T)")
    ax.set_title(f"Coacervate Dissolution Profile — {sample_label}", fontweight="bold")
    ax.grid(True, ls=":", alpha=0.5)
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper left", framealpha=0.9)

    fig.tight_layout()
    if out_path:
        fig.savefig(out_path, bbox_inches="tight")
    return fig, ax, auc_result


_PALETTE = ["#1F4E78", "#C00000", "#2E7D32", "#7B1FA2", "#E67E22", "#00838F"]
# Purple family for the dextran-style Absorbance AUC panel.
_PURPLE = ["#7A3B9E", "#9B4DCA", "#5B2C9E", "#B14AED", "#6A4C93", "#C56CF0"]


def plot_samples(
    samples: list[dict],
    *,
    auc_window: Optional[tuple[float, float]] = None,
    kind: str = "spline",
    smoothing: Optional[float] = None,
    title: str = "Coacervate Dissolution Profile",
    out_path: Optional[str] = None,
):
    """Plot one or more samples (overlay) as absorbance vs. concentration.

    Args:
        samples: list of dicts, each with keys:
                 'label', 'concentration', 'pct_transmittance'.
        auc_window: (low, high) concentration window to shade and integrate.
        kind: curve-fit type.
        smoothing: spline smoothing (None = auto).
        title: plot title.
        out_path: optional path to save the figure.

    Returns:
        (fig, ax, results) where results is a list of AUC dicts (one per sample,
        each with an added 'label' key).
    """
    fig, ax = plt.subplots(figsize=(9.0, 5.6), dpi=120)
    results = []
    all_conc = []

    for i, s in enumerate(samples):
        conc = np.asarray(s["concentration"], dtype=float)
        absb = transmittance_to_absorbance(np.asarray(s["pct_transmittance"], dtype=float))
        all_conc.append(conc)

        fit = fit_curve(conc, absb, kind=kind, smoothing=smoothing)
        xs, ys = fit.dense(400)
        auc = compute_auc(conc, absb, window=auc_window, use_fit=True,
                          kind=kind, smoothing=smoothing)
        results.append({"label": s["label"], **auc})

        color = _PALETTE[i % len(_PALETTE)]
        ax.plot(xs, ys, "-", color=color, lw=2.2, zorder=3,
                label=f"{s['label']}  (AUC={auc['auc']:.4f})")
        ax.plot(conc, absb, "o", color=color, ms=5, mec="white", mew=0.6, zorder=4)

    if auc_window is not None:
        lo, hi = min(auc_window), max(auc_window)
        ax.axvspan(lo, hi, color="#9DC3E6", alpha=0.20, zorder=1,
                   label=f"AUC window [{hi:.3f} → {lo:.3f}]")

    conc_all = np.concatenate(all_conc)
    ax.set_xlim(conc_all.max() * 1.02, conc_all.min() - conc_all.max() * 0.02)
    ax.set_xlabel("Concentration (formula fraction)  —  most → least concentrated")
    ax.set_ylabel("Absorbance  (A = 2 − log₁₀ %T)")
    ax.set_title(title, fontweight="bold")
    ax.grid(True, ls=":", alpha=0.5)
    ax.set_ylim(bottom=0)
    ax.legend(loc="upper right", framealpha=0.9, fontsize=9)

    fig.tight_layout()
    if out_path:
        fig.savefig(out_path, bbox_inches="tight")
    return fig, ax, results


def _unimodal(y, mode: str):
    """Enforce a clean single-peak/valley shape to remove tail wiggles.

    mode='peak'  : non-decreasing up to the max, then non-increasing (absorbance).
    mode='valley': non-increasing down to the min, then non-decreasing (%T).
    """
    y = np.asarray(y, dtype=float).copy()
    if mode == "peak":
        i = int(np.argmax(y))
        y[: i + 1] = np.maximum.accumulate(y[: i + 1])
        y[i:] = np.minimum.accumulate(y[i:])
    else:  # valley
        i = int(np.argmin(y))
        y[: i + 1] = np.minimum.accumulate(y[: i + 1])
        y[i:] = np.maximum.accumulate(y[i:])
    return y


def _est_noise_std(y) -> float:
    """Robust point-to-point noise estimate (from 2nd differences)."""
    y = np.asarray(y, dtype=float)
    if len(y) < 4:
        return 1.0
    d2 = np.diff(y, 2)
    mad = np.median(np.abs(d2 - np.median(d2)))
    sigma = 1.4826 * mad / np.sqrt(6.0)
    return max(float(sigma), 0.3)


def _smoothing_for(y) -> float:
    """UnivariateSpline smoothing target: follow real structure (incl. bimodal
    dips) down to the estimated noise floor, not the whole-curve variance."""
    n = len(np.asarray(y))
    return n * (_est_noise_std(y) ** 2)



def _format_dilution_axis(ax, x_all, dilution_ticks):
    """Configure an axis as a clean, non-crowded dilution (1:X) log axis."""
    from matplotlib.ticker import NullFormatter, NullLocator

    ax.set_xscale("log")
    ticks = [t for t in dilution_ticks if x_all.min() * 0.9 <= t <= x_all.max() * 1.15]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"1:{t}" for t in ticks], rotation=45, ha="right")
    # remove minor ticks/labels so 1:1..1:5 don't collide
    ax.xaxis.set_minor_locator(NullLocator())
    ax.xaxis.set_minor_formatter(NullFormatter())
    ax.set_xlim(max(x_all.min() * 0.9, 0.9), x_all.max() * 1.15)  # 1:1 at left
    ax.set_xlabel("Dilution (1:X)  —  most → least concentrated", fontsize=12)
    ax.grid(True, which="major", ls=":", alpha=0.6)


def plot_transmittance_and_absorbance(
    samples: list[dict],
    *,
    auc_window: Optional[tuple[float, float]] = None,
    kind: str = "spline",
    smoothing: Optional[float] = None,
    title: str = "Coacervate Dissolution Profile",
    pct_ylim: tuple[float, float] = (0.0, 100.0),
    abs_ylim: tuple[float, float] = (0.0, 0.6),
    dilution_ticks: tuple[int, ...] = (1, 2, 10, 100, 500),
    out_path: Optional[str] = None,
):
    """Two-panel figure for formulators, DILUTION (1:X) on both x-axes.

    Left  : % Transmittance vs. dilution (1:X)
    Right : Absorbance vs. dilution (1:X)

    Both panels use a clean log dilution axis with rotated, non-overlapping
    1:X ticks and identical FIXED y-scales so figures are directly comparable.

    Args:
        samples: list of dicts with 'label', 'concentration' (formula fraction),
                 'pct_transmittance'.
        auc_window: (low, high) formula-fraction window shaded on both panels and
                    integrated (AUC, over concentration) on the absorbance panel.
        kind: curve-fit type.
        smoothing: spline smoothing (None = auto).
        title: figure title.
        pct_ylim: fixed y-limits for the %T panel (default 0-100).
        abs_ylim: fixed y-limits for the absorbance panel (default 0-0.6).
        dilution_ticks: 1:X tick positions.
        out_path: optional save path.

    Returns:
        (fig, (ax_t, ax_a), results) where results is a list of AUC dicts.
    """
    fig, results = plot_coacervation(
        samples, view="both", auc_window=auc_window, kind=kind, smoothing=smoothing,
        title=title, pct_ylim=pct_ylim, abs_ylim=abs_ylim,
        dilution_ticks=dilution_ticks, out_path=out_path,
    )
    return fig, fig.axes, results


def _dilution_tag(lo, hi):
    """Format an AUC window (formula fractions lo<hi) as a '1:1-1:20' label."""
    if lo is None or hi is None:
        return ""
    x_hi = dilution_ratio(hi)   # more concentrated end -> smaller 1:X
    x_lo = dilution_ratio(lo)   # more diluted end     -> larger 1:X
    return f"1:{x_hi:g}-1:{x_lo:g}"


def _draw_panel(ax, samples, panel, *, kind, smoothing, dilution_ticks, ylim,
                auc_window, results, shape="free", external_pct_legend=False):
    """Draw one dilution-axis panel ('pct' or 'abs') for all samples.

    shape='free'     : follow the data (captures bimodal / two-phase dips).
    shape='unimodal' : force a single valley/peak (legacy tidy shape).
    """
    all_x = []
    all_conc = []
    abs_totals = {}
    abs_ymax = []
    for i, s in enumerate(samples):
        conc = np.asarray(s["concentration"], dtype=float)
        pct = np.asarray(s["pct_transmittance"], dtype=float)
        absb = transmittance_to_absorbance(pct)
        xdil = dilution_ratio(conc)
        all_x.append(xdil)
        all_conc.append(conc)
        color = _PALETTE[i % len(_PALETTE)]
        lx = np.log10(np.clip(xdil, 1e-9, None))
        lx_dense = np.linspace(lx.min(), lx.max(), 400)
        x_dense = 10 ** lx_dense

        if panel == "pct":
            s_val = smoothing if smoothing is not None else _smoothing_for(pct)
            fit = fit_curve(lx, pct, kind=kind, smoothing=s_val)
            y = np.clip(np.asarray(fit(lx_dense)), pct.min(), pct.max())
            if shape == "unimodal":
                y = _unimodal(y, "valley")
            ax.plot(x_dense, y, "-", color=color, lw=2.4, zorder=3, label=s["label"])
            ax.plot(xdil, pct, "o", color=color, ms=5, mec="white", mew=0.6, zorder=4)
        else:
            # Absorbance vs CONCENTRATION (formula fraction), dextran-style
            # (purple): full-range AUC (total) + consumer-window AUC.
            pcolor = _PURPLE[i % len(_PURPLE)]
            c_dense = np.linspace(conc.min(), conc.max(), 400)
            s_val = smoothing if smoothing is not None else _smoothing_for(absb)
            fit = fit_curve(conc, absb, kind=kind, smoothing=s_val)
            y = np.clip(np.asarray(fit(c_dense)), absb.min(), absb.max())
            consumer = next((r["auc"] for r in results if r["label"] == s["label"]), 0.0)
            total = compute_auc(conc, absb, window=None, use_fit=True,
                                kind=kind, smoothing=s_val)["auc"]
            abs_totals[s["label"]] = total
            abs_ymax.append(float(np.nanmax(absb)))
            base = float(absb.min())
            # filled area under the curve + dashed baseline
            ax.fill_between(c_dense, base, y, color=pcolor, alpha=0.28, zorder=1)
            ax.axhline(base, color=pcolor, ls="--", lw=0.9, alpha=0.5, zorder=1)
            ax.plot(c_dense, y, "-", color=pcolor, lw=2.4, zorder=3,
                    label=f"{s['label']}  AUC={total:.4f}  consumer={consumer:.4f}")

    ax.set_ylim(*ylim)
    if panel == "pct":
        x_all = np.concatenate(all_x)
        _format_dilution_axis(ax, x_all, dilution_ticks)
        ax.set_ylabel("% Transmittance", fontsize=13)
        ax.set_title("% Transmittance vs. Dilution", fontweight="bold", fontsize=14)
        if external_pct_legend:
            handles, labels = ax.get_legend_handles_labels()
            ax.legend(
                handles, [textwrap.fill(l, _LEGEND_WRAP) for l in labels],
                title="Samples", loc="upper left", bbox_to_anchor=(1.02, 1.0),
                borderaxespad=0, framealpha=0.95, fontsize=9,
            )
        else:
            handles, labels = ax.get_legend_handles_labels()
            ax.legend(handles, [textwrap.fill(l, 44) for l in labels],
                      loc="lower left", framealpha=0.9, fontsize=11)
        if auc_window is not None:
            lo, hi = min(auc_window), max(auc_window)
            ax.axvspan(dilution_ratio(hi), dilution_ratio(lo),
                       color="#9DC3E6", alpha=0.18, zorder=1)
    else:
        # Reversed concentration axis to 0 (left = concentrated), dextran-style.
        ax.set_xlim(0.51, 0.0)
        cticks = [0.5, 0.4, 0.3, 0.2, 0.1, 0.0]
        ax.set_xticks(cticks)
        ax.set_xticklabels([f"{t:g}" for t in cticks])
        ax.set_xlabel("Concentration (formula fraction; left = concentrated)", fontsize=12)
        ax.grid(True, which="major", ls=":", alpha=0.6)
        ax.set_ylabel("Absorbance  A = −log10(%T/100)", fontsize=13)
        # Keep a sensible minimum ceiling so weak/flat samples aren't over-zoomed
        # (which magnifies noise); the axis still grows for strong coacervators.
        top = max(abs_ymax) if abs_ymax else 0.6
        ax.set_ylim(0, max(round(top * 1.15 + 0.049, 1), 0.3))
        tag = _dilution_tag(min(auc_window), max(auc_window)) if auc_window else ""
        if len(samples) == 1:
            lbl = samples[0]["label"]
            total = abs_totals.get(lbl, 0.0)
            consumer = next((r["auc"] for r in results if r["label"] == lbl), 0.0)
            ax.set_title(f"{lbl}\nAUC(total)={total:.4f}   consumer({tag})={consumer:.4f}",
                         fontweight="bold", fontsize=13)
        else:
            ax.set_title("Absorbance AUC — total vs consumer window",
                         fontweight="bold", fontsize=14)
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles, [textwrap.fill(l, 44) for l in labels],
                  loc="upper left", framealpha=0.9, fontsize=10)


_LEGEND_WRAP = 34  # characters per legend line when the legend sits beside the plot
_AXES_W = 8.6      # inches reserved for the plot itself, so long names never squeeze it


def _external_legend_size(labels):
    """Figure (width, height) in inches for a %T plot with the legend beside it."""
    wrapped = [textwrap.wrap(l, _LEGEND_WRAP) or [""] for l in labels]
    longest = max(len(line) for w in wrapped for line in w)
    legend_w = 0.085 * longest + 0.9
    legend_h = 0.19 * sum(len(w) for w in wrapped) + 0.09 * len(wrapped) + 0.8
    return _AXES_W + legend_w, max(6.2, legend_h + 0.6), legend_w


def plot_coacervation(
    samples: list[dict],
    *,
    view: str = "both",
    auc_window: Optional[tuple[float, float]] = None,
    kind: str = "spline",
    smoothing: Optional[float] = None,
    title: str = "Coacervate Dissolution Profile",
    pct_ylim: tuple[float, float] = (0.0, 100.0),
    abs_ylim: tuple[float, float] = (0.0, 0.6),
    dilution_ticks: tuple[int, ...] = (1, 2, 10, 100, 500),
    out_path: Optional[str] = None,
    shape: str = "free",
):
    """Render coacervation graphs with a selectable view.

    Args:
        samples: list of dicts with 'label', 'concentration', 'pct_transmittance'.
        view: 'both' (%T + Absorbance), 'pct' (%T only), or 'abs' (Absorbance only).
        auc_window: (low, high) formula-fraction window for AUC + shading.
        kind, smoothing: curve-fit controls.
        title: figure title.
        pct_ylim, abs_ylim: fixed y-scales for comparability.
        dilution_ticks: 1:X tick positions.
        out_path: optional save path.
        shape: 'free' captures bimodal/two-phase dips; 'unimodal' forces a
               single valley/peak (legacy).

    Returns:
        (fig, results) where results is a list of AUC dicts (one per sample).
    """
    plt.rcParams.update({"font.size": 13})

    # AUC results are always computed (absorbance-based), regardless of view.
    results = []
    for s in samples:
        conc = np.asarray(s["concentration"], dtype=float)
        absb = transmittance_to_absorbance(np.asarray(s["pct_transmittance"], dtype=float))
        auc = compute_auc(conc, absb, window=auc_window, use_fit=True,
                          kind=kind, smoothing=smoothing)
        total = compute_auc(conc, absb, window=None, use_fit=True,
                            kind=kind, smoothing=smoothing)
        results.append({"label": s["label"], **auc, "total_auc": total["auc"]})

    if view == "both":
        fig, (ax_t, ax_a) = plt.subplots(1, 2, figsize=(15.5, 6.4), dpi=120)
        panels = [("pct", ax_t, pct_ylim), ("abs", ax_a, abs_ylim)]
    elif view == "pct":
        external_pct_legend = len(samples) > 1
        legend_w = 0.0
        if external_pct_legend:
            fig_w, fig_h, legend_w = _external_legend_size([s["label"] for s in samples])
        else:
            fig_w, fig_h = 9.0, 6.2
        fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=120)
        panels = [("pct", ax, pct_ylim)]
    else:  # 'abs'
        external_pct_legend = False
        fig, ax = plt.subplots(figsize=(9.0, 6.2), dpi=120)
        panels = [("abs", ax, abs_ylim)]

    if view == "both":
        external_pct_legend = False

    for panel, ax, ylim in panels:
        _draw_panel(ax, samples, panel, kind=kind, smoothing=smoothing,
                    dilution_ticks=dilution_ticks, ylim=ylim,
                    auc_window=auc_window, results=results, shape=shape,
                    external_pct_legend=external_pct_legend)

    fig.suptitle(title, fontweight="bold", fontsize=16, y=1.02)
    if external_pct_legend:
        fig.tight_layout(rect=(0, 0, 1 - legend_w / fig.get_figwidth(), 0.96))
    else:
        fig.tight_layout()
    if out_path:
        fig.savefig(out_path, bbox_inches="tight")
    return fig, results


def plot_time_course(
    troughs: list[dict],
    *,
    view: str = "pct",
    auc_window: Optional[tuple[float, float]] = None,
    kind: str = "spline",
    smoothing: Optional[float] = None,
    title: str = "Coacervate Dissolution — Time Course",
    pct_ylim: tuple[float, float] = (0.0, 100.0),
    abs_ylim: tuple[float, float] = (0.0, 0.6),
    dilution_ticks: tuple[int, ...] = (1, 2, 5, 10, 20, 100),
    cmap: str = "turbo",
    frac: float = 0.25,
    out_path: Optional[str] = None,
):
    """Overlay dilution curves for multiple timepoints, colored by time.
    One subplot per trough (sample); each timepoint is a colored best-fit curve
    with raw points, on the dilution (1:X) axis — like the 0-15 min slide.

    Args:
        troughs: list of dicts, one per sample:
                 {'label': str, 'series': [{'time': float, 'concentration': ...,
                  'pct_transmittance': ...}, ...]}.
        view: 'pct' (%Transmittance) or 'abs' (Absorbance).
        auc_window: (low, high) formula-fraction window shaded on each panel.
        kind, smoothing: curve-fit controls.
        title: figure title.
        pct_ylim, abs_ylim: fixed y-scales.
        dilution_ticks: 1:X tick positions.
        cmap: matplotlib colormap for the time axis.
        out_path: optional save path.

    Returns:
        fig
    """
    from matplotlib.colors import Normalize

    plt.rcParams.update({"font.size": 13})
    is_pct = view != "abs"
    n = max(1, len(troughs))
    fig, axes = plt.subplots(1, n, figsize=(7.8 * n, 6.2), dpi=120, squeeze=False)
    axes = axes[0]

    all_times = sorted({s["time"] for tr in troughs for s in tr["series"]})
    tmin, tmax = (min(all_times), max(all_times)) if all_times else (0.0, 15.0)
    norm = Normalize(vmin=tmin, vmax=tmax if tmax > tmin else tmin + 1.0)
    cmap_obj = plt.get_cmap(cmap)

    for ax, tr in zip(axes, troughs):
        all_x = []
        for s in sorted(tr["series"], key=lambda z: z["time"]):
            conc = np.asarray(s["concentration"], dtype=float)
            pct = np.asarray(s["pct_transmittance"], dtype=float)
            xdil = dilution_ratio(conc)
            all_x.append(xdil)
            lx = np.log10(np.clip(xdil, 1e-9, None))
            lxd = np.linspace(lx.min(), lx.max(), 400)
            xd = 10 ** lxd
            color = cmap_obj(norm(s["time"]))
            if is_pct:
                fit = fit_curve(lx, pct, kind="lowess", smoothing=frac)
                y = np.clip(np.asarray(fit(lxd)), pct.min(), pct.max())
                yr = pct
            else:
                absb = transmittance_to_absorbance(pct)
                fit = fit_curve(lx, absb, kind="lowess", smoothing=frac)
                y = np.clip(np.asarray(fit(lxd)), absb.min(), absb.max())
                yr = absb
            ax.plot(xd, y, "-", color=color, lw=2.0, zorder=3, label=f"{s['time']:g} min")
            ax.plot(xdil, yr, "o", color=color, ms=3.2, alpha=0.55, mec="none", zorder=4)

        if all_x:
            _format_dilution_axis(ax, np.concatenate(all_x), dilution_ticks)
        ax.set_ylim(*(pct_ylim if is_pct else abs_ylim))
        ax.set_ylabel("% Transmittance" if is_pct
                      else "Absorbance  (A = 2 − log₁₀ %T)", fontsize=13)
        ax.set_title(tr["label"], fontweight="bold", fontsize=13)
        if auc_window is not None:
            lo, hi = min(auc_window), max(auc_window)
            ax.axvspan(dilution_ratio(hi), dilution_ratio(lo),
                       color="#9DC3E6", alpha=0.18, zorder=1)
        ax.legend(title="Time", fontsize=9, framealpha=0.9,
                  loc="lower right" if is_pct else "upper right")

    fig.suptitle(title, fontweight="bold", fontsize=16, y=1.02)
    fig.tight_layout()
    if out_path:
        fig.savefig(out_path, bbox_inches="tight")
    return fig


def plot_small_multiples(
    panels: list[dict],
    *,
    view: str = "pct",
    auc_window: Optional[tuple[float, float]] = None,
    kind: str = "spline",
    smoothing: Optional[float] = None,
    ncols: int = 4,
    pct_ylim: tuple[float, float] = (0.0, 100.0),
    abs_ylim: tuple[float, float] = (0.0, 0.6),
    dilution_ticks: tuple[int, ...] = (1, 2, 5, 10, 20, 100),
    cmap: str = "turbo",
    title: str = "Coacervation Data — Time-course grid",
    frac: float = 0.25,
    out_path: Optional[str] = None,
):
    """Grid of small-multiple panels: one sample per panel, 0-15 min time-course.

    Like the capability slide — every polymer/surfactant in a chassis as its own
    %T-vs-dilution panel with time-colored curves and a shared Time legend.
    """
    import math
    from matplotlib.colors import Normalize
    from matplotlib.lines import Line2D

    plt.rcParams.update({"font.size": 11})
    is_pct = view != "abs"
    n = max(1, len(panels))
    ncols = max(1, min(ncols, n))
    nrows = math.ceil(n / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.3 * ncols, 3.7 * nrows),
                             dpi=120, squeeze=False)

    all_times = sorted({s["time"] for p in panels for s in p["series"]})
    tmin, tmax = (min(all_times), max(all_times)) if all_times else (0.0, 15.0)
    norm = Normalize(vmin=tmin, vmax=tmax if tmax > tmin else tmin + 1.0)
    cmap_obj = plt.get_cmap(cmap)

    for idx, panel in enumerate(panels):
        ax = axes[idx // ncols][idx % ncols]
        all_x = []
        for s in sorted(panel["series"], key=lambda z: z["time"]):
            conc = np.asarray(s["concentration"], dtype=float)
            pct = np.asarray(s["pct_transmittance"], dtype=float)
            xdil = dilution_ratio(conc)
            all_x.append(xdil)
            lx = np.log10(np.clip(xdil, 1e-9, None))
            lxd = np.linspace(lx.min(), lx.max(), 400)
            xd = 10 ** lxd
            color = cmap_obj(norm(s["time"]))
            if is_pct:
                fit = fit_curve(lx, pct, kind="lowess", smoothing=frac)
                y = np.clip(np.asarray(fit(lxd)), pct.min(), pct.max())
                yr = pct
            else:
                absb = transmittance_to_absorbance(pct)
                fit = fit_curve(lx, absb, kind="lowess", smoothing=frac)
                y = np.clip(np.asarray(fit(lxd)), absb.min(), absb.max())
                yr = absb
            ax.plot(xd, y, "-", color=color, lw=1.8, zorder=3)
            ax.plot(xdil, yr, "o", color=color, ms=2.4, alpha=0.5, mec="none", zorder=4)
        if all_x:
            _format_dilution_axis(ax, np.concatenate(all_x), dilution_ticks)
        ax.set_ylim(*(pct_ylim if is_pct else abs_ylim))
        ax.set_title(panel["label"], fontweight="bold", fontsize=11)
        ax.tick_params(labelsize=8)
        if auc_window is not None:
            lo, hi = min(auc_window), max(auc_window)
            ax.axvspan(dilution_ratio(hi), dilution_ratio(lo),
                       color="#9DC3E6", alpha=0.18, zorder=1)

    for j in range(n, nrows * ncols):
        axes[j // ncols][j % ncols].axis("off")

    for r in range(nrows):
        axes[r][0].set_ylabel("% Transmittance" if is_pct else "Absorbance", fontsize=10)

    handles = [Line2D([0], [0], color=cmap_obj(norm(t)), lw=2.5, label=f"{t:g} min")
               for t in all_times]
    fig.legend(handles=handles, title="Time", loc="center right",
               fontsize=9, bbox_to_anchor=(1.005, 0.5))

    fig.suptitle(title, fontweight="bold", fontsize=15, y=1.0)
    fig.tight_layout(rect=(0, 0, 0.93, 1))
    if out_path:
        fig.savefig(out_path, bbox_inches="tight")
    return fig


def plot_3d_surface(
    troughs: list[dict],
    *,
    view: str = "pct",
    title: str = "Coacervation Data — 3D Surface",
    dilution_ticks: tuple[int, ...] = (1, 2, 10, 100, 500),
    cmap: str = "viridis",
    out_path: Optional[str] = None,
):
    """3D surface of the full landscape: Dilution (1:X) × Time (min) × %T/Absorbance.

    Args:
        troughs: list of dicts, one per sample:
                 {'label': str, 'series': [{'time', 'concentration',
                  'pct_transmittance'}, ...]}.
        view: 'pct' (%Transmittance, default) or 'abs' (Absorbance).
        title: figure title.
        dilution_ticks: 1:X tick positions.
        cmap: surface colormap.
        out_path: optional save path.

    Returns:
        fig
    """
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401  (registers 3d projection)

    is_pct = view != "abs"
    n = max(1, len(troughs))
    fig = plt.figure(figsize=(8.5 * n, 6.8), dpi=120)

    for i, tr in enumerate(troughs):
        ax = fig.add_subplot(1, n, i + 1, projection="3d")
        series = sorted(tr["series"], key=lambda z: z["time"])
        conc = np.asarray(series[0]["concentration"], dtype=float)
        xdil = dilution_ratio(conc)
        order = np.argsort(xdil)
        X = np.log10(xdil[order])
        times = [s["time"] for s in series]

        Z = []
        for s in series:
            y = np.asarray(s["pct_transmittance"], dtype=float)[order]
            if not is_pct:
                y = transmittance_to_absorbance(y)
            Z.append(y)
        Z = np.array(Z)
        Xg, Yg = np.meshgrid(X, times)

        surf = ax.plot_surface(Xg, Yg, Z, cmap=cmap, edgecolor="none",
                               antialiased=True, alpha=0.95)

        ticks = [t for t in dilution_ticks if xdil.min() * 0.9 <= t <= xdil.max() * 1.1]
        ax.set_xticks([np.log10(t) for t in ticks])
        ax.set_xticklabels([f"1:{t}" for t in ticks], fontsize=8)
        ax.set_xlabel("Dilution (1:X)", fontsize=10, labelpad=6)
        ax.set_ylabel("Time (min)", fontsize=10, labelpad=6)
        ax.set_zlabel("% Transmittance" if is_pct else "Absorbance",
                      fontsize=10, labelpad=6)
        ax.set_title(tr["label"], fontweight="bold", fontsize=12)
        ax.view_init(elev=28, azim=-60)
        fig.colorbar(surf, ax=ax, shrink=0.5, pad=0.08)

    fig.suptitle(title, fontweight="bold", fontsize=15, y=1.0)
    fig.tight_layout()
    if out_path:
        fig.savefig(out_path, bbox_inches="tight")
    return fig


def _prop_scatter(ax, items, xkey, xlabel, metric_label, group_by=None, gcolor=None):
    pts = [d for d in items if d.get(xkey) is not None]
    if not pts:
        ax.text(0.5, 0.5, f"No {xlabel} values\n(edit polymer_properties.csv)",
                ha="center", va="center", transform=ax.transAxes,
                color="#8a5a00", fontsize=11)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(metric_label)
        return
    grouped = group_by in ("chassis", "polymer", "surfactant") and gcolor
    for d in pts:
        c = gcolor.get(str(d.get(group_by) or "?")) if grouped else "#C00000"
        ax.scatter([d[xkey]], [d["auc"]], s=64, color=c, edgecolor="white",
                   linewidth=0.6, zorder=3)
        ax.annotate(str(d.get("component") or d.get("polymer", "")), (d[xkey], d["auc"]),
                    textcoords="offset points", xytext=(5, 3), fontsize=8)
    xs = np.array([d[xkey] for d in pts], dtype=float)
    ys = np.array([d["auc"] for d in pts], dtype=float)
    if len(xs) >= 3 and xs.std() > 0:
        b, a = np.polyfit(xs, ys, 1)
        xr = np.linspace(xs.min(), xs.max(), 50)
        ax.plot(xr, b * xr + a, "--", color="#555", lw=1.4, zorder=2)
        if ys.std() > 0:
            r = float(np.corrcoef(xs, ys)[0, 1])
            ax.text(0.03, 0.97, f"r = {r:.2f}", transform=ax.transAxes, va="top",
                    fontsize=10, color="#1F4E78",
                    bbox=dict(boxstyle="round,pad=0.25", fc="#EAF1FB", ec="#1F4E78"))
    ax.set_xlabel(xlabel)
    ax.set_ylabel(metric_label)
    ax.grid(True, ls=":", alpha=0.5)


def plot_comparison(items: list[dict], *, group_by: str = "none",
                    metric_label: str = "AUC (absorbance)",
                    title: str = "Coacervation Data — Polymer Comparison",
                    out_path: Optional[str] = None):
    """Compare samples: AUC ranking + AUC vs MW / charge, optionally colored by group.

    Args:
        items: dicts with keys label, polymer, auc, mw_kda, charge, and (for
               grouping) chassis / polymer.
        group_by: 'none', 'chassis', or 'polymer' — colors points/bars by group.
        metric_label: y-axis label.
        title: figure title.
        out_path: optional save path.

    Returns:
        fig
    """
    plt.rcParams.update({"font.size": 12})
    grouped = group_by in ("chassis", "polymer", "surfactant")
    gcolor, uniq = None, []
    if grouped:
        uniq = sorted(set(str(d.get(group_by) or "?") for d in items))
        cmap = plt.get_cmap("tab10")
        gcolor = {g: cmap(i % 10) for i, g in enumerate(uniq)}

    fig, axes = plt.subplots(1, 3, figsize=(18, 5.8), dpi=120)

    # --- ranking (bar) ---
    s = sorted(items, key=lambda d: d["auc"])
    bar_colors = ([gcolor[str(d.get(group_by) or "?")] for d in s]
                  if grouped else "#1F4E78")
    axes[0].barh([d["label"] for d in s], [d["auc"] for d in s], color=bar_colors)
    axes[0].set_xlabel(metric_label)
    axes[0].set_title("AUC ranking", fontweight="bold")
    axes[0].grid(True, axis="x", ls=":", alpha=0.5)
    axes[0].tick_params(axis="y", labelsize=7)

    _prop_scatter(axes[1], items, "mw_kda", "Molecular weight (kDa)", metric_label,
                  group_by, gcolor)
    axes[1].set_title("AUC vs. Molecular weight", fontweight="bold")

    _prop_scatter(axes[2], items, "charge", "Charge density (meq/g)", metric_label,
                  group_by, gcolor)
    axes[2].set_title("AUC vs. Charge density", fontweight="bold")

    if grouped and uniq:
        from matplotlib.patches import Patch
        handles = [Patch(color=gcolor[g], label=g) for g in uniq]
        fig.legend(handles=handles, title=group_by.title(), loc="lower center",
                   ncol=min(len(uniq), 6), fontsize=9, bbox_to_anchor=(0.5, -0.08))

    fig.suptitle(title, fontweight="bold", fontsize=15, y=1.02)
    fig.tight_layout()
    if out_path:
        fig.savefig(out_path, bbox_inches="tight")
    return fig

