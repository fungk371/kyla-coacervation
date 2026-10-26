"""Best ILS performers + the design direction to make them better.

Left  : formulas ranked by ILS conditioning composite (who is best today).
Right : the 'conditioning frontier' - coacervate amount (noise-robust hump
        height, p95 above floor) vs conditioning. Same-polymer BC128o/GH130
        pairs are linked to show the chassis lever; the fit line is the
        frontier; the arrow marks the design direction (raise coacervate amount
        in the persistent BC128o chassis) and the shaded band is the headroom
        above today's best.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import make_brandon_ipct_fingerprints as B

R = "Reports"
CH_COL = {"BC128o M": "#2E75B6", "GH130 LT1": "#16a085"}
CH_MARK = {"BC128o M": "o", "GH130 LT1": "s"}
COND = ["wet_slip", "detangle_wide", "detangle_fine", "smooth_surface",
        "smooth_interfiber", "moisturized"]


def amount_p95(path, tr):
    x, y = B.curve(path, tr)
    cx, cy, _ = B.clean_curve(x, y)
    fx, fy = B.smooth_hybrid(cx, cy)
    floor = float(np.min(fy[:max(3, len(fy) // 10)]))
    return max(0.0, float(np.percentile(fy, 95)) - floor)


def main():
    amt = {}
    for poly, ch, path, tr in B.SAMPLES:
        amt[(poly, ch)] = amount_p95(path, tr)

    ils = pd.read_csv(r"raw_data\brandon_ils_detail.csv")
    ils["amount"] = ils.apply(lambda s: amt.get((s["polymer"], s["chassis"]), np.nan), axis=1)
    ils["conditioning"] = ils[COND].mean(axis=1)
    ils["label"] = ils["polymer"] + " / " + ils["chassis"].str.split().str[0]

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(16, 7.2),
                                   gridspec_kw={"width_ratios": [1, 1.25]})

    # ---------- LEFT: ranked conditioning ----------
    d = ils.sort_values("conditioning")
    colors = [CH_COL[c] for c in d["chassis"]]
    axL.barh(range(len(d)), d["conditioning"], color=colors, edgecolor="white")
    axL.set_yticks(range(len(d)))
    axL.set_yticklabels(d["label"], fontsize=8.5)
    for i, v in enumerate(d["conditioning"]):
        axL.text(v + 0.03, i, f"{v:.1f}", va="center", fontsize=8)
    # highlight the top 3
    for i in range(len(d) - 3, len(d)):
        axL.get_yticklabels()[i].set_fontweight("bold")
    axL.set_xlim(0, 10.5)
    axL.set_xlabel("ILS conditioning composite (mean of slip, detangle, smooth, moisturized)")
    axL.set_title("Best performers today (by ILS conditioning)", fontweight="bold", fontsize=11)
    axL.grid(True, axis="x", ls=":", alpha=0.5)
    axL.legend(handles=[plt.Rectangle((0, 0), 1, 1, fc=CH_COL["BC128o M"], label="BC128o M"),
                        plt.Rectangle((0, 0), 1, 1, fc=CH_COL["GH130 LT1"], label="GH130 LT1")],
               fontsize=9, loc="lower right")

    # ---------- RIGHT: conditioning frontier ----------
    # link same-polymer chassis pairs
    for poly in ils["polymer"].unique():
        sub = ils[ils.polymer == poly].sort_values("amount")
        if len(sub) == 2:
            axR.plot(sub["amount"], sub["conditioning"], "-", color="#b0b0b0",
                     lw=1.0, alpha=0.7, zorder=1)
    for _, r in ils.iterrows():
        axR.scatter(r["amount"], r["conditioning"], s=90, zorder=3,
                    color=CH_COL[r["chassis"]], marker=CH_MARK[r["chassis"]],
                    edgecolor="white", linewidth=0.8)

    # frontier fit
    x, yv = ils["amount"].values, ils["conditioning"].values
    m = np.isfinite(x) & np.isfinite(yv)
    b1, b0 = np.polyfit(x[m], yv[m], 1)
    rr = np.corrcoef(x[m], yv[m])[0, 1]
    xs = np.linspace(x[m].min(), x[m].max(), 50)
    axR.plot(xs, b0 + b1 * xs, "--", color="#c0392b", lw=2,
             label=f"conditioning frontier (r={rr:+.2f})")

    # label top-3 performers
    top = ils.sort_values("conditioning").tail(3)
    for _, r in top.iterrows():
        axR.annotate(r["label"], (r["amount"], r["conditioning"]),
                     textcoords="offset points", xytext=(8, -4), fontsize=8.5,
                     fontweight="bold")

    # headroom band above today's best conditioning
    best = ils["conditioning"].max()
    axR.axhspan(best, best + 0.6, color="#f1c40f", alpha=0.15)
    axR.axhline(best, color="#f1c40f", lw=1.2, ls=":")
    axR.text(x[m].min(), best + 0.28, "  headroom above today's best",
             color="#b7950b", fontsize=8.5, va="center")

    # design-direction arrow (up the frontier)
    x0, x1 = np.percentile(x[m], 35), np.percentile(x[m], 92)
    axR.annotate("", xy=(x1, b0 + b1 * x1), xytext=(x0, b0 + b1 * x0),
                 arrowprops=dict(arrowstyle="-|>", color="#c0392b", lw=2.5))
    axR.text(np.mean([x0, x1]), b0 + b1 * np.mean([x0, x1]) - 0.45,
             "raise coacervate amount\n(natural polymer + persistent BC128o chassis)",
             color="#c0392b", fontsize=8.5, ha="center")

    axR.set_xlabel("Coacervate amount  (inverse-%T hump height, p95 above floor)")
    axR.set_ylabel("ILS conditioning composite")
    axR.set_title("How to make it better: move up the conditioning frontier",
                  fontweight="bold", fontsize=11)
    axR.grid(True, ls=":", alpha=0.5)
    axR.legend(fontsize=8.5, loc="lower right")

    fig.suptitle("Brandon prototypes \u2014 best conditioners and the lever to improve them",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = f"{R}/brandon_best_performers.png"
    fig.savefig(out, dpi=150); plt.close(fig)
    print(f"wrote {out}")

    # print the chassis-lever gains (GH130 -> BC128o for same polymer)
    print("\nChassis lever (switch GH130 -> BC128o, same polymer):")
    piv = ils.pivot_table(index="polymer", columns="chassis", values="conditioning")
    piv["gain_BC_over_GH"] = piv["BC128o M"] - piv["GH130 LT1"]
    print(piv.round(2).sort_values("gain_BC_over_GH", ascending=False).to_string())


if __name__ == "__main__":
    main()
