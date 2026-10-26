"""Effect of DOUBLING the hydrophobe (base -> *) on the dextran outcomes.

The '*' = same cationic charge, ~2x n-C16 hydrophobe DS (Dow/Lyndsay). This
pairs Dex-B/Dex-B* and Dex-J/Dex-J* and shows what doubling the hydrophobe does
to silicone deposition (FTIR ppm) and rinse friction (DRF), across chassis --
alongside the fact that their %T coacervation AUC is ~0 throughout.

Output: Reports/dextran_hydrophobe_effect.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

R = "Reports"
DEPO = r"raw_data\ptl_depo_dextran.csv"
PAIRS = [("Dex-B", "Dex-B*"), ("Dex-J", "Dex-J*")]
CH_COL = {"CH2": "#1f77b4", "CH2 + LAPB": "#d62728", "CH2 + APG": "#2ca02c"}


def main():
    d = pd.read_csv(DEPO)
    fig, (axS, axF) = plt.subplots(1, 2, figsize=(14, 6))
    for ax, col, ylab, ttl, better in [
        (axS, "Si_ppm", "Silicone deposition (FTIR ppm)  \u2191 better",
         "Silicone deposition", "up"),
        (axF, "DRF", "DRF rinse friction (gF)  \u2193 better",
         "Rinse friction", "down"),
    ]:
        for base, star in PAIRS:
            for _, chn in enumerate(d["chassis"].unique()):
                for sil in d["silicone"].unique():
                    b = d[(d.polymer == base) & (d.chassis == chn) & (d.silicone == sil)]
                    s = d[(d.polymer == star) & (d.chassis == chn) & (d.silicone == sil)]
                    if len(b) and len(s):
                        y0, y1 = float(b[col].iloc[0]), float(s[col].iloc[0])
                        ls = "-" if base == "Dex-J" else "--"
                        ax.plot([0, 1], [y0, y1], ls, color=CH_COL.get(chn, "#888"),
                                marker="o", lw=2, alpha=0.85)
                        ax.annotate(f"{base[-1] if base[-1].isalpha() else base} {chn.split('+')[-1].strip()} {sil}",
                                    (1, y1), fontsize=6.5, xytext=(4, 0),
                                    textcoords="offset points", va="center")
        ax.set_xticks([0, 1]); ax.set_xticklabels(["base", "\u00d72 hydrophobe (*)"])
        ax.set_xlim(-0.15, 1.5); ax.set_ylabel(ylab)
        ax.set_title(ttl, fontweight="bold")
        ax.grid(True, axis="y", ls=":", alpha=0.5)
    handles = [plt.Line2D([0], [0], color=c, lw=2, label=k) for k, c in CH_COL.items()]
    handles += [plt.Line2D([0], [0], color="#555", lw=2, ls="-", label="Dex-J / J*"),
                plt.Line2D([0], [0], color="#555", lw=2, ls="--", label="Dex-B / B*")]
    axS.legend(handles=handles, fontsize=8, loc="upper right")
    fig.suptitle("Does doubling the hydrophobe help? \u2014 Dex-B/B* & Dex-J/J* "
                 "(same charge, 2\u00d7 n-C16).  %T coacervation AUC \u2248 0 for all of these.",
                 fontsize=12, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{R}/dextran_hydrophobe_effect.png", dpi=150)
    plt.close(fig)
    print(f"wrote {R}/dextran_hydrophobe_effect.png\n")

    # numeric base -> * deltas for Si deposition
    print("Si deposition (ppm): base -> *2 hydrophobe")
    for base, star in PAIRS:
        for chn in d["chassis"].unique():
            for sil in d["silicone"].unique():
                b = d[(d.polymer == base) & (d.chassis == chn) & (d.silicone == sil)]
                s = d[(d.polymer == star) & (d.chassis == chn) & (d.silicone == sil)]
                if len(b) and len(s):
                    y0, y1 = float(b.Si_ppm.iloc[0]), float(s.Si_ppm.iloc[0])
                    print(f"  {base:6s}->{star:7s} {chn:11s} {sil:6s}: "
                          f"{y0:6.1f} -> {y1:6.1f}  ({y1 - y0:+.1f})")


if __name__ == "__main__":
    main()
