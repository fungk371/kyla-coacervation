"""
End-to-end pipeline demo:
  raw kinetic .txt  ->  parse  ->  map wells to concentration (troughs)  ->
  absorbance-vs-concentration plot with best fit + windowed AUC.

Also cross-checks the well->concentration mapping against the known
'Data to Graph' values in the source .xlsm.
"""

from pathlib import Path

import numpy as np
from openpyxl import load_workbook

from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import sample_curve, build_well_map, FORMULA_FRACTIONS
from coacervation_plotting import plot_absorbance_vs_concentration


def cross_check_mapping():
    """Confirm trough-1 rows A-D at 3 min match Data to Graph column G."""
    wb = load_workbook(Path("raw_data") / "2025 1023 01.xlsm", data_only=True)
    plate = wb["Plate 1"]
    # find the 00:03:00 row in Plate 1 (col A = time, wells start col C=A1)
    target_row = None
    for r in range(2, plate.max_row + 1):
        if str(plate.cell(row=r, column=1).value) == "00:03:00":
            target_row = r
            break
    # Plate 1 columns C.. are A1,A2,...; first 12 = A1..A12 (trough 1, fraction idx 0..11)
    a1 = plate.cell(row=target_row, column=3).value   # A1 -> fraction 0.5
    a2 = plate.cell(row=target_row, column=4).value   # A2 -> fraction 0.47593

    dg = wb["Data to Graph"]
    g5 = dg["G5"].value   # GH130 XL-40 R35 at 3 min, fraction 0.5
    g6 = dg["G6"].value   # fraction 0.47593
    wb.close()

    print("Cross-check (Plate1 A1/A2 @3min  vs  Data to Graph G5/G6):")
    print(f"  A1={a1:.5f}  G5={g5:.5f}  match={np.isclose(a1, g5)}")
    print(f"  A2={a2:.5f}  G6={g6:.5f}  match={np.isclose(a2, g6)}")


def main():
    raw = Path("raw_data") / "TestFileforXML_2026. 08. 07_08.31.25 (1).txt"
    long_df = parse_kinetic_plate_file(raw)
    print(f"Parsed {len(long_df)} rows, {long_df['well'].nunique()} wells, "
          f"timepoints {sorted(long_df['timepoint_minutes'].unique())[:3]}...")

    print(f"Layout: {len(build_well_map())} wells mapped, "
          f"{len(FORMULA_FRACTIONS)} formula fractions per trough.\n")

    cross_check_mapping()
    print()

    for trough in (1, 2):
        curve, tp = sample_curve(long_df, trough=trough, timepoint_minutes=3.0)
        conc = curve["formula_fraction"].to_numpy()
        pct_t = curve["transmission_pct"].to_numpy()
        out = Path(f"pipeline_trough{trough}_absorbance.png")
        _, _, auc = plot_absorbance_vs_concentration(
            conc, pct_t,
            sample_label=f"Trough {trough} @ {tp:.1f} min",
            auc_window=(0.10, 0.50), kind="spline", out_path=str(out),
        )
        print(f"Trough {trough} @ {tp:.1f} min: {len(conc)} points, "
              f"AUC[0.10-0.50]={auc['auc']:.4f} -> {out.name}")


if __name__ == "__main__":
    main()
