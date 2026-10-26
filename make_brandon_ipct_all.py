"""Brandon's inverse-%T set: every opaque prototype run so far, one overview.

16-leg design = 2 chassis (BC128o M, GH130 LT1) x 8 polymers @ 0.25% active
(NH3196 control, Pq-6/22/47/53, Cassia, Nat Clear, Nat Caready), all opaque
(05PO + 1.0 DwC), inverse %T at t=0.

Files -> legs:
  BC128o_3196_NatCaready_200uL       T1 NH3196(1)      T2 Nat Caready(8)
  BC128oPQ6_PQ22                      T1 Pq-6(2)        T2 Pq-22(3)
  BC128oPQ47_PQ53                     T1 Pq-47(4)       T2 Pq-53(5)
  Opaque_GH130_3196_and_Nat_Caready  T1 NH3196(9)      T2 Nat Caready(16)
  GH130_Cassia_NatClear_200uL        T1 Cassia(14)     T2 Nat Clear(15)

Outputs: Reports/brandon_ipct_overlay.png (2 panels by chassis),
         Reports/brandon_ipct_metrics.png (dip-depth + floor bars), console table.
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
DL = r"C:\Users\fung.k.1\Downloads"
_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))


def _find(cands):
    return next((p for p in cands if os.path.exists(p)), cands[0])


F_BC_CTRL = _find([r"raw_data\BC128o_3196_NatCaready_200uL.txt",
                   rf"{DL}\BC128o_3196_NatCaready_200uL.txt"])
F_BC_PQ0622 = _find([rf"{DL}\BC128oPQ6_PQ22.txt", r"raw_data\BC128oPQ6_PQ22.txt"])
F_BC_PQ4753 = _find([rf"{DL}\BC128oPQ47_PQ53.txt", r"raw_data\BC128oPQ47_PQ53.txt"])
F_GH_CTRL = _find([r"raw_data\Opaque_GH130_3196_and_Nat_Caready.txt"])
F_GH_CASNC = _find([r"raw_data\GH130_Cassia_NatClear_200uL.txt"])

# (leg, polymer, chassis, file, trough, color)
SAMPLES = [
    (1, "NH3196 (ctrl)", "BC128o M", F_BC_CTRL, 1, "#8a8f98"),
    (2, "Polyquat-6", "BC128o M", F_BC_PQ0622, 1, "#2E75B6"),
    (3, "Polyquat-22", "BC128o M", F_BC_PQ0622, 2, "#c0392b"),
    (4, "Polyquat-47", "BC128o M", F_BC_PQ4753, 1, "#27ae60"),
    (5, "Polyquat-53", "BC128o M", F_BC_PQ4753, 2, "#8E44AD"),
    (8, "Nat Caready", "BC128o M", F_BC_CTRL, 2, "#e67e22"),
    (9, "NH3196 (ctrl)", "GH130 LT1", F_GH_CTRL, 1, "#8a8f98"),
    (14, "Cassia", "GH130 LT1", F_GH_CASNC, 1, "#16a085"),
    (15, "Nat Clear", "GH130 LT1", F_GH_CASNC, 2, "#B9770A"),
    (16, "Nat Caready", "GH130 LT1", F_GH_CTRL, 2, "#e67e22"),
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


def total_auc(x, y):
    absb = transmittance_to_absorbance(np.asarray(y, float))
    lx = np.log10(np.clip(np.asarray(x, float), 1e-9, None))
    o = np.argsort(lx)
    return float(_trapz(absb[o], lx[o]))


def analyze(path, trough):
    x, y = curve(path, trough)
    cx, cy, _ = clean_curve(x, y)
    fx, fy = smooth_hybrid(cx, cy)
    fp = clas.inverse_pct_fingerprint(x, y) or {}
    # deepest post-peak re-turbidity dip on the smoothed curve
    dip_pct, dip_dil, dip_depth = None, None, 0.0
    pk = fp.get("peak_dilution"); pkp = fp.get("peak_pct")
    if pk and pkp is not None:
        m = fx > pk
        if m.any():
            di = np.argmin(fy[m]); dip_pct = float(fy[m][di]); dip_dil = float(fx[m][di])
            dip_depth = max(0.0, float(pkp) - dip_pct)
    return dict(x=x, y=y, fx=fx, fy=fy, cx=cx, floor=fp.get("baseline_pct"),
                onset=fp.get("onset_dilution"), peak_pct=pkp, peak_dil=pk,
                dip_pct=dip_pct, dip_dil=dip_dil, dip_depth=dip_depth,
                total_auc=total_auc(cx, cy))


def main():
    chassis_order = ["BC128o M", "GH130 LT1"]
    results = []
    fig, axes = plt.subplots(1, 2, figsize=(16, 6.4))
    for ax, ch in zip(axes, chassis_order):
        xmins, xmaxs = [], []
        for leg, poly, c2, path, tr, col in SAMPLES:
            if c2 != ch:
                continue
            r = analyze(path, tr)
            results.append((leg, poly, ch, r))
            ax.plot(r["fx"], r["fy"], "-", color=col, lw=2.2, label=f"{poly}")
            xmins.append(r["cx"].min()); xmaxs.append(r["cx"].max())
        if xmins:
            _dil_axis(ax, min(xmins), max(xmaxs), fs=9)
        ax.set_ylim(0, 100)
        ax.set_xlabel("Dilution (1:X)"); ax.set_ylabel("%T (upper phase)")
        ax.grid(True, which="both", ls=":", alpha=0.5)
        ax.set_title(f"{ch} chassis \u2014 0.25% polymer, opaque (05PO)", fontweight="bold")
        ax.legend(fontsize=8.5, ncol=2)
    fig.suptitle("Brandon inverse %T \u2014 all opaque prototypes so far (t=0)  "
                 "\u25bc = re-turbidity dip (coacervation signature)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(f"{R}/brandon_ipct_overlay.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/brandon_ipct_overlay.png\n")

    # metrics bars: dip depth (coacervation signature) + floor
    labels = [f"{p}\n{c.split()[0]}" for (_, p, c, _r) in results]
    depth = [r["dip_depth"] for (_, _, _, r) in results]
    floor = [r["floor"] or 0 for (_, _, _, r) in results]
    cols = []
    for (_, _, c, _r) in results:
        cols.append("#2E75B6" if c == "BC128o M" else "#16a085")
    fig, ax = plt.subplots(1, 2, figsize=(16, 5.2))
    xp = np.arange(len(labels))
    ax[0].bar(xp, depth, color=cols, edgecolor="white")
    ax[0].set_xticks(xp); ax[0].set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax[0].set_ylabel("Re-turbidity dip depth (%T)"); ax[0].grid(True, axis="y", ls=":", alpha=0.5)
    ax[0].set_title("Coacervation dip depth (bigger = more re-turbidity)", fontweight="bold", fontsize=11)
    ax[1].bar(xp, floor, color=cols, edgecolor="white")
    ax[1].set_xticks(xp); ax[1].set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
    ax[1].set_ylabel("Opaque floor (%T at concentrated)"); ax[1].grid(True, axis="y", ls=":", alpha=0.5)
    ax[1].set_title("Opaque floor (base opacity, lower = more opaque)", fontweight="bold", fontsize=11)
    fig.suptitle("Brandon inverse %T metrics \u2014 BC128o M (blue) vs GH130 LT1 (green)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(f"{R}/brandon_ipct_metrics.png", dpi=150); plt.close(fig)
    print(f"wrote {R}/brandon_ipct_metrics.png\n")

    print(f"{'leg':>3s} {'polymer':14s} {'chassis':10s} {'floor':>6s} {'onset':>7s} "
          f"{'peak':>13s} {'dip':>14s} {'dipdepth':>8s} {'totAUC':>7s}")
    for leg, poly, ch, r in sorted(results, key=lambda z: (z[2], z[0])):
        onset = f"1:{r['onset']:g}" if r['onset'] else "--"
        peak = f"{r['peak_pct']:g}%@1:{r['peak_dil']:g}" if r['peak_pct'] else "--"
        dip = f"{r['dip_pct']:.0f}%@1:{r['dip_dil']:.0f}" if r['dip_pct'] else "--"
        print(f"{leg:>3d} {poly:14s} {ch:10s} {r['floor']:6.1f} {onset:>7s} "
              f"{peak:>13s} {dip:>14s} {r['dip_depth']:8.1f} {r['total_auc']:7.2f}")


if __name__ == "__main__":
    main()
