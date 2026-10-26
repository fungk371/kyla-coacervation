"""Copy, rename and sort the dextran %T plate files into Organized/ folders (originals untouched).

Run from Gamsky_Coacervation/:  python organize_dextran_outputs.py [--apply]
"""
import hashlib
import re
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from coacervation_layout import annotate_concentration
from coacervation_parser import parse_kinetic_plate_file
from make_data_workbook import F, SAMPLES_1PCT

ROOT = Path(r"C:\Users\fung.k.1\Downloads\Dextrans PercentT")
DEST = ROOT / "Organized"
CSV = Path("raw_data/POlymer test/Dextran_Project_Share/data/all_time_formula_fraction_curves.csv")
RAW = Path("raw_data")

CH = {"GH150 EED0": "EED0", "GH150 DDu0, 3.6% LAPB": "LAPB", "GH150 DDu0, 3.6% APG": "APG", "water": "water"}
FOLDER = {"EED0": "EED0", "LAPB": "DDu0_LAPB", "APG": "DDu0_APG"}


def poly_code(name):
    name = re.sub(r"^0\.4%\s*", "", name).replace("PTL water", "PTLwater").replace(" ", "").replace("-", "")
    return name.replace("*", "star")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def folder_for(chassis):
    real = {c for c in chassis if c != "water"}
    return FOLDER[real.pop()] if len(real) == 1 else "Mixed_or_control_plates"


def stamp(name):
    m = re.search(r"(\d{4})\. (\d{2})\. (\d{2})_(\d{2})\.(\d{2})", name)
    return f"{m[1]}{m[2]}{m[3]}_{m[4]}{m[5]}" if m else None


def plan_04():
    d = pd.read_csv(CSV)
    d["ff"], d["t"] = d["Formula_fraction"].round(5), d["Time_min"].round(1)
    ref = {k: g.groupby(["ff", "t"])["%T"].mean() for k, g in d.groupby(["Dataset", "Chassis", "Polymer"])}
    rows = []
    for f in sorted((ROOT / "0.4percent").glob("*.txt")):
        df = annotate_concentration(parse_kinetic_plate_file(str(f))).dropna(subset=["formula_fraction"]).copy()
        df["ff"], df["t"] = df["formula_fraction"].round(5), df["timepoint_minutes"].round(1)
        found, evidence = {}, []
        for tr in (1, 2):
            s = df[df["trough"] == tr].groupby(["ff", "t"])["transmission_pct"].mean()
            best = None
            for (ds, ch, po), r in ref.items():
                idx = s.index.intersection(r.index)
                if len(idx) >= 100:
                    mae = float(np.mean(np.abs(s.loc[idx].to_numpy() - r.loc[idx].to_numpy())))
                    if best is None or mae < best[0]:
                        best = (mae, ch, po, ds)
            if best and best[0] < 0.01:
                found[tr] = (CH[best[1]], poly_code(best[2]))
                evidence.append(f"T{tr}: exact match to Dow CSV '{best[3]}'")
        if f.name.startswith("Run"):
            rows.append((f, "Other", None, f"InMarket_20260826_{f.stem.split()[0]}.txt",
                         "Not dextran: 26 Aug in-market product run (per project notes); product names to be confirmed"))
        elif len(found) == 2:
            chs = [found[1][0], found[2][0]]
            tag = "-".join(dict.fromkeys(chs))
            name = f"0.4pct_{tag}_{found[1][1]}-{found[2][1]}_{stamp(f.name)}.txt"
            rows.append((f, "0.4pct", folder_for(chs), name, "; ".join(evidence)))
        else:
            rows.append((f, "0.4pct", "Needs_review", f.name, "No exact match in Dow CSV; identify from your notes"))
    return rows


def plan_1():
    known = {}
    for key, p in F.items():
        known[sha(RAW / p)] = key
    by_file = {}
    for ch, poly, role, fname, tr in SAMPLES_1PCT:
        by_file.setdefault(fname, {})[tr] = (ch, poly, role)
    short = {"GH150 DDU0 + 3.6% APG": "APG", "GH150 DDU0 + 3.6% LAPB": "LAPB", "GH150 EED0": "EED0",
             "NATIVE Scalp Detox (competitor)": "EED0"}
    rows = []
    for f in sorted((ROOT / "1percent").glob("*.txt")):
        h = sha(f)
        key = known.get(h)
        if key is None:
            note = "NoShake dilution series (T1 CD2 / T2 Dex-K); chassis EED0 per your earlier correction" if "noshake" in f.name.lower() else "No identical copy in raw_data; check manually"
            if "noshake" in f.name.lower():
                rows.append((f, "1pct", "NoShake", "1pct_EED0_CD2-DexK_NoShake.txt", note))
            else:
                rows.append((f, "1pct", "Needs_review", f.name, note))
            continue
        t = by_file[F[key]]
        chs = [short[t[i][0]] for i in (1, 2)]
        polys = [poly_code(t[i][1]) for i in (1, 2)]
        tag = "-".join(dict.fromkeys(chs))
        if key == "apg_ctrl":
            name, folder = "1pct_APG_NoSalt-PTLwater_20260903.txt", "Mixed_or_control_plates"
        elif key == "l7":
            name, folder = "1pct_EED0_NATIVE-DexK_20260904.txt", "Mixed_or_control_plates"
        elif key == "apg_dexk":
            name, folder = "1pct_APG-LAPB_DexK-DexK_20260903.txt", "Mixed_or_control_plates"
        else:
            date = re.match(r"(\d{8})", F[key])[1]
            name, folder = f"1pct_{tag}_{polys[0]}-{polys[1]}_{date}.txt", FOLDER[chs[0]]
        why = f"Identical to raw_data/{F[key]}" + ("" if f.name == F[key] else f" (your file is named '{f.name}')")
        rows.append((f, "1pct", folder, name, why))
    return rows


def main(apply):
    plan = plan_04() + plan_1()
    out = []
    for src, group, folder, new, why in plan:
        sub = DEST / group if group == "Other" else DEST / group / folder
        out.append({"Original_file": src.name, "Original_folder": src.parent.name, "New_name": new,
                    "New_folder": str(sub.relative_to(DEST)), "Basis": why})
        if apply:
            sub.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, sub / new)
    df = pd.DataFrame(out)
    pd.set_option("display.width", 250, "display.max_colwidth", 80)
    print(df[["Original_file", "New_folder", "New_name"]].to_string(index=False))
    if apply:
        df.to_csv(DEST / "File_Rename_Manifest.csv", index=False)
        print(f"\nCopied {len(df)} files to {DEST}")
    else:
        print("\nDry run only. Re-run with --apply to copy.")


if __name__ == "__main__":
    main("--apply" in sys.argv)
