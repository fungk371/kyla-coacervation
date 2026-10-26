"""Batch-ingest all matched past phase-diagram experiments into the app DB.

14 Excel volumes files, each matched to its 20 transmission .txt files (10 UV
reads x 2 plates). Naming: polymer x surfactant. "Excel" is a polymer; "RL" /
"Rhamnolipid" is a surfactant (pH 7). SCG/SLESS/SLS runs are pH 5.5.
Each experiment_id is deleted first so re-runs replace rather than duplicate.
"""
import shutil
import sqlite3
import tempfile
from pathlib import Path

import coacervation_phase as cphase

ROOT = Path(r"C:\Users\fung.k.1\Downloads\Phase Diagram\OUTPUTS")
XL = ROOT / "Input sheets Past Exp" / "Suf_Pol"
PAST = ROOT / "Past Exp Out Surf_Pol"

# (excel filename, txt folder, txt group prefix, experiment_id, display name)
JOBS = [
    ("20260107 AMT SCG_ph5_5.xlsx",   PAST, "20260107 AMT SCG",            "ph_amt_scg",     "AMT x SCG (pH 5.5)"),
    ("20260107 AMT SLESS_ph5_5.xlsx", PAST, "20260107 AMT SLESS",          "ph_amt_sless",   "AMT x SLESS (pH 5.5)"),
    ("20260107 AMT SLS_ph5_5.xlsx",   PAST, "20260107 AMT SLS",            "ph_amt_sls",     "AMT x SLS (pH 5.5)"),
    ("20260105 DADMAC_SCG_ph5_5.xlsx",   PAST, "20260106 20260106 DADMAC SCG",  "ph_dadmac_scg",  "DADMAC x SCG (pH 5.5)"),
    ("20260105 DADMAC_SLESS_ph5_5.xlsx", PAST, "20260106 20260106 DAMAC SLESS", "ph_dadmac_sless","DADMAC x SLESS (pH 5.5)"),
    ("20260105 DADMAC_SLS_ph5_5.xlsx",   PAST, "20260105 20260105 DADMAC SLS",  "ph_dadmac_sls",  "DADMAC x SLS (pH 5.5)"),
    ("20260106 KG30M SCG_ph5_5.xlsx",   PAST, "20260106 KG30M SCG",   "ph_kg30m_scg",   "KG30M x SCG (pH 5.5)"),
    ("20260106 KG30M SLESS_ph5_5.xlsx", PAST, "20260106 KG30M SLESS", "ph_kg30m_sless", "KG30M x SLESS (pH 5.5)"),
    ("20260106 KG30M SLS_ph5_5.xlsx",   PAST, "20260106 KG30M SLS",   "ph_kg30m_sls",   "KG30M x SLS (pH 5.5)"),
    ("KG30M Rham pH 7 .xlsx",   PAST, "20260109 KG30M Rhamnolipid", "ph_kg30m_rl", "KG30M x Rhamnolipid (pH 7)"),
    ("Excel SCG_ph5_5.xlsx",    PAST, "20260109 Excel SCG",   "ph_excel_scg",   "Excel x SCG (pH 5.5)"),
    ("Excel SLESS_ph5_5.xlsx",  PAST, "20260109 Excel SLESS", "ph_excel_sless", "Excel x SLESS (pH 5.5)"),
    ("Excel SLS_ph5_5.xlsx",    PAST, "20260109 Excel SLS",   "ph_excel_sls",   "Excel x SLS (pH 5.5)"),
    ("26010102 JR30M_RL_Ph7.xlsx", PAST, "20260102 20260102 JR30M_RL", "ph_jr30m_rl", "JR30M x Rhamnolipid (pH 7)"),
]

DB = "phase_diagrams.db"


def delete_experiment(eid):
    if not Path(DB).exists():
        return
    con = sqlite3.connect(DB)
    try:
        con.execute("DELETE FROM measurements WHERE experiment_id = ?", (eid,))
        con.commit()
    except Exception:  # noqa: BLE001
        pass
    finally:
        con.close()


def main():
    ok, fail = 0, 0
    for xl_name, folder, grp, eid, name in JOBS:
        xl = XL / xl_name
        if not xl.exists():
            print(f"SKIP {eid}: excel missing -> {xl_name}")
            fail += 1
            continue
        files = [f for f in folder.glob("*.txt") if f.name.startswith(grp + " ")]
        if len(files) < 2:
            print(f"SKIP {eid}: no txt for prefix '{grp}' ({len(files)} found)")
            fail += 1
            continue
        tmp = Path(tempfile.mkdtemp(prefix="ing_"))
        for f in files:
            shutil.copy(f, tmp / f.name)
        try:
            delete_experiment(eid)
            cphase.ingest(xl, tmp, eid, name, n_reads=len(files) // 2)
            print(f"OK  {eid:16s} <- {len(files)} txt  '{name}'")
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"FAIL {eid}: {e}")
            fail += 1
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{ok} ingested, {fail} failed.\nExperiments now in DB:")
    for e in cphase.list_experiments():
        print(f"  {e['experiment_id']:16s} {e.get('surfactant')} x {e.get('polymer')}"
              f"  ({e['n_points']} pts)")


if __name__ == "__main__":
    main()
