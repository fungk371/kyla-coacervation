"""Inverse-%T fingerprint for GH130 Cassia (T1) + Nat Clear (T2), 200 uL read.

Overlays raw upper-phase %T points + smooth curve vs dilution (1:X), t=0, and
prints the inverse-%T fingerprint (floor / onset / peak / dip / redissolution /
AUC) for each trough.

Output: Reports/opaque_ipct_cassia_natclear.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import os

import coacervation_lasentec as clas
from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import dilution_ratio
from make_dextran_figs import clean_curve
from make_dextran_timepoint_analysis import smooth_hybrid, _dil_axis

R = "Reports"


def _find(cands):
    return next((p for p in cands if os.path.exists(p)), cands[0])


PATH = _find([
    r"C:\Users\fung.k.1\Downloads\GH130_Cassia_NatClear_200uL.txt",
    r"raw_data\GH130_Cassia_NatClear_200uL.txt",
])
TROUGHS = {1: ("GH130 \u00b7 Cassia polymer", "#8e44ad"),
           2: ("GH130 \u00b7 Nat Clear", "#2E75B6")}


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


def main():
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.2))
    print(f"{'poly':16s} {'floor':>6s} {'onset':>7s} {'peak':>14s} "
          f"{'dip':>16s} {'redis':>8s} {'AUC':>7s}")
    for ax, (tr, (lab, col)) in zip(axes, TROUGHS.items()):
        x, y = curve(PATH, tr)
        cx, cy, _ = clean_curve(x, y)
        fx, fy = smooth_hybrid(cx, cy)
        ax.plot(fx, fy, "-", color=col, lw=2.4, label=lab)
        ax.plot(x, y, "o", color=col, ms=3.0, alpha=0.30)
        fp = clas.inverse_pct_fingerprint(x, y)
        if fp:
            # locate the deepest post-peak dip on the smoothed curve
            dip_txt = "--"
            try:
                pk = fp["peak_dilution"]
                mask = fx > pk
                if mask.any():
                    di = np.argmin(fy[mask])
                    dx = fx[mask][di]; dy = fy[mask][di]
                    dip_txt = f"{dy:.0f}%@1:{dx:.0f}"
            except Exception:
                pass
            ax.axvline(fp["peak_dilution"], color=col, ls=":", alpha=0.5)
            print(f"{lab.split(chr(183))[1].strip()[:16]:16s} "
                  f"{fp['baseline_pct']:6.1f} 1:{fp['onset_dilution']:<5g} "
                  f"{fp['peak_pct']:>5g}%@1:{fp['peak_dilution']:<5g} "
                  f"{dip_txt:>16s} {str(fp['redissolution_dilution']):>8s} "
                  f"{fp['inverse_auc']:>7.1f}")
        _dil_axis(ax, cx.min(), cx.max(), fs=9)
        ax.set_ylim(0, 100)
        ax.set_xlabel("Dilution (1:X)")
        ax.set_ylabel("%T (upper phase)")
        ax.grid(True, which="both", ls=":", alpha=0.5)
        ax.set_title(lab, fontweight="bold")
        ax.legend(loc="lower right", fontsize=9)
    fig.suptitle("Inverse %T \u2014 GH130 Cassia + Nat Clear (200 \u00b5L upper-phase read, t=0)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{R}/opaque_ipct_cassia_natclear.png", dpi=150)
    plt.close(fig)
    print(f"\nwrote {R}/opaque_ipct_cassia_natclear.png")


if __name__ == "__main__":
    main()
