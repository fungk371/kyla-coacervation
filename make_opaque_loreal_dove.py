"""Inverse-%T for competitor opaque shampoos + FBRM + consumer cross-check.

lorealvsdove.txt: T1 = L'Oreal Hyaluron Plump, T2 = Dove Intensive Repair.
Both opaque -> inverse %T. Overlays raw %T + smooth curve vs dilution (t=0),
prints inverse-%T fingerprint (floor/onset/peak/dip/AUC) AND a total turbidity
AUC (absorbance x log-dilution), then tabulates against known FBRM floc metrics
and blind-Controls consumer scores so we can see if it all lines up.

Output: Reports/opaque_ipct_loreal_dove.png
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


def _find(cands):
    return next((p for p in cands if os.path.exists(p)), cands[0])


PATH = _find([r"C:\Users\fung.k.1\Downloads\lorealvsdove.txt",
              r"raw_data\lorealvsdove.txt"])
TROUGHS = {1: ("L'Oreal Hyaluron Plump", "#27ae60"),
           2: ("Dove Intensive Repair", "#c0392b")}

# Known FBRM (1:49, DI) + blind-Controls consumer (top-box), from prior work.
FBRM = {"L'Oreal Hyaluron Plump": {"frac_gt30": 6.3, "peak_um": 4.7},
        "Dove Intensive Repair": {"frac_gt30": 26.4, "peak_um": 18.8}}
CONSUMER = {"L'Oreal Hyaluron Plump": {"Fragrance 10h": "mid", "No-weigh-down": "mid"},
            "Dove Intensive Repair": {"Fragrance 10h": "WINS all", "No-weigh-down": "WINS"}}


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
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2))
    summary = {}
    for ax, (tr, (lab, col)) in zip(axes, TROUGHS.items()):
        x, y = curve(PATH, tr)
        cx, cy, _ = clean_curve(x, y)
        fx, fy = smooth_hybrid(cx, cy)
        ax.plot(fx, fy, "-", color=col, lw=2.4, label=lab)
        ax.plot(x, y, "o", color=col, ms=3.0, alpha=0.30)
        fp = clas.inverse_pct_fingerprint(x, y) or {}
        tot = total_turbidity_auc(cx, cy)
        dip_txt = "--"
        pk = fp.get("peak_dilution")
        if pk:
            m = fx > pk
            if m.any():
                di = np.argmin(fy[m]); dx = fx[m][di]; dy = fy[m][di]
                dip_txt = f"{dy:.0f}%@1:{dx:.0f}"
        summary[lab] = dict(floor=fp.get("baseline_pct"), onset=fp.get("onset_dilution"),
                            peak_pct=fp.get("peak_pct"), peak_dil=fp.get("peak_dilution"),
                            dip=dip_txt, inv_auc=fp.get("inverse_auc"), total_auc=tot,
                            redis=fp.get("redissolution_dilution"))
        _dil_axis(ax, cx.min(), cx.max(), fs=9)
        ax.set_ylim(0, 100)
        ax.set_xlabel("Dilution (1:X)"); ax.set_ylabel("%T (upper phase)")
        ax.grid(True, which="both", ls=":", alpha=0.5)
        ax.set_title(lab, fontweight="bold")
        ax.legend(loc="lower right", fontsize=9)
    fig.suptitle("Inverse %T \u2014 L'Oreal Hyaluron Plump vs Dove Intensive Repair (t=0)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{R}/opaque_ipct_loreal_dove.png", dpi=150)
    plt.close(fig)
    print(f"wrote {R}/opaque_ipct_loreal_dove.png\n")

    print(f"{'product':26s} {'floor':>6s} {'onset':>7s} {'peak':>13s} {'dip':>13s} "
          f"{'invAUC':>7s} {'totAUC':>7s} {'FBRM>30':>8s} {'peakum':>7s}")
    for lab, s in summary.items():
        fb = FBRM.get(lab, {})
        onset = f"1:{s['onset']:g}" if s['onset'] else "--"
        peak = f"{s['peak_pct']:g}%@1:{s['peak_dil']:g}" if s['peak_pct'] else "--"
        inv = f"{s['inv_auc']:.1f}" if s['inv_auc'] is not None else "--"
        print(f"{lab:26s} {s['floor']:6.1f} {onset:>7s} {peak:>13s} {s['dip']:>13s} "
              f"{inv:>7s} {s['total_auc']:7.2f} {fb.get('frac_gt30','--'):>8} {fb.get('peak_um','--'):>7}")
    print("\nConsumer (blind Controls TB): Dove WINS all fragrance touchpoints + no-weigh-down;")
    print("L'Oreal mid-pack. FBRM: Dove 26.4% >30um / 18.8um (big flocs) vs L'Oreal 6.3% / 4.7um (small).")


if __name__ == "__main__":
    main()
