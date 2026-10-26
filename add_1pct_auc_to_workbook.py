"""Add 1% AUC summaries, a same-method 0.4% vs 1% comparison, and the PTL join to the dextran %T workbook.

Usage: python add_1pct_auc_to_workbook.py <workbook.xlsx> [<workbook2.xlsx> ...]
AUC method (approximates the Dow-share 0.4% table; see AUC_validation_0.4pct):
  A = -log10(%T/100); excess = A - min(A); AUC_total = trapezoid(excess, formula fraction) over all wells;
  AUC_consumer = same over dilution 1:2 to 1:10; Peak_abs = max(A).  Summary columns = AUC_total at 0,1,3,5,10,15 min.
"""
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook

TIMES = [0, 1, 3, 5, 10, 15]
CONSUMER = (2, 10)
PTL_CSV = Path(r"C:\VScode_Projects\Gamsky_Databricks_Access\Gamsky_Coacervation\raw_data\ptl_depo_dextran.csv")
DOW = Path(r"C:\VScode_Projects\Dextran_Project_Share\data")


def canon_chassis(c):
    c = c.upper()
    if "APG" in c:
        return "DDu0 + APG"
    if "LAPB" in c:
        return "DDu0 + LAPB"
    if "EED0" in c:
        return "EED0"
    return c


def canon_poly(p):
    p = p.replace("0.4% ", "").strip()
    return p.replace("Dex ", "Dex-") if p.startswith("Dex ") else p


def auc_curve(g):
    g = g.dropna(subset=["pctT"]).sort_values("Formula_fraction")
    f, y = g["Formula_fraction"].to_numpy(float), g["pctT"].to_numpy(float)
    a = -np.log10(np.clip(y, 1e-6, None) / 100.0)
    ex = a - a.min()
    m = (f >= 1 / (1 + CONSUMER[1])) & (f <= 1 / (1 + CONSUMER[0]))
    return dict(AUC_total=round(float(np.trapezoid(ex, f)), 4), AUC_consumer=round(float(np.trapezoid(ex[m], f[m])), 4),
                Peak_abs=round(float(a.max()), 4))


def by_time(long_df):
    rows = []
    for (conc, ch, pol, role, t), g in long_df.groupby(["Concentration", "Chassis", "Polymer", "Role", "Time_min"]):
        rows.append(dict(Concentration=conc, Chassis=ch, Polymer=pol, Role=role, Time_min=int(round(t)), **auc_curve(g)))
    return pd.DataFrame(rows)


def summary(bt):
    s = bt[bt.Time_min.isin(TIMES)].pivot_table(index=["Chassis", "Polymer", "Role"], columns="Time_min", values="AUC_total").reset_index()
    s = s[["Chassis", "Polymer", "Role"] + [t for t in TIMES if t in s.columns]]
    s["Sum_0_15"] = s[[t for t in TIMES if t in s.columns]].sum(axis=1).round(4)
    s["Avg_0_15"] = (s["Sum_0_15"] / len([t for t in TIMES if t in s.columns])).round(6)
    s["Label"] = s["Chassis"].map(canon_chassis) + " | " + s["Polymer"]
    return s.sort_values("Sum_0_15", ascending=False).reset_index(drop=True)


def main(path):
    path = Path(path)
    backup = path.with_name(path.stem + "_backup" + path.suffix)
    if not backup.exists():
        shutil.copy(path, backup)
    long_df = pd.read_excel(path, sheet_name="PctT_Long")
    # same method on both concentrations so 0.4% vs 1% is like-for-like
    bt = by_time(long_df)
    bt1, bt04 = bt[bt.Concentration == "1%"].drop(columns="Concentration"), bt[bt.Concentration == "0.4%"].drop(columns="Concentration")
    sum1, sum04 = summary(bt1), summary(bt04)

    # validation against Mark/Dow-share 0.4% table
    dow = pd.read_csv(DOW / "auc_all_times.csv")
    dow["Polymer"] = dow["Polymer"].str.replace("0.4% ", "", regex=False)
    val = bt04.merge(dow[["Chassis", "Polymer", "Time_min", "AUC_total", "AUC_consumer", "Peak_abs"]],
                     on=["Chassis", "Polymer", "Time_min"], suffixes=("_recomputed", "_dow"), how="inner")
    val["total_ratio"] = (val["AUC_total_recomputed"] / val["AUC_total_dow"].replace(0, np.nan)).round(3)
    big = val[val["AUC_total_dow"] > 0.02]
    med_err = float((abs(big["AUC_total_recomputed"] - big["AUC_total_dow"]) / big["AUC_total_dow"]).median())
    corr = float(np.corrcoef(val["AUC_total_recomputed"], val["AUC_total_dow"])[0, 1])

    # 0.4% vs 1% side by side (Sum_0_15 and t=3), matched on chassis + polymer
    for d in (sum1, sum04):
        d["key_ch"], d["key_pol"] = d["Chassis"].map(canon_chassis), d["Polymer"].map(canon_poly)
    both = sum04.merge(sum1, on=["key_ch", "key_pol"], suffixes=("_0.4pct", "_1pct"))
    cmp_ = pd.DataFrame({
        "Chassis": both["key_ch"], "Polymer": both["key_pol"],
        "Sum_0_15_0.4pct": both["Sum_0_15_0.4pct"], "Sum_0_15_1pct": both["Sum_0_15_1pct"],
        "Ratio_1pct_over_0.4pct": (both["Sum_0_15_1pct"] / both["Sum_0_15_0.4pct"].replace(0, np.nan)).round(2),
        "AUC_t0_0.4pct": both["0_0.4pct"], "AUC_t0_1pct": both["0_1pct"],
        "AUC_t15_0.4pct": both["15_0.4pct"], "AUC_t15_1pct": both["15_1pct"],
    }).sort_values(["Chassis", "Sum_0_15_1pct"], ascending=[True, False])

    # PTL join (Mark's PTL table, CH2 = GH150 EED0 chassis family)
    ptl = pd.read_csv(PTL_CSV)
    cmap = {"CH2": "EED0", "CH2 + LAPB": "DDu0 + LAPB", "CH2 + APG": "DDu0 + APG"}
    ptl["key_ch"], ptl["key_pol"] = ptl["chassis"].map(cmap), ptl["polymer"].map(canon_poly)
    a04 = sum04[["key_ch", "key_pol", "Sum_0_15", "Avg_0_15", 0, 3, 15]].rename(columns={
        "Sum_0_15": "AUC_Sum_0_15_0.4pct", "Avg_0_15": "AUC_Avg_0_15_0.4pct", 0: "AUC_t0_0.4pct", 3: "AUC_t3_0.4pct", 15: "AUC_t15_0.4pct"})
    a1 = sum1[["key_ch", "key_pol", "Sum_0_15", 0, 3]].rename(columns={"Sum_0_15": "AUC_Sum_0_15_1pct", 0: "AUC_t0_1pct", 3: "AUC_t3_1pct"})
    join = ptl.merge(a04, on=["key_ch", "key_pol"], how="left").merge(a1, on=["key_ch", "key_pol"], how="left")
    join = join.rename(columns={"key_ch": "coac_chassis", "key_pol": "coac_polymer"})

    notes = [
        "UPDATE (1% AUC): AUC_1pct_summary and AUC_1pct_by_time hold the 1% polymer AUCs, same layout as the 0.4% sheets.",
        "AUC method: A = -log10(%T/100); excess = A - min(A); AUC_total = trapezoid(excess vs formula fraction) over all wells; AUC_consumer = dilution 1:2-1:10; Peak_abs = max A. Raw wells, no smoothing. Summary columns are AUC_total at 0,1,3,5,10,15 min; Sum_0_15 is their sum.",
        "AUC_0.4pct_recomputed and AUC_1pct use this one method, so 0.4% vs 1% is like-for-like (AUC_0.4_vs_1pct). The original AUC_0.4pct_summary / _by_time sheets are the Dow-share values, unchanged.",
        "AUC_validation_0.4pct compares my recomputed 0.4% values with the Dow-share table: for rows with Dow AUC_total > 0.02 the median difference is {:.0%} (r = {:.2f} over all {} rows). Mine run higher where the Dow values were smoothed or cleaned (e.g. APG CD2 Sum_0_15 0.27 vs 0.18).".format(med_err, corr, len(val)),
        "PTL_vs_AUC joins the PTL table (DRF, wSACS, dSACS, IFF, Si_ppm; chassis CH2 = EED0 family) to AUC by chassis + polymer. PTL concentration is assumed to match the 0.4% runs; 1% AUC is shown for reference only.",
        "1% has no PTL data. 1% controls (No-salt control, PTL water blank) and the NATIVE competitor are included in the 1% sheets.",
    ]

    wb = load_workbook(path)
    if "Notes_1pct_AUC" in wb.sheetnames:
        del wb["Notes_1pct_AUC"]
    ws = wb.create_sheet("Notes_1pct_AUC", 0)
    ws.cell(row=1, column=1, value="Notes")
    for i, n in enumerate(notes):
        ws.cell(row=2 + i, column=1, value=n)
    ws.column_dimensions["A"].width = 160
    for name in ["AUC_1pct_summary", "AUC_1pct_by_time", "AUC_0.4_vs_1pct", "AUC_0.4pct_recomputed", "AUC_validation_0.4pct", "PTL_vs_AUC"]:
        if name in wb.sheetnames:
            del wb[name]
    wb.save(path)
    with pd.ExcelWriter(path, engine="openpyxl", mode="a") as xw:
        sum1.drop(columns=["key_ch", "key_pol"]).to_excel(xw, sheet_name="AUC_1pct_summary", index=False)
        bt1.to_excel(xw, sheet_name="AUC_1pct_by_time", index=False)
        cmp_.to_excel(xw, sheet_name="AUC_0.4_vs_1pct", index=False)
        sum04.drop(columns=["key_ch", "key_pol"]).to_excel(xw, sheet_name="AUC_0.4pct_recomputed", index=False)
        val.to_excel(xw, sheet_name="AUC_validation_0.4pct", index=False)
        join.to_excel(xw, sheet_name="PTL_vs_AUC", index=False)
        for name in ["AUC_1pct_summary", "AUC_1pct_by_time", "AUC_0.4_vs_1pct", "AUC_0.4pct_recomputed", "AUC_validation_0.4pct", "PTL_vs_AUC"]:
            ws = xw.book[name]
            ws.freeze_panes = "A2"
            for col in ws.columns:
                w = max(len(str(c.value)) if c.value is not None else 0 for c in list(col)[:200])
                ws.column_dimensions[col[0].column_letter].width = min(max(w + 2, 10), 60)
    print(path, "| 1% summary rows", len(sum1), "| by-time rows", len(bt1), "| compared pairs", len(cmp_), "| PTL rows", len(join),
          "| PTL rows with 0.4% AUC", int(join["AUC_Sum_0_15_0.4pct"].notna().sum()), "| validation rows", len(val),
          "| median total ratio", float(val["total_ratio"].median()))
    return sum1, cmp_, join


if __name__ == "__main__":
    for p in sys.argv[1:]:
        s1, c, j = main(p)
    pd.set_option("display.width", 250)
    print(s1.drop(columns=["Label"]).to_string())
    print(c.to_string())
