"""One-image overview of ALL 21 formulas at 1% polymer (Mark-Brown 24-panel style).

7 polymers x 3 chassis (guar/3196 has no 1% data, so 21 not 24). One panel per
formula, 0-15 min %T time-course on the 1:X dilution axis, coloured by time,
laid out as rows = polymer, columns = chassis (EED0 | LAPB | APG).

Output: Reports/dextran_1pct_all21.png
"""
from make_dextran_figs import series
from make_dextran_chassis_compare import POLYMERS
from coacervation_plotting import plot_small_multiples

R = "Reports"
KEY_TIMES = {0, 1, 3, 5, 10, 15}
CHASSIS = ["EED0", "LAPB", "APG"]
POLY_ORDER = ["CD2", "Dex-K", "Dex-A", "Dex-B", "Dex-B*", "Dex-J", "Dex-J*"]
AUC_WINDOW = (1.0 / (1 + 20), 1.0 / (1 + 1))  # consumer window 1:1-1:20


def main():
    panels = []
    for pkey in POLY_ORDER:
        for ch in CHASSIS:
            chdict = POLYMERS.get(pkey, {})
            if ch not in chdict:
                continue
            path, tr = chdict[ch]
            path = path if path.startswith("raw_data") else f"raw_data/{path}"
            ser = [d for d in series(path, tr) if round(d["time"]) in KEY_TIMES]
            panels.append({"label": f"{pkey} \u00b7 {ch}", "series": ser})

    plot_small_multiples(
        panels, view="pct", auc_window=AUC_WINDOW, ncols=3, frac=0.25,
        title=(f"1% dextran screen \u2014 all {len(panels)} formulas "
               "(7 polymers \u00d7 3 chassis) \u2014 %T time-course 0\u201315 min\n"
               "rows = polymer,  columns = EED0 | LAPB | APG"),
        out_path=f"{R}/dextran_1pct_all21.png",
    )
    print(f"wrote {R}/dextran_1pct_all21.png  ({len(panels)} panels)")


if __name__ == "__main__":
    main()
