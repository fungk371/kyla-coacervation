"""Parse P&G PTL test-report CSV exports.

The Nexus PTL export is long/EAV: one row per (sample, parameter, rep), with
blank displayvalue rows for un-filled slots. Keyed by Batch ID (B-YYYYMMDD-NNNNN)
so it joins straight to the coacervation library. Steps: 2=DRF, 3=Wet SACS,
4=Dry SACS, 5=IFF.

parse_ptl_report(path) -> tidy DataFrame of real measurements.
aggregate(paths)       -> mean/std/n per (batchid, step, parameter).
summarise(paths)       -> one row per batchid with the headline metrics.
"""
import pandas as pd

STEP_KIND = {"2": "DRF", "3": "Wet SACS", "4": "Dry SACS", "5": "IFF"}

# headline metric per sample -> (step, parameter) ; direction: lower/higher better
HEADLINE = {
    "DRF_final_rinse_friction": ("2", "Final Rinse Friction - Shampoo", "lower"),
    "wSACS_friction": ("3", "Friction", "lower"),
    "wSACS_detangling": ("3", "Detangling", "lower"),
    "dSACS_friction": ("4", "Friction", "lower"),
    "dSACS_detangling": ("4", "Detangling", "lower"),
    "IFF_peak_force": ("5", "Sum of Peak Force", "lower"),
}


def parse_ptl_report(path):
    df = pd.read_csv(path, dtype=str)
    df = df[df["displayvalue"].notna() & (df["displayvalue"].str.strip() != "")].copy()
    df["value"] = pd.to_numeric(df["displayvalue"], errors="coerce")
    df = df.dropna(subset=["value"])
    df["step"] = df["step"].astype(str).str.strip()
    return df[["batchid", "batchdesc", "sampleid", "step", "parameter",
               "displayunits", "value", "rep"]]


def aggregate(paths):
    alld = pd.concat([parse_ptl_report(p) for p in paths], ignore_index=True)
    return alld.groupby(["batchid", "batchdesc", "step", "parameter"],
                        as_index=False).agg(mean=("value", "mean"),
                                            std=("value", "std"), n=("value", "count"))


def summarise(paths):
    agg = aggregate(paths)
    rows = []
    for (bid, desc), g in agg.groupby(["batchid", "batchdesc"]):
        row = {"batchid": bid, "batchdesc": desc}
        for name, (step, param, _dir) in HEADLINE.items():
            hit = g[(g["step"] == step) & (g["parameter"] == param)]
            row[name] = float(hit["mean"].iloc[0]) if len(hit) else None
        rows.append(row)
    return pd.DataFrame(rows)


if __name__ == "__main__":
    import os
    d = os.path.expanduser("~/Downloads")
    paths = [os.path.join(d, f) for f in (
        "DRF_Test_Report_2026-09-21.csv", "Wet_SACS_Test_Report_2026-09-21.csv",
        "Dry_SACS_Test_Report_2026-09-21.csv", "IFF_Test_Report_2026-09-21.csv")]
    paths = [p for p in paths if os.path.exists(p)]
    agg = aggregate(paths)
    print("=== all aggregated (mean across reps) ===")
    print(agg.to_string(index=False))
    print("\n=== headline summary (one row per sample) ===")
    print(summarise(paths).to_string(index=False))
