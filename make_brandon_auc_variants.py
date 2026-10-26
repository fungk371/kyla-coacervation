"""Experiment with different AUC definitions for coacervation 'amount'.

Current metric integrates the clearing curve over the WHOLE dilution path
(onset -> end), which drags in the far-dilute tail (trivial dilution clearing).
This tests AUC restricted to the actual coacervation HUMP and other windows:

  auc_full   onset -> end of curve         (current definition)
  auc_win    integral over 1:1 .. 1:100    (method-faithful coacervation window)
  auc_hump   integral over the FIRST hump only (onset_i -> offset_i, <=1:100)
  auc_fwhm   integral only where %T >= half-max (the FWHM breadth region)

Each is correlated vs every ILS attribute + a conditioning composite (n=16).
"""
import numpy as np
import pandas as pd
import make_brandon_ipct_fingerprints as B
import make_brandon_ipct_method as M
import make_brandon_ils_detail as D

_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))


def pearson(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    return float(np.corrcoef(x[m], y[m])[0, 1]) if m.sum() >= 3 else np.nan


def auc_variants(path, tr):
    x, y = B.curve(path, tr)
    cx, cy, _ = B.clean_curve(x, y)
    fx, fy = B.smooth_hybrid(cx, cy)
    u = np.log10(fx)
    floor = float(np.min(fy[:max(3, len(fy) // 10)]))
    amp = float(np.max(fy) - floor) or 1.0
    clip = np.clip(fy - floor, 0, None)

    # full: onset (>=floor+15%amp) -> end
    thr15 = floor + 0.15 * amp
    onset_i = next((i for i in range(len(fy)) if fy[i] >= thr15), 0)
    auc_full = float(_trapz(clip[onset_i:], u[onset_i:]))

    # window 1:1 .. 1:100
    win = (fx >= 1.0) & (fx <= 100.0)
    auc_win = float(_trapz(clip[win], u[win])) if win.sum() >= 2 else 0.0

    # first hump only (<=1:100)
    m = fx <= 100.0
    h = M.first_hump(fx[m], fy[m], floor)
    lo, hi = h["onset_i"], h["offset_i"]
    cm = clip[m]; um = u[m]
    auc_hump = float(_trapz(cm[lo:hi + 1], um[lo:hi + 1])) if hi > lo else 0.0

    # FWHM region only (%T >= half-max)
    half = floor + 0.5 * amp
    ab = np.where(fy >= half)[0]
    if len(ab):
        s, e = ab[0], ab[-1]
        auc_fwhm = float(_trapz(clip[s:e + 1], u[s:e + 1]))
    else:
        auc_fwhm = 0.0

    return dict(auc_full=auc_full, auc_win=auc_win, auc_hump=auc_hump,
                auc_fwhm=auc_fwhm, height=max(0.0, float(np.max(fy)) - floor))


def main():
    vals = {k: {} for k in ["auc_full", "auc_win", "auc_hump", "auc_fwhm", "height"]}
    for poly, ch, path, tr in B.SAMPLES:
        v = auc_variants(path, tr)
        for k in vals:
            vals[k][(poly, ch)] = v[k]

    ils = pd.read_csv(r"raw_data\brandon_ils_detail.csv")
    for k in vals:
        ils[k] = ils.apply(lambda s: vals[k].get((s["polymer"], s["chassis"]), np.nan), axis=1)

    cond = ["wet_slip", "detangle_wide", "detangle_fine", "smooth_surface",
            "smooth_interfiber", "moisturized"]
    ils["conditioning"] = ils[cond].mean(axis=1)

    metrics = ["auc_full", "auc_win", "auc_hump", "auc_fwhm", "height"]
    attrs = ["conditioning"] + D.WET + D.DRY
    rows = []
    for a in attrs:
        row = {"attribute": D.LABEL.get(a, a)}
        for k in metrics:
            row["r_" + k] = pearson(ils[k], ils[a])
        rows.append(row)
    tab = pd.DataFrame(rows).sort_values("r_auc_full", ascending=False)

    pd.set_option("display.width", 160)
    pd.set_option("display.max_rows", 60)
    fmt = {"r_" + k: "{:+.2f}".format for k in metrics}
    print("\nPearson r of each AUC definition vs ILS attribute (n=16)\n")
    print(tab.to_string(index=False, formatters=fmt))

    print("\nCross-correlation of the AUC definitions themselves:")
    print(ils[metrics].corr().round(2).to_string())

    print("\nPer-sample AUC values (BC128o then GH130), to see what each captures:")
    show = ils[["polymer", "chassis"] + metrics].copy()
    for k in metrics:
        show[k] = show[k].round(1)
    print(show.to_string(index=False))


if __name__ == "__main__":
    main()
