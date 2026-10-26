"""One-off: load raw_data/lasentec_brandon.csv (Merquats screening Lasentec
results, wide chord-distribution format) into the app's lasentec_store.json
so the Analyze tab can plot it (per-chassis Response vs Ch. Midpoints, like
the source workbook charts). Run from Gamsky_Coacervation/.
"""
import coacervation_lasentec as clas

POLY = {"NH3196": "Control (NH3196)", "Pq6": "Pq-6", "Pq22": "Pq-22",
        "Pq47": "Pq-47", "Pq53": "Pq-53", "NatCaready": "NatCaready",
        "NatClear": "NatClear", "Cassia": "Cassia"}
CH = {"GH130": "Merq GH130", "BC128o": "Merq BC128"}


def name_of(col):
    p, c = col.rsplit("_", 1)
    return f"{POLY[p]} ({CH[c]})"


def chassis_of(col):
    _, c = col.rsplit("_", 1)
    return CH[c]


if __name__ == "__main__":
    recs = clas.ingest_wide_chord_csv(r"raw_data\lasentec_brandon.csv",
                                      name_of=name_of, chassis_of=chassis_of)
    print(f"Ingested {len(recs)} Lasentec records:")
    for r in recs:
        print(f"  {r['key']:35s} chassis={r['chassis']:14s} "
              f"peak={r['metrics']['peak_um']:>6.1f}um  frac>30={r['metrics']['frac_gt30']:>5.1f}%")
