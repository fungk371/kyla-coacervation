"""Lasentec (FBRM) floc-structure analysis vs coacervation amount & ILS.

Tests the standing hypothesis: coacervate AMOUNT (inverse-%T) explains most of
the conditioning, and coacervate STRUCTURE / floc size (Lasentec) explains the
residual -- e.g. why the guar 3196 control conditions well in GH130 on only
moderate coacervate amount (loose, large flocs).

FBRM chord-count metrics per sample:
  total     total chord counts (population density of flocs)
  mean_chord   count-weighted mean chord length (um)
  sqwt_mean    square-weighted mean chord (emphasises COARSE flocs)
  pct_coarse   % of counts above 50 um (large-floc fraction)
  coarse50     absolute counts above 50 um
"""
import numpy as np
import pandas as pd
import make_brandon_ipct_fingerprints as B

POLY = {"NH3196": "NH3196", "Pq6": "Polyquat-6", "Pq22": "Polyquat-22",
        "Pq47": "Polyquat-47", "Pq53": "Polyquat-53", "NatCaready": "Nat Caready",
        "NatClear": "Nat Clear", "Cassia": "Cassia"}
CH = {"GH130": "GH130 LT1", "BC128o": "BC128o M"}


def pearson(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    return float(np.corrcoef(x[m], y[m])[0, 1]) if m.sum() >= 3 else np.nan


def partial(x, y, z):
    rxy, rxz, ryz = pearson(x, y), pearson(x, z), pearson(y, z)
    d = np.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))
    return (rxy - rxz * ryz) / d if d > 0 else np.nan


def amount_windowed(path, tr, cap=50.0):
    x, y = B.curve(path, tr)
    cx, cy, _ = B.clean_curve(x, y)
    fx, fy = B.smooth_hybrid(cx, cy)
    floor = float(np.min(fy[:max(3, len(fy) // 10)]))
    m = fx <= cap
    return max(0.0, float(np.percentile(fy[m], 95)) - floor) if m.any() else 0.0


def main():
    las = pd.read_csv(r"raw_data\lasentec_brandon.csv")
    mid = las["chord"].values
    rows = []
    for col in las.columns[1:]:
        c = las[col].values.astype(float)
        tot = c.sum()
        mean_chord = float((c * mid).sum() / tot)
        sqwt = float((c * mid ** 2).sum() / (c * mid).sum())
        coarse50 = float(c[mid > 50].sum())
        pct_coarse = 100.0 * coarse50 / tot
        pcode, ccode = col.rsplit("_", 1)
        rows.append({"polymer": POLY[pcode], "chassis": CH[ccode],
                     "total": tot, "mean_chord": mean_chord, "sqwt_mean": sqwt,
                     "coarse50": coarse50, "pct_coarse": pct_coarse})
    fdf = pd.DataFrame(rows)

    # coacervate amount (windowed <=1:50 p95 height)
    amt = {(p, c): amount_windowed(path, tr) for p, c, path, tr in B.SAMPLES}
    fdf["amount"] = fdf.apply(lambda s: amt.get((s.polymer, s.chassis), np.nan), axis=1)

    ils = pd.read_csv(r"raw_data\brandon_ils_detail.csv")
    cond = ["wet_slip", "detangle_wide", "detangle_fine", "smooth_surface",
            "smooth_interfiber", "moisturized"]
    ils["conditioning"] = ils[cond].mean(axis=1)
    m = fdf.merge(ils[["polymer", "chassis", "conditioning"]], on=["polymer", "chassis"])

    pd.set_option("display.width", 170)
    print("\nPer-sample FBRM floc metrics + coacervate amount + ILS conditioning:")
    show = m.copy()
    for c in ["total", "mean_chord", "sqwt_mean", "coarse50", "pct_coarse", "amount"]:
        show[c] = show[c].round(1)
    print(show.sort_values(["chassis", "conditioning"], ascending=[True, False]).to_string(index=False))

    print("\nCorrelation with ILS conditioning (n=16):")
    for met in ["amount", "total", "mean_chord", "sqwt_mean", "pct_coarse", "coarse50"]:
        print(f"  {met:11s}: r_all={pearson(m[met], m['conditioning']):+.2f}   "
              f"BC128o={pearson(m[m.chassis=='BC128o M'][met], m[m.chassis=='BC128o M']['conditioning']):+.2f}   "
              f"GH130={pearson(m[m.chassis=='GH130 LT1'][met], m[m.chassis=='GH130 LT1']['conditioning']):+.2f}")

    print("\nDoes floc structure ADD to amount? (partial r vs conditioning, controlling for amount):")
    for met in ["total", "mean_chord", "sqwt_mean", "pct_coarse", "coarse50"]:
        print(f"  {met:11s}: partial r = {partial(m[met], m['conditioning'], m['amount']):+.2f}")

    print("\nHow correlated is floc structure with coacervate amount itself?")
    for met in ["total", "mean_chord", "sqwt_mean", "pct_coarse", "coarse50"]:
        print(f"  amount vs {met:11s}: r = {pearson(m['amount'], m[met]):+.2f}")


if __name__ == "__main__":
    main()
