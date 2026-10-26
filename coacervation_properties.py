"""
Component property lookup (molecular weight, charge density) for structure-property
comparisons. Values live in component_properties.csv (edit it with measured data).
The table can hold both polymers and surfactants (see the 'type' column).
"""

from __future__ import annotations

import csv
from pathlib import Path

PROPS_CSV = Path("component_properties.csv")
LEGACY_CSV = Path("polymer_properties.csv")


def polymer_key(polymer_or_label: str) -> str:
    """Extract a polymer identity from a polymer string or full sample label.

    'GH150 EED0 0.4% 3196' -> '3196'
    '0.4% Dex-K'           -> 'Dex-K'
    """
    s = str(polymer_or_label).strip()
    if "%" in s:
        s = s.split("%")[-1].strip()
    else:
        parts = s.split()
        s = parts[-1].strip() if parts else s
    return s


def canon_key(s: str) -> str:
    """Canonical form for matching polymer names across spacing/hyphen variants.

    'Dex-B', 'Dex B', 'DexB' -> 'dexb';  'Dex-B*' -> 'dexb*'.
    """
    return str(s).strip().lower().replace(" ", "").replace("-", "")


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_properties(path: str | Path | None = None) -> dict:
    """Return {canonical_key: {component, type, mw_kda, charge_density_meq_g, notes}}.

    Reads component_properties.csv (falls back to legacy polymer_properties.csv).
    Accepts a 'component' column (or legacy 'polymer').
    """
    props: dict[str, dict] = {}
    p = Path(path) if path else (PROPS_CSV if PROPS_CSV.exists() else LEGACY_CSV)
    if not p.exists():
        return props
    with p.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = (row.get("component") or row.get("polymer") or "").strip()
            if not key:
                continue
            props[canon_key(key)] = {
                "component": key,
                "type": (row.get("type") or "").strip(),
                "mw_kda": _num(row.get("mw_kda")),
                "charge_density_meq_g": _num(row.get("charge_density_meq_g")),
                "notes": (row.get("notes") or "").strip(),
            }
    return props
