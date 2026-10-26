"""Performance-data store for the Performance Library (ILS / PTL / Consumer).

Generic, format-agnostic: each dataset is an uploaded CSV parsed into rows +
columns and stored under a kind. A 'batch id' column (auto-detected) is the key
that ties a formula's ILS, PTL, deposition and consumer data together, plus to
its coacervation fingerprint. Real parsers can be specialised once example files
are provided; for now any CSV is accepted and viewable/correlatable.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd

STORE = Path("perf_data_store.json")
KINDS = ("ils", "ptl", "consumer")

# candidate header names that identify the batch-id / join key
_BATCH_HINTS = ["batch_id", "batch id", "batchid", "batch", "nexus_id",
                "nexus id", "sample_id", "sample id", "formula", "formula_id"]


def _load() -> dict:
    if STORE.exists():
        try:
            d = json.loads(STORE.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save(d: dict) -> None:
    STORE.write_text(json.dumps(d, indent=2), encoding="utf-8")


def detect_batch_col(columns: list) -> str:
    low = {c.lower().strip(): c for c in columns}
    for hint in _BATCH_HINTS:
        if hint in low:
            return low[hint]
    # fuzzy: any column containing 'batch' or 'id'
    for c in columns:
        cl = c.lower()
        if "batch" in cl or cl.endswith("id") or cl == "id":
            return c
    return columns[0] if columns else ""


def numeric_columns(columns: list, rows: list) -> list:
    out = []
    for c in columns:
        vals = [r.get(c) for r in rows]
        nums = [v for v in vals if _isnum(v)]
        if len(nums) >= max(2, 0.5 * len([v for v in vals if v not in (None, "")])):
            out.append(c)
    return out


def _isnum(v) -> bool:
    try:
        f = float(v)
        return math.isfinite(f)
    except (TypeError, ValueError):
        return False


def ingest_csv(kind: str, path, filename: str = "") -> dict:
    """Parse a CSV and store it under `kind`. Returns the stored dataset."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind '{kind}'")
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    rows = json.loads(df.to_json(orient="records"))  # NaN -> null, clean types
    columns = list(df.columns)
    ds = {
        "kind": kind,
        "filename": filename or "",
        "columns": columns,
        "batch_col": detect_batch_col(columns),
        "numeric_columns": numeric_columns(columns, rows),
        "rows": rows,
        "n": len(rows),
    }
    d = _load()
    d[kind] = ds
    _save(d)
    return ds


def get_dataset(kind: str) -> dict:
    return _load().get(kind, {"kind": kind, "columns": [], "rows": [], "n": 0,
                              "batch_col": "", "numeric_columns": []})


def all_datasets() -> dict:
    return {k: get_dataset(k) for k in KINDS}


def clear(kind: str) -> bool:
    d = _load()
    if kind in d:
        d.pop(kind, None)
        _save(d)
        return True
    return False


def _norm_batch(v) -> str:
    return str(v or "").strip().lower()


def joined_by_batch(kinds=KINDS) -> dict:
    """Return {batch_id: {kind: row, ...}} joining datasets on their batch col."""
    out = {}
    for k in kinds:
        ds = get_dataset(k)
        bc = ds.get("batch_col")
        if not bc:
            continue
        for r in ds.get("rows", []):
            key = _norm_batch(r.get(bc))
            if not key:
                continue
            out.setdefault(key, {})[k] = r
    return out


def correlate(kind: str, x_col: str, y_col: str) -> dict:
    """Pearson r of two numeric columns within one dataset."""
    ds = get_dataset(kind)
    xs, ys, labels = [], [], []
    bc = ds.get("batch_col")
    for r in ds.get("rows", []):
        if _isnum(r.get(x_col)) and _isnum(r.get(y_col)):
            xs.append(float(r[x_col]))
            ys.append(float(r[y_col]))
            labels.append(str(r.get(bc, "")))
    if len(xs) < 3:
        return {"ok": False, "error": "Need at least 3 rows with both values."}
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    sx = math.sqrt(sum((v - mx) ** 2 for v in xs))
    sy = math.sqrt(sum((v - my) ** 2 for v in ys))
    if sx == 0 or sy == 0:
        return {"ok": False, "error": "A column has no variance."}
    r = sum((a - mx) * (b - my) for a, b in zip(xs, ys)) / (sx * sy)
    return {"ok": True, "r": round(r, 3), "n": len(xs),
            "xs": xs, "ys": ys, "labels": labels}
