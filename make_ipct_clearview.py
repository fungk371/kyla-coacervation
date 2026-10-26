"""'Clear-read equivalent' view of inverse %T, for formulators.

Opaque inverse %T is confusing (starts dark, clarifies, then re-clouds). This
transforms it so it reads like a normal CLEAR-shampoo %T dilution curve, where
coacervation shows as a DIP from a clear (100%T) baseline.

Transform (per sample, on the smoothed curve vs log-dilution):
  baseline   = running max of %T  (the 'best clarity reached' = base-opacity
               clearing; monotonic, ignores the coacervation re-turbidity)
  coac_turb  = baseline - %T      (>=0; the extra turbidity from coacervate only)
  clear_%T   = 100 - coac_turb     (reads clear, dips at the coacervation window)

This isolates coacervation from the opaque base, so DEPTH = amount and WIDTH =
how broad the coacervation window is are directly readable.

Demo on GH130 LT1 (Cassia / NH3196 / Nat Caready / Nat Clear).
Output: Reports/ipct_clearview_gh130.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import dilution_ratio
from make_dextran_figs import clean_curve
from make_dextran_timepoint_analysis import smooth_hybrid, _dil_axis

R = "Reports"
_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))

F_CTRL = r"raw_data\Opaque_GH130_3196_and_Nat_Caready.txt"   # T1 NH3196, T2 Nat Caready
F_CASNC = r"raw_data\GH130_Cassia_NatClear_200uL.txt"        # T1 Cassia, T2 Nat Clear
SAMPLES = [
    ("Cassia", F_CASNC, 1, "#16a085"),
    ("NH3196 (ctrl)", F_CTRL, 1, "#8a8f98"),
    ("Nat Caready", F_CTRL, 2, "#e67e22"),
    ("Nat Clear", F_CASNC, 2, "#B9770A"),
]


def curve(path, trough, tp=0):
    df = annotate_concentration(parse_kinetic_plate_file(path))
    t = min(sorted(df["timepoint_minutes"].unique()), key=lambda z: abs(z - tp))
    sel = df[(df["trough"] == trough) & (df["timepoint_minutes"] == t)].dropna(
        subset=["formula_fraction"]).sort_values("formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(sel["formula_fraction"].to_numpy(float)), float)
    y = sel["transmission_pct"].to_numpy(float)
    o = np.argsort(x)
    return x[o], y[o]


def clear_view(path, trough):
    x, y = curve(path, trough)
    cx, cy, _ = clean_curve(x, y)
    fx, fy = smooth_hybrid(cx, cy)
    baseline = np.maximum.accumulate(fy)          # base-opacity clearing envelope
    coac = np.clip(baseline - fy, 0, None)        # coacervation-only turbidity
    clear = 100.0 - coac                          # reads like a clear-%T sample
    lx = np.log10(np.clip(fx, 1e-9, None))
    amount = float(_trapz(coac, lx))              # area = amount of coacervation
    # width = decades where coac >= half of its peak (FWHM)
    width = 0.0; peak = float(coac.max())
    if peak > 2:
        mask = coac >= 0.5 * peak
        if mask.any():
            width = float(lx[mask].max() - lx[mask].min())
    peak_dil = float(fx[int(np.argmax(coac))]) if peak > 0 else np.nan
    return dict(fx=fx, fy=fy, clear=clear, coac=coac, amount=amount,
                width=width, peak=peak, peak_dil=peak_dil, cx=cx)


def main():
    fig, axes = plt.subplots(1, 2, figsize=(16, 6.2))
    xs_lo, xs_hi = [], []
    print(f"{'polymer':16s} {'coac amount':>11s} {'width(dec)':>10s} {'peak turb':>10s} {'@dil':>8s}")
    rows = []
    for name, path, tr, col in SAMPLES:
        r = clear_view(path, tr)
        rows.append((name, r, col))
        axes[0].plot(r["fx"], r["fy"], "-", color=col, lw=2.3, label=name)
        axes[1].plot(r["fx"], r["clear"], "-", color=col, lw=2.3, label=name)
        xs_lo.append(r["cx"].min()); xs_hi.append(r["cx"].max())
        pk = f"1:{r['peak_dil']:.0f}" if r["peak"] > 2 else "--"
        print(f"{name:16s} {r['amount']:11.2f} {r['width']:10.2f} {r['peak']:10.1f} {pk:>8s}")

    axes[0].set_title("As measured \u2014 inverse %T (opaque)", fontweight="bold")
    axes[0].set_ylabel("%T (upper phase)")
    axes[1].set_title("Clear-read equivalent \u2014 coacervation = a DIP\n"
                      "(base opacity removed; reads like a clear shampoo)", fontweight="bold")
    axes[1].set_ylabel("Equivalent clear %T")
    # annotate the deepest (Cassia) with width/amount
    best = max(rows, key=lambda z: z[1]["amount"])
    bn, br, bc = best
    if br["peak"] > 2:
        axes[1].annotate(f"{bn}\nwidth {br['width']:.2f} dec\namount {br['amount']:.0f}",
                         xy=(br["peak_dil"], 100 - br["peak"]),
                         xytext=(br["peak_dil"] / 6, 100 - br["peak"] - 6),
                         fontsize=10, fontweight="bold", color=bc,
                         arrowprops=dict(arrowstyle="->", color=bc))
    for ax in axes:
        _dil_axis(ax, min(xs_lo), max(xs_hi), fs=9)
        ax.set_ylim(0, 100)
        ax.set_xlabel("Dilution (1:X)   \u2014   rinse \u2192")
        ax.grid(True, which="both", ls=":", alpha=0.5)
        ax.legend(fontsize=9)
    fig.suptitle("Inverse %T made formulator-friendly \u2014 GH130 LT1 (0.25% polymer, t=0)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(f"{R}/ipct_clearview_gh130.png", dpi=150); plt.close(fig)
    print(f"\nwrote {R}/ipct_clearview_gh130.png")


if __name__ == "__main__":
    main()
