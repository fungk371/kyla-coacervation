"""Reference-convention (Eric Johnson) view of our centrifuged inverse %T.

Since we read the CENTRIFUGED SUPERNATANT, coacervation = %T rises UP (coacervate
captures opacifier + sediments it -> supernatant clears -> %T hump). Height of
hump = AMOUNT of phase separation; width of elevated region = WIDTH of the
coacervate-forming dilution window (matches the BC-1 reference slide).

Left  : full range (1:1 -> 1:539) - the hump is buried because we dilute far past it.
Right : zoomed to 1:1 -> 1:50 (the reference range) with amount + width arrows.

Demo on GH130 LT1 (Cassia / NH3196 / Nat Caready / Nat Clear).
Output: Reports/ipct_reference_view.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator, FuncFormatter
import numpy as np

from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import dilution_ratio
from make_dextran_figs import clean_curve
from make_dextran_timepoint_analysis import smooth_hybrid

R = "Reports"
_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))
F_CTRL = r"raw_data\Opaque_GH130_3196_and_Nat_Caready.txt"
F_CASNC = r"raw_data\GH130_Cassia_NatClear_200uL.txt"
SAMPLES = [
    ("Cassia", F_CASNC, 1, "#16a085"),
    ("NH3196 (ctrl)", F_CTRL, 1, "#2E75B6"),
    ("Nat Caready", F_CTRL, 2, "#e67e22"),
    ("Nat Clear", F_CASNC, 2, "#B9770A"),
]
ZTICKS = [1, 2, 3, 5, 10, 20, 30, 50]


def curve(path, trough, tp=0):
    df = annotate_concentration(parse_kinetic_plate_file(path))
    t = min(sorted(df["timepoint_minutes"].unique()), key=lambda z: abs(z - tp))
    sel = df[(df["trough"] == trough) & (df["timepoint_minutes"] == t)].dropna(
        subset=["formula_fraction"]).sort_values("formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(sel["formula_fraction"].to_numpy(float)), float)
    y = sel["transmission_pct"].to_numpy(float)
    o = np.argsort(x)
    return x[o], y[o]


def smoothed(path, trough):
    x, y = curve(path, trough)
    cx, cy, _ = clean_curve(x, y)
    fx, fy = smooth_hybrid(cx, cy)
    return fx, fy


def hump_metrics(fx, fy, dmax=50.0):
    """Reference convention: floor, peak (amount=peak-floor), coacervate width."""
    m = fx <= dmax
    x, y = fx[m], fy[m]
    if len(x) < 4:
        return None
    floor = float(np.min(y))
    ip = int(np.argmax(y)); peak = float(y[ip]); peak_dil = float(x[ip])
    amount = peak - floor
    thr = floor + 0.5 * amount
    above = x[y >= thr]
    onset = float(above.min()) if above.size else peak_dil
    upper = float(above.max()) if above.size else peak_dil
    width_dec = np.log10(upper / max(onset, 1e-9))
    # area above floor over log-dilution = total phase separation
    lx = np.log10(np.clip(x, 1e-9, None))
    area = float(_trapz(np.clip(y - floor, 0, None), lx))
    return dict(floor=floor, peak=peak, peak_dil=peak_dil, amount=amount,
                onset=onset, upper=upper, width_dec=width_dec, area=area)


def _axis(ax, xmin, xmax):
    ax.set_xscale("log")
    tk = [t for t in ZTICKS if xmin * 0.9 <= t <= xmax * 1.15]
    ax.set_xticks(tk); ax.xaxis.set_major_formatter(FuncFormatter(lambda v, p: f"1:{v:g}"))
    ax.set_xlim(max(xmin * 0.9, 0.9), xmax * 1.1)


def main():
    fig, axes = plt.subplots(1, 2, figsize=(16, 6.4))
    print(f"{'polymer':16s} {'floor':>6s} {'peak':>13s} {'amount':>7s} "
          f"{'onset':>7s} {'width(dec)':>10s} {'area':>7s}")
    lo_full, hi_full = [], []
    for name, path, tr, col in SAMPLES:
        fx, fy = smoothed(path, tr)
        lo_full.append(fx.min()); hi_full.append(fx.max())
        axes[0].plot(fx, fy, "-", color=col, lw=2.2, label=name)
        m = fx <= 50
        axes[1].plot(fx[m], fy[m], "-", color=col, lw=2.4, label=name)
        met = hump_metrics(fx, fy)
        if met:
            print(f"{name:16s} {met['floor']:6.1f} "
                  f"{met['peak']:.0f}%@1:{met['peak_dil']:<6.0f} {met['amount']:7.1f} "
                  f"1:{met['onset']:<5.0f} {met['width_dec']:10.2f} {met['area']:7.1f}")

    # reference-style arrows on the strongest (Cassia) in the zoom panel
    fx, fy = smoothed(F_CASNC, 1)
    met = hump_metrics(fx, fy)
    if met:
        col = "#16a085"
        # yellow AMOUNT arrow (peak height above floor)
        axes[1].annotate("", xy=(met["peak_dil"], met["peak"]),
                         xytext=(met["peak_dil"], met["floor"]),
                         arrowprops=dict(arrowstyle="<->", color="#e8a800", lw=3))
        axes[1].text(met["peak_dil"] * 1.1, (met["peak"] + met["floor"]) / 2,
                     f"AMOUNT\n(phase sep)\n\u2248 {met['amount']:.0f} %T",
                     color="#a97a00", fontsize=10, fontweight="bold", va="center")
        # green WIDTH arrow (coacervate-forming region)
        yb = met["floor"] + 0.5 * met["amount"]
        axes[1].annotate("", xy=(met["onset"], yb), xytext=(met["upper"], yb),
                         arrowprops=dict(arrowstyle="<->", color="#2ecc40", lw=3))
        axes[1].text(np.sqrt(met["onset"] * met["upper"]), yb + 4,
                     f"WIDTH of coacervate region \u2248 {met['width_dec']:.2f} dec",
                     color="#1f9e2e", fontsize=10, fontweight="bold", ha="center")

    axes[0].set_title("Full range (1:1 \u2192 1:539) \u2014 hump buried by over-dilution",
                      fontweight="bold")
    axes[1].set_title("Zoom to 1:1 \u2192 1:50 (reference range) \u2014 coacervation = %T HUMP UP",
                      fontweight="bold")
    _axis(axes[0], min(lo_full), max(hi_full))
    _axis(axes[1], 1, 50)
    for ax in axes:
        ax.set_ylim(0, 100)
        ax.set_xlabel("Dilution (Water:Shampoo, 1:X)")
        ax.set_ylabel("%T (centrifuged supernatant)")
        ax.grid(True, which="both", ls=":", alpha=0.5)
        ax.legend(fontsize=9)
    fig.suptitle("Inverse %T in the Eric Johnson convention \u2014 GH130 LT1 "
                 "(centrifuged supernatant, t=0)", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(f"{R}/ipct_reference_view.png", dpi=150); plt.close(fig)
    print(f"\nwrote {R}/ipct_reference_view.png")


if __name__ == "__main__":
    main()
