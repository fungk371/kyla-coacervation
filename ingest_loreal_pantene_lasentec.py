"""Ingest the L'Oreal Hyaluron Plump (DI water vs 7gpg, +1:10 dilution) and
Pantene M10 (7gpg, 1:49) Lasentec runs (2026-09-25) into lasentec_store.json,
and print a metrics comparison table."""
import coacervation_lasentec as clas

FILES = [
    ("lasentec_data/LorealHyaluronPlump_7gpg_09252026.csv",
     "L'Oreal Hyaluron Plump (7gpg, 1:49)", "L'Oreal Hyaluron Plump", 49),
    ("lasentec_data/LorealHyaluronPlump_7gpg_09252026_1TENdilution.csv",
     "L'Oreal Hyaluron Plump (7gpg, 1:9)", "L'Oreal Hyaluron Plump", 9),
    ("lasentec_data/DIwaterLorealHyaluronPlump_DIwater_09252026_1TENdilution.csv",
     "L'Oreal Hyaluron Plump (DI water/0gpg, 1:9)", "L'Oreal Hyaluron Plump", 9),
    ("lasentec_data/PanteneM10_7gpg_1to49_09252026.csv",
     "Pantene M10 (7gpg, 1:49)", "Pantene M10", 49),
]

# stale keys from earlier (incorrect) labeling - remove before re-ingesting
STALE_KEYS = [
    "name:l'oreal hyaluron plump (7gpg, 1:10)@1:10",
    "name:l'oreal hyaluron plump (di water/0gpg, 1:10)@1:10",
    "name:l'oreal hyaluron plump (7gpg, neat)",
]

if __name__ == "__main__":
    for k in STALE_KEYS:
        clas.delete_record(k)
    rows = []
    for path, name, chassis, dilution in FILES:
        mids, counts = clas.parse_fbrm(path)
        metrics = clas.compute_metrics(mids, counts)
        rec = clas.upsert_record(sample_id="", batch_id="", name=name, csv_name=path,
                                 metrics=metrics, dilution=dilution, chassis=chassis)
        rows.append(rec)
        print(f"{name:48s} n_scans={metrics['n_scans']:3d} n_steady={metrics['n_steady']:3d} "
              f"peak={metrics['peak_um']:>7.1f}um  frac>30={metrics['frac_gt30']:>5.1f}%  "
              f"sqrwt={str(metrics['sqrwt_um']):>7s}um  total={metrics['total_counts']:>8.1f}  "
              f"modes={metrics['modes_um']}")
