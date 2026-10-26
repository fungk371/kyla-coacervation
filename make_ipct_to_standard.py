"""Convert an inverse-%T (opaque) curve into the equivalent STANDARD %T profile
and name each dilution/rinse phase.

Inverse %T (centrifuged supernatant): coacervate traps + sediments the
opacifier, so the supernatant CLEARS -> %T rises (a hump). The amount of
coacervate at each dilution = clearing above the opaque floor.

Standard %T (a clear shampoo): coacervate makes the sample TURBID -> %T drops
(a dip). So the same coacervation event, expressed as a standard reading, is the
INVERSE of the clearing: standard %T = 100 - (coacervation signal, normalised).

x-axis = dilution = the RINSE (left = neat product, right = progressively rinsed
with water). Phases named along it.

Output: Reports/ipct_to_standard_profile.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import make_brandon_ipct_fingerprints as B
import make_brandon_ipct_method as M

R = "Reports"
SAMPLE = ("Cassia", "GH130 LT1")     # re-clouds within window -> shows full cycle


def phases(ax, onset, peak, offset, ytop=100):
    bands = [
        (1.0, onset, "#e9ecef", "In-bottle\n(neat product)"),
        (onset, peak, "#cfe3f7", "Coacervation\nforming"),
        (peak, offset, "#fde3b3", "Redissolution\n(rinse-out)"),
        (offset, 100, "#e6f4ea", "Rinsed away\n(very dilute)"),
    ]
    for lo, hi, col, lab in bands:
        if hi > lo:
            ax.axvspan(lo, hi, color=col, alpha=0.7, zorder=0)
            ax.text(np.sqrt(lo * hi), ytop * 0.965, lab, ha="center", va="top",
                    fontsize=8, color="#333")
    ax.axvline(peak, color="#16a085", ls="--", lw=1.5)
    ax.text(peak, ytop * 0.5, "  peak coacervation\n  (max deposition)",
            color="#0e6b57", fontsize=8.5, rotation=90, va="center")


def main():
    poly, ch = SAMPLE
    path, tr = next((p, t) for (pp, cc, p, t) in B.SAMPLES if pp == poly and cc == ch)
    x, y = B.curve(path, tr)
    cx, cy, _ = B.clean_curve(x, y)
    fx, fy = B.smooth_hybrid(cx, cy)
    floor = float(np.min(fy[:max(3, len(fy) // 10)]))
    m = fx <= 100.0
    fxw, fyw = fx[m], fy[m]
    h = M.first_hump(fxw, fyw, floor)
    onset, peak, offset = h["onset"], h["peak_dil"], (h["offset"] if not h["censored"] else 100)

    # coacervation signal + standard-%T-equivalent (flip to a dip)
    sig = np.clip(fyw - floor, 0, None)
    turb = 100.0 * sig / (sig.max() or 1.0)
    std = 100.0 - turb

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(15.5, 6.4))

    # ---- LEFT: inverse %T as measured ----
    phases(axL, onset, peak, offset)
    axL.plot(fxw, fyw, "-", lw=2.8, color="#1f4e79", zorder=3)
    axL.axhline(floor, ls=":", color="#c0392b", lw=1)
    axL.annotate("supernatant CLEARS as coacervate\ntraps + sediments the opacifier",
                 xy=(peak, h["peak_pct"]), xytext=(peak * 1.3, 40),
                 fontsize=8.5, color="#1f4e79",
                 arrowprops=dict(arrowstyle="->", color="#1f4e79"))
    B._dil_axis(axL, 1, 100, fs=9); axL.set_xlim(1, 100); axL.set_ylim(0, 100)
    axL.set_xlabel("Dilution (Water:Shampoo, 1:X)   \u2014  RINSE  \u2192")
    axL.set_ylabel("%T (centrifuged supernatant)")
    axL.set_title("Inverse %T (as measured, opaque)\ncoacervation = clearing hump UP",
                  fontweight="bold", fontsize=11)

    # ---- RIGHT: converted to standard %T profile ----
    phases(axR, onset, peak, offset)
    axR.plot(fxw, std, "-", lw=2.8, color="#8e44ad", zorder=3)
    axR.annotate("coacervate makes it TURBID\n-> %T dips (standard reading)",
                 xy=(peak, std[int(np.argmin(np.abs(fxw - peak)))]),
                 xytext=(peak * 1.3, 60), fontsize=8.5, color="#8e44ad",
                 arrowprops=dict(arrowstyle="->", color="#8e44ad"))
    B._dil_axis(axR, 1, 100, fs=9); axR.set_xlim(1, 100); axR.set_ylim(0, 100)
    axR.set_xlabel("Dilution (Water:Shampoo, 1:X)   \u2014  RINSE  \u2192")
    axR.set_ylabel("%T (equivalent standard reading)")
    axR.set_title("Converted to a STANDARD %T profile\ncoacervation = turbidity DIP DOWN",
                  fontweight="bold", fontsize=11)

    fig.suptitle(f"{poly} ({ch}) \u2014 same coacervation, two readings.  "
                 "Moving right = adding water = the rinse.",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(f"{R}/ipct_to_standard_profile.png", dpi=150)
    plt.close(fig)
    print(f"wrote {R}/ipct_to_standard_profile.png")


if __name__ == "__main__":
    main()
