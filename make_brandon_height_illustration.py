"""Illustrate the hump-height definitions ON the actual inverse-%T curve.

Shows, for a strong coacervator and a weak one, what the 'floor' is, what part
gets subtracted, and where peak / p95 / height / AUC live -- so 'removing the
floor' is visually obvious.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import make_brandon_ipct_fingerprints as B

R = "Reports"


def get(poly, ch):
    for p, c, path, tr in B.SAMPLES:
        if p == poly and c == ch:
            return path, tr
    raise KeyError((poly, ch))


def panel(ax, poly, ch):
    path, tr = get(poly, ch)
    x, y = B.curve(path, tr)
    cx, cy, _ = B.clean_curve(x, y)
    fx, fy = B.smooth_hybrid(cx, cy)
    k = max(3, len(fy) // 10)
    floor = float(np.min(fy[:k]))
    peak = float(np.max(fy)); pi = int(np.argmax(fy))
    peak_dil = float(fx[pi])
    p95 = float(np.percentile(fy, 95))

    # raw + smoothed curve
    ax.plot(fx, fy, "-", color="#1f4e78", lw=2.6, zorder=4, label="%T curve (smoothed)")
    ax.plot(x, y, "o", color="#1f4e78", ms=3, alpha=0.25, zorder=3)

    # floor band = the part we REMOVE (subtract)
    ax.axhspan(0, floor, color="#9aa4ad", alpha=0.22, zorder=0)
    ax.axhline(floor, color="#5a6470", lw=1.4, ls="-", zorder=2)
    ax.text(fx.min(), floor / 2, "  FLOOR (opaque baseline)\n  \u2014 this part is subtracted",
            color="#3d454e", fontsize=8.5, va="center", zorder=5)

    # area above floor = AUC
    ax.fill_between(fx, floor, fy, where=(fy > floor), color="#2E75B6",
                    alpha=0.12, zorder=1, label="area above floor = AUC")

    # peak & p95
    ax.axhline(peak, color="#c0392b", lw=1.0, ls=":", zorder=2)
    ax.plot([peak_dil], [peak], "o", color="#c0392b", ms=8, zorder=6)
    ax.text(peak_dil, peak + 1.5, "peak", color="#c0392b", fontsize=9,
            ha="center", fontweight="bold")
    ax.axhline(p95, color="#e67e22", lw=1.0, ls="--", zorder=2)
    ax.text(fx.max(), p95 - 2.2, "p95 (robust peak)  ", color="#b9600f",
            fontsize=8, ha="right", va="top")

    # HEIGHT arrow = peak - floor (what we measure)
    xa = peak_dil * 0.45
    ax.annotate("", xy=(xa, peak), xytext=(xa, floor),
                arrowprops=dict(arrowstyle="<|-|>", color="#c0392b", lw=2.4), zorder=6)
    ax.text(xa * 0.92, (peak + floor) / 2,
            f"HEIGHT\n= peak \u2212 floor\n= {peak - floor:.0f} %T",
            color="#c0392b", fontsize=9, ha="right", va="center", fontweight="bold")

    lo, hi = float(min(cx.min(), x.min())), float(max(cx.max(), x.max()))
    B._dil_axis(ax, lo, hi, fs=8)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Dilution (Water:Shampoo, 1:X)  \u2014  rinse \u2192")
    ax.set_ylabel("%T (centrifuged supernatant)")
    ax.set_title(f"{poly} / {ch.split()[0]}", fontweight="bold")
    ax.grid(True, which="both", ls=":", alpha=0.4)
    ax.legend(fontsize=8, loc="upper left")


def main():
    fig, axes = plt.subplots(1, 2, figsize=(16, 6.8))
    panel(axes[0], "Nat Clear", "BC128o M")   # strong coacervator
    panel(axes[1], "Polyquat-6", "BC128o M")  # weak coacervator
    fig.suptitle("What the hump-height definitions measure \u2014 'removing the floor' = "
                 "subtracting the opaque baseline the coacervate must clear above",
                 fontsize=12.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = f"{R}/brandon_height_illustration.png"
    fig.savefig(out, dpi=150); plt.close(fig)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
