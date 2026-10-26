"""Lasentec / FBRM: Pantene DMR - 0 gpg vs 7 gpg water hardness.

Same 4-panel diagnostic as the L'Oreal Hyaluron 0-vs-7 gpg comparison:
  * ...panteneM10_09112026_diwater.csv  -> 0 gpg (soft / DI)
  * PanteneDMR_091626_7gpg.csv          -> 7 gpg (hard)

Layout: a 'Ch. Midpoints' row gives the 100 chord-length bin centres (microns);
each numbered row is one timepoint with 100 counts (cols 4..103). Early all-zero
scans are instrument start-up (dropped by the steady-state mask).

Output: Reports/lasentec_pantene_0vs7gpg.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import csv
import os
from datetime import datetime

R = "Reports"
DL = r"C:\Users\fung.k.1\Downloads"


def _find(cands):
    return next((p for p in cands if os.path.exists(p)), cands[0])


F0 = _find([rf"{DL}\panteneM10_09112026_diwater.csv",
            rf"{DL}\PanteneDMR_diwater.csv"])
F7 = _find([rf"{DL}\PanteneDMR_091626_7gpg.csv"])


def parse_lasentec(path):
    mids = None
    counts, tstr = [], []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if not row:
                continue
            tag = (row[0] or "").strip()
            if tag == "Ch. Midpoints":
                mids = np.array([float(x) for x in row[4:104]])
            elif tag.isdigit() and len(row) >= 104:
                vals = [float(x) if str(x).strip() not in ("", "nan") else 0.0
                        for x in row[4:104]]
                counts.append(vals)
                tstr.append(row[2].strip())
    counts = np.array(counts)
    t = []
    for s in tstr:
        try:
            t.append(datetime.strptime(s, "%I:%M:%S %p"))
        except ValueError:
            t.append(None)
    t0 = next((x for x in t if x), None)
    elapsed = np.array([(x - t0).total_seconds() if x and t0 else i
                        for i, x in enumerate(t)], float)
    return mids, counts, elapsed


def _bins(mids, dist):
    fine = dist[mids < 10].sum()
    med = dist[(mids >= 10) & (mids < 100)].sum()
    coarse = dist[mids >= 100].sum()
    return fine, med, coarse


def _sqrwt_mean(mids, dist):
    num = (dist * mids**3).sum()
    den = (dist * mids**2).sum()
    return num / den if den > 0 else np.nan


def _frac_gt(mids, dist, thr=30.0):
    tot = dist.sum()
    return 100.0 * dist[mids >= thr].sum() / tot if tot > 0 else np.nan


def _peak(mids, dist):
    return mids[int(np.argmax(dist))] if dist.max() > 0 else np.nan


def _steady(counts, tot):
    add = int(np.argmax(tot > 0.4 * tot.max())) if tot.max() > 0 else 0
    steady = (tot >= 0.5 * tot.max()) & (np.arange(len(tot)) > add + 2)
    if not steady.any():
        steady = np.arange(len(tot)) > add
    return add, steady


def main():
    mids, c0, t0 = parse_lasentec(F0)
    m7, c7, t7 = parse_lasentec(F7)
    tot0, tot7 = c0.sum(axis=1), c7.sum(axis=1)
    _, st0 = _steady(c0, tot0)
    _, st7 = _steady(c7, tot7)
    dist0 = c0[st0].mean(axis=0)
    dist7 = c7[st7].mean(axis=0)
    sqr0 = np.array([_sqrwt_mean(mids, c) for c in c0])
    sqr7 = np.array([_sqrwt_mean(mids, c) for c in c7])

    C0, C7 = "#2E75B6", "#c0392b"
    L0, L7 = "0 gpg (soft / DI)", "7 gpg (hard)"
    fig, ax = plt.subplots(2, 2, figsize=(15, 10))

    a = ax[0, 0]
    a.plot(mids, dist0, "-", color=C0, lw=2.2, label=L0)
    a.plot(mids, dist7, "-", color=C7, lw=2.2, label=L7)
    a.set_xscale("log"); a.set_xlabel("Chord length (\u00b5m)")
    a.set_ylabel("Mean counts / channel"); a.grid(True, ls=":", alpha=0.5)
    a.set_title("Chord-length distribution", fontweight="bold"); a.legend(fontsize=9)

    a = ax[0, 1]
    labels = ["<10 \u00b5m", "10\u2013100 \u00b5m", ">100 \u00b5m"]
    b0 = _bins(mids, dist0); b7 = _bins(mids, dist7)
    x = np.arange(3); w = 0.34
    a.bar(x - w / 2, b0, w, color=C0, label=L0)
    a.bar(x + w / 2, b7, w, color=C7, label=L7)
    for xi, (v0, v7) in zip(x, zip(b0, b7)):
        a.text(xi - w / 2, v0, f"{v0:.0f}", ha="center", va="bottom", fontsize=7.5, color=C0)
        a.text(xi + w / 2, v7, f"{v7:.0f}", ha="center", va="bottom", fontsize=7.5, color=C7)
    a.set_xticks(x); a.set_xticklabels(labels)
    a.set_ylabel("Counts / s"); a.set_title("Counts by size bin", fontweight="bold")
    a.legend(fontsize=9); a.grid(True, axis="y", ls=":", alpha=0.5)

    a = ax[1, 0]
    a.plot(t0, tot0, "-", color=C0, lw=1.6, label=L0)
    a.plot(t7, tot7, "-", color=C7, lw=1.6, label=L7)
    a.set_xlabel("Elapsed time (s)"); a.set_ylabel("Total counts / s")
    a.grid(True, ls=":", alpha=0.5); a.set_title("Total counts over time", fontweight="bold")
    a.legend(fontsize=9)

    a = ax[1, 1]
    a.plot(t0, sqr0, "-", color=C0, lw=1.6, label=L0)
    a.plot(t7, sqr7, "-", color=C7, lw=1.6, label=L7)
    a.set_ylim(0, max(80, np.nanmax(np.concatenate([sqr0, sqr7])) * 1.1))
    a.set_xlabel("Elapsed time (s)"); a.set_ylabel("Square-wt mean chord (\u00b5m)")
    a.grid(True, ls=":", alpha=0.5)
    a.set_title("Square-weighted mean chord (large-particle size)", fontweight="bold")
    a.legend(fontsize=9)

    fig.suptitle("Lasentec FBRM \u2014 Pantene DMR \u2014 0 gpg vs 7 gpg water hardness",
                 fontsize=14.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(f"{R}/lasentec_pantene_0vs7gpg.png", dpi=150)
    plt.close(fig)
    print(f"wrote {R}/lasentec_pantene_0vs7gpg.png\n")

    print(f"{'metric':22s} {'0 gpg':>10s} {'7 gpg':>10s}")
    print(f"{'peak chord (um)':22s} {_peak(mids, dist0):10.1f} {_peak(m7, dist7):10.1f}")
    print(f"{'sqr-wt mean (um)':22s} {_sqrwt_mean(mids, dist0):10.1f} {_sqrwt_mean(m7, dist7):10.1f}")
    print(f"{'% counts > 30 um':22s} {_frac_gt(mids, dist0):10.1f} {_frac_gt(m7, dist7):10.1f}")
    print(f"{'total counts (steady)':22s} {dist0.sum():10.0f} {dist7.sum():10.0f}")
    print(f"{'<10 um counts':22s} {b0[0]:10.0f} {b7[0]:10.0f}")
    print(f"{'10-100 um counts':22s} {b0[1]:10.0f} {b7[1]:10.0f}")
    print(f"{'>100 um counts':22s} {b0[2]:10.0f} {b7[2]:10.0f}")


if __name__ == "__main__":
    main()
