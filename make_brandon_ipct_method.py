"""Method-faithful inverse-%T reading (Eric Johnson / SWIC convention).

Mechanism: coacervate traps the opacifier particles and pulls them down on
centrifugation, so a CLEARER supernatant (higher %T) = MORE coacervate. The
method reports two things off the FIRST hump:
    * HEIGHT of the hump  = amount of phase separation (coacervate)
    * WIDTH of the first hump (onset -> return) = width of coacervate-forming region

Two views (per user): zoomed 1:1-1:100 and full dilution range.

Outputs (Reports/):
  brandon_ipct_method_overlay_zoom.png   (1:1-1:100, both chassis)
  brandon_ipct_method_overlay_full.png   (full range, both chassis)
  brandon_ipct_method_widthheight.png    (the 2 method readouts: height + width)
  brandon_ipct_method_annotated.png      (reference-style: green width, yellow height)
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.signal import find_peaks

import make_brandon_ipct_fingerprints as B

R = "Reports"
POLY_COL, CH_COL, POLY_ORDER = B.POLY_COL, B.CH_COL, B.POLY_ORDER


def first_hump(fx, fy, floor):
    """Onset / peak / offset of the FIRST coacervate-forming hump."""
    amp = float(np.max(fy) - floor) or 1.0
    peaks, _ = find_peaks(fy, prominence=max(2.0, 0.08 * amp))
    pi = int(peaks[0]) if len(peaks) else int(np.argmax(fy))
    peak_pct = float(fy[pi]); peak_dil = float(fx[pi])
    a1 = peak_pct - floor or 1.0
    thr = floor + 0.15 * a1
    onset_i = 0
    for i in range(pi, -1, -1):
        if fy[i] <= thr:
            onset_i = i; break
    offset_i, censored = len(fy) - 1, True
    for i in range(pi, len(fy)):
        if fy[i] <= thr:
            offset_i, censored = i, False; break
    if censored:                       # never returns: use first re-cloud trough
        troughs, _ = find_peaks(-fy[pi:], prominence=max(2.0, 0.05 * amp))
        if len(troughs):
            offset_i, censored = pi + int(troughs[0]), False
    onset, offset = float(fx[onset_i]), float(fx[offset_i])
    return dict(onset=onset, peak_dil=peak_dil, peak_pct=peak_pct, offset=offset,
                height=max(0.0, peak_pct - floor),
                width_dec=float(np.log10(offset / onset)) if offset > onset > 0 else 0.0,
                onset_i=onset_i, pi=pi, offset_i=offset_i, censored=censored)


def analyze():
    res = {}
    for poly, ch, path, tr in B.SAMPLES:
        x, y = B.curve(path, tr)
        cx, cy, _ = B.clean_curve(x, y)
        fx, fy = B.smooth_hybrid(cx, cy)
        floor = float(np.min(fy[:max(3, len(fy) // 10)]))
        # measure the FIRST hump in the coacervation window (<=1:100); the far
        # dilute tail clears by trivial dilution, so it is excluded from metrics.
        m = fx <= 100.0
        h = first_hump(fx[m], fy[m], floor)
        res[(poly, ch)] = dict(fx=fx, fy=fy, rawx=x, rawy=y, cx=cx, floor=floor, **h)
    return res


def _overlay(res, xlim, fname, title):
    fig, axes = plt.subplots(1, 2, figsize=(17, 6.6))
    for ax, ch in zip(axes, ["BC128o M", "GH130 LT1"]):
        for poly in POLY_ORDER:
            if (poly, ch) not in res:
                continue
            r = res[(poly, ch)]
            ax.plot(r["fx"], r["fy"], "-", color=POLY_COL[poly], lw=2.4, label=poly)
        B._dil_axis(ax, xlim[0], xlim[1], fs=9)
        ax.set_xlim(xlim[0], xlim[1])
        ax.set_ylim(0, 100)
        ax.set_xlabel("Dilution (Water:Shampoo, 1:X)  \u2014  rinse \u2192")
        ax.set_ylabel("%T (centrifuged supernatant)")
        ax.grid(True, which="both", ls=":", alpha=0.5)
        ax.set_title(f"{ch} chassis", fontweight="bold")
        ax.legend(fontsize=8.5, ncol=2)
    fig.suptitle(title, fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{R}/{fname}", dpi=150); plt.close(fig)
    print(f"wrote {R}/{fname}")


def _widthheight(res):
    fig, axes = plt.subplots(1, 2, figsize=(16, 5.8))
    xp = np.arange(len(POLY_ORDER)); w = 0.4
    for ax, key, ylab, ttl in [
        (axes[0], "height", "Hump height (%T above floor)",
         "AMOUNT of phase separation \u2014 hump HEIGHT"),
        (axes[1], "width_dec", "First-hump width (decades of dilution)",
         "WIDTH of coacervate-forming region \u2014 first hump"),
    ]:
        for kk, ch in enumerate(["BC128o M", "GH130 LT1"]):
            vals = [float(res[(p, ch)][key]) if (p, ch) in res else 0.0 for p in POLY_ORDER]
            ax.bar(xp + (kk - 0.5) * w, vals, w, color=CH_COL[ch], edgecolor="white", label=ch)
            for i, v in enumerate(vals):
                if v:
                    ax.text(i + (kk - 0.5) * w, v, f"{v:.0f}" if key == "height" else f"{v:.1f}",
                            ha="center", va="bottom", fontsize=7)
        ax.set_xticks(xp); ax.set_xticklabels(POLY_ORDER, rotation=30, ha="right", fontsize=8)
        ax.set_ylabel(ylab); ax.set_title(ttl, fontweight="bold", fontsize=10.5)
        ax.grid(True, axis="y", ls=":", alpha=0.5); ax.legend()
    fig.suptitle("The two method readouts \u2014 amount (height) & width of coacervation (t=0)",
                 fontsize=12.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(f"{R}/brandon_ipct_method_widthheight.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/brandon_ipct_method_widthheight.png")


def _annotated(res):
    exemplars = [("Cassia", "GH130 LT1"), ("NH3196", "BC128o M")]
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.6))
    for ax, (poly, ch) in zip(axes, exemplars):
        r = res[(poly, ch)]
        fx, fy, floor = r["fx"], r["fy"], r["floor"]
        col = POLY_COL[poly]
        ax.plot(r["rawx"], r["rawy"], "o", ms=2.4, alpha=0.2, color="#999")
        ax.plot(fx, fy, "-", lw=2.6, color=col)
        # GREEN width arrow (first-hump onset -> offset) at ~35% of peak height
        yline = floor + 0.35 * (r["peak_pct"] - floor)
        ax.annotate("", xy=(r["offset"], yline), xytext=(r["onset"], yline),
                    arrowprops=dict(arrowstyle="<->", color="#2ca02c", lw=3))
        ax.text(np.sqrt(r["onset"] * r["offset"]), yline + 3,
                f"width of coacervate-forming region\n1:{r['onset']:.0f} \u2192 1:{r['offset']:.0f}"
                + ("  (\u2265, persists)" if r["censored"] else ""),
                color="#1e7d1e", fontsize=8.5, ha="center", fontweight="bold")
        # YELLOW height arrow (amount)
        ax.annotate("", xy=(r["peak_dil"], r["peak_pct"]), xytext=(r["peak_dil"], floor),
                    arrowprops=dict(arrowstyle="<->", color="#e8a200", lw=3))
        ax.text(r["peak_dil"] * 1.05, (floor + r["peak_pct"]) / 2,
                f"amount of\nphase separation\n(height {r['height']:.0f}%T)",
                color="#b07d00", fontsize=8.5, va="center")
        B._dil_axis(ax, 1, 100, fs=8); ax.set_xlim(1, 100); ax.set_ylim(0, 100)
        ax.set_xlabel("Dilution (Water:Shampoo, 1:X)")
        ax.set_ylabel("%T (centrifuged supernatant)")
        ax.set_title(f"{poly} ({ch})", fontweight="bold")
        ax.grid(True, which="both", ls=":", alpha=0.4)
    fig.suptitle("How to read inverse %T (Eric Johnson / SWIC): clearer supernatant = more coacervate\n"
                 "green = WIDTH of coacervate-forming region   |   yellow = AMOUNT (hump height)",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(f"{R}/brandon_ipct_method_annotated.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/brandon_ipct_method_annotated.png")


def main():
    res = analyze()
    _overlay(res, (1, 100), "brandon_ipct_method_overlay_zoom.png",
             "Brandon inverse %T \u2014 coacervation region (1:1\u20131:100), clearer = more coacervate")
    _overlay(res, (1, 540), "brandon_ipct_method_overlay_full.png",
             "Brandon inverse %T \u2014 full dilution range (1:1\u20131:539)")
    _widthheight(res)
    _annotated(res)
    print(f"\n{'polymer':13s} {'chassis':10s} {'onset':>7s} {'peak':>10s} "
          f"{'offset':>8s} {'height':>6s} {'width_dec':>9s}")
    for poly, ch, _p, _t in B.SAMPLES:
        r = res[(poly, ch)]
        cz = "\u2265" if r["censored"] else " "
        print(f"{poly:13s} {ch:10s} 1:{r['onset']:<5.0f} {r['peak_pct']:.0f}@1:{r['peak_dil']:<4.0f} "
              f"{cz}1:{r['offset']:<5.0f} {r['height']:6.0f} {r['width_dec']:9.2f}")


if __name__ == "__main__":
    main()
