"""All 4 opaque competitor shampoos: inverse %T + FBRM + consumer cross-check.

Files (t=0, in-well direct read):
  lorealvsdove.txt        T1 L'Oreal Hyaluron Plump, T2 Dove Intensive Repair
  PanteneDMR_Kerastate.txt T1 Pantene DMR,           T2 Kerastase Nutritive

Produces a 2x2 inverse-%T panel, a scatter of the coacervation-hump AUC vs FBRM
floc fraction (>30 um), and a console table lining up inverse %T / FBRM / consumer.

Outputs: Reports/opaque_ipct_competitors4.png, Reports/opaque_ipct_vs_fbrm.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os

import coacervation_lasentec as clas
from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import dilution_ratio, transmittance_to_absorbance
from make_dextran_figs import clean_curve
from make_dextran_timepoint_analysis import smooth_hybrid, _dil_axis

R = "Reports"
_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))
DL = r"C:\Users\fung.k.1\Downloads"


def _find(cands):
    return next((p for p in cands if os.path.exists(p)), cands[0])


LD = _find([rf"{DL}\lorealvsdove.txt", r"raw_data\lorealvsdove.txt"])
PK = _find([rf"{DL}\PanteneDMR_Kerastate.txt", r"raw_data\PanteneDMR_Kerastate.txt"])

# (label, file, trough, color, FBRM frac>30, FBRM peak um, consumer note)
COMP = [
    ("Pantene DMR",            PK, 1, "#2E75B6", 1.3, 3.8, "worst fragrance longevity"),
    ("L'Oreal Hyaluron Plump", LD, 1, "#27ae60", 6.3, 4.7, "mid-pack"),
    ("Kerastase Nutritive",    PK, 2, "#8E44AD", 9.8, 5.4, "loses most touchpoints"),
    ("Dove Intensive Repair",  LD, 2, "#c0392b", 26.4, 18.8, "WINS fragrance + no-weigh-down"),
]


def curve(path, trough, tp=0):
    df = annotate_concentration(parse_kinetic_plate_file(path))
    times = sorted(df["timepoint_minutes"].unique())
    t = min(times, key=lambda z: abs(z - tp))
    sel = df[(df["trough"] == trough) & (df["timepoint_minutes"] == t)].dropna(
        subset=["formula_fraction"]).sort_values("formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(sel["formula_fraction"].to_numpy(float)), float)
    y = sel["transmission_pct"].to_numpy(float)
    o = np.argsort(x)
    return x[o], y[o]


def total_turbidity_auc(x, y):
    absb = transmittance_to_absorbance(np.asarray(y, float))
    lx = np.log10(np.clip(np.asarray(x, float), 1e-9, None))
    o = np.argsort(lx)
    return float(_trapz(absb[o], lx[o]))


def main():
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    axes = axes.ravel()
    rows = []
    for ax, (lab, path, tr, col, frac, pk_um, cons) in zip(axes, COMP):
        x, y = curve(path, tr)
        cx, cy, _ = clean_curve(x, y)
        fx, fy = smooth_hybrid(cx, cy)
        ax.plot(fx, fy, "-", color=col, lw=2.4, label=lab)
        ax.plot(x, y, "o", color=col, ms=2.8, alpha=0.28)
        fp = clas.inverse_pct_fingerprint(x, y) or {}
        tot = total_turbidity_auc(cx, cy)
        dip_txt = "--"
        pkd = fp.get("peak_dilution")
        if pkd:
            m = fx > pkd
            if m.any():
                di = np.argmin(fy[m]); dx = fx[m][di]; dy = fy[m][di]
                dip_txt = f"{dy:.0f}%@1:{dx:.0f}"
        rows.append(dict(lab=lab, floor=fp.get("baseline_pct"), onset=fp.get("onset_dilution"),
                         peak_pct=fp.get("peak_pct"), peak_dil=fp.get("peak_dilution"),
                         dip=dip_txt, inv_auc=fp.get("inverse_auc"), total_auc=tot,
                         frac=frac, pk_um=pk_um, cons=cons))
        _dil_axis(ax, cx.min(), cx.max(), fs=9)
        ax.set_ylim(0, 100)
        ax.set_xlabel("Dilution (1:X)"); ax.set_ylabel("%T")
        ax.grid(True, which="both", ls=":", alpha=0.5)
        ax.set_title(f"{lab}  (FBRM >30\u00b5m: {frac}%)", fontweight="bold", fontsize=11)
    fig.suptitle("Inverse %T \u2014 4 opaque competitor shampoos (t=0, in-well)",
                 fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    fig.savefig(f"{R}/opaque_ipct_competitors4.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/opaque_ipct_competitors4.png\n")

    # ---- correlation scatter: hump AUC & total AUC vs FBRM frac>30 ----
    fracs = np.array([r["frac"] for r in rows], float)
    inv = np.array([r["inv_auc"] if r["inv_auc"] is not None else np.nan for r in rows], float)
    tot = np.array([r["total_auc"] for r in rows], float)
    r_inv = np.corrcoef(fracs, inv)[0, 1]
    r_tot = np.corrcoef(fracs, tot)[0, 1]
    fig, ax = plt.subplots(1, 2, figsize=(13, 5.2))
    for a, vals, ttl, rr in [(ax[0], inv, "Coacervation-hump AUC", r_inv),
                             (ax[1], tot, "Total turbidity AUC", r_tot)]:
        for r_ in rows:
            a.scatter(r_["frac"], (inv if ttl.startswith("Coac") else tot)[rows.index(r_)],
                      s=90, color=dict((c[0], c[3]) for c in COMP)[r_["lab"]], zorder=3)
            a.annotate(r_["lab"], (r_["frac"], (inv if ttl.startswith("Coac") else tot)[rows.index(r_)]),
                       fontsize=8, xytext=(5, 4), textcoords="offset points")
        m = ~np.isnan(vals)
        if m.sum() >= 2 and fracs[m].std():
            z = np.polyfit(fracs[m], vals[m], 1); xg = np.linspace(fracs.min(), fracs.max(), 40)
            a.plot(xg, np.polyval(z, xg), "--", color="#888", lw=1)
        a.set_xlabel("FBRM floc fraction (% counts > 30 \u00b5m)")
        a.set_ylabel(ttl)
        a.set_title(f"{ttl} vs FBRM floc  (r = {rr:+.2f}, n=4)", fontweight="bold", fontsize=11)
        a.grid(True, ls=":", alpha=0.5)
    fig.suptitle("Inverse-%T coacervation vs FBRM floc size \u2014 competitors",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{R}/opaque_ipct_vs_fbrm.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/opaque_ipct_vs_fbrm.png\n")

    print(f"{'product':26s} {'floor':>6s} {'onset':>7s} {'peak':>13s} {'dip':>13s} "
          f"{'humpAUC':>8s} {'totAUC':>7s} {'FBRM>30':>8s} {'um':>5s}  consumer")
    for r in rows:
        onset = f"1:{r['onset']:g}" if r['onset'] else "--"
        peak = f"{r['peak_pct']:g}%@1:{r['peak_dil']:g}" if r['peak_pct'] else "--"
        inv_s = f"{r['inv_auc']:.1f}" if r['inv_auc'] is not None else "--"
        print(f"{r['lab']:26s} {r['floor']:6.1f} {onset:>7s} {peak:>13s} {r['dip']:>13s} "
              f"{inv_s:>8s} {r['total_auc']:7.2f} {r['frac']:>7}% {r['pk_um']:>5}  {r['cons']}")
    print(f"\nhump-AUC vs FBRM floc r = {r_inv:+.2f} | total-AUC vs FBRM floc r = {r_tot:+.2f}  (n=4)")


if __name__ == "__main__":
    main()
