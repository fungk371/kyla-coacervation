"""
Parser for the 'Sample Info' shampoo-formula workbook.

Each run tab contains a 'Sample Info' block:
    A19 'Sample Info'
    row+1 : Trough Position | BatchID | SampleID | Description | Hardness |
            Sample Key | HHS Shake Speed | HHS Shake Time | HHS Shake Temp
    Trough_01 ... (Sample 1 = wells A-D)
    Trough_02 ... (Sample 2 = wells E-H)
    'Sample 1 (A1-D12):' | <Chassis> | <Polymer>
    'Sample 2 (E1-H12)'  | <Chassis> | <Polymer>
    'Time' | 0 | 1 | 2 | ...        (timepoints across columns)
    'Temperature(..)' | 37 | 37 | ...
    A1 | <%T at each timepoint> ...  (96 well rows A1..H12)

This module extracts sample names (Chassis + Polymer), submission metadata, and
the kinetic well data as the same long format used elsewhere, so the run tabs can
be analysed and visualised directly (auto-naming the two troughs).
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from openpyxl import load_workbook

from coacervation_layout import annotate_concentration

WELL_RE = re.compile(r"^[A-H](?:[1-9]|1[0-2])$")


def _find_marker(ws, text, col=1, max_row=40):
    for r in range(1, max_row + 1):
        v = ws.cell(row=r, column=col).value
        if isinstance(v, str) and text.lower() in v.lower():
            return r
    return None


def list_run_sheets(path: str | Path) -> list[str]:
    """Return worksheet names that contain a 'Sample Info' block."""
    wb = load_workbook(path, data_only=True)
    out = []
    for name in wb.sheetnames:
        ws = wb[name]
        if not hasattr(ws, "max_row"):
            continue
        if _find_marker(ws, "sample info") is not None:
            out.append(name)
    wb.close()
    return out


def _join(*vals) -> str:
    return " ".join(str(v).strip() for v in vals if v not in (None, "")).strip()


def parse_run_sheet(path: str | Path, sheet: str) -> dict:
    """Parse one run tab -> sample names, metadata, and long kinetic dataframe.

    Returns dict with:
        sample_names: {"1": name1, "2": name2}
        trough_meta:  {trough_position: {header: value}}
        metadata:     flattened submission metadata (batch ids, hardness, shake...)
        long_df:      DataFrame (well,row,column,timepoint_minutes,temperature_c,
                      transmission_pct) annotated with trough/formula_fraction.
    """
    wb = load_workbook(path, data_only=True)
    ws = wb[sheet]
    info_row = _find_marker(ws, "sample info") or 19

    # --- sample names (Chassis + Polymer) ---
    names = {}
    trough_cp = {}
    for r in range(info_row, info_row + 16):
        a = ws.cell(row=r, column=1).value
        if isinstance(a, str):
            low = a.lower()
            if low.startswith("sample 1"):
                chassis = ws.cell(row=r, column=2).value
                polymer = ws.cell(row=r, column=3).value
                names["1"] = _join(chassis, polymer)
                trough_cp["1"] = {"chassis": chassis, "polymer": polymer}
            elif low.startswith("sample 2"):
                chassis = ws.cell(row=r, column=2).value
                polymer = ws.cell(row=r, column=3).value
                names["2"] = _join(chassis, polymer)
                trough_cp["2"] = {"chassis": chassis, "polymer": polymer}

    # --- trough metadata table ---
    hdr_row = info_row + 1
    headers = [ws.cell(row=hdr_row, column=c).value for c in range(1, 10)]
    trough_meta = {}
    for r in (hdr_row + 1, hdr_row + 2):
        rowvals = {headers[c - 1]: ws.cell(row=r, column=c).value
                   for c in range(1, 10) if headers[c - 1]}
        pos = rowvals.get("Trough Position")
        if pos:
            trough_meta[str(pos)] = rowvals

    # --- kinetic data block ---
    time_row = None
    for r in range(info_row, info_row + 20):
        a = ws.cell(row=r, column=1).value
        if isinstance(a, str) and a.strip().lower().startswith("time"):
            time_row = r
            break
    if time_row is None:
        wb.close()
        raise ValueError(f"No 'Time' row found in sheet {sheet}")

    times, cols = [], []
    c = 2
    while True:
        v = ws.cell(row=time_row, column=c).value
        if v is None:
            break
        try:
            times.append(float(v))
            cols.append(c)
        except (TypeError, ValueError):
            break
        c += 1

    temp_row = time_row + 1
    temps = [ws.cell(row=temp_row, column=cc).value for cc in cols]

    rows = []
    r = temp_row + 1
    while True:
        well = ws.cell(row=r, column=1).value
        if not (isinstance(well, str) and WELL_RE.match(well.strip())):
            break
        well = well.strip()
        for i, cc in enumerate(cols):
            val = ws.cell(row=r, column=cc).value
            if val is None:
                continue
            try:
                pct = float(val)
            except (TypeError, ValueError):
                continue
            rows.append({
                "well": well,
                "row": well[0],
                "column": int(well[1:]),
                "timepoint_minutes": round(times[i], 4),
                "temperature_c": float(temps[i]) if temps[i] is not None else None,
                "transmission_pct": pct,
            })
        r += 1
    wb.close()

    if not rows:
        raise ValueError(f"No well data parsed from sheet {sheet}")

    long_df = annotate_concentration(pd.DataFrame(rows))

    # flattened metadata for the submission form
    t1 = trough_meta.get("Trough_01") or trough_meta.get("Trough_1") or {}
    metadata = {
        "sample_id": t1.get("SampleID") or t1.get("BatchID") or "",
        "study": _join(sheet),
        "salt_mM": "",
        "temperature_c": next((t for t in temps if t is not None), None),
    }
    return {
        "sample_names": names,
        "trough_meta": trough_meta,
        "trough_cp": trough_cp,
        "metadata": metadata,
        "long_df": long_df,
    }


if __name__ == "__main__":
    import sys

    p = sys.argv[1]
    sheets = list_run_sheets(p)
    print(f"Run sheets ({len(sheets)}): {sheets}")
    if len(sys.argv) > 2:
        info = parse_run_sheet(p, sys.argv[2])
        print("Sample names:", info["sample_names"])
        print("Metadata:", info["metadata"])
        df = info["long_df"]
        print(f"Rows: {len(df)}  wells: {df['well'].nunique()}  "
              f"timepoints: {sorted(df['timepoint_minutes'].unique())}")
