"""One workbook with the numerical %T behind the 0.4% and 1% dextran curves, plus an input/raw-file inventory.

Run from Gamsky_Coacervation/:  ..\\databricks_venv\\Scripts\\python.exe make_data_workbook.py
"""
import datetime
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from coacervation_analysis import dilution_ratio
from coacervation_layout import annotate_concentration
from coacervation_parser import parse_kinetic_plate_file

RAW = Path("raw_data")
CSV_04 = RAW / "POlymer test" / "Dextran_Project_Share" / "data"
OUT = Path("Reports") / "Dextran_PctT_0.4_and_1pct_AllTimepoints.xlsx"

APG, LAPB, EED0 = "GH150 DDU0 + 3.6% APG", "GH150 DDU0 + 3.6% LAPB", "GH150 EED0"

# (chassis, polymer, role, file, trough)
F = {
    "apg_cd2b": "20260903_APG_CD2_DexB_RawData.txt",
    "apg_bj": "20260903_DexBstar_DexJ_RawData.txt",
    "apg_ja": "20260903_DexJstar_DexA_RawData.txt",
    "apg_ctrl": "20260903_NoSalt_PTLWater_RawData.txt",
    "apg_dexk": "20260903_APGDexK_LAPBDexK_RawData.txt",
    "e1": "20260904_1_GH150EED0_CD2_DexB_1percent.txt",
    "e2": "20260904_2_GH150EED0_DexBstar_DexJ_1percent.txt",
    "e3": "20260904_3_GH150EED0_Dexjstar_DexA_1percent.txt",
    "l4": "20260904_4_GH150DDU0_LAPB_1percent_DexBstar_DexJ.txt",
    "l5": "20260904_5_GH150DDU0_LAPB_1percent_CD2_DexB.txt",
    "l6": "20260904_6_GH150DDU0_LAPB_1percent_DexJstar_DexA.txt",
    "l7": "20260904_7_GH150DDU0_LAPB_1percent_NATIVE_DexK.txt",
}
SAMPLES_1PCT = [
    (APG, "CD2", "Variant", F["apg_cd2b"], 1), (APG, "Dex-B", "Variant", F["apg_cd2b"], 2),
    (APG, "Dex-B*", "Variant", F["apg_bj"], 1), (APG, "Dex-J", "Variant", F["apg_bj"], 2),
    (APG, "Dex-J*", "Variant", F["apg_ja"], 1), (APG, "Dex-A", "Variant", F["apg_ja"], 2),
    (APG, "Dex-K", "Variant", F["apg_dexk"], 1),
    (APG, "No-salt control", "Control", F["apg_ctrl"], 1), (APG, "PTL water (blank)", "Control", F["apg_ctrl"], 2),
    (LAPB, "CD2", "Variant", F["l5"], 1), (LAPB, "Dex-B", "Variant", F["l5"], 2),
    (LAPB, "Dex-B*", "Variant", F["l4"], 1), (LAPB, "Dex-J", "Variant", F["l4"], 2),
    (LAPB, "Dex-J*", "Variant", F["l6"], 1), (LAPB, "Dex-A", "Variant", F["l6"], 2),
    (LAPB, "Dex-K", "Variant", F["apg_dexk"], 2),
    (EED0, "CD2", "Variant", F["e1"], 1), (EED0, "Dex-B", "Variant", F["e1"], 2),
    (EED0, "Dex-B*", "Variant", F["e2"], 1), (EED0, "Dex-J", "Variant", F["e2"], 2),
    (EED0, "Dex-J*", "Variant", F["e3"], 1), (EED0, "Dex-A", "Variant", F["e3"], 2),
    (EED0, "Dex-K", "Variant", F["l7"], 2),
    ("NATIVE Scalp Detox (competitor)", "NATIVE", "Competitor", F["l7"], 1),
]


def load_1pct():
    frames = []
    for chassis, polymer, role, fname, trough in SAMPLES_1PCT:
        df = annotate_concentration(parse_kinetic_plate_file(str(RAW / fname)))
        df = df[df["trough"] == trough].dropna(subset=["formula_fraction"]).copy()
        out = pd.DataFrame({
            "Concentration": "1%", "Chassis": chassis, "Polymer": polymer, "Role": role,
            "Source_file": fname, "Trough": trough, "Well": df["well"],
            "Time_min": df["timepoint_minutes"], "Formula_fraction": df["formula_fraction"],
            "Dilution_1_to_X": dilution_ratio(df["formula_fraction"].to_numpy()), "pctT": df["transmission_pct"],
        })
        frames.append(out)
    return pd.concat(frames, ignore_index=True)


def load_04():
    d = pd.read_csv(CSV_04 / "all_time_formula_fraction_curves.csv")
    d = d[~d["Polymer"].str.contains("water", case=False)]
    return pd.DataFrame({
        "Concentration": "0.4%", "Chassis": d["Chassis"], "Polymer": d["Polymer"].str.replace(r"^0\.4%\s*", "", regex=True),
        "Role": "Variant", "Source_file": d["Dataset"], "Trough": None, "Well": None,
        "Time_min": d["Time_min"], "Formula_fraction": d["Formula_fraction"],
        "Dilution_1_to_X": d["Diluent_ratio"], "pctT": d["%T"],
    })


def wide_all_times(long_df):
    out = []
    for (conc, chassis), g in long_df.groupby(["Concentration", "Chassis"]):
        g = g.assign(Dilution_1_to_X=g["Dilution_1_to_X"].round(2), Time_min=g["Time_min"].round(1))
        w = g.pivot_table(index="Dilution_1_to_X", columns=["Polymer", "Time_min"], values="pctT", aggfunc="mean")
        w.columns = [f"{p} | {t:g} min" for p, t in w.columns]
        w = w.reset_index()
        w.insert(0, "Chassis", chassis)
        w.insert(0, "Concentration", conc)
        out.append(w)
    return pd.concat(out, ignore_index=True)


def inventory():
    rows = []
    for p in sorted(list(RAW.glob("*.txt")) + list(RAW.glob("*.xls*")) + list(Path(".").glob("*.xls*"))):
        sheets = ""
        if p.suffix.lower() in (".xlsx", ".xlsm"):
            try:
                wb = load_workbook(p, read_only=True)
                sheets = ", ".join(wb.sheetnames)
                wb.close()
            except Exception as exc:  # unreadable stub files are listed, not fatal
                sheets = f"(unreadable: {type(exc).__name__})"
        kind = "Raw plate-reader data (.txt)" if p.suffix.lower() == ".txt" else "Input / metadata sheet"
        rows.append({
            "Type": kind, "File": p.name, "Folder": str(p.parent), "Size_KB": round(p.stat().st_size / 1024, 1),
            "Modified": datetime.datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d"), "Sheets": sheets,
        })
    return pd.DataFrame(rows)


def main():
    long_df = pd.concat([load_04(), load_1pct()], ignore_index=True)
    long_df = long_df.sort_values(["Concentration", "Chassis", "Polymer", "Time_min", "Dilution_1_to_X"])
    sample_map = (long_df.groupby(["Concentration", "Chassis", "Polymer", "Role", "Source_file", "Trough"], dropna=False)
                  .agg(Timepoints=("Time_min", "nunique"), Points=("pctT", "size")).reset_index())
    auc = pd.read_csv(CSV_04 / "auc_over_time_summary.csv")
    auc_t = pd.read_csv(CSV_04 / "auc_all_times.csv")
    readme = pd.DataFrame({"Notes": [
        "Numerical %T behind the 0.4% and 1% dextran curves (same chassis/polymer matrix).",
        "PctT_Long: every well/timepoint. Dilution_1_to_X = (1 - formula fraction) / formula fraction; plotted as 1:X.",
        "PctT_Wide_AllTimes: dilution (rows) x polymer at every timepoint (columns, e.g. 'CD2 | 3 min'), one block per concentration and chassis.",
        "Plotted figures remove isolated bubble spikes and fit a smooth curve; this sheet is the uncleaned measured data.",
        "AUC_0.4pct: AUC summaries shared in the Dow project folder (0.4% only). 1% AUC is not included here.",
        "Sample_Map: which plate file/trough each polymer came from. Inventory: all input sheets and raw plate files.",
        "1% Dex-K in EED0 comes from the 20260904_7 plate (trough 2); trough 1 is the NATIVE competitor.",
    ]})
    OUT.parent.mkdir(exist_ok=True)
    with pd.ExcelWriter(OUT, engine="openpyxl") as xw:
        readme.to_excel(xw, sheet_name="README", index=False)
        sample_map.to_excel(xw, sheet_name="Sample_Map", index=False)
        wide_all_times(long_df).to_excel(xw, sheet_name="PctT_Wide_AllTimes", index=False)
        long_df.to_excel(xw, sheet_name="PctT_Long", index=False)
        auc.to_excel(xw, sheet_name="AUC_0.4pct_summary", index=False)
        auc_t.to_excel(xw, sheet_name="AUC_0.4pct_by_time", index=False)
        inventory().to_excel(xw, sheet_name="Inventory", index=False)
        for ws in xw.book.worksheets:
            ws.freeze_panes = "A2"
            for col in ws.columns:
                width = max(len(str(c.value)) if c.value is not None else 0 for c in list(col)[:200])
                ws.column_dimensions[col[0].column_letter].width = min(max(width + 2, 10), 70)
    print(f"{OUT}: long rows={len(long_df)}, samples={len(sample_map)}")


if __name__ == "__main__":
    main()
