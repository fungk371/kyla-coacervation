"""GH130 LT1 Polyquat-6 (T1) + Polyquat-22 (T2) - SoftMax 'matrix' export.

This file is a SoftMax Pro kinetic export in the 8-row x 12-col BLOCK layout
(UTF-16), one block per timepoint, not the wide A1..H12 format. Parse it, then
plot inverse %T in the reference (peak-up) convention like the other GH130 legs.

Output: Reports/gh130_pq6_pq22_ipct.png
"""
import re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import coacervation_lasentec as clas
from coacervation_layout import annotate_concentration
from coacervation_analysis import dilution_ratio
from make_dextran_figs import clean_curve
from make_dextran_timepoint_analysis import smooth_hybrid, _dil_axis

R = "Reports"
PATH = r"raw_data\GH130_PQ6_PQ22.txt"
ROWS = "ABCDEFGH"


def _tmin(s):
    hh, mm, ss = (int(p) for p in s.split(":"))
    return hh * 60 + mm + ss / 60.0


def parse_softmax_matrix(path):
    with open(path, "rb") as f:
        text = f.read().decode("utf-16")
    recs, block, tp = [], [], None

    def flush():
        for ridx, vals in enumerate(block):
            if ridx >= 8:
                break
            for cidx, v in enumerate(vals):
                recs.append((tp, f"{ROWS[ridx]}{cidx + 1}", v))

    for ln in text.splitlines():
        cells = ln.split("\t")
        c0 = cells[0].strip()
        if re.match(r"^\d\d:\d\d:\d\d$", c0):
            if block:
                flush(); block = []
            tp = _tmin(c0)
            block.append([float(x) if x.strip() else np.nan for x in cells[2:14]])
        elif ln.strip() == "":
            if block:
                flush(); block = []
        elif len(cells) >= 14 and cells[0] == "" and cells[1] == "":
            block.append([float(x) if x.strip() else np.nan for x in cells[2:14]])
    if block:
        flush()
    return pd.DataFrame(recs, columns=["timepoint_minutes", "well", "transmission_pct"])


def curve(df, trough, tp=0):
    t = min(sorted(df["timepoint_minutes"].unique()), key=lambda z: abs(z - tp))
    sel = df[(df["trough"] == trough) & (df["timepoint_minutes"] == t)].dropna(
        subset=["formula_fraction"]).sort_values("formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(sel["formula_fraction"].to_numpy(float)), float)
    y = sel["transmission_pct"].to_numpy(float)
    o = np.argsort(x)
    return x[o], y[o]


def main():
    df = annotate_concentration(parse_softmax_matrix(PATH))
    troughs = [("Polyquat-6", 1, "#2E75B6"), ("Polyquat-22", 2, "#c0392b")]
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    lo, hi = [], []
    print(f"{'polymer':13s} {'floor':>5s} {'onset':>7s} {'peak':>12s} {'redis':>8s} "
          f"{'recloud':>7s} {'width':>6s} {'AUC':>6s}")
    for name, tr, col in troughs:
        x, y = curve(df, tr)
        cx, cy, _ = clean_curve(x, y)
        fx, fy = smooth_hybrid(cx, cy)
        ax.plot(fx, fy, "-", color=col, lw=2.4, label=f"{name} (GH130 LT1)")
        ax.plot(x, y, "o", color=col, ms=2.6, alpha=0.28)
        fp = clas.inverse_pct_fingerprint(x, y) or {}
        pk, pkp = fp.get("peak_dilution"), fp.get("peak_pct")
        recloud, redis = 0.0, fp.get("redissolution_dilution")
        if pk and pkp is not None:
            m = fx > pk
            if m.any():
                j = int(np.argmin(fy[m])); recloud = max(0.0, pkp - float(fy[m][j]))
                if redis is None:
                    redis = float(fx[m][j])
        lo.append(cx.min()); hi.append(cx.max())
        onset = f"1:{fp['onset_dilution']:g}" if fp.get("onset_dilution") else "-"
        peak = f"{pkp:.0f}@1:{pk:.0f}" if pkp else "-"
        rd = f"1:{redis:.0f}" if redis else "none"
        wd = (f"{np.log10(redis/fp['onset_dilution']):.2f}"
              if redis and fp.get("onset_dilution") else "-")
        print(f"{name:13s} {fp.get('baseline_pct',0):5.0f} {onset:>7s} {peak:>12s} "
              f"{rd:>8s} {recloud:7.0f} {wd:>6s} {fp.get('inverse_auc',0):6.0f}")
    _dil_axis(ax, min(lo), max(hi), fs=9)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Dilution (1:X)  \u2014  rinse \u2192")
    ax.set_ylabel("%T (centrifuged supernatant)")
    ax.grid(True, which="both", ls=":", alpha=0.5)
    ax.set_title("GH130 LT1 \u2014 Polyquat-6 & Polyquat-22 inverse %T (t=0)\n"
                 "\u2605 peak (max clearing)   \u25bc re-cloud (redissolution)",
                 fontweight="bold")
    ax.legend(fontsize=10)
    fig.tight_layout()
    fig.savefig(f"{R}/gh130_pq6_pq22_ipct.png", dpi=150)
    plt.close(fig)
    print(f"\nwrote {R}/gh130_pq6_pq22_ipct.png")


if __name__ == "__main__":
    main()
