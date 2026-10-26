"""
Sample composition / ingredient resolver for the coacervation platform.

Given a coacervation sample or catalogued product, return its composition from
the right source, routed by whether it is an internal P&G formula or an external
competitor product:

  * INTERNAL (P&G)  -> EBR as-made batch composition (silver_ebr.batch_details),
                       bridged from the Nexus sample via s_batch.u_referencekey;
                       optional Enovia/FIS nominal formula BOM.
  * EXTERNAL (competitor) -> Mintel INCI ingredient list + claims
                       (groupdb_beauty_di_rd.mintel), matched by GTIN/record_id
                       or brand + product name.

All sources here are Databricks tables/views, so this reuses the SINGLE PAT-based
connection already used by ``coacervation_nexus`` (``DATABRICKS_ACCESS_TOKEN``).
No separate Mintel API token is needed for this path (that is the live REST
connector ``coacervation_mintel``, kept separate). Server-safety: PAT only, never
interactive OAuth, and every lookup degrades gracefully to ``{"ok": False,...}``
when unconfigured so the web app is unaffected.

KEY-RESOLUTION NOTE (the one thing to verify before trusting this live):
the internal bridge assumes the stored sample id equals ``s_batch.s_batchid`` (or
an ``EBR#####`` reference). Confirm with one known sample round-trip; ``key=`` lets
you override which column is filtered.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

# Reuse the Nexus connector's PAT-safe connection + config (one auth path).
try:
    import coacervation_nexus as _cnx
except Exception:  # pragma: no cover
    _cnx = None

# Catalog/schema locations (from the user's verified queries).
NEXUS_SBATCH = "cdl_stc_prod.silver_nexus.s_batch"
EBR_FORMULA_BATCHES = "cdl_stc_prod.silver_ebr.formula_batches"
EBR_BATCH_DETAILS = "cdl_stc_prod.silver_ebr.batch_details"
ENOVIA_BOM = "cdl_stc_prod.gold_stc.bom_core_prod_raw_material_assoc_curr_vw"
MINTEL = "groupdb_beauty_di_rd.mintel"

# Product categories treated as internal vs external (matches app PRODUCT_CATEGORIES).
_INTERNAL_CATS = {"in_market", "benchmark", "control", "development"}
_EXTERNAL_CATS = {"competitor"}


# --------------------------------------------------------------------------- #
# Status / connection (delegated to coacervation_nexus)
# --------------------------------------------------------------------------- #
def status() -> dict[str, Any]:
    """Readiness WITHOUT opening a connection. Same PAT/warehouse as Nexus.

    Adds a reminder that Mintel lives in a different catalog and needs a
    cross-catalog SELECT grant on the same token.
    """
    base = _cnx.status() if _cnx is not None else {"ready": False}
    return {
        **base,
        "sources": {
            "internal_ebr": EBR_BATCH_DETAILS,
            "internal_enovia": ENOVIA_BOM,
            "external_mintel": MINTEL,
        },
        "note": ("Mintel is in groupdb_beauty_di_rd; ensure the same PAT has "
                 "SELECT on that catalog as well as cdl_stc_prod."),
    }


def _query(sql: str) -> pd.DataFrame:
    """Run a read-only query on the shared PAT connection; caller handles errors."""
    if _cnx is None:
        raise RuntimeError("coacervation_nexus (Databricks connection) is unavailable.")
    conn = _cnx._connect()
    try:
        return pd.read_sql(sql, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _in_list(ids) -> str:
    """Build a safe SQL IN-list from ids (single-quote escaped)."""
    clean = sorted({str(i).strip() for i in ids if str(i).strip()})
    return "', '".join(i.replace("'", "''") for i in clean)


def _df_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    return [{k: ("" if pd.isna(v) else v) for k, v in row.items()}
            for row in df.to_dict("records")]


# --------------------------------------------------------------------------- #
# INTERNAL: EBR as-made composition (verified query, bridged via Nexus s_batch)
# --------------------------------------------------------------------------- #
def internal_composition(ids: list[str], key: str = "auto") -> dict[str, Any]:
    """As-made batch composition for internal sample ids.

    ``key``:
      * ``"ebr"``      - ``ids`` are EBR references (``EBR96309``); filter u_referencekey.
      * ``"sample"``   - ``ids`` are Nexus sample ids; filter s_batch.s_batchid.
      * ``"auto"``     - route each id: ``EBR\\d+`` -> ebr, else sample.

    Uses the user's verified join chain:
        s_batch.u_referencekey -('EBR' stripped)-> formula_batches.batch_id
        -> batch_details (material_number / description / actual_amount / units).
    Returns ``{ok, rows, grouped}`` where grouped is keyed by the input id.
    """
    ids = [str(i).strip() for i in ids if str(i).strip()]
    if not ids:
        return {"ok": False, "error": "No ids provided."}

    ebr_ids = [i for i in ids if i.upper().startswith("EBR")]
    sample_ids = [i for i in ids if not i.upper().startswith("EBR")]
    if key == "ebr":
        ebr_ids, sample_ids = ids, []
    elif key == "sample":
        ebr_ids, sample_ids = [], ids

    frames: list[pd.DataFrame] = []
    try:
        if ebr_ids:
            frames.append(_query(f"""
                SELECT s.s_batchid            AS sample_id,
                       s.u_referencekey       AS ebr_ref,
                       bd.material_number      AS material_number,
                       bd.description          AS description,
                       bd.actual_amount        AS amount,
                       bd.actual_units         AS units
                FROM {NEXUS_SBATCH} s
                JOIN {EBR_FORMULA_BATCHES} fb
                     ON CAST(fb.batch_id AS STRING) = regexp_replace(s.u_referencekey, '^EBR', '')
                JOIN {EBR_BATCH_DETAILS} bd
                     ON bd.batch_id = fb.batch_id
                WHERE s.u_referencekey IN ('{_in_list(ebr_ids)}')
                  AND bd.material_number IS NOT NULL
            """))
        if sample_ids:
            frames.append(_query(f"""
                SELECT s.s_batchid            AS sample_id,
                       s.u_referencekey       AS ebr_ref,
                       bd.material_number      AS material_number,
                       bd.description          AS description,
                       bd.actual_amount        AS amount,
                       bd.actual_units         AS units
                FROM {NEXUS_SBATCH} s
                JOIN {EBR_FORMULA_BATCHES} fb
                     ON CAST(fb.batch_id AS STRING) = regexp_replace(s.u_referencekey, '^EBR', '')
                JOIN {EBR_BATCH_DETAILS} bd
                     ON bd.batch_id = fb.batch_id
                WHERE s.s_batchid IN ('{_in_list(sample_ids)}')
                  AND bd.material_number IS NOT NULL
            """))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "source": "ebr"}

    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    rows = _df_records(df)
    grouped: dict[str, list] = {}
    for r in rows:
        grouped.setdefault(str(r.get("sample_id") or r.get("ebr_ref") or ""), []).append(r)
    return {"ok": True, "source": "ebr", "rows": rows, "grouped": grouped,
            "n": len(rows)}


WS_RE = re.compile(r"WS-?\d{6,}", re.I)


def worksheet_for(sample_ids: list[str], key: str = "auto") -> dict[str, Any]:
    """Find the Nexus worksheet id(s) (WS-...) linked to a sample.

    The exact worksheet column of ``s_batch`` is not confirmed, so instead of
    guessing a column name (and risking a SQL error), this pulls the sample's
    ``s_batch`` row(s) and scans all values for a ``WS-######`` pattern. Robust
    to schema differences; degrades to an empty list on any failure.
    """
    ids = [str(i).strip() for i in sample_ids if str(i).strip()]
    if not ids:
        return {"ok": False, "error": "No ids provided."}
    ebr_ids = [i for i in ids if i.upper().startswith("EBR")]
    sample_ids2 = [i for i in ids if not i.upper().startswith("EBR")]
    col = "u_referencekey" if (key == "ebr" or (key == "auto" and ebr_ids and not sample_ids2)) else "s_batchid"
    filt = ebr_ids if col == "u_referencekey" else (sample_ids2 or ids)
    try:
        df = _query(f"SELECT * FROM {NEXUS_SBATCH} WHERE {col} IN ('{_in_list(filt)}') LIMIT 50")
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "source": "s_batch"}
    found: list[str] = []
    for rec in _df_records(df):
        for v in rec.values():
            for m in WS_RE.findall(str(v)):
                w = m.upper()
                if not w.startswith("WS-"):
                    w = "WS-" + w[2:]
                if w not in found:
                    found.append(w)
    return {"ok": True, "worksheet": found}


def enovia_bom(keys: list[str], key_col: str | None = None) -> dict[str, Any]:
    """Nominal formula BOM from Enovia/FIS.

    The exact join column of ``bom_core_prod_raw_material_assoc_curr_vw`` is not
    yet confirmed, so ``key_col`` must be supplied (e.g. a product/formula id
    column). Without it, this returns a not-configured result rather than
    guessing a column and shipping broken SQL. Wrapped so any schema mismatch
    degrades gracefully.
    """
    keys = [str(k).strip() for k in keys if str(k).strip()]
    if not keys:
        return {"ok": False, "error": "No keys provided."}
    if not key_col:
        return {"ok": False, "configured": False,
                "error": ("Enovia BOM join column not confirmed. Pass key_col= once "
                          f"the keying column of {ENOVIA_BOM} is verified.")}
    try:
        df = _query(f"""
            SELECT *
            FROM {ENOVIA_BOM}
            WHERE {key_col} IN ('{_in_list(keys)}')
        """)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "source": "enovia"}
    return {"ok": True, "source": "enovia", "rows": _df_records(df)}


# --------------------------------------------------------------------------- #
# EXTERNAL: Mintel INCI + claims
# --------------------------------------------------------------------------- #
def mintel_lookup(*, record_id: str = "", gtin: str = "",
                  brand: str = "", name: str = "") -> dict[str, Any]:
    """Competitor INCI + claims from Mintel.

    Match priority: record_id -> gtin (if a barcode column exists) -> brand+name
    text. The user's verified SELECT exposes ingredients_standard_form (INCI) and
    product_description; a dedicated claims column is selected if present.
    """
    where = ""
    if record_id:
        where = f"record_id = '{str(record_id).replace(chr(39), chr(39) * 2)}'"
    elif gtin:
        g = str(gtin).replace("'", "''")
        where = f"try_cast(bar_code AS string) = '{g}'"
    else:
        parts = []
        if brand:
            parts.append(f"lower(brand) LIKE '%{str(brand).lower().replace(chr(39), chr(39)*2)}%'")
        if name:
            parts.append(f"lower(product_description) LIKE '%{str(name).lower().replace(chr(39), chr(39)*2)}%'")
        if not parts:
            return {"ok": False, "error": "Provide record_id, gtin, or brand/name."}
        where = " AND ".join(parts)

    try:
        df = _query(f"""
            SELECT record_id, brand, category, sub_category,
                   ingredients_standard_form, product_description,
                   functional_claims, free_from_claims, natural_claims,
                   suitable_for_claims, positioning_claims,
                   ethical___environmental_claims
            FROM {MINTEL}
            WHERE {where}
            LIMIT 25
        """)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "source": "mintel"}

    rows = _df_records(df)
    return {"ok": True, "source": "mintel", "rows": rows, "n": len(rows),
            "best": rows[0] if rows else None}


# --------------------------------------------------------------------------- #
# Router
# --------------------------------------------------------------------------- #
def is_internal(product: dict) -> bool:
    """Decide internal vs external from the catalogued product's category/tag."""
    cat = str(product.get("category") or "").strip().lower()
    tag = str(product.get("tag") or "").strip().lower()
    if cat in _EXTERNAL_CATS or "external" in tag:
        return False
    if cat in _INTERNAL_CATS or "p&g" in tag or "p & g" in tag:
        return True
    # default: if it has a P&G Batch/Sample id, treat as internal; else external.
    return bool(product.get("batch_id") or product.get("sample_id"))


def resolve_composition(product: dict, worksheet: bool = False) -> dict[str, Any]:
    """Route a catalogued product/sample to the right composition source.

    ``product`` is a dict that may carry: category/tag, batch_id, sample_id,
    ebr_ref, gtin, brand, name. When ``worksheet`` is set and the product is
    internal, also attach any linked Nexus worksheet id(s). Returns the source
    result plus which route ran.
    """
    if is_internal(product):
        ids = [product.get("ebr_ref"), product.get("sample_id"), product.get("batch_id")]
        ids = [i for i in ids if i]
        if not ids:
            return {"ok": False, "route": "internal",
                    "error": "No EBR ref / sample id / batch id on this internal product."}
        res = internal_composition(ids)
        out = {"route": "internal", **res}
        if worksheet:
            ws = worksheet_for(ids)
            if ws.get("ok"):
                out["worksheet"] = ws.get("worksheet", [])
        return out
    # external -> Mintel
    res = mintel_lookup(gtin=str(product.get("gtin") or ""),
                        brand=str(product.get("brand") or ""),
                        name=str(product.get("name") or ""))
    out = {"route": "external", **res}
    # Fallback: when Mintel has no record, surface the catalog's own ingredient
    # notes + claims so the panel still shows something (clearly not a full INCI).
    if not res.get("rows"):
        cat_inci = str(product.get("ingredients") or "").strip()
        cat_claims = str(product.get("claims") or "").strip()
        if cat_inci or cat_claims:
            out["ok"] = True
            out["source"] = "catalog"
            out["catalog_fallback"] = True
            out["note"] = ("No Mintel record for this product; showing catalog "
                           "ingredient notes (not a full INCI list).")
            out["best"] = {
                "brand": product.get("brand", ""),
                "product_description": product.get("name", ""),
                "ingredients_standard_form": cat_inci,
                "catalog_claims": cat_claims,
                "consumer_feedback": str(product.get("consumer_feedback") or ""),
            }
            out["rows"] = [out["best"]]
            out["n"] = 1
    return out
