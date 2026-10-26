"""Correlate inverse-%T coacervation AMOUNT with each ILS wet & dry attribute.

Which specific consumer attributes does coacervate amount (inverse-%T AUC)
predict? Ranks the Pearson r of AUC vs every wet/dry sensory attribute.

Outputs:
  Reports/brandon_ils_attr_corr.png   (r of AUC vs each attribute, wet vs dry)
  Reports/brandon_ils_top_scatter.png (AUC vs the strongest attributes)
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
WET = ["creaminess", "amount_lather", "rinse_drag", "clean_feel_wet", "wet_slip",
       "alignment", "detangle_wide", "detangle_fine"]
DRY = ["dry_clumping", "comb_body", "comb_tips", "smooth_look", "smooth_surface",
       "smooth_interfiber", "volume", "shine", "clean_feel_dry", "moisturized"]
LABEL = {"creaminess": "Lather creaminess", "amount_lather": "Lather amount",
         "rinse_drag": "Rinse drag count", "clean_feel_wet": "Clean feel (wet)",
         "wet_slip": "Wet slip / conditioned", "alignment": "Visual alignment",
         "detangle_wide": "Detangle (wide tooth)", "detangle_fine": "Detangle (fine tooth)",
         "dry_clumping": "Dry clumping", "comb_body": "Comb body", "comb_tips": "Comb tips",
         "smooth_look": "Smooth look", "smooth_surface": "Smooth surface feel",
         "smooth_interfiber": "Smooth inter-fiber feel", "volume": "Volume/fullness",
         "shine": "Clean shine", "clean_feel_dry": "Clean feel (dry)",
         "moisturized": "Moisturized feel"}


def pearson(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    return float(np.corrcoef(x[m], y[m])[0, 1]) if m.sum() >= 3 else np.nan


def main():
    fps = {}
    for poly, ch, path, tr in B.SAMPLES:
        r = B.fingerprint(path, tr)
        fps[(poly, ch)] = r["auc"]
    ils = pd.read_csv(r"raw_data\brandon_ils_detail.csv")
    ils["auc"] = ils.apply(lambda s: fps.get((s["polymer"], s["chassis"]), np.nan), axis=1)

    # correlation of AUC vs each attribute
    corr = []
    for attr in WET + DRY:
        corr.append({"attr": attr, "kind": "wet" if attr in WET else "dry",
                     "r": pearson(ils["auc"], ils[attr])})
    cdf = pd.DataFrame(corr).sort_values("r")

    # ---- Fig 1: correlation bars ----
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = ["#2E75B6" if k == "wet" else "#c47f1a" for k in cdf["kind"]]
    ax.barh(range(len(cdf)), cdf["r"], color=colors, edgecolor="white")
    ax.set_yticks(range(len(cdf)))
    ax.set_yticklabels([LABEL[a] for a in cdf["attr"]], fontsize=9)
    for i, v in enumerate(cdf["r"]):
        ax.text(v + (0.02 if v >= 0 else -0.02), i, f"{v:+.2f}",
                va="center", ha="left" if v >= 0 else "right", fontsize=8)
    ax.axvline(0, color="#333", lw=0.8)
    ax.set_xlim(-1, 1)
    ax.set_xlabel("Pearson r  —  inverse-%T coacervation AUC (amount) vs attribute")
    ax.set_title("Which consumer attributes does coacervate AMOUNT predict?\n"
                 "blue = wet attributes, gold = dry attributes  (n=16, directional)",
                 fontweight="bold", fontsize=11)
    ax.legend(handles=[plt.Rectangle((0, 0), 1, 1, fc="#2E75B6", label="Wet"),
                       plt.Rectangle((0, 0), 1, 1, fc="#c47f1a", label="Dry")], fontsize=9)
    ax.grid(True, axis="x", ls=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(f"{R}/brandon_ils_attr_corr.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/brandon_ils_attr_corr.png")

    # ---- Fig 2: scatter of the 3 strongest ----
    top = cdf.reindex(cdf["r"].abs().sort_values(ascending=False).index)["attr"].tolist()[:3]
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.4))
    for ax, attr in zip(axes, top):
        for _, rr in ils.iterrows():
            ax.scatter(rr["auc"], rr[attr], s=120, color=CH_COL[rr["chassis"]],
                       marker=CH_MARK[rr["chassis"]], edgecolor="#333", zorder=3)
            ax.annotate(rr["polymer"], (rr["auc"], rr[attr]), fontsize=6.5,
                        xytext=(3, 3), textcoords="offset points")
        ax.set_xlabel("Inverse-%T AUC (coacervate amount)")
        ax.set_ylabel(LABEL[attr])
        ax.set_title(f"{LABEL[attr]}\nr = {pearson(ils['auc'], ils[attr]):+.2f}",
                     fontweight="bold", fontsize=10)
        ax.grid(True, ls=":", alpha=0.5)
    fig.suptitle("Coacervate amount vs the strongest-correlated consumer attributes",
                 fontsize=12.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{R}/brandon_ils_top_scatter.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/brandon_ils_top_scatter.png\n")

    print(f"{'attribute':26s} {'kind':4s} {'r(AUC)':>7s}")
    for _, rr in cdf.iloc[::-1].iterrows():
        print(f"{LABEL[rr['attr']]:26s} {rr['kind']:4s} {rr['r']:+7.2f}")


if __name__ == "__main__":
    main()
