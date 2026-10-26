"""Equilibrium-time analysis for AUC timepoint selection.

Answers, empirically:
  1) When does the coacervation signal (total AUC) reach equilibrium across the
     0-15 min kinetic read? -> supports Parth's "5 min" vs a t=0/3 default.
  2) Does SHAKING change the equilibrium time / direction? (shake vs no-shake,
     EED0 + APG, CD2 & Dex-K).
  3) Are t=3 and t=5 interchangeable (robot fill-delay hypothesis)?  Rank &
     value correlation between timepoints.
  4) Framework note for correlating a chosen timepoint to ILS/PTL performance.

Total AUC = absorbance integrated over log-dilution (whole curve).

Outputs: Reports/equilibrium_allformulas.png,
         Reports/equilibrium_shake_vs_noshake.png   + console tables.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os

from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import dilution_ratio, transmittance_to_absorbance
from make_dextran_figs import clean_curve
from make_dextran_chassis_compare import POLYMERS

R = "Reports"
CHASSIS = ["EED0", "LAPB", "APG"]
POLY_ORDER = ["CD2", "Dex-K", "Dex-A", "Dex-B", "Dex-B*", "Dex-J", "Dex-J*"]
TIMES = list(range(0, 16))
_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))


def _curve(path, trough, tp):
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
    cx, cy, _ = clean_curve(x[o], y[o])
    return cx, cy


def auc(path, trough, tp):
    c = _curve(path, trough, tp)
    if c is None or len(c[0]) < 3:
        return None
    x, y = c
    absb = transmittance_to_absorbance(y)
    lx = np.log10(np.clip(x, 1e-9, None))
    o = np.argsort(lx)
    return float(_trapz(absb[o], lx[o]))


def auc_series(path, trough):
    return np.array([auc(path, trough, t) for t in TIMES], float)


def t_equilibrium(series, tol=0.05):
    """First time (min) after which AUC stays within tol*final of final value."""
    final = series[-1]
    if not np.isfinite(final) or final == 0:
        return np.nan
    band = tol * abs(final)
    for i, t in enumerate(TIMES):
        if np.all(np.abs(series[i:] - final) <= band):
            return t
    return TIMES[-1]


# =============================================================== 1) all formulas
def all_formulas():
    labels, series_list, teq = [], [], []
    for pkey in POLY_ORDER:
        for ch in CHASSIS:
            chd = POLYMERS.get(pkey, {})
            if ch not in chd:
                continue
            path, tr = chd[ch]
            path = path if path.startswith("raw_data") else f"raw_data/{path}"
            s = auc_series(path, tr)
            if np.isnan(s).all():
                continue
            labels.append(f"{pkey}\u00b7{ch}")
            series_list.append(s)
            teq.append(t_equilibrium(s))
    teq = np.array(teq, float)

    fig, ax = plt.subplots(1, 2, figsize=(15, 5.6))
    for lab, s in zip(labels, series_list):
        f = s[-1] if s[-1] else 1.0
        ax[0].plot(TIMES, s / f, "-", lw=1.2, alpha=0.55)
    ax[0].axvline(3, color="#e67e22", ls="--", lw=1.5, label="t=3")
    ax[0].axvline(5, color="#c0392b", ls="--", lw=1.5, label="t=5 (Parth)")
    ax[0].axhline(1.0, color="k", ls=":", lw=1, alpha=0.5)
    ax[0].set_xlabel("Time (min)"); ax[0].set_ylabel("AUC / AUC(15 min)")
    ax[0].set_title("Approach to equilibrium (all 21 formulas)", fontweight="bold")
    ax[0].grid(True, ls=":", alpha=0.5); ax[0].legend(fontsize=9)

    ax[1].hist(teq, bins=np.arange(-0.5, 16.5, 1), color="#1f4e79", edgecolor="white")
    ax[1].axvline(np.nanmedian(teq), color="#c0392b", lw=2,
                  label=f"median = {np.nanmedian(teq):.0f} min")
    ax[1].set_xlabel("Time to equilibrium (min, within 5% of final)")
    ax[1].set_ylabel("# formulas"); ax[1].legend(fontsize=9)
    ax[1].set_title("When each formula equilibrates", fontweight="bold")
    ax[1].grid(True, axis="y", ls=":", alpha=0.5)
    fig.suptitle("AUC equilibrium across the kinetic read \u2014 1% dextran (shaken standard)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{R}/equilibrium_allformulas.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/equilibrium_allformulas.png")

    # timepoint value/rank correlations
    A = np.array(series_list)  # formulas x times
    def col(t): return A[:, TIMES.index(t)]
    print("\n=== timepoint comparability (value r, rank r) ===")
    for ta, tb in [(0, 3), (0, 5), (3, 5), (5, 15)]:
        a, b = col(ta), col(tb)
        vr = np.corrcoef(a, b)[0, 1]
        rr = np.corrcoef(a.argsort().argsort(), b.argsort().argsort())[0, 1]
        print(f"t{ta} vs t{tb}:  value r={vr:.3f}   rank r={rr:.3f}   "
              f"mean |Δ|={np.nanmean(np.abs(a-b)):.3f}")
    print(f"\nequilibrium (within 5% of final):")
    print(f"  median t_eq = {np.nanmedian(teq):.0f} min")
    print(f"  % equilibrated by t=3: {100*np.mean(teq<=3):.0f}%   "
          f"by t=5: {100*np.mean(teq<=5):.0f}%")
    return teq


# =============================================================== 2) shake vs no-shake
def _find(cands):
    return next((p for p in cands if os.path.exists(p)), cands[0])


NOSHAKE_EED0 = _find([r"raw_data\noshake_GH150DDU0_1percentCD2andDexK.txt",
                      r"C:\Users\fung.k.1\Downloads\noshake_GH150DDU0_1percentCD2andDexK.txt"])
NOSHAKE_APG = _find([r"raw_data\noshakeAPG_CD2_Dex_1percent.txt",
                     r"C:\Users\fung.k.1\Downloads\noshakeAPG_CD2_Dex_1percent.txt"])
SETS = {
    "EED0 CD2":   (r"raw_data\20260904_1_GH150EED0_CD2_DexB_1percent.txt", 1, NOSHAKE_EED0, 1),
    "EED0 Dex-K": (r"raw_data\20260904_7_GH150DDU0_LAPB_1percent_NATIVE_DexK.txt", 2, NOSHAKE_EED0, 2),
    "APG CD2":    (r"raw_data\20260903_APG_CD2_DexB_RawData.txt", 1, NOSHAKE_APG, 1),
    "APG Dex-K":  (r"raw_data\20260903_APGDexK_LAPBDexK_RawData.txt", 1, NOSHAKE_APG, 2),
}


def shake_vs_noshake():
    fig, axes = plt.subplots(1, 4, figsize=(19, 5), sharey=True)
    print("\n=== shake vs no-shake equilibrium ===")
    print(f"{'set':10s} {'shake teq':>10s} {'noshk teq':>10s} {'shk dir':>8s} {'nsh dir':>8s}")
    for ax, (name, (sp, st, npath, nt)) in zip(axes, SETS.items()):
        ss = auc_series(sp, st)
        ns = auc_series(npath, nt)
        ax.plot(TIMES, ss, "-o", color="#1f4e79", ms=3, label="shake")
        ax.plot(TIMES, ns, "--s", color="#e67e22", ms=3, label="no-shake")
        ax.axvline(3, color="#888", ls=":", lw=1); ax.axvline(5, color="#c0392b", ls=":", lw=1)
        ax.set_title(name, fontweight="bold"); ax.set_xlabel("Time (min)")
        ax.grid(True, ls=":", alpha=0.5); ax.legend(fontsize=8)
        s_dir = "up" if ss[-1] > ss[0] else "down"
        n_dir = "up" if ns[-1] > ns[0] else "down"
        print(f"{name:10s} {t_equilibrium(ss):10.0f} {t_equilibrium(ns):10.0f} "
              f"{s_dir:>8s} {n_dir:>8s}")
    axes[0].set_ylabel("Total AUC (absorbance \u00d7 log-dilution)")
    fig.suptitle("Shake vs no-shake \u2014 AUC approach to equilibrium (t=3 grey, t=5 red)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{R}/equilibrium_shake_vs_noshake.png", dpi=150); plt.close(fig)
    print(f"\nwrote {R}/equilibrium_shake_vs_noshake.png")


if __name__ == "__main__":
    all_formulas()
    shake_vs_noshake()
