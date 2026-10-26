"""Correlate Brandon inverse-%T coacervation with ILS consumer indices.

Joins each opaque sample's inverse-%T fingerprint (amount=height, width, AUC,
re-cloud depth) to the ILS tress-evaluation Wet/Dry/Overall index, by
polymer x chassis. Tests whether more/broader coacervation = better conditioning.

Outputs:
  Reports/brandon_ipct_vs_ils.png        (coacervation metrics vs Overall index)
  Reports/brandon_ipct_vs_ils_table.png  (joined numeric table)
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


def pearson(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    return float(np.corrcoef(x[m], y[m])[0, 1]) if m.sum() >= 3 else float("nan")


def main():
    fps = {}
    for poly, ch, path, tr in B.SAMPLES:
        r = B.fingerprint(path, tr)
        fps[(poly, ch)] = {"auc": r["auc"], "height": r["height"],
                           "width": r["width"], "recloud": r["redis_depth"]}
    ils = pd.read_csv(r"raw_data\brandon_ils.csv")

    rows = []
    for _, s in ils.iterrows():
        key = (s["polymer"], s["chassis"])
        if key in fps:
            rows.append({**fps[key], "polymer": s["polymer"], "chassis": s["chassis"],
                         "wet": s["wet"], "dry": s["dry"], "overall": s["overall"]})
    df = pd.DataFrame(rows)

    metrics = [("auc", "Inverse-%T AUC (coacervate amount)"),
               ("height", "Hump height (%T, amount)"),
               ("width", "Width (decades, breadth)"),
               ("recloud", "Re-cloud depth (redissolves)")]
    fig, axes = plt.subplots(2, 2, figsize=(14, 11))
    for ax, (mk, mlab) in zip(axes.ravel(), metrics):
        for _, rr in df.iterrows():
            ax.scatter(rr[mk], rr["overall"], s=130, color=CH_COL[rr["chassis"]],
                       marker=CH_MARK[rr["chassis"]], edgecolor="#333", zorder=3)
            ax.annotate(rr["polymer"], (rr[mk], rr["overall"]), fontsize=7.5,
                        xytext=(4, 3), textcoords="offset points")
        r_all = pearson(df[mk], df["overall"])
        r_bc = pearson(df[df.chassis == "BC128o M"][mk], df[df.chassis == "BC128o M"]["overall"])
        r_gh = pearson(df[df.chassis == "GH130 LT1"][mk], df[df.chassis == "GH130 LT1"]["overall"])
        ax.set_xlabel(mlab)
        ax.set_ylabel("ILS Overall conditioning index")
        ax.set_title(f"{mlab}\nPearson r: all={r_all:+.2f}  BC128o={r_bc:+.2f}  GH130={r_gh:+.2f}",
                     fontweight="bold", fontsize=10)
        ax.grid(True, ls=":", alpha=0.5)
    handles = [plt.Line2D([0], [0], marker=CH_MARK[k], ls="", mfc=c, mec="#333", ms=10, label=k)
               for k, c in CH_COL.items()]
    axes[0][0].legend(handles=handles, fontsize=9, loc="best")
    fig.suptitle("Brandon inverse-%T coacervation vs ILS consumer conditioning (by polymer \u00d7 chassis)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(f"{R}/brandon_ipct_vs_ils.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/brandon_ipct_vs_ils.png\n")

    print(f"{'metric':10s} {'r(all)':>7s} {'r(BC128o)':>10s} {'r(GH130)':>9s}  vs Overall")
    for mk, _ in metrics:
        print(f"{mk:10s} {pearson(df[mk], df['overall']):+7.2f} "
              f"{pearson(df[df.chassis=='BC128o M'][mk], df[df.chassis=='BC128o M']['overall']):+10.2f} "
              f"{pearson(df[df.chassis=='GH130 LT1'][mk], df[df.chassis=='GH130 LT1']['overall']):+9.2f}")
    print("\n-- vs Wet index --")
    for mk, _ in metrics:
        print(f"{mk:10s} r(all)={pearson(df[mk], df['wet']):+.2f}  "
              f"BC128o={pearson(df[df.chassis=='BC128o M'][mk], df[df.chassis=='BC128o M']['wet']):+.2f}  "
              f"GH130={pearson(df[df.chassis=='GH130 LT1'][mk], df[df.chassis=='GH130 LT1']['wet']):+.2f}")
    print("\njoined:")
    print(df[["polymer", "chassis", "auc", "height", "width", "recloud",
              "wet", "dry", "overall"]].round(1).to_string(index=False))


if __name__ == "__main__":
    main()
