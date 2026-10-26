"""
Coacervation plate layout: map wells -> (trough, formula fraction).

Derived from the master template sheet 'THIS IS THE ONE USED' in
'96 well plate calculations ID variable.xlsx':
  - Trough 1 = rows A-D, Trough 2 = rows E-H
  - Within a trough, wells are ordered row-major (A1..A12, B1..B12, ...)
  - Column AI3:AI50 gives the dilution factor (formula fraction) for each of
    the 48 positions, from 0.5 (most concentrated) down to 0.001852.

Two samples (troughs) per plate; each shares the same 48 formula fractions.
"""

from __future__ import annotations

import pandas as pd

# Dilution factors / formula fractions, positions 0..47 (AI3:AI50).
FORMULA_FRACTIONS: list[float] = [
    0.5, 0.475925926, 0.451851852, 0.427777778, 0.403703704, 0.37962963,
    0.355555556, 0.331481481, 0.307407407, 0.283333333, 0.259259259, 0.235185185,
    0.224074074, 0.212962963, 0.201851852, 0.190740741, 0.17962963, 0.168518519,
    0.157407407, 0.146296296, 0.135185185, 0.124074074, 0.112962963, 0.101851852,
    0.096296296, 0.090740741, 0.085185185, 0.07962963, 0.074074074, 0.068518519,
    0.062962963, 0.057407407, 0.051851852, 0.046296296, 0.040740741, 0.035185185,
    0.032407407, 0.02962963, 0.026851852, 0.024074074, 0.021296296, 0.018518519,
    0.015740741, 0.012962963, 0.010185185, 0.007407407, 0.00462963, 0.001851852,
]

TROUGH_ROWS = {1: ["A", "B", "C", "D"], 2: ["E", "F", "G", "H"]}


def build_well_map() -> dict[str, dict]:
    """Return {well_id: {trough, formula_fraction, dilution_index}}."""
    mapping: dict[str, dict] = {}
    for trough, rows in TROUGH_ROWS.items():
        idx = 0
        for row in rows:                 # row-major: A1..A12 then B1..B12 ...
            for col in range(1, 13):
                well = f"{row}{col}"
                mapping[well] = {
                    "trough": trough,
                    "formula_fraction": FORMULA_FRACTIONS[idx],
                    "dilution_index": idx,
                }
                idx += 1
    return mapping


def annotate_concentration(long_df: pd.DataFrame) -> pd.DataFrame:
    """Add trough / formula_fraction / dilution_index columns to a parsed long df.

    Args:
        long_df: output of coacervation_parser.parse_kinetic_plate_file
                 (must have a 'well' column).

    Returns:
        A copy with concentration columns added (wells not in the standard
        layout get NaN and can be filtered out).
    """
    wmap = build_well_map()
    df = long_df.copy()
    df["trough"] = df["well"].map(lambda w: wmap.get(w, {}).get("trough"))
    df["formula_fraction"] = df["well"].map(
        lambda w: wmap.get(w, {}).get("formula_fraction")
    )
    df["dilution_index"] = df["well"].map(
        lambda w: wmap.get(w, {}).get("dilution_index")
    )
    return df


def sample_curve(
    long_df: pd.DataFrame, trough: int, timepoint_minutes: float
) -> pd.DataFrame:
    """Extract a single sample's dilution curve at one timepoint.

    Returns a DataFrame sorted by descending concentration with columns:
        formula_fraction, transmission_pct, well, dilution_index
    """
    df = annotate_concentration(long_df)
    sel = df[(df["trough"] == trough)]
    # nearest available timepoint
    times = sorted(sel["timepoint_minutes"].unique())
    tp = min(times, key=lambda t: abs(t - timepoint_minutes))
    sel = sel[sel["timepoint_minutes"] == tp]
    sel = sel.dropna(subset=["formula_fraction"])
    sel = sel.sort_values("formula_fraction", ascending=False)
    return sel[
        ["formula_fraction", "transmission_pct", "well", "dilution_index"]
    ].reset_index(drop=True), tp
