"""Correlate %T coacervation (AUC) with PTL/FTIR deposition for the dextran set.

Joins the 0.4% coacervation AUC (Sum_0_15) per polymer x chassis to the PTL
silicone deposition (FTIR ppm) and rinse friction (DRF), by polymer x chassis
(silicone legs averaged). Tests whether more coacervate -> more Si deposition.

Output: Reports/pctT_vs_depo.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

R = "Reports"
COAC = r"raw_data\POlymer test\Dextran_Project_Share\data\auc_over_time_summary.csv"
DEPO = r"raw_data\ptl_depo_dextran.csv"

CH_MAP = {"GH150 EED0": "CH2",
          "GH150 DDu0, 3.6% LAPB": "CH2 + LAPB",
          "GH150 DDu0, 3.6% APG": "CH2 + APG"}
CH_COL = {"CH2": "#1f77b4", "CH2 + LAPB": "#d62728", "CH2 + APG": "#2ca02c"}


def canon_poly(s):
    s = str(s).replace("0.4%", "").strip()
    s = s.replace("Dex ", "Dex-").replace("Dex-Dex", "Dex")
    return s


def pearson(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    if m.sum() < 3:
        return float("nan")
    return float(np.corrcoef(x[m], y[m])[0, 1])


def main():
    coac = pd.read_csv(COAC)
    coac["chassis"] = coac["Chassis"].map(CH_MAP)
    coac["polymer"] = coac["Polymer"].map(canon_poly)
    coac = coac[["chassis", "polymer", "Sum_0_15"]].rename(columns={"Sum_0_15": "auc"})

    depo = pd.read_csv(DEPO)
    depo["polymer"] = depo["polymer"].map(canon_poly)
    # average silicone legs per polymer x chassis
    dagg = depo.groupby(["polymer", "chassis"], as_index=False).agg(
        Si_ppm=("Si_ppm", "mean"), DRF=("DRF", "mean"))

    df = coac.merge(dagg, on=["polymer", "chassis"], how="inner").dropna(subset=["auc"])
    df["is_bench"] = df["polymer"].isin(["3196", "CD2"])

    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2))
    for ax, ycol, ylab, ttl in [
        (axes[0], "Si_ppm", "Silicone deposition (FTIR, ppm)  \u2191 better",
         "Coacervation AUC vs silicone deposition"),
        (axes[1], "DRF", "DRF rinse friction (gF)  \u2193 better",
         "Coacervation AUC vs rinse friction"),
    ]:
        for _, r in df.iterrows():
            ax.scatter(r["auc"], r[ycol], s=120, color=CH_COL.get(r["chassis"], "#888"),
                       marker=("*" if r["is_bench"] else "o"),
                       edgecolor="#333", linewidth=0.7, zorder=3,
                       alpha=0.9)
            ax.annotate(f"{r['polymer']}", (r["auc"], r[ycol]), fontsize=7,
                        xytext=(4, 3), textcoords="offset points")
        r_all = pearson(df["auc"], df[ycol])
        r_dex = pearson(df[~df["is_bench"]]["auc"], df[~df["is_bench"]][ycol])
        ax.set_xlabel("Coacervation AUC (%T, 0.4% polymer, Sum 0-15 min)")
        ax.set_ylabel(ylab)
        ax.set_title(f"{ttl}\nPearson r: all={r_all:+.2f}, dextrans only={r_dex:+.2f}",
                     fontweight="bold", fontsize=11)
        ax.grid(True, ls=":", alpha=0.5)
    handles = [plt.Line2D([0], [0], marker="o", ls="", mfc=c, mec="#333", ms=9, label=k)
               for k, c in CH_COL.items()]
    handles.append(plt.Line2D([0], [0], marker="*", ls="", mfc="#999", mec="#333", ms=12,
                              label="benchmark (3196/CD2)"))
    axes[0].legend(handles=handles, fontsize=8.5, loc="upper left")
    fig.suptitle("Does %T coacervation predict deposition? \u2014 dextran set (polymer \u00d7 chassis)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{R}/pctT_vs_depo.png", dpi=150)
    plt.close(fig)
    print(f"wrote {R}/pctT_vs_depo.png\n")

    # per-chassis correlations
    print(f"{'group':16s} {'n':>3s} {'r(AUC,Si)':>10s} {'r(AUC,DRF)':>11s}")
    for ch in ["CH2", "CH2 + LAPB", "CH2 + APG"]:
        d = df[df["chassis"] == ch]
        print(f"{ch:16s} {len(d):3d} {pearson(d['auc'], d['Si_ppm']):+10.2f} "
              f"{pearson(d['auc'], d['DRF']):+11.2f}")
    print(f"{'ALL':16s} {len(df):3d} {pearson(df['auc'], df['Si_ppm']):+10.2f} "
          f"{pearson(df['auc'], df['DRF']):+11.2f}")
    dx = df[~df["is_bench"]]
    print(f"{'dextrans only':16s} {len(dx):3d} {pearson(dx['auc'], dx['Si_ppm']):+10.2f} "
          f"{pearson(dx['auc'], dx['DRF']):+11.2f}")
    print("\njoined rows:")
    print(df[["polymer", "chassis", "auc", "Si_ppm", "DRF"]].to_string(index=False))


if __name__ == "__main__":
    main()
