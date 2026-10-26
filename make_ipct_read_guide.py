"""How to read inverse %T: raw view vs the flipped 'coacervation signal' view.

LEFT  = inverse %T as measured (centrifuged supernatant): coacervation lifts %T
        off the opaque floor into a hump; annotated with floor / onset / height
        (amount) / width (rinse breadth) / re-cloud depth.
RIGHT = the same data flipped to a 'coacervation signal' = (%T - floor), which
        points UP like a standard-%T dip turned over: peak = amount, shaded area
        = total coacervation, x = rinse phase. Makes clear & opaque comparable.

Output: Reports/ipct_read_guide.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import make_brandon_ipct_fingerprints as B

R = "Reports"
EXEMPLARS = [("Cassia", "GH130 LT1"), ("NH3196", "BC128o M")]


def main():
    fig, axes = plt.subplots(len(EXEMPLARS), 2, figsize=(14.5, 5.4 * len(EXEMPLARS)),
                             squeeze=False)
    for row, (poly, ch) in enumerate(EXEMPLARS):
        path, tr = next((p, t) for (pp, cc, p, t) in B.SAMPLES
                        if pp == poly and cc == ch)
        r = B.fingerprint(path, tr)
        fx, fy = r["fx"], r["fy"]
        floor = r["floor"]
        col = B.POLY_COL[poly]

        # -------- LEFT: raw inverse %T, annotated --------
        axL = axes[row][0]
        axL.plot(r["rawx"], r["rawy"], "o", ms=2.4, alpha=0.22, color="#999")
        axL.plot(fx, fy, "-", lw=2.6, color=col)
        axL.axhline(floor, ls="--", color="#c0392b", lw=1.2)
        axL.text(fx.min(), floor + 3, f"opaque floor \u2248 {floor:.0f}%T",
                 fontsize=8.5, color="#c0392b")
        if r["onset"]:
            axL.axvline(r["onset"], ls=":", color="#555", lw=1)
            axL.text(r["onset"], 4, f" onset\n 1:{r['onset']:.0f}", fontsize=8, color="#555")
        # height arrow (amount)
        axL.annotate("", xy=(r["peak_dil"], r["peak_pct"]),
                     xytext=(r["peak_dil"], floor),
                     arrowprops=dict(arrowstyle="<->", color="#16a085", lw=2.2))
        axL.text(r["peak_dil"] * 1.05, (floor + r["peak_pct"]) / 2,
                 f"height {r['height']:.0f}\n= amount", fontsize=8.5, color="#0e6b57")
        # width band (rinse breadth)
        if r["w_hi"] and r["w_lo"] and r["w_hi"] > r["w_lo"]:
            axL.axvspan(r["w_lo"], r["w_hi"], color=col, alpha=0.10)
            axL.text(np.sqrt(r["w_lo"] * r["w_hi"]), 92,
                     f"width {r['width']:.1f} dec", fontsize=8, color=col, ha="center")
        # re-cloud depth
        if r["redis_dil"] and r["redis_depth"] > 1:
            j = int(np.argmin(np.abs(fx - r["redis_dil"])))
            axL.annotate("", xy=(r["redis_dil"], fy[j]),
                         xytext=(r["redis_dil"], fy[j] + r["redis_depth"]),
                         arrowprops=dict(arrowstyle="<->", color="#8E44AD", lw=2))
            axL.text(r["redis_dil"] * 1.05, fy[j] + r["redis_depth"] / 2,
                     f"re-cloud {r['redis_depth']:.0f}\n(redissolves)",
                     fontsize=8, color="#8E44AD")
        B._dil_axis(axL, r["cx"].min(), r["cx"].max(), fs=8)
        axL.set_ylim(0, 100)
        axL.set_ylabel("%T (centrifuged supernatant)")
        axL.set_title(f"{poly} ({ch}) \u2014 inverse %T as measured\n"
                      "coacervation = clearing hump UP", fontweight="bold", fontsize=10.5)
        axL.grid(True, which="both", ls=":", alpha=0.4)

        # -------- RIGHT: flipped coacervation signal (reads like standard %T) --------
        axR = axes[row][1]
        sig = np.clip(fy - floor, 0, None)
        axR.plot(fx, sig, "-", lw=2.6, color=col)
        axR.fill_between(fx, 0, sig, color=col, alpha=0.18)
        if r["onset"]:
            axR.axvline(r["onset"], ls=":", color="#555", lw=1)
        axR.plot(r["peak_dil"], r["height"], "o", color=col, ms=7)
        axR.text(r["peak_dil"] * 1.05, r["height"],
                 f"peak = amount ({r['height']:.0f})", fontsize=8.5, color=col, va="center")
        axR.text(0.02, 0.92, f"shaded area = AUC {r['auc']:.0f}\n= total coacervation",
                 transform=axR.transAxes, fontsize=8.5, color="#333")
        B._dil_axis(axR, r["cx"].min(), r["cx"].max(), fs=8)
        axR.set_ylim(0, 100)
        axR.set_ylabel("Coacervation signal  (%T \u2212 floor)")
        axR.set_title(f"{poly} ({ch}) \u2014 flipped 'coacervation signal'\n"
                      "peak = amount, area = total, x = rinse phase",
                      fontweight="bold", fontsize=10.5)
        axR.grid(True, which="both", ls=":", alpha=0.4)

    fig.suptitle("Two ways to read inverse %T \u2014 raw hump (left) vs coacervation-signal "
                 "transform that reads like standard %T (right)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(f"{R}/ipct_read_guide.png", dpi=150)
    plt.close(fig)
    print(f"wrote {R}/ipct_read_guide.png")


if __name__ == "__main__":
    main()
