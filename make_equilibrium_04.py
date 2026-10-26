"""Timepoint comparability + equilibrium for the 0.4% dataset (Dow share CSV).

Mirrors make_equilibrium_analysis but for 0.4% polymer, to confirm the same
t=3~=t=5 / slow-decline conclusions hold at the lower concentration.
"""
import numpy as np

from make_dextran_full_analysis import curve04, POLY_ORDER, CHASSIS, _load_conc_df
from coacervation_analysis import transmittance_to_absorbance

_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))


def total_auc(xy):
    if xy is None:
        return None
    x, y = xy
    if len(x) < 3:
        return None
    absb = transmittance_to_absorbance(np.asarray(y, float))
    lx = np.log10(np.clip(np.asarray(x, float), 1e-9, None))
    o = np.argsort(lx)
    return float(_trapz(absb[o], lx[o]))


def main():
    d = _load_conc_df()
    times = sorted(int(round(t)) for t in d["Time_min"].unique())
    times = [t for t in times if t <= 15]
    rows = []
    for pkey in POLY_ORDER:
        for ch, _ in CHASSIS:
            s = [total_auc(curve04(pkey, ch, timepoint=t)) for t in times]
            if any(v is None for v in s):
                continue
            rows.append(np.array(s, float))
    A = np.array(rows)
    print(f"0.4% dataset: {A.shape[0]} formulas, timepoints {times}")

    def col(t):
        return A[:, times.index(t)]

    print("\n=== 0.4% timepoint comparability (value r, rank r) ===")
    for ta, tb in [(0, 3), (0, 5), (3, 5), (5, 15)]:
        if ta not in times or tb not in times:
            continue
        a, b = col(ta), col(tb)
        vr = np.corrcoef(a, b)[0, 1]
        rr = np.corrcoef(a.argsort().argsort(), b.argsort().argsort())[0, 1]
        print(f"t{ta} vs t{tb}:  value r={vr:.3f}   rank r={rr:.3f}   mean |d|={np.mean(np.abs(a-b)):.3f}")

    # equilibrium within 5% of final
    fin = A[:, -1]
    teq = []
    for s in A:
        f = s[-1]
        band = 0.05 * abs(f) if f else 0
        te = times[-1]
        for i, t in enumerate(times):
            if np.all(np.abs(s[i:] - f) <= band):
                te = t; break
        teq.append(te)
    teq = np.array(teq, float)
    print(f"\nmedian t_eq = {np.median(teq):.0f} min   "
          f"| % eq by t3 = {100*np.mean(teq<=3):.0f}%   by t5 = {100*np.mean(teq<=5):.0f}%")
    # direction
    down = np.mean(A[:, -1] < A[:, 0])
    print(f"fraction declining over time (t15<t0): {100*down:.0f}%")


if __name__ == "__main__":
    main()
