"""Does WIDTH (breadth of the coacervation window) predict anything on its own?

Hypothesis: a wide coacervation window = the formula keeps phase-separating and
depositing over a LONG rinse (many decades of dilution), vs a narrow window that
only coacervates at one dilution. Raw width correlations just echo 'amount'
(width~height r~0.6), so we also compute the PARTIAL correlation of width vs
each attribute controlling for height (amount) -- width's UNIQUE contribution.
"""
import numpy as np
import pandas as pd
import make_brandon_ipct_fingerprints as B
import make_brandon_ils_detail as D


def pearson(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    return float(np.corrcoef(x[m], y[m])[0, 1]) if m.sum() >= 3 else np.nan


def partial(x, y, z):
    """corr(x,y | z) -- correlation of x,y after removing linear z."""
    rxy, rxz, ryz = pearson(x, y), pearson(x, z), pearson(y, z)
    d = np.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))
    return (rxy - rxz * ryz) / d if d > 0 else np.nan


def main():
    W, H = {}, {}
    for poly, ch, path, tr in B.SAMPLES:
        r = B.fingerprint(path, tr)
        W[(poly, ch)] = r["width"]; H[(poly, ch)] = r["height"]

    ils = pd.read_csv(r"raw_data\brandon_ils_detail.csv")
    ils["width"] = ils.apply(lambda s: W.get((s["polymer"], s["chassis"]), np.nan), axis=1)
    ils["height"] = ils.apply(lambda s: H.get((s["polymer"], s["chassis"]), np.nan), axis=1)

    cond = ["wet_slip", "detangle_wide", "detangle_fine", "smooth_surface",
            "smooth_interfiber", "moisturized"]
    ils["conditioning"] = ils[cond].mean(axis=1)

    attrs = ["conditioning"] + D.WET + D.DRY
    rows = []
    for a in attrs:
        rows.append({"attribute": D.LABEL.get(a, a),
                     "r_width_raw": pearson(ils["width"], ils[a]),
                     "r_width_partial_ctrl_height": partial(ils["width"], ils[a], ils["height"])})
    tab = pd.DataFrame(rows).sort_values("r_width_partial_ctrl_height", ascending=False)

    pd.set_option("display.width", 140)
    pd.set_option("display.max_rows", 60)
    print("\nWidth vs ILS attribute: raw r, and partial r controlling for amount(height)  (n=16)\n")
    print(tab.to_string(index=False,
          formatters={"r_width_raw": "{:+.2f}".format,
                      "r_width_partial_ctrl_height": "{:+.2f}".format}))

    print(f"\nwidth ~ height cross-correlation: r = {pearson(ils['width'], ils['height']):+.2f}")
    print("\nPer-sample width (decades) and height (%T):")
    show = ils[["polymer", "chassis", "width", "height"]].copy()
    show["width"] = show["width"].round(2); show["height"] = show["height"].round(1)
    print(show.to_string(index=False))


if __name__ == "__main__":
    main()
