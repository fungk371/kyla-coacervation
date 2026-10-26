"""Which definition of 'hump height' correlates best with ILS conditioning, & why.

Height is currently peak(%T) - floor. But there are several defensible ways to
turn the clearing curve into an amount-of-coacervate number. This tests them:

  h_peak_floor   peak %T minus opaque floor            (current)
  h_abs_peak     absolute peak %T (no floor subtracted)
  h_robust_peak  mean of top-3 %T points minus floor   (noise-robust peak)
  h_p95          95th-percentile %T minus floor        (spike-robust)
  h_first_hump   height of the FIRST hump (<=1:100) minus floor (method-faithful)
  h_norm_clear   (peak - floor)/(100 - floor) = FRACTION of available opacity cleared
  h_med_floor    peak minus MEDIAN of the concentrated end (robust floor)

Each is correlated vs the conditioning composite + key attributes (n=16).
"""
import numpy as np
import pandas as pd
import make_brandon_ipct_fingerprints as B
import make_brandon_ipct_method as M
import make_brandon_ils_detail as D


def pearson(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    return float(np.corrcoef(x[m], y[m])[0, 1]) if m.sum() >= 3 else np.nan


def height_defs(path, tr):
    x, y = B.curve(path, tr)
    cx, cy, _ = B.clean_curve(x, y)
    fx, fy = B.smooth_hybrid(cx, cy)
    k = max(3, len(fy) // 10)
    floor = float(np.min(fy[:k]))
    med_floor = float(np.median(fy[:k]))
    peak = float(np.max(fy))
    topk = float(np.mean(np.sort(fy)[-3:]))
    p95 = float(np.percentile(fy, 95))
    m = fx <= 100.0
    fh = M.first_hump(fx[m], fy[m], floor)["height"]
    return dict(
        h_peak_floor=max(0.0, peak - floor),
        h_abs_peak=peak,
        h_robust_peak=max(0.0, topk - floor),
        h_p95=max(0.0, p95 - floor),
        h_first_hump=fh,
        h_norm_clear=(peak - floor) / (100.0 - floor) if floor < 100 else 0.0,
        h_med_floor=max(0.0, peak - med_floor),
    )


DEFS = ["h_peak_floor", "h_abs_peak", "h_robust_peak", "h_p95",
        "h_first_hump", "h_norm_clear", "h_med_floor"]


def main():
    vals = {k: {} for k in DEFS}
    for poly, ch, path, tr in B.SAMPLES:
        v = height_defs(path, tr)
        for k in DEFS:
            vals[k][(poly, ch)] = v[k]

    ils = pd.read_csv(r"raw_data\brandon_ils_detail.csv")
    for k in DEFS:
        ils[k] = ils.apply(lambda s: vals[k].get((s["polymer"], s["chassis"]), np.nan), axis=1)

    cond = ["wet_slip", "detangle_wide", "detangle_fine", "smooth_surface",
            "smooth_interfiber", "moisturized"]
    ils["conditioning"] = ils[cond].mean(axis=1)

    attrs = ["conditioning", "smooth_surface", "moisturized", "wet_slip",
             "detangle_wide", "clean_feel_wet"]
    rows = []
    for k in DEFS:
        row = {"height_def": k}
        for a in attrs:
            row[a] = pearson(ils[k], ils[a])
        rows.append(row)
    tab = pd.DataFrame(rows).sort_values("conditioning", ascending=False)

    pd.set_option("display.width", 160)
    fmt = {a: "{:+.2f}".format for a in attrs}
    print("\nPearson r of each HEIGHT definition vs ILS attribute (n=16)\n")
    print(tab.to_string(index=False, formatters=fmt))

    # split by chassis to see robustness of the conditioning correlation
    print("\nConditioning correlation split by chassis (robustness):")
    rows2 = []
    for k in DEFS:
        bc = ils[ils.chassis == "BC128o M"]
        gh = ils[ils.chassis == "GH130 LT1"]
        rows2.append({"height_def": k,
                      "r_all": pearson(ils[k], ils["conditioning"]),
                      "r_BC128o": pearson(bc[k], bc["conditioning"]),
                      "r_GH130": pearson(gh[k], gh["conditioning"])})
    t2 = pd.DataFrame(rows2).sort_values("r_all", ascending=False)
    print(t2.to_string(index=False, formatters={c: "{:+.2f}".format
          for c in ["r_all", "r_BC128o", "r_GH130"]}))


if __name__ == "__main__":
    main()
