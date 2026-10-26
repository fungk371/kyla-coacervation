"""Replace the 3 rerun-only phase cells with their REAL plates (run from Gamsky_Coacervation/)."""
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import coacervation_phase as cphase

DL = Path(r"C:\Users\fung.k.1\Downloads")
DB = "phase_diagrams.db"

# (excel, zip, txt prefix, experiment_id, name)
JOBS = [
    ("20261007 NatCaready + SLS.xlsx", "OneDrive_3_10-23-2026.zip", "20261007 NatCaready + SLS",
     "20261007 NatCaready + SLS", "NatCaready x SLS pH 5.5 (REAL)"),
    ("20261014 NatCaready+ SLE3S .xlsx", "OneDrive_2_10-23-2026 (1).zip", "20261014 NatCaready + SLE3S",
     "20261014 NatCaready + SLE3S", "NatCaready x SLE3S pH 5.5 (REAL)"),
    ("20261012 N3196 + SLE3S.xlsx", "OneDrive_1_10-23-2026 (2).zip", "20261014 3196 + SLE3S",
     "20261014 N3196 + SLE3S", "N3196 x SLE3S pH 5.5 (REAL)"),
]
# mis-ingested earlier (Excel had SLE3S stocks and no polymer name)
BAD = ["20261007 natcaready SLS -REAL"]


def delete(eid):
    con = sqlite3.connect(DB)
    con.execute("DELETE FROM measurements WHERE experiment_id = ?", (eid,))
    con.commit()
    con.close()


for b in BAD:
    delete(b)

for xl, z, grp, eid, name in JOBS:
    tmp = Path(tempfile.mkdtemp(prefix="real_"))
    with zipfile.ZipFile(DL / z) as zf:
        for m in zf.namelist():
            if m.endswith(".txt"):
                (tmp / Path(m).name).write_bytes(zf.read(m))
    files = list(tmp.glob("*.txt"))
    assert all(f.name.startswith(grp + " ") for f in files), (eid, [f.name for f in files][:3])
    delete(eid)
    cphase.ingest(DL / xl, tmp, eid, name, n_reads=len(files) // 2)
    print("OK", eid, len(files), "txt")
    shutil.rmtree(tmp, ignore_errors=True)
