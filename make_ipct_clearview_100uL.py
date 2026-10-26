"""Formulator-friendly (clear-read) view of the 100 uL inverse-%T run.

GH130_3196andNatCaready_100uL.txt: T1 = Nhance 3196, T2 = Nat Caready 0.25%.
Reuses the clear_view transform (running-max baseline subtraction) from
make_ipct_clearview and compares the 100 uL vs 200 uL coacervation amount/width.

Output: Reports/ipct_clearview_100uL.png
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os

from make_dextran_timepoint_analysis import _dil_axis
from make_ipct_clearview import clear_view


def _find(cands):
    return next((p for p in cands if os.path.exists(p)), cands[0])


R = "Reports"
F100 = _find([r"C:\Users\fung.k.1\Downloads\GH130_3196andNatCaready_100uL.txt",
              r"raw_data\GH130_3196andNatCaready_100uL.txt"])
F200 = _find([r"raw_data\Opaque_GH130_3196_and_Nat_Caready.txt"])
TROUGHS = [("Nhance 3196", 1, "#2E75B6"), ("Nat Caready 0.25%", 2, "#c0392b")]


def main():
    fig, axes = plt.subplots(1, 2, figsize=(16, 6.2))
    xs_lo, xs_hi = [], []
    print(f"{'sample':20s} {'vol':>5s} {'amount':>7s} {'width(dec)':>10s} {'peakturb':>9s} {'@dil':>8s}")
    for name, tr, col in TROUGHS:
        r = clear_view(F100, tr)
        axes[0].plot(r["fx"], r["fy"], "-", color=col, lw=2.3, label=name)
        axes[1].plot(r["fx"], r["clear"], "-", color=col, lw=2.3, label=name)
        xs_lo.append(r["cx"].min()); xs_hi.append(r["cx"].max())
        pk = f"1:{r['peak_dil']:.0f}" if r["peak"] > 2 else "--"
        print(f"{name:20s} {'100':>5s} {r['amount']:7.2f} {r['width']:10.2f} {r['peak']:9.1f} {pk:>8s}")
        # 200 uL reference numbers (dashed on clear panel)
        try:
            r2 = clear_view(F200, tr)
            axes[1].plot(r2["fx"], r2["clear"], "--", color=col, lw=1.6, alpha=0.7)
            pk2 = f"1:{r2['peak_dil']:.0f}" if r2["peak"] > 2 else "--"
            print(f"{name:20s} {'200':>5s} {r2['amount']:7.2f} {r2['width']:10.2f} {r2['peak']:9.1f} {pk2:>8s}")
        except Exception:
            pass

    axes[0].set_title("As measured \u2014 inverse %T (100 \u00b5L, opaque)", fontweight="bold")
    axes[0].set_ylabel("%T (upper phase)")
    axes[1].set_title("Clear-read equivalent \u2014 coacervation = a DIP\n"
                      "(100 \u00b5L solid, 200 \u00b5L dashed reference)", fontweight="bold")
    axes[1].set_ylabel("Equivalent clear %T")
    for ax in axes:
        _dil_axis(ax, min(xs_lo), max(xs_hi), fs=9)
        ax.set_ylim(0, 100)
        ax.set_xlabel("Dilution (1:X)   \u2014   rinse \u2192")
        ax.grid(True, which="both", ls=":", alpha=0.5)
        ax.legend(fontsize=9)
    fig.suptitle("Inverse %T made formulator-friendly \u2014 GH130 100 \u00b5L run (t=0)",
                 fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(f"{R}/ipct_clearview_100uL.png", dpi=150); plt.close(fig)
    print(f"\nwrote {R}/ipct_clearview_100uL.png")


if __name__ == "__main__":
    main()
