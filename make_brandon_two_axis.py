"""Two-axis coacervation model: AMOUNT (inverse-%T) x STRUCTURE (Lasentec floc
coarseness) -> ILS conditioning. Shows floc coarseness explains the residual
that amount alone misses (notably the guar 3196 control).
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import make_brandon_ipct_fingerprints as B

R = "Reports"
POLY = {"NH3196": "NH3196", "Pq6": "Polyquat-6", "Pq22": "Polyquat-22",
        "Pq47": "Polyquat-47", "Pq53": "Polyquat-53", "NatCaready": "Nat Caready",
        "NatClear": "Nat Clear", "Cassia": "Cassia"}
CH = {"GH130": "GH130 LT1", "BC128o": "BC128o M"}
CH_COL = {"BC128o M": "#2E75B6", "GH130 LT1": "#16a085"}
CH_MARK = {"BC128o M": "o", "GH130 LT1": "s"}


def amount_windowed(path, tr, cap=50.0):
    x, y = B.curve(path, tr)
    cx, cy, _ = B.clean_curve(x, y)
    fx, fy = B.smooth_hybrid(cx, cy)
    floor = float(np.min(fy[:max(3, len(fy) // 10)]))
    m = fx <= cap
    return max(0.0, float(np.percentile(fy[m], 95)) - floor) if m.any() else 0.0


def main():
    las = pd.read_csv(r"raw_data\lasentec_brandon.csv")
    mid = las["chord"].values
    rows = []
    for col in las.columns[1:]:
        c = las[col].values.astype(float)
        sqwt = float((c * mid ** 2).sum() / (c * mid).sum())
        pcode, ccode = col.rsplit("_", 1)
        rows.append({"polymer": POLY[pcode], "chassis": CH[ccode], "sqwt_mean": sqwt})
    fdf = pd.DataFrame(rows)
    amt = {(p, c): amount_windowed(path, tr) for p, c, path, tr in B.SAMPLES}
    fdf["amount"] = fdf.apply(lambda s: amt.get((s.polymer, s.chassis), np.nan), axis=1)

    ils = pd.read_csv(r"raw_data\brandon_ils_detail.csv")
    cond = ["wet_slip", "detangle_wide", "detangle_fine", "smooth_surface",
            "smooth_interfiber", "moisturized"]
    ils["conditioning"] = ils[cond].mean(axis=1)
    m = fdf.merge(ils[["polymer", "chassis", "conditioning"]], on=["polymer", "chassis"])
    m["label"] = m["polymer"] + "/" + m["chassis"].str.split().str[0]

    # residual of conditioning after amount
    b1, b0 = np.polyfit(m["amount"], m["conditioning"], 1)
    m["resid"] = m["conditioning"] - (b0 + b1 * m["amount"])

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(16, 7))

    # ---- A: two-axis map ----
    sc = axA.scatter(m["amount"], m["sqwt_mean"],
                     s=40 + (m["conditioning"] - 5) * 55,
                     c=m["conditioning"], cmap="viridis", vmin=6, vmax=10,
                     edgecolor="k", linewidth=0.6, zorder=3)
    for _, r in m.iterrows():
        axA.annotate(r["label"], (r["amount"], r["sqwt_mean"]),
                     textcoords="offset points", xytext=(6, 3), fontsize=7.3)
    cb = fig.colorbar(sc, ax=axA); cb.set_label("ILS conditioning", fontsize=9)
    axA.set_xlabel("AXIS 1 \u2014 coacervate amount (inverse-%T height, \u22641:50)")
    axA.set_ylabel("AXIS 2 \u2014 floc coarseness (Lasentec sq-wt mean chord, \u00b5m)")
    axA.set_title("Two-axis coacervation map\n(bubble size & colour = conditioning)",
                  fontweight="bold", fontsize=11)
    axA.grid(True, ls=":", alpha=0.5)
    axA.annotate("guar 3196: modest amount but\nLARGE flocs \u2192 conditions above its amount",
                 xy=(m[m.polymer=='NH3196'].sort_values('sqwt_mean').iloc[-1]['amount'],
                     m[m.polymer=='NH3196'].sort_values('sqwt_mean').iloc[-1]['sqwt_mean']),
                 xytext=(0.30, 0.86), textcoords="axes fraction", fontsize=8.5,
                 color="#b7410e",
                 arrowprops=dict(arrowstyle="->", color="#b7410e", lw=1.5))

    # ---- B: residual vs floc coarseness ----
    for _, r in m.iterrows():
        axB.scatter(r["sqwt_mean"], r["resid"], s=90, color=CH_COL[r["chassis"]],
                    marker=CH_MARK[r["chassis"]], edgecolor="white", zorder=3)
    rr = np.corrcoef(m["sqwt_mean"], m["resid"])[0, 1]
    c1, c0 = np.polyfit(m["sqwt_mean"], m["resid"], 1)
    xs = np.linspace(m["sqwt_mean"].min(), m["sqwt_mean"].max(), 50)
    axB.plot(xs, c0 + c1 * xs, "--", color="#c0392b", lw=2,
             label=f"r = {rr:+.2f}")
    axB.axhline(0, color="#888", lw=0.8)
    for _, r in m.iterrows():
        if abs(r["resid"]) > 0.6 or r["polymer"] == "NH3196":
            axB.annotate(r["label"], (r["sqwt_mean"], r["resid"]),
                         textcoords="offset points", xytext=(6, 2), fontsize=7.5,
                         fontweight="bold" if r["polymer"] == "NH3196" else "normal")
    axB.set_xlabel("Floc coarseness (Lasentec sq-wt mean chord, \u00b5m)")
    axB.set_ylabel("Conditioning residual  (actual \u2212 predicted by amount)")
    axB.set_title("Floc coarseness explains what amount misses",
                  fontweight="bold", fontsize=11)
    axB.grid(True, ls=":", alpha=0.5)
    axB.legend(handles=[plt.Line2D([], [], ls="--", color="#c0392b", label=f"r = {rr:+.2f}"),
                        plt.Line2D([], [], marker="o", ls="", color=CH_COL["BC128o M"], label="BC128o M"),
                        plt.Line2D([], [], marker="s", ls="", color=CH_COL["GH130 LT1"], label="GH130 LT1")],
               fontsize=8.5, loc="upper left")

    fig.suptitle("Coacervation = AMOUNT \u00d7 STRUCTURE: inverse-%T + Lasentec together predict conditioning",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = f"{R}/brandon_two_axis.png"
    fig.savefig(out, dpi=150); plt.close(fig)
    print(f"wrote {out}")
    print(f"residual vs floc coarseness r = {rr:+.2f}")
    print(m[["label", "amount", "sqwt_mean", "conditioning", "resid"]]
          .sort_values("resid", ascending=False).round(2).to_string(index=False))


if __name__ == "__main__":
    main()
