"""Cross-method fingerprint store + similarity flagging.

Stores a compact numeric fingerprint for every plotted profile (%T, inverse %T,
phase diagram, Lasentec) so a newly generated profile can be flagged as similar
to something measured before ("similar profile to <sample>").

Similarity = 100 * (1 - normalized RMS distance) over the shared feature axes,
each feature min-max normalized across the stored population + the query.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

STORE = Path("fingerprint_store.json")

# feature keys per kind (built from the fingerprint dicts each tab already makes)
FEATURES = {
    "pct":      ["auc", "trough_dilution", "onset", "breadth"],
    "ipct":     ["inverse_auc", "width_decades", "onset_dilution", "peak_pct"],
    "phase":    ["coac_area", "clear_frac", "mean_transmission"],
    "lasentec": ["peak_um", "frac_gt30", "n_modes"],
}


def _isnum(v) -> bool:
    try:
        f = float(v)
        return math.isfinite(f)
    except (TypeError, ValueError):
        return False


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


def _vec(kind: str, fp: dict):
    keys = FEATURES.get(kind) or sorted(k for k in fp if _isnum(fp.get(k)))
    vec = [float(fp[k]) if k in fp and _isnum(fp.get(k)) else None for k in keys]
    return vec, keys


def save_fingerprint(kind: str, name: str, fp: dict, batch_id: str = "") -> None:
    """Insert/replace the stored fingerprint for (kind, name)."""
    name = (name or "").strip()
    if not name:
        return
    d = _load()
    vec, keys = _vec(kind, fp)
    if all(v is None for v in vec):
        return
    recs = [r for r in d.get(kind, []) if r.get("name") != name]
    recs.append({"name": name, "batch_id": (batch_id or "").strip(),
                 "keys": keys, "vec": vec})
    d[kind] = recs
    _save(d)


def find_similar(kind: str, fp: dict, exclude_name: str = "", top: int = 1,
                 min_similarity: float = 0.0) -> list:
    """Return the most similar stored profiles of the same kind (excluding self)."""
    d = _load()
    recs = [r for r in d.get(kind, []) if r.get("name") != (exclude_name or "").strip()]
    if not recs:
        return []
    vec, keys = _vec(kind, fp)
    n = len(keys)
    allvecs = [r.get("vec", []) for r in recs] + [vec]
    lo = [None] * n
    hi = [None] * n
    for j in range(n):
        vals = [v[j] for v in allvecs if j < len(v) and v[j] is not None and _isnum(v[j])]
        if vals:
            lo[j], hi[j] = min(vals), max(vals)

    def norm(v):
        out = []
        for j in range(n):
            vj = v[j] if j < len(v) else None
            if vj is None or lo[j] is None or hi[j] is None or hi[j] == lo[j]:
                out.append(None)
            else:
                out.append((vj - lo[j]) / (hi[j] - lo[j]))
        return out

    qn = norm(vec)
    results = []
    for r in recs:
        rn = norm(r.get("vec", []))
        diffs = [(a - b) ** 2 for a, b in zip(qn, rn) if a is not None and b is not None]
        if not diffs:
            continue
        dist = math.sqrt(sum(diffs) / len(diffs))  # normalized RMS in [0,1]
        sim = round(100.0 * (1.0 - dist), 1)
        if sim >= min_similarity:
            results.append({"name": r["name"], "batch_id": r.get("batch_id", ""),
                            "similarity": sim})
    results.sort(key=lambda z: -z["similarity"])
    return results[:top]


def record_and_match(kind: str, name: str, fp: dict, batch_id: str = "",
                     top: int = 1):
    """Find similar PRIOR profiles, then store this one. Returns match list."""
    matches = find_similar(kind, fp, exclude_name=name, top=top)
    save_fingerprint(kind, name, fp, batch_id=batch_id)
    return matches


def clear(kind: str = "") -> None:
    if not kind:
        _save({})
        return
    d = _load()
    d[kind] = []
    _save(d)
