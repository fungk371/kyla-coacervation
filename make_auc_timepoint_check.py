"""Timepoint-choice diagnostic for AUC reporting: t=0 vs t=3 vs 0-2 min average.

Questions answered:
  1) Does the FORMULA RANKING change with timepoint? (rank-invariance test)
  2) Is t=0 noisier / more artifact-prone than later reads? (well-to-well
     roughness, count of bubble/spike wells, spread of replicate-adjacent wells)

Uses the 1% dextran plates (21 formulas). Total AUC = absorbance integrated over
log-dilution (whole curve), matching make_dextran_total_auc.

Output: Reports/auc_timepoint_check.png  + console tables.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import dilution_ratio, transmittance_to_absorbance
from make_dextran_figs import clean_curve
from make_dextran_chassis_compare import POLYMERS

R = "Reports"
CHASSIS = ["EED0", "LAPB", "APG"]
POLY_ORDER = ["CD2", "Dex-K", "Dex-A", "Dex-B", "Dex-B*", "Dex-J", "Dex-J*"]
_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))


def _raw_curve(path, trough, tp):
    """Return (x_dilution_sorted, y_pct_raw) at nearest timepoint, no cleaning."""
    df = annotate_concentration(parse_kinetic_plate_file(path))
    sel = df[df["trough"] == trough].dropna(subset=["formula_fraction"])
    if sel.empty:
        return None
    times = sorted(sel["timepoint_minutes"].unique())
    t = min(times, key=lambda z: abs(z - tp))
    cur = sel[sel["timepoint_minutes"] == t].sort_values("formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(cur["formula_fraction"].to_numpy(float)), float)
    y = cur["transmission_pct"].to_numpy(float)
    o = np.argsort(x)
    return x[o], y[o]


def total_auc_from(x, y):
    absb = transmittance_to_absorbance(np.asarray(y, float))
    lx = np.log10(np.clip(np.asarray(x, float), 1e-9, None))
    o = np.argsort(lx)
    return float(_trapz(absb[o], lx[o]))


def auc_at(path, trough, tp):
    c = _raw_curve(path, trough, tp)
    if c is None:
        return None
    x, y = c
    cx, cy, _ = clean_curve(x, y)
    if len(cx) < 3:
        return None
    return total_auc_from(cx, cy)


def auc_avg(path, trough, tps=(0, 1, 2)):
    vals = [auc_at(path, trough, t) for t in tps]
    vals = [v for v in vals if v is not None]
    return float(np.mean(vals)) if vals else None


def roughness(path, trough, tp):
    """Artifact proxies at one timepoint: local roughness + #spikes removed."""
    c = _raw_curve(path, trough, tp)
    if c is None:
        return None
    x, y = c
    # spikes removed by the conservative bubble filter
    cx, cy, nrem = clean_curve(x, y)
    # well-to-well roughness = std of 2nd difference of RAW %T (bubble/mixing noise)
    if len(y) >= 3:
        rough = float(np.std(np.diff(y, 2)))
    else:
        rough = np.nan
    return rough, nrem


def main():
    labels, t0s, t3s, avgs = [], [], [], []
    rough0, rough3, spikes0, spikes3 = [], [], [], []
    for pkey in POLY_ORDER:
        for ch in CHASSIS:
            chd = POLYMERS.get(pkey, {})
            if ch not in chd:
                continue
            path, tr = chd[ch]
            path = path if path.startswith("raw_data") else f"raw_data/{path}"
            a0, a3 = auc_at(path, tr, 0), auc_at(path, tr, 3)
            av = auc_avg(path, tr, (0, 1, 2))
            if None in (a0, a3, av):
                continue
            labels.append(f"{pkey}\u00b7{ch}")
            t0s.append(a0); t3s.append(a3); avgs.append(av)
            r0 = roughness(path, tr, 0); r3 = roughness(path, tr, 3)
            rough0.append(r0[0]); spikes0.append(r0[1])
            rough3.append(r3[0]); spikes3.append(r3[1])

    t0s, t3s, avgs = map(np.array, (t0s, t3s, avgs))
    rough0, rough3 = np.array(rough0), np.array(rough3)
    spikes0, spikes3 = np.array(spikes0), np.array(spikes3)

    # rank comparison (higher AUC = rank 1)
    r_t0 = (-t0s).argsort().argsort() + 1
    r_t3 = (-t3s).argsort().argsort() + 1
    drank = r_t0 - r_t3

    print("=== AUC by timepoint (whole-curve, absorbance x log-dilution) ===")
    print(f"{'formula':14s} {'t0':>7s} {'t3':>7s} {'0-2avg':>7s} "
          f"{'rk0':>4s} {'rk3':>4s} {'d':>3s}")
    order = (-t3s).argsort()
    for i in order:
        print(f"{labels[i]:14s} {t0s[i]:7.3f} {t3s[i]:7.3f} {avgs[i]:7.3f} "
              f"{r_t0[i]:4d} {r_t3[i]:4d} {drank[i]:+3d}")

    # correlations / stability
    sp = np.corrcoef(r_t0, r_t3)[0, 1]
    max_shift = int(np.abs(drank).max())
    print(f"\nrank corr t0 vs t3 = {sp:.3f}   |   max rank shift = {max_shift}")
    print(f"mean roughness  t0 = {np.nanmean(rough0):.2f}   t3 = {np.nanmean(rough3):.2f}")
    print(f"mean #spikes    t0 = {spikes0.mean():.2f}   t3 = {spikes3.mean():.2f}")
    print(f"formulas rougher at t0 than t3: {(rough0 > rough3).sum()}/{len(rough0)}")
    print(f"formulas more spikes at t0: {(spikes0 > spikes3).sum()}/{len(spikes0)}")

    # ---- figure ----
    fig, ax = plt.subplots(1, 3, figsize=(17, 5.6))
    x = np.arange(len(labels)); w = 0.28
    o = (-t3s).argsort()
    L = [labels[i] for i in o]
    ax[0].bar(x - w, t0s[o], w, color="#e67e22", label="t=0")
    ax[0].bar(x, t3s[o], w, color="#1f4e79", label="t=3")
    ax[0].bar(x + w, avgs[o], w, color="#2e9e5b", label="0-2 avg")
    ax[0].set_xticks(x); ax[0].set_xticklabels(L, rotation=90, fontsize=7)
    ax[0].set_ylabel("Total AUC"); ax[0].legend(fontsize=9)
    ax[0].set_title("AUC by timepoint", fontweight="bold")
    ax[0].grid(True, axis="y", ls=":", alpha=0.5)

    ax[1].scatter(t3s, t0s, c="#c0392b", s=36)
    lim = [min(t0s.min(), t3s.min()), max(t0s.max(), t3s.max())]
    ax[1].plot(lim, lim, "k--", lw=1, alpha=0.6)
    ax[1].set_xlabel("AUC at t=3"); ax[1].set_ylabel("AUC at t=0")
    ax[1].set_title(f"t0 vs t3  (rank r={sp:.3f}, max shift {max_shift})", fontweight="bold")
    ax[1].grid(True, ls=":", alpha=0.5)

    ax[2].bar(x - w / 2, rough0[o], w, color="#e67e22", label="t=0")
    ax[2].bar(x + w / 2, rough3[o], w, color="#1f4e79", label="t=3")
    ax[2].set_xticks(x); ax[2].set_xticklabels(L, rotation=90, fontsize=7)
    ax[2].set_ylabel("Well-to-well roughness (raw %T)")
    ax[2].set_title("Artifact proxy: t=0 vs t=3", fontweight="bold")
    ax[2].legend(fontsize=9); ax[2].grid(True, axis="y", ls=":", alpha=0.5)

    fig.suptitle("AUC timepoint diagnostic \u2014 rank invariance & t=0 artifact check "
                 "(1% dextran, 21 formulas)", fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(f"{R}/auc_timepoint_check.png", dpi=150)
    plt.close(fig)
    print(f"\nwrote {R}/auc_timepoint_check.png")


if __name__ == "__main__":
    main()
