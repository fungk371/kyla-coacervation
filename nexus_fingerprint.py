"""Nexus 'Beauty ANA PercentT Coacervation Profile' fingerprint engine + export.

Computes every REPORTABLE parameter the Nexus method stores, per sample, at
0/3/5/10/15 min, and writes the Flex Template ('Reportable Data' sheet) that you
drop into the SDMS Import folder for the Flexible Driver to ingest.

Column names match the template EXACTLY (no parentheses; 'Cl Dil' = clear
dilution). Metric order matches the template.

CAVEAT: the historical Databricks export was placeholder data (all 9.0), so the
Onset / Cl-Dil / Breadth definitions here are my best reading of the parameter
names and should be validated against a real Nexus run before production use.
"""
import numpy as np
import openpyxl

from coacervation_parser import parse_kinetic_plate_file
from coacervation_layout import annotate_concentration
from coacervation_analysis import (
    dilution_ratio, transmittance_to_absorbance, compute_auc, compute_fingerprint,
)

TIMEPOINTS = [0, 3, 5, 10, 15]
WIN_10 = (1.0 / (1 + 10), 1.0 / (1 + 1))
WIN_20 = (1.0 / (1 + 20), 1.0 / (1 + 1))

# metric name templates in the EXACT order/spelling of the Flex Template
_METRIC_FMTS = [
    "Full AUC {t}Min",
    "AUC 1:1 to 1:10 dilution window {t}Min",
    "AUC 1:1 to 1:20 dilution window {t}Min",
    "Minimum %T {t}Min",
    "Dilution ratio at minimum %T {t}Min",
    "Dilution ratio Coacervation Onset {t}Min",
    "Dilution ratio Coacervation Cl Dil {t}Min",
    "Coacervation Breadth clear onset {t}Min",
    "Maximum Absorbance {t}Min",
    "Dilution Ratio Maximum Absorbance {t}Min",
]
REPORTABLE_COLS = [f.format(t=t) for f in _METRIC_FMTS for t in TIMEPOINTS]
PARAMLIST_VARIANT = "Beauty ANA PercentT Coacervation Profile;Reportable"


def _curve_at(path, trough, tp, sheet=None):
    if sheet:
        from coacervation_sampleinfo import parse_run_sheet
        df = parse_run_sheet(path, sheet)["long_df"]
    else:
        df = annotate_concentration(parse_kinetic_plate_file(path))
    sub = df[df["trough"] == trough].dropna(subset=["formula_fraction"])
    if sub.empty:
        return None
    t = min(sorted(sub["timepoint_minutes"].unique()), key=lambda z: abs(z - tp))
    cur = sub[sub["timepoint_minutes"] == t].sort_values("formula_fraction", ascending=False)
    ff = cur["formula_fraction"].to_numpy(float)
    y = cur["transmission_pct"].to_numpy(float)
    x = np.asarray(dilution_ratio(ff), float)
    o = np.argsort(x)
    return x[o], y[o], ff[o]


def fingerprint(path, trough, sheet=None):
    """Return {exact_template_param_name: value} for one sample (50 metrics)."""
    out = {}
    for tp in TIMEPOINTS:
        c = _curve_at(path, trough, tp, sheet=sheet)
        if c is None:
            for f in _METRIC_FMTS:
                out[f.format(t=tp)] = None
            continue
        x, y, ff = c
        absb = np.asarray(transmittance_to_absorbance(y), float)

        full = compute_auc(ff, absb, window=None, use_fit=True)["auc"]
        a10 = compute_auc(ff, absb, window=WIN_10, use_fit=True)["auc"]
        a20 = compute_auc(ff, absb, window=WIN_20, use_fit=True)["auc"]
        imin = int(np.argmin(y)); imax = int(np.argmax(absb))
        fp = compute_fingerprint(ff, y) or {}
        onset = fp.get("onset_dilution"); cldil = fp.get("recovery_dilution")
        if onset and cldil and cldil > onset:
            breadth = round(float(np.log10(cldil / onset)), 3)
        else:
            breadth = fp.get("width_decades")

        vals = {
            "Full AUC {t}Min": round(full, 4),
            "AUC 1:1 to 1:10 dilution window {t}Min": round(a10, 4),
            "AUC 1:1 to 1:20 dilution window {t}Min": round(a20, 4),
            "Minimum %T {t}Min": round(float(y[imin]), 2),
            "Dilution ratio at minimum %T {t}Min": round(float(x[imin]), 1),
            "Dilution ratio Coacervation Onset {t}Min": round(onset, 1) if onset else None,
            "Dilution ratio Coacervation Cl Dil {t}Min": round(cldil, 1) if cldil else None,
            "Coacervation Breadth clear onset {t}Min": breadth,
            "Maximum Absorbance {t}Min": round(float(absb[imax]), 3),
            "Dilution Ratio Maximum Absorbance {t}Min": round(float(x[imax]), 1),
        }
        for f, v in vals.items():
            out[f.format(t=tp)] = v
    return out


def export_nexus_template(samples, out_path, *, id_suffix=";1;1;1"):
    """Write the Flex Template ('Reportable Data' sheet).

    samples: list of dicts {'sample_id': 'S-...', 'path': ..., 'trough': 1|2}
    """
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Reportable Data"
    ws.append(["Sample_ID", "Paramlist_Variant"] + REPORTABLE_COLS)
    for s in samples:
        fp = fingerprint(s["path"], s["trough"], sheet=s.get("sheet"))
        row = [f"{s['sample_id']}{id_suffix}", PARAMLIST_VARIANT] + [fp.get(c) for c in REPORTABLE_COLS]
        ws.append(row)
    wb.save(out_path)
    return out_path


if __name__ == "__main__":
    samples = [
        {"sample_id": "S-DEMO-CD2", "path": "raw_data/20260904_5_GH150DDU0_LAPB_1percent_CD2_DexB.txt", "trough": 1},
        {"sample_id": "S-DEMO-DexK", "path": "raw_data/20260903_APGDexK_LAPBDexK_RawData.txt", "trough": 2},
    ]
    out = export_nexus_template(samples, "Reports/nexus_percentT_export_demo.xlsx")
    print("wrote", out)
    fp = fingerprint(samples[0]["path"], samples[0]["trough"])
    print("\nLAPB CD2 1% fingerprint (3 min slice):")
    for c in REPORTABLE_COLS:
        if "3Min" in c:
            print(f"  {c:46s} {fp[c]}")
