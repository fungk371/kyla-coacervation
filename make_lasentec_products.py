"""Lasentec / FBRM chord-length distributions: competitor shampoos in DI water.

Overlays commercial shampoos measured by FBRM in DI (soft / 0 gpg) water, in the
normalized chord-length-distribution style (counts scaled to peak = 1.0 vs log
chord length). FBRM reports counts per chord-length channel every few seconds.

DI-water (0 gpg) runs (add 7 gpg runs to PRODUCTS as they come in):
  * panteneM10_09112026_diwater.csv        -> Pantene M10
  * DoveIntRepair_09112026_diwater_2.csv   -> Dove Intensive Repair (short run)
  * KerataseNutritive_09112026_diwater.csv -> Kerastase Nutritive
  * LOreal Hyaluron Plump_sep10_FINAL.csv  -> L'Oreal Hyaluron Plump (0 gpg)

Layout: a 'Ch. Midpoints' row gives the 100 chord-length bin centres (microns);
each subsequent numbered row is one timepoint with 100 counts (cols 4..103).
Runs may begin with a pre-shampoo DI water baseline (all-zero scans).

Outputs (Reports/):
  * lasentec_overlay_normalized.png  -> single-panel normalized overlay
  * lasentec_competitors_diwater.png -> 4-panel diagnostic (absolute counts etc.)
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import csv
from datetime import datetime

R = "Reports"
DL = r"C:\Users\fung.k.1\Downloads"

# (label, path, colour) -- add 7 gpg runs to this list as they come in
PRODUCTS = [
    ("Pantene M10", rf"{DL}\panteneM10_09112026_diwater.csv", "#2E75B6"),
    ("Kerastase Nutritive", rf"{DL}\KerataseNutritive_09112026_diwater_1.csv", "#8E44AD"),
    ("L'Oreal Hyaluron Plump", rf"{DL}\LOreal Hyaluron Plump_sep10_FINAL.csv", "#27ae60"),
    ("Dove Intensive Repair", rf"{DL}\DoveIntensiveRepairREAL_09112026_diwater.csv", "#c0392b"),
]


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


def _steady(counts, tot):
    """Shampoo-addition point + steady-state mask (post-addition plateau)."""
    add = int(np.argmax(tot > 0.4 * tot.max())) if tot.max() > 0 else 0
    steady = (tot >= 0.5 * tot.max()) & (np.arange(len(tot)) > add + 2)
    if not steady.any():
        steady = np.arange(len(tot)) > add
    return add, steady


def load(label, path, colour):
    mids, counts, t = parse_lasentec(path)
    tot = counts.sum(axis=1)
    add, steady = _steady(counts, tot)
    dist = counts[steady].mean(axis=0)
    norm = dist / dist.max() if dist.max() > 0 else dist
    sqr = np.array([_sqrwt_mean(mids, c) for c in counts])
    return dict(label=label, colour=colour, mids=mids, counts=counts, t=t,
                tot=tot, add=add, steady=steady, dist=dist, norm=norm, sqr=sqr)


def overlay(data, mids):
    """Single-panel normalized chord-length distribution overlay (Parth style)."""
    fig, a = plt.subplots(figsize=(9, 6))
    for d in data:
        a.plot(mids, d["norm"], "-", color=d["colour"], lw=2.4, label=d["label"])
    a.set_xscale("log")
    a.set_xlim(1, 1000)
    a.set_ylim(0, 1.05)
    a.set_xlabel("Chord length (\u00b5m)", fontsize=12)
    a.set_ylabel("Counts (normalized to peak)", fontsize=12)
    a.grid(True, which="both", ls=":", alpha=0.5)
    a.set_title("Lasentec FBRM \u2014 shampoo coacervate/particle size in DI water (0 gpg)",
                fontsize=13, fontweight="bold")
    a.legend(fontsize=10, frameon=True)
    fig.tight_layout()
    fig.savefig(f"{R}/lasentec_overlay_normalized.png", dpi=150)
    plt.close(fig)
    print(f"wrote {R}/lasentec_overlay_normalized.png")


def diagnostic(data, mids):
    """4-panel diagnostic: absolute dist, size bins, total counts + size vs time."""
    n = len(data)
    fig, ax = plt.subplots(2, 2, figsize=(15, 10))

    a = ax[0, 0]
    for d in data:
        a.plot(mids, d["dist"], "-", color=d["colour"], lw=2.2, label=d["label"])
    a.set_xscale("log"); a.set_xlabel("Chord length (\u00b5m)")
    a.set_ylabel("Mean counts / channel"); a.grid(True, ls=":", alpha=0.5)
    a.set_title("Absolute chord-length distribution", fontweight="bold")
    a.legend(fontsize=8.5)

    a = ax[0, 1]
    labels = ["<10 \u00b5m", "10\u2013100 \u00b5m", ">100 \u00b5m"]
    bins = [_bins(mids, d["dist"]) for d in data]
    x = np.arange(3); w = 0.8 / n
    ymax = max(v for b in bins for v in b)
    for i, (d, b) in enumerate(zip(data, bins)):
        dx = (i - (n - 1) / 2) * w
        a.bar(x + dx, b, w, color=d["colour"], label=d["label"])
        for xi, v in zip(x, b):
            a.text(xi + dx, v + ymax * 0.01, f"{v:.0f}", ha="center",
                   fontsize=6.5, color=d["colour"], rotation=90, va="bottom")
    a.set_xticks(x); a.set_xticklabels(labels)
    a.set_ylabel("Counts / s"); a.set_title("Counts by size bin", fontweight="bold")
    a.legend(fontsize=8.5); a.grid(True, axis="y", ls=":", alpha=0.5)

    a = ax[1, 0]
    dur = []
    for d in data:
        t_add = d["t"][d["add"]]
        post = d["t"] >= t_add
        a.plot(d["t"][post] - t_add, d["tot"][post], "-", color=d["colour"],
               lw=1.6, label=d["label"])
        dur.append((d["t"][post] - t_add).max())
    a.set_xlim(0, min(dur))  # crop to window all samples share at equilibrium
    a.set_xlabel("Time since shampoo added (s)"); a.set_ylabel("Total counts / s")
    a.grid(True, ls=":", alpha=0.5)
    a.set_title("Total counts at equilibrium", fontweight="bold")
    a.legend(fontsize=8.5)

    a = ax[1, 1]
    for d in data:
        a.plot(d["t"], d["sqr"], "-", color=d["colour"], lw=1.6, label=d["label"])
    a.set_ylim(0, 140)
    a.set_xlabel("Elapsed time (s)"); a.set_ylabel("Square-wt mean chord (\u00b5m)")
    a.grid(True, ls=":", alpha=0.5)
    a.set_title("Square-weighted mean chord (large-particle size)", fontweight="bold")
    a.legend(fontsize=8.5)

    fig.suptitle("Lasentec FBRM \u2014 competitor shampoos in DI water (0 gpg)",
                 fontsize=14.5, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(f"{R}/lasentec_competitors_diwater.png", dpi=150)
    plt.close(fig)
    print(f"wrote {R}/lasentec_competitors_diwater.png")


def main():
    data = [load(*p) for p in PRODUCTS]
    mids = data[0]["mids"]
    overlay(data, mids)
    diagnostic(data, mids)

    # ---- console summary ----
    for d in data:
        f, m, c = _bins(mids, d["dist"])
        pk = mids[int(np.argmax(d["dist"]))]
        print(f"\n{d['label']}  (add@scan {d['add']}, {d['steady'].sum()} steady scans)")
        print(f"  counts/s  <10um={f:8.0f}  10-100um={m:8.0f}  >100um={c:6.2f}  total={f+m+c:8.0f}")
        print(f"  peak channel = {pk:.1f} um   square-weighted mean chord = "
              f"{np.nanmean(d['sqr'][d['steady']]):.1f} um")


if __name__ == "__main__":
    main()
