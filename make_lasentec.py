"""Lasentec / FBRM chord-length distribution: L'Oreal Hyaluron Plump.

Compares the same shampoo measured in 0 gpg vs 7 gpg water. FBRM reports counts
per chord-length channel (a size/count proxy for coacervate/particles) every
few seconds. Files:
  * ..._sep10_FINAL.csv       -> 0 gpg  (soft water)
  * ..._7gpg_09112026.csv     -> 7 gpg  (hard water)

Layout: a 'Ch. Midpoints' row gives the 100 chord-length bin centres (microns);
each subsequent numbered row is one timepoint with 100 counts (cols 4..103).
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import csv
from datetime import datetime

R = "Reports"
F0 = r"C:\Users\fung.k.1\Downloads\LOreal Hyaluron Plump_sep10_FINAL.csv"
F7 = r"C:\Users\fung.k.1\Downloads\LOreal Hyaluron Plump_7gpg_09112026.csv"


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
    # elapsed seconds from first timestamp
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
    """Counts in <10, 10-100, >100 um bins (matches iC FBRM statistics)."""
    fine = dist[mids < 10].sum()
    med = dist[(mids >= 10) & (mids < 100)].sum()
    coarse = dist[mids >= 100].sum()
    return fine, med, coarse


def _sqrwt_mean(mids, dist):
    """Square-weighted mean chord length = sum(n L^3)/sum(n L^2)."""
    num = (dist * mids**3).sum()
    den = (dist * mids**2).sum()
    return num / den if den > 0 else np.nan


def main():
    d0 = parse_lasentec(F0)
    d7 = parse_lasentec(F7)
    mids = d0[0]
    counts0, t0 = d0[1], d0[2]
    counts7, t7 = d7[1], d7[2]
    tot0 = counts0.sum(axis=1)
    tot7 = counts7.sum(axis=1)

    # shampoo-addition point = first scan above 40% of max total counts
    add0 = int(np.argmax(tot0 > 0.4 * tot0.max()))
    add7 = int(np.argmax(tot7 > 0.4 * tot7.max()))
    # 7 gpg: the user ran ~1 min of HARD WATER ONLY before adding shampoo
    base7 = t7 < 60.0
    steady0 = (tot0 >= 0.5 * tot0.max()) & (np.arange(len(tot0)) > add0 + 2)
    steady7 = (t7 >= 75.0) & (tot7 >= 0.5 * np.median(tot7[t7 >= 75.0]))

    dist0 = counts0[steady0].mean(axis=0)
    dist7 = counts7[steady7].mean(axis=0)
    distB = counts7[base7].mean(axis=0) if base7.any() else np.zeros_like(mids)

    # square-weighted mean chord per scan
    sqr0 = np.array([_sqrwt_mean(mids, c) for c in counts0])
    sqr7 = np.array([_sqrwt_mean(mids, c) for c in counts7])

    fig, ax = plt.subplots(2, 2, figsize=(15, 10))
    C0, C7, CB = "#2E75B6", "#c0392b", "#7a7f87"
    L0, L7 = "0 gpg (soft), + shampoo", "7 gpg (hard), + shampoo"

    # (0,0) distribution: baseline (hard water only) vs both steady
    a = ax[0, 0]
    a.plot(mids, distB, "--", color=CB, lw=1.8, label="7 gpg HARD WATER ONLY (pre-shampoo)")
    a.plot(mids, dist0, "-", color=C0, lw=2.2, label=L0)
    a.plot(mids, dist7, "-", color=C7, lw=2.2, label=L7)
    a.set_xscale("log"); a.set_xlabel("Chord length (\u00b5m)")
    a.set_ylabel("Mean counts / channel"); a.grid(True, ls=":", alpha=0.5)
    a.set_title("Chord-length distribution", fontweight="bold"); a.legend(fontsize=8.5)

    # (0,1) bin bar chart matching iC FBRM stats
    a = ax[0, 1]
    labels = ["<10 \u00b5m", "10\u2013100 \u00b5m", ">100 \u00b5m"]
    b0 = _bins(mids, dist0); b7 = _bins(mids, dist7); bB = _bins(mids, distB)
    x = np.arange(3); w = 0.26
    a.bar(x - w, b0, w, color=C0, label=L0)
    a.bar(x, b7, w, color=C7, label=L7)
    a.bar(x + w, bB, w, color=CB, label="7 gpg hard water only")
    for xi, vals in zip(x, zip(b0, b7, bB)):
        for dx, v, c in zip((-w, 0, w), vals, (C0, C7, CB)):
            a.text(xi + dx, v + 150, f"{v:.0f}", ha="center", fontsize=7.5, color=c)
    a.set_xticks(x); a.set_xticklabels(labels)
    a.set_ylabel("Counts / s"); a.set_title("Counts by size bin", fontweight="bold")
    a.legend(fontsize=8.5); a.grid(True, axis="y", ls=":", alpha=0.5)

    # (1,0) total counts over time, pre-shampoo window shaded
    a = ax[1, 0]
    a.plot(t0, tot0, "-", color=C0, lw=1.6, label=L0)
    a.plot(t7, tot7, "-", color=C7, lw=1.6, label=L7)
    a.axvspan(0, 60, color="#f0d000", alpha=0.18)
    a.text(30, a.get_ylim()[1] * 0.5 if False else max(tot7) * 0.35,
           "7 gpg:\nhard water\nonly", ha="center", fontsize=8.5, color="#7a5c00")
    a.set_xlabel("Elapsed time (s)"); a.set_ylabel("Total counts / s")
    a.grid(True, ls=":", alpha=0.5); a.set_title("Total counts over time", fontweight="bold")
    a.legend(fontsize=8.5)

    # (1,1) square-weighted mean chord length over time
    a = ax[1, 1]
    a.plot(t0, sqr0, "-", color=C0, lw=1.6, label=L0)
    a.plot(t7, sqr7, "-", color=C7, lw=1.6, label=L7)
    a.axvspan(0, 60, color="#f0d000", alpha=0.18)
    a.set_ylim(0, 80)
    a.set_xlabel("Elapsed time (s)"); a.set_ylabel("Square-wt mean chord (\u00b5m)")
    a.grid(True, ls=":", alpha=0.5)
    a.set_title("Square-weighted mean chord (large-particle size)", fontweight="bold")
    a.legend(fontsize=8.5)

    fig.suptitle("Lasentec FBRM \u2014 L'Oreal Hyaluron Plump \u2014 0 gpg vs 7 gpg (+ hard-water baseline)",
                 fontsize=14.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(f"{R}/lasentec_hyaluron_0vs7gpg.png", dpi=150)
    plt.close(fig)
    print(f"wrote {R}/lasentec_hyaluron_0vs7gpg.png")

    # ---- console summary ----
    def report(lab, mids, dist, sqr_scan, mask):
        f, m, c = _bins(mids, dist)
        print(f"\n{lab}")
        print(f"  counts/s  <10um={f:8.0f}  10-100um={m:8.0f}  >100um={c:6.2f}  total={f+m+c:8.0f}")
        print(f"  square-weighted mean chord = {np.nanmean(sqr_scan[mask]):.1f} um")

    report("0 gpg (soft) + shampoo [steady]", mids, dist0, sqr0, steady0)
    report("7 gpg (hard) + shampoo [steady]", mids, dist7, sqr7, steady7)
    fB, mB, cB = _bins(mids, distB)
    print(f"\n7 gpg HARD WATER ONLY (pre-shampoo baseline, {base7.sum()} scans)")
    print(f"  counts/s  <10um={fB:8.0f}  10-100um={mB:8.0f}  >100um={cB:6.2f}  total={fB+mB+cB:8.0f}")
    print(f"  => baseline is {100*(fB+mB+cB)/(sum(_bins(mids,dist7))):.1f}% of the 7 gpg + shampoo total")


if __name__ == "__main__":
    main()
