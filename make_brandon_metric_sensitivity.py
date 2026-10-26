"""Sensitivity: does the choice of coacervation-AMOUNT metric change the story?

The user asked: what if 'amount' is defined as HEIGHT only, WIDTH only, or AUC?
This recomputes the Pearson r of each metric vs every ILS attribute so we can
see (a) which attributes are robust across metric choice and (b) whether AUC's
strength is really height x width or is driven by one component.
"""
import numpy as np
import pandas as pd
import make_brandon_ipct_fingerprints as B
import make_brandon_ils_detail as D


def pearson(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    return float(np.corrcoef(x[m], y[m])[0, 1]) if m.sum() >= 3 else np.nan


def main():
    metrics = {"height": {}, "width": {}, "auc": {}}
    for poly, ch, path, tr in B.SAMPLES:
        r = B.fingerprint(path, tr)
        for m in metrics:
            metrics[m][(poly, ch)] = r[m]

    ils = pd.read_csv(r"raw_data\brandon_ils_detail.csv")
    for m in metrics:
        ils[m] = ils.apply(lambda s: metrics[m].get((s["polymer"], s["chassis"]), np.nan), axis=1)

    # composite conditioning score = mean of the classic conditioning attributes
    cond = ["wet_slip", "detangle_wide", "detangle_fine", "smooth_surface",
            "smooth_interfiber", "moisturized"]
    ils["conditioning"] = ils[cond].mean(axis=1)

    attrs = D.WET + D.DRY + ["conditioning"]
    rows = []
    for a in attrs:
        rows.append({"attribute": D.LABEL.get(a, a),
                     "r_height": pearson(ils["height"], ils[a]),
                     "r_width": pearson(ils["width"], ils[a]),
                     "r_auc": pearson(ils["auc"], ils[a])})
    tab = pd.DataFrame(rows).sort_values("r_auc", ascending=False)

    pd.set_option("display.width", 120)
    pd.set_option("display.max_rows", 60)
    print("\nPearson r of each coacervation-amount metric vs ILS attribute (n=16)\n")
    print(tab.to_string(index=False,
          formatters={"r_height": "{:+.2f}".format,
                      "r_width": "{:+.2f}".format,
                      "r_auc": "{:+.2f}".format}))

    # how correlated are the three metrics with each other?
    print("\nCross-correlation of the metrics themselves:")
    mm = ils[["height", "width", "auc"]].corr()
    print(mm.round(2).to_string())


if __name__ == "__main__":
    main()
