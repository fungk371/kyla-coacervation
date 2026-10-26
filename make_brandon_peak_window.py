"""Does capping the peak at <=1:100 (excluding trivial far-dilute clearing)
change the ranking and the correlation with ILS conditioning?

Past ~1:100 the supernatant clears mostly because the shampoo (and its
opacifier) is nearly gone -- trivial dilution, not coacervation. This compares
the GLOBAL peak height vs the peak height measured only inside the coacervation
window (<=1:100 and <=1:50).
"""
import numpy as np
import pandas as pd
import make_brandon_ipct_fingerprints as B

CAPS = {"global": np.inf, "win100": 100.0, "win50": 50.0}


def pearson(x, y):
    x, y = np.asarray(x, float), np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    return float(np.corrcoef(x[m], y[m])[0, 1]) if m.sum() >= 3 else np.nan


def heights(path, tr):
    x, y = B.curve(path, tr)
    cx, cy, _ = B.clean_curve(x, y)
    fx, fy = B.smooth_hybrid(cx, cy)
    floor = float(np.min(fy[:max(3, len(fy) // 10)]))
    out = {}
    for name, cap in CAPS.items():
        m = fx <= cap
        pk = float(np.max(fy[m])) if m.any() else floor
        pk_dil = float(fx[m][int(np.argmax(fy[m]))]) if m.any() else np.nan
        out["h_" + name] = max(0.0, pk - floor)
        out["dil_" + name] = pk_dil
    return out


def main():
    rows = []
    for poly, ch, path, tr in B.SAMPLES:
        h = heights(path, tr)
        rows.append({"polymer": poly, "chassis": ch, **h})
    df = pd.DataFrame(rows)

    ils = pd.read_csv(r"raw_data\brandon_ils_detail.csv")
    cond = ["wet_slip", "detangle_wide", "detangle_fine", "smooth_surface",
            "smooth_interfiber", "moisturized"]
    ils["conditioning"] = ils[cond].mean(axis=1)
    m = ils.merge(df, on=["polymer", "chassis"])

    print("\nPeak dilution (1:X) where the GLOBAL max sits -- flags trivial far tail:")
    show = m[["polymer", "chassis", "dil_global", "dil_win100",
              "h_global", "h_win100", "h_win50"]].copy()
    for c in ["dil_global", "dil_win100"]:
        show[c] = show[c].round(0)
    for c in ["h_global", "h_win100", "h_win50"]:
        show[c] = show[c].round(1)
    print(show.to_string(index=False))

    print("\nCorrelation with ILS conditioning (n=16):")
    for name in CAPS:
        r = pearson(m["h_" + name], m["conditioning"])
        bc = m[m.chassis == "BC128o M"]; gh = m[m.chassis == "GH130 LT1"]
        rbc = pearson(bc["h_" + name], bc["conditioning"])
        rgh = pearson(gh["h_" + name], gh["conditioning"])
        print(f"  {name:7s}: r_all={r:+.2f}   BC128o={rbc:+.2f}   GH130={rgh:+.2f}")

    print("\nRanking by coacervate amount -- global vs <=1:100:")
    rk = m[["polymer", "chassis"]].copy()
    rk["rank_global"] = m["h_global"].rank(ascending=False).astype(int)
    rk["rank_win100"] = m["h_win100"].rank(ascending=False).astype(int)
    rk["shift"] = rk["rank_global"] - rk["rank_win100"]
    print(rk.sort_values("rank_win100").to_string(index=False))


if __name__ == "__main__":
    main()
