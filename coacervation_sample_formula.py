"""Ingredient index + search for already-run %T samples.

Caches each sample's Enovia formula (ingredient list) by Batch ID in a local
JSON store, so the Analyze tab can filter past %T runs by ingredient(s) without
re-querying Databricks every time. Formulas are pulled via
``coacervation_nexus.formula_composition`` (Nexus -> Enovia) and cached.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import coacervation_nexus as cnx

STORE = Path("sample_formula_store.json")


def _norm(name: str) -> str:
    """Normalize an ingredient name for matching (lowercase, collapse spaces)."""
    return " ".join(str(name or "").strip().lower().split())


def load_store() -> dict:
    if STORE.exists():
        try:
            return json.loads(STORE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_store(store: dict) -> None:
    STORE.write_text(json.dumps(store, indent=2), encoding="utf-8")


def get_ingredients(batch_id: str, store: dict | None = None,
                    refresh: bool = False) -> dict:
    """Return the cached ingredient record for a batch id, fetching if missing.

    Record shape: ``{"ingredients": [desc...], "product": str, "ok": bool,
    "note": str, "updated": iso}``. Non-resolving batches are cached as empty so
    we don't re-query them every time.
    """
    bid = str(batch_id or "").strip()
    if not bid:
        return {"ok": False, "ingredients": [], "note": "no batch id"}
    own = store is None
    store = load_store() if own else store
    if not refresh and bid in store:
        return store[bid]
    rec = {"ok": False, "ingredients": [], "product": "", "note": "",
           "updated": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        fc = cnx.formula_composition(bid)
        rec["ok"] = bool(fc.get("ok"))
        rec["ingredients"] = [str(i.get("description") or "").strip()
                              for i in (fc.get("ingredients") or [])
                              if str(i.get("description") or "").strip()
                              and str(i.get("description") or "").strip() != "N/A"]
        rec["product"] = str(fc.get("product_desc") or "")
        rec["note"] = str(fc.get("note") or fc.get("error") or "")
    except Exception as e:  # noqa: BLE001
        rec["note"] = str(e)
    store[bid] = rec
    if own:
        save_store(store)
    return rec


def ensure_for_batches(batch_ids: list[str], limit: int = 40) -> dict:
    """Fetch+cache formulas for any batch ids not already cached (capped)."""
    store = load_store()
    todo = [b for b in dict.fromkeys(str(x).strip() for x in batch_ids if str(x).strip())
            if b not in store]
    fetched = 0
    for bid in todo[:limit]:
        get_ingredients(bid, store=store, refresh=False)
        fetched += 1
    if fetched:
        save_store(store)
    return {"cached": len(store), "fetched": fetched,
            "remaining": max(0, len(todo) - fetched)}


def ingredient_index(store: dict | None = None) -> list[dict]:
    """Aggregate all ingredients across the store -> [{name, norm, n_batches}]."""
    store = load_store() if store is None else store
    counts: dict[str, dict] = {}
    for rec in store.values():
        for ing in (rec.get("ingredients") or []):
            key = _norm(ing)
            if not key:
                continue
            slot = counts.setdefault(key, {"name": ing, "norm": key, "n_batches": 0})
            slot["n_batches"] += 1
    return sorted(counts.values(), key=lambda d: (-d["n_batches"], d["name"].lower()))


def batches_with_ingredients(selected: list[str], mode: str = "and",
                             store: dict | None = None) -> set[str]:
    """Return batch ids whose formula contains the selected ingredient(s)."""
    store = load_store() if store is None else store
    want = {_norm(s) for s in selected if _norm(s)}
    if not want:
        return set()
    out = set()
    for bid, rec in store.items():
        have = {_norm(i) for i in (rec.get("ingredients") or [])}
        if mode == "or":
            if have & want:
                out.add(bid)
        else:  # and
            if want <= have:
                out.add(bid)
    return out
