"""
Databricks / Nexus reagent-and-sample lookup for the coacervation platform.

Mirrors the pattern in ``procter-gamble/Ternary_Diagrams`` (``get_all_reagent_data_batch``):
query the Nexus ``sdidataitem`` table - keyed by ``keyid1`` - to pull the recorded
parameters (composition, prep metadata, pH, ...) for a set of ids.  In the AP app
those ids are reagent lots (``RL-...``); here they are coacervation sample **BatchIDs**
(``B-YYYYMMDD-NNNNN``) that the app already tracks per trough (``sample_key``).

Reuses the project's existing connection config in ``databricks_template`` (warehouse
``dafdca59f4814dd3``, catalog ``cdl_stc_prod.silver_nexus``).

Server-safety: this module authenticates with a **Personal Access Token** only
(``DATABRICKS_ACCESS_TOKEN`` env / ``.env``).  It never falls back to interactive
browser OAuth, which would hang a web server.  If no token is set it reports
"token not configured" and the rest of the app is unaffected.
"""

from __future__ import annotations

import functools
import math
import os
import socket
import sys
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    def load_dotenv(*_a, **_k):  # type: ignore
        return False

try:
    from databricks import sql as _dbsql
except Exception:  # pragma: no cover - package missing
    _dbsql = None

# Reuse the project's connection config (hostname / warehouse / DNS override).
_TEMPLATE = None
for _cand in (Path(__file__).resolve().parent, Path(__file__).resolve().parent.parent):
    if (_cand / "databricks_template.py").exists():
        if str(_cand) not in sys.path:
            sys.path.insert(0, str(_cand))
        try:
            import databricks_template as _TEMPLATE  # type: ignore
        except Exception:
            _TEMPLATE = None
        break

CATALOG = "cdl_stc_prod.silver_nexus"


def _config() -> dict:
    cfg = dict(getattr(_TEMPLATE, "DATABRICKS_CONFIG", {}) or {})
    return {
        "server_hostname": os.getenv("DATABRICKS_SERVER_HOSTNAME") or cfg.get("server_hostname"),
        "http_path": os.getenv("DATABRICKS_HTTP_PATH") or cfg.get("http_path"),
        "catalog": cfg.get("catalog", "cdl_stc_prod"),
        "schema": cfg.get("schema", "silver_nexus"),
    }


def _token() -> str | None:
    from flask import has_request_context, request

    if has_request_context():
        token = request.headers.get("X-Databricks-Access-Token")
        if token:
            return token
    load_dotenv()
    # override=True so a freshly-pasted token in .env is picked up live (an empty
    # value loaded at an earlier startup would otherwise stick for the process).
    for p in (Path.cwd(), Path(__file__).resolve().parent):
        env = p / ".env"
        if env.exists():
            load_dotenv(env, override=True)
    tok = os.getenv("DATABRICKS_ACCESS_TOKEN") or os.getenv("DATABRICKS_TOKEN")
    if not tok:
        cfg = getattr(_TEMPLATE, "DATABRICKS_CONFIG", {}) or {}
        tok = cfg.get("access_token")
    return tok or None


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #
def status() -> dict[str, Any]:
    """Report readiness WITHOUT opening a connection (never blocks the server)."""
    cfg = _config()
    return {
        "package_installed": _dbsql is not None,
        "template_found": _TEMPLATE is not None,
        "token_configured": bool(_token()),
        "server_hostname": cfg.get("server_hostname") or "",
        "http_path": cfg.get("http_path") or "",
        "catalog": CATALOG,
        "ready": bool(_dbsql is not None and cfg.get("server_hostname")
                      and cfg.get("http_path") and _token()),
    }


# --------------------------------------------------------------------------- #
# Connection (PAT only - no interactive OAuth on the server)
# --------------------------------------------------------------------------- #
def _connect():
    if _dbsql is None:
        raise RuntimeError("databricks-sql-connector is not installed.")
    cfg = _config()
    token = _token()
    if not (cfg.get("server_hostname") and cfg.get("http_path")):
        raise RuntimeError("Databricks connection config missing (databricks_template).")
    if not token:
        raise RuntimeError(
            "DATABRICKS_ACCESS_TOKEN not set. Add a Personal Access Token to your "
            ".env to enable server-side Nexus lookups (browser OAuth is disabled "
            "here so the web server cannot hang)."
        )
    # Apply the project's corporate DNS override if present.
    try:
        if _TEMPLATE is not None:
            dns = getattr(_TEMPLATE, "DNS_OVERRIDE", None)
            if dns:
                try:
                    socket.gethostbyname(dns["hostname"])
                except socket.gaierror:
                    _TEMPLATE.apply_dns_override()
    except Exception:
        pass
    return _dbsql.connect(
        server_hostname=cfg["server_hostname"],
        http_path=cfg["http_path"],
        access_token=token,
        _retry_stop_after_attempts_count=5,
        user_agent_entry="Coacervation-Platform",
        session_configuration={"ansi_mode": "true"},
    )


# --------------------------------------------------------------------------- #
# Lookups
# --------------------------------------------------------------------------- #
def lookup_batches(batch_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Return Nexus-recorded parameters for each sample BatchID.

    Queries ``sdidataitem`` (keyed by ``keyid1``) - the same general data-item
    table the AP app uses for reagent composition - projecting parameter name,
    value and units.  Returns ``{batch_id: {"params": [{parameter, value, units}],
    "n_params": int}}`` for every id that has rows.
    """
    ids = sorted({str(b).strip() for b in batch_ids if str(b).strip()})
    if not ids:
        return {}
    id_list = "', '".join(i.replace("'", "''") for i in ids)
    query = f"""
        SELECT sdi.keyid1     AS batch_id,
               sdi.paramid    AS parameter,
               sdi.displayvalue AS value,
               sdi.displayunits AS units
        FROM {CATALOG}.sdidataitem sdi
        WHERE sdi.keyid1 IN ('{id_list}')
    """
    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    out: dict[str, dict[str, Any]] = {}
    if df is None or df.empty:
        return out
    for bid, grp in df.groupby("batch_id"):
        params = [
            {
                "parameter": str(r.get("parameter", "")),
                "value": ("" if pd.isna(r.get("value")) else str(r.get("value"))),
                "units": ("" if pd.isna(r.get("units")) else str(r.get("units"))),
            }
            for _, r in grp.iterrows()
        ]
        out[str(bid)] = {"params": params, "n_params": len(params)}
    return out


def lookup_flat(batch_ids: list[str]) -> list[dict[str, Any]]:
    """Flattened one-row-per-parameter view, convenient for a UI table."""
    data = lookup_batches(batch_ids)
    rows: list[dict[str, Any]] = []
    for bid, info in data.items():
        for p in info["params"]:
            rows.append({"batch_id": bid, **p})
    return rows


# --------------------------------------------------------------------------- #
# Full batch report (details + samples + test results + QA + genealogy)
# --------------------------------------------------------------------------- #
# These production tables live in a DIFFERENT catalog than the reagent/sample
# lookups above (verified: cdl_beauty_prod, not cdl_stc_prod).
BATCH_CATALOG = "cdl_beauty_prod"
_BNX = f"{BATCH_CATALOG}.silver_nexus"
_BPS = f"{BATCH_CATALOG}.silver_ps"


def _records(df) -> list[dict[str, Any]]:
    if df is None or df.empty:
        return []
    return [{k: ("" if pd.isna(v) else v) for k, v in row.items()}
            for row in df.to_dict("records")]


@functools.lru_cache(maxsize=64)
def batch_report(batch_id: str) -> dict[str, Any]:
    """Full Nexus report for one production BatchID.

    Returns batch_details, samples, test_results (+ test_summary), qa_results and
    genealogy. All six queries reuse ONE connection (avoids 6x connect cost) and
    the whole report is cached per batch id so repeat views are instant.
    """
    bid = str(batch_id or "").strip()
    if not bid:
        return {"ok": False, "error": "No batch id provided."}
    safe = bid.replace("'", "''")
    queries = {
        "batch_details": f"SELECT * FROM {_BNX}.nexus_batch_dim WHERE s_batchid = '{safe}'",
        "samples": f"SELECT * FROM {_BNX}.nexus_sample_dim WHERE batchid = '{safe}'",
        "test_results": (f"SELECT * FROM {_BNX}.nexus_all_test_results_dim "
                         f"WHERE batchid = '{safe}' LIMIT 2000"),
        "test_summary": (
            "SELECT paramlistid AS test_group, s_datasetstatus AS dataset_status, "
            "COUNT(*) AS total_results, COUNT(DISTINCT keyid1) AS distinct_samples, "
            "COUNT(displayvalue) AS values_recorded, COUNT(enteredvalue) AS numeric_values "
            f"FROM {_BNX}.nexus_all_test_results_dim WHERE batchid = '{safe}' "
            "GROUP BY paramlistid, s_datasetstatus ORDER BY paramlistid"),
        "qa_results": f"SELECT * FROM {_BPS}.batch_tracker_qa_results WHERE nexus_batch_id = '{safe}'",
        "genealogy": f"SELECT * FROM {_BNX}.nexus_batch_genealogy_dim WHERE s_batchid = '{safe}'",
    }
    out: dict[str, Any] = {"ok": True, "batch_id": bid}
    conn = _connect()
    try:
        for key, q in queries.items():
            try:
                out[key] = _records(pd.read_sql(q, conn))
            except Exception as e:  # noqa: BLE001
                out[key] = []
                out.setdefault("errors", {})[key] = str(e)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    out["counts"] = {k: len(out.get(k) or []) for k in
                     ("batch_details", "samples", "test_results",
                      "qa_results", "genealogy")}
    return out


@functools.lru_cache(maxsize=128)
def formula_composition(batch_id: str) -> dict[str, Any]:
    """Formula/ingredient breakdown for a BatchID, bridging Nexus -> Enovia PLM.

    Nexus batch -> prod_id -> Enovia reference key -> formulation_part +
    formula_ingredient rows (with raw-material/formulation-part titles). Cached.
    Enovia tables live in cdl_stc_prod.silver_enovia_plm.
    """
    bid = str(batch_id or "").strip()
    if not bid:
        return {"ok": False, "error": "No batch id provided."}
    safe = bid.replace("'", "''")
    enovia = "cdl_stc_prod.silver_enovia_plm"
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT s_batchid, batchdesc, prod_id, batchstatus, batchtype "
                    f"FROM {_BNX}.nexus_batch_dim WHERE s_batchid = '{safe}'")
        batch = cur.fetchone()
        if not batch:
            return {"ok": False, "error": f"No Nexus batch found for {bid}."}
        prod_id = str(batch[2] or "")
        psafe = prod_id.replace("'", "''")
        cur.execute(f"SELECT s_productid, productdesc, u_referencesystem, "
                    f"u_referencekey FROM {_BNX}.nexus_product_dim "
                    f"WHERE s_productid = '{psafe}'")
        product = cur.fetchone()
        enovia_key = str((product[3] if product and product[3] else prod_id) or "")
        ekey = enovia_key.replace("'", "''")
        formulation = None
        try:
            cur.execute(f"SELECT name, revision, title, description, state "
                        f"FROM {enovia}.formulation_part__t WHERE name = '{ekey}'")
            formulation = cur.fetchone()
        except Exception:  # noqa: BLE001
            formulation = None
        cur.execute(f"""
            WITH rm_desc AS (
                SELECT name, FIRST(title) AS title
                FROM {enovia}.raw_material__t GROUP BY name),
            fp_desc AS (
                SELECT name, FIRST(title) AS title
                FROM {enovia}.formulation_part__t GROUP BY name)
            SELECT fi.to_name AS ingredient_id, fi.to_type AS ingredient_type,
                   COALESCE(rm.title, fp.title, 'N/A') AS ingredient_description,
                   fi.quantity, fi.unit_of_measure,
                   fi.adjustable_ingredient_flag AS adjustable, fi.usage
            FROM {enovia}.formula_ingredient__r_vw fi
            LEFT JOIN rm_desc rm
                ON fi.to_name = rm.name AND fi.to_type = 'Raw Material'
            LEFT JOIN fp_desc fp
                ON fi.to_name = fp.name AND fi.to_type = 'Formulation Part'
            WHERE fi.from_name = '{ekey}' ORDER BY fi.treeorder""")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        cur.close()
    finally:
        try:
            conn.close()
        except Exception:
            pass

    ingredients = []
    for r in rows:
        d = dict(zip(cols, r))
        try:
            q = float(d.get("quantity"))
        except (TypeError, ValueError):
            q = None
        ingredients.append({
            "ingredient_id": str(d.get("ingredient_id") or ""),
            "ingredient_type": str(d.get("ingredient_type") or ""),
            "description": str(d.get("ingredient_description") or ""),
            "quantity": q,
            "unit": str(d.get("unit_of_measure") or ""),
            "adjustable": str(d.get("adjustable") or ""),
            "usage": str(d.get("usage") or ""),
        })
    total = sum(i["quantity"] for i in ingredients
                if isinstance(i["quantity"], (int, float)))
    return {
        "ok": True, "batch_id": bid,
        "product_desc": str(batch[1] or ""), "prod_id": prod_id,
        "enovia_key": enovia_key,
        "formulation": ({"name": formulation[0], "revision": formulation[1],
                         "title": formulation[2], "description": formulation[3],
                         "state": formulation[4]} if formulation else None),
        "ingredients": ingredients, "n_ingredients": len(ingredients),
        "total": round(total, 3),
        "note": ("" if ingredients else
                 f"Batch {bid}: product '{batch[1] or prod_id}' is not linked to an "
                 "Enovia formulation (no formula on file to display)."),
    }


# --------------------------------------------------------------------------- #
# Performance Library -- Batch vs Batch test comparison (Nexus test results)
# --------------------------------------------------------------------------- #
# User-facing test groups -> the raw ``paramlistid`` values recorded in Nexus.
TEST_GROUPS: dict[str, dict[str, Any]] = {
    "sacs_dry": {"label": "SACS (Dry)",
                 "paramlistids": ["ST SACS - Dry", "PTL DOC-0381411 Dry SACS"],
                 "lower_better": True},
    "sacs_wet": {"label": "SACS (Wet)",
                 "paramlistids": ["ST SACS - Wet", "PTL DOC-0381411 Wet SACS"],
                 "lower_better": True},
    "drf": {"label": "DRF (Rinse Friction / Wet Feel)",
            "paramlistids": ["DRF - Summary Calculations",
                             "DRF - Sample Replicate Calculations"],
            "lower_better": True},
    "iff": {"label": "IFF (Inter-Fiber Friction)",
            "paramlistids": ["IFF", "Texture Analyzer - IFF"],
            "lower_better": True},
    "ils": {"label": "ILS (Sensory)",
            "paramlistids": ["ST In Lab Screening (ILS) v1"],
            "lower_better": False},
    "si_depo": {"label": "Silicone deposition",
                "paramlistids": ["PTL MBC 95556956 Si Depo"],
                "lower_better": False},
    "faalc_depo": {"label": "Fatty alcohol deposition",
                   "paramlistids": ["PTL MBC 95523603 Fa Alc Depo"],
                   "lower_better": False},
}


def _sql_in(values: list[str]) -> str:
    """Build a safe quoted ``IN`` list from strings (single-quotes escaped)."""
    return "', '".join(str(v).replace("'", "''") for v in values)


def search_batches(term: str, limit: int = 25) -> list[dict[str, Any]]:
    """Type-ahead search over Nexus batches by id or description.

    Multi-word terms are AND-ed across the description, so "GH150 LAPB Dex-K"
    matches batches whose batchdesc contains all three tokens.
    """
    t = str(term or "").strip()
    if len(t) < 2:
        return []

    def _esc(s: str) -> str:
        return s.replace("'", "''").replace("%", r"\%").replace("_", r"\_")

    lim = max(1, min(int(limit or 25), 100))
    words = [w for w in t.split() if w]
    if len(words) > 1:
        and_desc = " AND ".join(f"batchdesc ILIKE '%{_esc(w)}%'" for w in words)
        where = f"({and_desc}) OR s_batchid ILIKE '%{_esc(t)}%'"
    else:
        safe = _esc(t)
        where = f"s_batchid ILIKE '%{safe}%' OR batchdesc ILIKE '%{safe}%'"
    query = f"""
        SELECT s_batchid AS batch_id, batchdesc
        FROM {_BNX}.nexus_batch_dim
        WHERE {where}
        ORDER BY s_batchid
        LIMIT {lim}
    """
    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    rows = _records(df)
    return [{"batch_id": str(r.get("batch_id") or ""),
             "batchdesc": str(r.get("batchdesc") or "")} for r in rows]


def batch_comparison(batch_ids: list[str],
                     test_groups: list[str]) -> dict[str, Any]:
    """Average each test parameter per batch for the chosen test groups.

    Returns ``{ok, rows, batches, test_types}`` where every row is one
    (batch, test_type, parameter) aggregate with avg / stddev / n_replicates.
    """
    ids = [str(b).strip() for b in (batch_ids or []) if str(b).strip()]
    ids = list(dict.fromkeys(ids))  # de-dup, keep order
    if not ids:
        return {"ok": False, "error": "Select at least one Batch ID."}
    groups = [g for g in (test_groups or []) if g in TEST_GROUPS]
    if not groups:
        return {"ok": False, "error": "Select at least one test type."}

    paramlistids: list[str] = []
    for g in groups:
        paramlistids.extend(TEST_GROUPS[g]["paramlistids"])
    paramlistids = list(dict.fromkeys(paramlistids))

    query = f"""
        SELECT b.s_batchid           AS batch_id,
               b.batchdesc           AS batchdesc,
               tr.paramlistid        AS test_type,
               tr.paramid            AS parameter,
               AVG(tr.enteredvalue)  AS avg_value,
               STDDEV(tr.enteredvalue) AS std_dev,
               COUNT(*)              AS n_replicates
        FROM {_BNX}.nexus_all_test_results_dim tr
        JOIN {_BNX}.nexus_batch_dim b ON tr.batchid = b.s_batchid
        WHERE b.s_batchid IN ('{_sql_in(ids)}')
          AND tr.paramlistid IN ('{_sql_in(paramlistids)}')
          AND tr.enteredvalue IS NOT NULL
        GROUP BY b.s_batchid, b.batchdesc, tr.paramlistid, tr.paramid
        ORDER BY tr.paramlistid, tr.paramid, b.s_batchid
    """
    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    rows: list[dict[str, Any]] = []
    for r in _records(df):
        def _num(v):
            try:
                return None if v is None or v == "" else round(float(v), 4)
            except (TypeError, ValueError):
                return None
        rows.append({
            "batch_id": str(r.get("batch_id") or ""),
            "batchdesc": str(r.get("batchdesc") or ""),
            "test_type": str(r.get("test_type") or ""),
            "parameter": str(r.get("parameter") or ""),
            "avg_value": _num(r.get("avg_value")),
            "std_dev": _num(r.get("std_dev")),
            "n_replicates": int(r.get("n_replicates") or 0),
        })

    # Batches that actually returned data, in the user's requested order.
    found = {r["batch_id"]: r["batchdesc"] for r in rows}
    batches = [{"batch_id": b, "batchdesc": found.get(b, "")}
               for b in ids if b in found]
    test_types = list(dict.fromkeys(r["test_type"] for r in rows))
    return {"ok": True, "rows": rows, "batches": batches,
            "test_types": test_types,
            "requested_batches": ids, "groups": groups}


# --------------------------------------------------------------------------- #
# Performance Library -- Ingredient / Chassis / Request comparison modes
# --------------------------------------------------------------------------- #
_ENOVIA = "cdl_stc_prod.silver_enovia_plm"

# Chassis families derived from batch-description patterns (LIKE, case-insens).
CHASSIS_PATTERNS: dict[str, dict[str, Any]] = {
    "eed0": {"label": "EED0 (SLS/AOS/CAPB)", "like": ["%EED0%"]},
    "ddu0_apg": {"label": "DDU0 + APG", "like": ["%DDU0%APG%"]},
    "ddu0_lapb": {"label": "DDU0 + LAPB", "like": ["%DDU0%LAPB%"]},
    "bc128": {"label": "BC128", "like": ["%BC128%"]},
    "bc185": {"label": "BC185", "like": ["%BC185%"]},
    "gh150": {"label": "GH150", "like": ["%GH150%"]},
}


def _num(v):
    try:
        return None if v is None or v == "" else round(float(v), 4)
    except (TypeError, ValueError):
        return None


def _paramlistids(test_groups: list[str]) -> tuple[list[str], list[str]]:
    """Return (valid group keys, expanded paramlistid list) for the request."""
    groups = [g for g in (test_groups or []) if g in TEST_GROUPS]
    pls: list[str] = []
    for g in groups:
        pls.extend(TEST_GROUPS[g]["paramlistids"])
    return groups, list(dict.fromkeys(pls))


def search_ingredients(term: str, limit: int = 25) -> list[dict[str, Any]]:
    """Type-ahead over Enovia raw materials by GCAS code or title."""
    t = str(term or "").strip()
    if len(t) < 2:
        return []
    safe = t.replace("'", "''").replace("%", r"\%").replace("_", r"\_")
    lim = max(1, min(int(limit or 25), 100))
    query = f"""
        SELECT name, title FROM (
            SELECT name, FIRST(title) AS title
            FROM {_ENOVIA}.raw_material__t GROUP BY name)
        WHERE name ILIKE '%{safe}%' OR title ILIKE '%{safe}%'
        ORDER BY name LIMIT {lim}
    """
    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return [{"gcas": str(r.get("name") or ""), "title": str(r.get("title") or "")}
            for r in _records(df)]


def search_requests(term: str, limit: int = 25) -> list[dict[str, Any]]:
    """Type-ahead over Nexus requests by request id."""
    t = str(term or "").strip()
    if len(t) < 2:
        return []
    safe = t.replace("'", "''").replace("%", r"\%").replace("_", r"\_")
    lim = max(1, min(int(limit or 25), 100))
    query = f"""
        SELECT s_requestid, d_requester, requeststatus, u_departmentid
        FROM {_BNX}.nexus_requests
        WHERE s_requestid ILIKE '%{safe}%'
        ORDER BY s_requestid DESC LIMIT {lim}
    """
    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return [{"request_id": str(r.get("s_requestid") or ""),
             "requester": str(r.get("d_requester") or ""),
             "status": str(r.get("requeststatus") or ""),
             "department": str(r.get("u_departmentid") or "")}
            for r in _records(df)]


def ingredient_comparison(gcas_list: list[str],
                          test_groups: list[str]) -> dict[str, Any]:
    """Average performance across ALL formulations containing each ingredient."""
    ids = list(dict.fromkeys(str(g).strip() for g in (gcas_list or []) if str(g).strip()))
    if not ids:
        return {"ok": False, "error": "Select at least one ingredient."}
    groups, pls = _paramlistids(test_groups)
    if not pls:
        return {"ok": False, "error": "Select at least one test type."}
    query = f"""
        SELECT fi.to_name            AS group_id,
               rm.title              AS group_label,
               tr.paramlistid        AS test_type,
               tr.paramid            AS parameter,
               AVG(tr.enteredvalue)  AS avg_value,
               STDDEV(tr.enteredvalue) AS std_dev,
               COUNT(DISTINCT b.s_batchid) AS n_batches,
               COUNT(*)              AS n_datapoints
        FROM {_BNX}.nexus_all_test_results_dim tr
        JOIN {_BNX}.nexus_batch_dim b ON tr.batchid = b.s_batchid
        JOIN {_ENOVIA}.formula_ingredient__r_vw fi ON b.prod_id = fi.from_name
        JOIN (SELECT name, FIRST(title) AS title
              FROM {_ENOVIA}.raw_material__t GROUP BY name) rm
          ON fi.to_name = rm.name
        WHERE fi.to_name IN ('{_sql_in(ids)}')
          AND fi.to_type = 'Raw Material'
          AND fi.quantity > 0
          AND tr.paramlistid IN ('{_sql_in(pls)}')
          AND tr.enteredvalue IS NOT NULL
        GROUP BY fi.to_name, rm.title, tr.paramlistid, tr.paramid
        ORDER BY tr.paramlistid, tr.paramid, fi.to_name
    """
    return _run_group_comparison(query, "ingredient", groups,
                                 ordered_ids=ids)


def chassis_comparison(chassis_keys: list[str], test_groups: list[str],
                       ingredient_gcas: str | None = None,
                       custom_patterns: list[str] | None = None) -> dict[str, Any]:
    """Average performance per chassis family (from batch-description patterns)."""
    groups, pls = _paramlistids(test_groups)
    if not pls:
        return {"ok": False, "error": "Select at least one test type."}

    conds: list[tuple[str, str]] = []  # (label, sql_condition)
    for key in (chassis_keys or []):
        spec = CHASSIS_PATTERNS.get(key)
        if not spec:
            continue
        ors = " OR ".join(f"b.batchdesc LIKE '{p}'" for p in spec["like"])
        conds.append((spec["label"], f"({ors})"))
    for pat in (custom_patterns or []):
        p = str(pat or "").strip()
        if not p:
            continue
        safe = p.replace("'", "''")
        conds.append((f"Custom: {p}", f"b.batchdesc RLIKE '{safe}'"))
    if not conds:
        return {"ok": False, "error": "Select at least one chassis (or add a custom pattern)."}

    case_sql = "CASE " + " ".join(
        f"WHEN {cond} THEN '{label.replace(chr(39), chr(39) * 2)}'"
        for label, cond in conds) + " ELSE 'Other' END"
    match_sql = "(" + " OR ".join(cond for _, cond in conds) + ")"

    ingr_join = ingr_where = ""
    if ingredient_gcas and str(ingredient_gcas).strip():
        g = str(ingredient_gcas).strip().replace("'", "''")
        ingr_where = (f" AND EXISTS (SELECT 1 FROM {_ENOVIA}.formula_ingredient__r_vw fi "
                      f"WHERE fi.from_name = b.prod_id AND fi.to_name = '{g}' "
                      f"AND fi.to_type = 'Raw Material' AND fi.quantity > 0)")

    query = f"""
        SELECT {case_sql}       AS group_label,
               {case_sql}       AS group_id,
               tr.paramlistid   AS test_type,
               tr.paramid       AS parameter,
               AVG(tr.enteredvalue)  AS avg_value,
               STDDEV(tr.enteredvalue) AS std_dev,
               COUNT(DISTINCT b.s_batchid) AS n_batches,
               COUNT(*)         AS n_datapoints
        FROM {_BNX}.nexus_all_test_results_dim tr
        JOIN {_BNX}.nexus_batch_dim b ON tr.batchid = b.s_batchid{ingr_join}
        WHERE {match_sql}
          AND tr.paramlistid IN ('{_sql_in(pls)}')
          AND tr.enteredvalue IS NOT NULL{ingr_where}
        GROUP BY group_label, group_id, tr.paramlistid, tr.paramid
        ORDER BY tr.paramlistid, tr.paramid, group_label
    """
    ordered = [CHASSIS_PATTERNS[k]["label"] for k in (chassis_keys or [])
               if k in CHASSIS_PATTERNS] + [f"Custom: {p}" for p in (custom_patterns or [])]
    return _run_group_comparison(query, "chassis", groups, ordered_ids=ordered)


def _run_group_comparison(query: str, mode: str, groups: list[str],
                          ordered_ids: list[str]) -> dict[str, Any]:
    """Shared executor for ingredient/chassis grouped comparisons."""
    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    rows: list[dict[str, Any]] = []
    for r in _records(df):
        rows.append({
            "group_id": str(r.get("group_id") or ""),
            "group_label": str(r.get("group_label") or ""),
            "test_type": str(r.get("test_type") or ""),
            "parameter": str(r.get("parameter") or ""),
            "avg_value": _num(r.get("avg_value")),
            "std_dev": _num(r.get("std_dev")),
            "n_batches": int(r.get("n_batches") or 0),
            "n_datapoints": int(r.get("n_datapoints") or 0),
        })
    label_by_id: dict[str, str] = {}
    nb_by_id: dict[str, int] = {}
    for r in rows:
        label_by_id.setdefault(r["group_id"], r["group_label"])
        nb_by_id[r["group_id"]] = max(nb_by_id.get(r["group_id"], 0), r["n_batches"])
    present = [g for g in ordered_ids if g in label_by_id]
    present += [g for g in label_by_id if g not in present]  # any extras
    group_list = [{"id": g, "label": label_by_id.get(g, g),
                   "n_batches": nb_by_id.get(g, 0)} for g in present]
    test_types = list(dict.fromkeys(r["test_type"] for r in rows))
    return {"ok": True, "mode": mode, "rows": rows, "groups": group_list,
            "test_types": test_types}


def request_results(request_ids: list[str],
                    test_groups: list[str]) -> dict[str, Any]:
    """All batches + test results under one or more Nexus request ids."""
    ids = list(dict.fromkeys(str(r).strip() for r in (request_ids or []) if str(r).strip()))
    if not ids:
        return {"ok": False, "error": "Select at least one request id."}
    _groups, pls = _paramlistids(test_groups)
    if not pls:
        return {"ok": False, "error": "Select at least one test type."}
    query = f"""
        WITH req_batches AS (
            SELECT DISTINCT r.s_requestid, r.d_requester, r.requeststatus,
                   r.u_departmentid, s.batchid
            FROM {_BNX}.nexus_requests r
            JOIN {_BNX}.nexus_sample_dim s ON r.s_requestid = s.requestid
            WHERE r.s_requestid IN ('{_sql_in(ids)}'))
        SELECT rb.s_requestid    AS request_id,
               rb.d_requester    AS requester,
               rb.requeststatus  AS status,
               rb.u_departmentid AS department,
               rb.batchid        AS batch_id,
               b.batchdesc       AS batchdesc,
               b.prod_id         AS prod_id,
               tr.paramlistid    AS test_type,
               tr.paramid        AS parameter,
               AVG(tr.enteredvalue) AS avg_value,
               STDDEV(tr.enteredvalue) AS std_dev,
               COUNT(*)          AS n_replicates
        FROM req_batches rb
        JOIN {_BNX}.nexus_batch_dim b ON rb.batchid = b.s_batchid
        JOIN {_BNX}.nexus_all_test_results_dim tr ON tr.batchid = rb.batchid
        WHERE tr.paramlistid IN ('{_sql_in(pls)}')
          AND tr.enteredvalue IS NOT NULL
        GROUP BY rb.s_requestid, rb.d_requester, rb.requeststatus, rb.u_departmentid,
                 rb.batchid, b.batchdesc, b.prod_id, tr.paramlistid, tr.paramid
        ORDER BY rb.s_requestid, b.batchdesc, tr.paramlistid, tr.paramid
    """
    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    rows = []
    for r in _records(df):
        rows.append({
            "request_id": str(r.get("request_id") or ""),
            "requester": str(r.get("requester") or ""),
            "status": str(r.get("status") or ""),
            "department": str(r.get("department") or ""),
            "batch_id": str(r.get("batch_id") or ""),
            "batchdesc": str(r.get("batchdesc") or ""),
            "prod_id": str(r.get("prod_id") or ""),
            "test_type": str(r.get("test_type") or ""),
            "parameter": str(r.get("parameter") or ""),
            "avg_value": _num(r.get("avg_value")),
            "std_dev": _num(r.get("std_dev")),
            "n_replicates": int(r.get("n_replicates") or 0),
        })
    return {"ok": True, "rows": rows, "requested": ids}


# --------------------------------------------------------------------------- #
# Performance Library -- Correlation engine (instrument vs sensory, X vs Y)
# --------------------------------------------------------------------------- #
# Test types a user can put on either axis of a correlation.
CORR_TEST_TYPES: list[tuple[str, str]] = [
    ("ST SACS - Dry", "SACS Dry"),
    ("ST SACS - Wet", "SACS Wet"),
    ("DRF - Summary Calculations", "DRF (rinse friction / wet feel)"),
    ("Texture Analyzer - IFF", "IFF"),
    ("ST In Lab Screening (ILS) v1", "ILS (sensory)"),
    ("PTL MBC 95556956 Si Depo", "Silicone deposition"),
    ("PTL MBC 95523603 Fa Alc Depo", "Fatty alcohol deposition"),
]

# Curated correlation pairs shown as one-click cards (verified params exist).
CORR_PRESETS: list[dict[str, str]] = [
    {"label": "SACS Dry Friction vs ILS Clean Feel",
     "x_test_type": "ST SACS - Dry", "x_param": "Friction",
     "y_test_type": "ST In Lab Screening (ILS) v1", "y_param": "Clean Feel ILS"},
    {"label": "SACS Wet Detangling vs ILS First Detangling Stroke",
     "x_test_type": "ST SACS - Wet", "x_param": "Detangling",
     "y_test_type": "ST In Lab Screening (ILS) v1", "y_param": "First Detangling Stroke ILS"},
    {"label": "Silicone on Hair vs SACS Dry Friction",
     "x_test_type": "PTL MBC 95556956 Si Depo", "x_param": "Silicone on Hair",
     "y_test_type": "ST SACS - Dry", "y_param": "Friction"},
    {"label": "SACS Dry Friction vs SACS Dry Resistance at Tips",
     "x_test_type": "ST SACS - Dry", "x_param": "Friction",
     "y_test_type": "ST SACS - Dry", "y_param": "Resistance at Tips"},
]


def list_parameters(test_type: str, limit: int = 60) -> list[str]:
    """Distinct numeric parameters recorded for a paramlistid (for dropdowns)."""
    t = str(test_type or "").strip()
    if not t:
        return []
    safe = t.replace("'", "''")
    query = f"""
        SELECT paramid, COUNT(*) AS n
        FROM {_BNX}.nexus_all_test_results_dim
        WHERE paramlistid = '{safe}' AND enteredvalue IS NOT NULL
        GROUP BY paramid ORDER BY n DESC LIMIT {max(1, min(int(limit or 60), 200))}
    """
    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return [str(r.get("paramid") or "") for r in _records(df)
            if str(r.get("paramid") or "").strip()]


def _chassis_of(desc: str) -> str:
    """Best-match chassis family label for a batch description (else 'Other')."""
    d = desc or ""
    for spec in CHASSIS_PATTERNS.values():
        for pat in spec["like"]:
            parts = [p for p in pat.split("%") if p]
            if parts and all(p in d for p in parts):
                return spec["label"]
    return "Other"


def _regression(xs: list[float], ys: list[float]) -> dict[str, Any]:
    """Simple linear regression: slope, intercept, r, r^2."""
    n = len(xs)
    if n < 2:
        return {"r2": None, "slope": None, "intercept": None, "correlation": None}
    sx, sy = sum(xs), sum(ys)
    sxx = sum(v * v for v in xs)
    syy = sum(v * v for v in ys)
    sxy = sum(xs[i] * ys[i] for i in range(n))
    denx = n * sxx - sx * sx
    deny = n * syy - sy * sy
    if denx <= 0 or deny <= 0:
        return {"r2": 0.0, "slope": 0.0, "intercept": round(sy / n, 5), "correlation": 0.0}
    slope = (n * sxy - sx * sy) / denx
    intercept = (sy - slope * sx) / n
    r = (n * sxy - sx * sy) / math.sqrt(denx * deny)
    return {"r2": round(r * r, 4), "slope": round(slope, 5),
            "intercept": round(intercept, 5), "correlation": round(r, 4)}


def ingredient_dose_response(gcas: str, test_groups: list[str],
                             min_pct: float | None = None,
                             max_pct: float | None = None) -> dict[str, Any]:
    """Dose-response: ingredient level (%) vs each performance parameter.

    Every point is one batch: its level of the ingredient (from the Enovia
    formula) against the batch's average value for a test parameter. Points are
    grouped into (test_type, parameter) series, tagged with chassis family, and
    fitted with a linear regression (slope / R^2). This powers plots like
    "DADMAC level (%) vs SACS Dry Friction".
    """
    g = str(gcas or "").strip()
    if not g:
        return {"ok": False, "error": "Select an ingredient (GCAS)."}
    groups, pls = _paramlistids(test_groups)
    if not pls:
        return {"ok": False, "error": "Select at least one test type."}

    conds = [f"fi.to_name = '{g.replace(chr(39), chr(39) * 2)}'",
             "fi.to_type = 'Raw Material'", "fi.quantity > 0",
             f"tr.paramlistid IN ('{_sql_in(pls)}')",
             "tr.enteredvalue IS NOT NULL"]
    if min_pct is not None:
        conds.append(f"fi.quantity >= {float(min_pct)}")
    if max_pct is not None:
        conds.append(f"fi.quantity <= {float(max_pct)}")
    query = f"""
        SELECT fi.quantity          AS ingredient_pct,
               b.s_batchid          AS batch_id,
               b.batchdesc          AS batchdesc,
               tr.paramlistid       AS test_type,
               tr.paramid           AS parameter,
               AVG(tr.enteredvalue) AS avg_value
        FROM {_BNX}.nexus_all_test_results_dim tr
        JOIN {_BNX}.nexus_batch_dim b ON tr.batchid = b.s_batchid
        JOIN {_ENOVIA}.formula_ingredient__r_vw fi ON b.prod_id = fi.from_name
        WHERE {" AND ".join(conds)}
        GROUP BY fi.quantity, b.s_batchid, b.batchdesc, tr.paramlistid, tr.paramid
        ORDER BY tr.paramlistid, tr.paramid, fi.quantity
    """
    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    # readable label + lower_better per paramlistid, from TEST_GROUPS
    gl: dict[str, dict[str, Any]] = {}
    for key in groups:
        spec = TEST_GROUPS[key]
        for pl in spec["paramlistids"]:
            gl[pl] = {"label": spec["label"], "lower_better": spec.get("lower_better")}

    series: dict[tuple, dict[str, Any]] = {}
    for r in _records(df):
        x = _num(r.get("ingredient_pct"))
        y = _num(r.get("avg_value"))
        if x is None or y is None:
            continue
        tt = str(r.get("test_type") or "")
        pm = str(r.get("parameter") or "")
        k = (tt, pm)
        meta = gl.get(tt, {"label": tt, "lower_better": None})
        s = series.setdefault(k, {
            "test_type": tt, "parameter": pm,
            "test_label": meta["label"], "lower_better": meta["lower_better"],
            "points": []})
        s["points"].append({
            "x": x, "y": y,
            "batch_id": str(r.get("batch_id") or ""),
            "batchdesc": str(r.get("batchdesc") or ""),
            "chassis": _chassis_of(str(r.get("batchdesc") or "")),
        })

    out = []
    for s in series.values():
        pts = s["points"]
        reg = _regression([p["x"] for p in pts], [p["y"] for p in pts])
        s["regression"] = reg
        s["n_points"] = len(pts)
        s["x_range"] = [min(p["x"] for p in pts), max(p["x"] for p in pts)]
        out.append(s)
    out.sort(key=lambda s: (-(s["regression"].get("r2") or 0), s["test_label"]))
    return {"ok": True, "gcas": g, "groups": groups, "series": out,
            "n_series": len(out)}


def correlation(x_test_type: str, x_param: str,
                y_test_type: str, y_param: str) -> dict[str, Any]:
    """Per-batch scatter of one parameter vs another, with regression stats.

    Inner-joins batches that have BOTH measurements, so ``n`` is the overlap.
    """
    xt, xp, yt, yp = (str(v or "").strip() for v in
                      (x_test_type, x_param, y_test_type, y_param))
    if not (xt and xp and yt and yp):
        return {"ok": False, "error": "Pick an X and Y test type and parameter."}
    q = lambda s: s.replace("'", "''")  # noqa: E731
    query = f"""
        WITH x_data AS (
            SELECT b.s_batchid, b.batchdesc, b.prod_id, AVG(tr.enteredvalue) AS x_value
            FROM {_BNX}.nexus_all_test_results_dim tr
            JOIN {_BNX}.nexus_batch_dim b ON tr.batchid = b.s_batchid
            WHERE tr.paramlistid = '{q(xt)}' AND tr.paramid = '{q(xp)}'
              AND tr.enteredvalue IS NOT NULL
            GROUP BY b.s_batchid, b.batchdesc, b.prod_id),
        y_data AS (
            SELECT b.s_batchid, AVG(tr.enteredvalue) AS y_value
            FROM {_BNX}.nexus_all_test_results_dim tr
            JOIN {_BNX}.nexus_batch_dim b ON tr.batchid = b.s_batchid
            WHERE tr.paramlistid = '{q(yt)}' AND tr.paramid = '{q(yp)}'
              AND tr.enteredvalue IS NOT NULL
            GROUP BY b.s_batchid)
        SELECT x.s_batchid, x.batchdesc, x.prod_id, x.x_value, y.y_value
        FROM x_data x JOIN y_data y ON x.s_batchid = y.s_batchid
    """
    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    points = []
    for r in _records(df):
        xv, yv = _num(r.get("x_value")), _num(r.get("y_value"))
        if xv is None or yv is None:
            continue
        desc = str(r.get("batchdesc") or "")
        points.append({"batch_id": str(r.get("s_batchid") or ""),
                       "batchdesc": desc, "chassis": _chassis_of(desc),
                       "x": xv, "y": yv})
    stats = _regression([p["x"] for p in points], [p["y"] for p in points])
    return {"ok": True, "points": points, "n": len(points),
            "x_label": f"{xp}  ({xt})", "y_label": f"{yp}  ({yt})", **stats}


# --------------------------------------------------------------------------- #
# Performance Library -- ILS & PTL dashboards (Nexus test results)
# --------------------------------------------------------------------------- #
ILS_PARAMLISTID = "ST In Lab Screening (ILS) v1"
DRF_VARIANTS = ["Liquid Shampoo", "Liquid Conditioner", "Liquid System"]


def _batches_meta(ids: list[str]) -> list[dict[str, Any]]:
    return [{"batch_id": b} for b in ids]


def ils_results(batch_ids: list[str]) -> dict[str, Any]:
    """All ILS sensory data (Preparation / Wet / Dry variants) for batches."""
    ids = list(dict.fromkeys(str(b).strip() for b in (batch_ids or []) if str(b).strip()))
    if not ids:
        return {"ok": False, "error": "Select at least one batch."}
    query = f"""
        SELECT b.s_batchid AS batch_id, b.batchdesc AS batchdesc,
               tr.variantid AS variant, tr.paramid AS parameter,
               AVG(tr.enteredvalue) AS value, MAX(tr.displayvalue) AS display_value
        FROM {_BNX}.nexus_all_test_results_dim tr
        JOIN {_BNX}.nexus_batch_dim b ON tr.batchid = b.s_batchid
        WHERE tr.paramlistid = '{ILS_PARAMLISTID}'
          AND b.s_batchid IN ('{_sql_in(ids)}')
        GROUP BY b.s_batchid, b.batchdesc, tr.variantid, tr.paramid
        ORDER BY b.s_batchid, tr.variantid, tr.paramid
    """
    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    rows, found = [], {}
    for r in _records(df):
        bid = str(r.get("batch_id") or "")
        found.setdefault(bid, str(r.get("batchdesc") or ""))
        rows.append({
            "batch_id": bid, "batchdesc": str(r.get("batchdesc") or ""),
            "variant": str(r.get("variant") or ""),
            "parameter": str(r.get("parameter") or ""),
            "value": _num(r.get("value")),
            "display_value": ("" if r.get("display_value") is None
                              else str(r.get("display_value"))),
        })
    batches = [{"batch_id": b, "batchdesc": found.get(b, "")}
               for b in ids if b in found]
    return {"ok": True, "rows": rows, "batches": batches}


def sacs_results(batch_ids: list[str]) -> dict[str, Any]:
    """Replicate-level SACS Dry/Wet values (Friction/Detangling/Resistance)."""
    ids = list(dict.fromkeys(str(b).strip() for b in (batch_ids or []) if str(b).strip()))
    if not ids:
        return {"ok": False, "error": "Select at least one batch."}
    query = f"""
        SELECT b.s_batchid AS batch_id, b.batchdesc AS batchdesc,
               tr.paramlistid AS test_type, tr.paramid AS parameter,
               tr.enteredvalue AS value
        FROM {_BNX}.nexus_all_test_results_dim tr
        JOIN {_BNX}.nexus_batch_dim b ON tr.batchid = b.s_batchid
        WHERE tr.paramlistid IN ('ST SACS - Dry', 'ST SACS - Wet')
          AND tr.paramid IN ('Friction', 'Detangling', 'Resistance at Tips')
          AND tr.enteredvalue IS NOT NULL
          AND b.s_batchid IN ('{_sql_in(ids)}')
        ORDER BY b.s_batchid, tr.paramlistid, tr.paramid
    """
    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    rows, found = [], {}
    for r in _records(df):
        bid = str(r.get("batch_id") or "")
        found.setdefault(bid, str(r.get("batchdesc") or ""))
        tt = "Dry" if "Dry" in str(r.get("test_type") or "") else "Wet"
        v = _num(r.get("value"))
        if v is None:
            continue
        rows.append({"batch_id": bid, "test_type": tt,
                     "parameter": str(r.get("parameter") or ""), "value": v})
    batches = [{"batch_id": b, "batchdesc": found.get(b, "")}
               for b in ids if b in found]
    return {"ok": True, "rows": rows, "batches": batches}


def drf_profile(batch_ids: list[str],
                variant: str = "Liquid Shampoo") -> dict[str, Any]:
    """DRF summary stats (rinse friction / wet feel) per batch for a variant."""
    ids = list(dict.fromkeys(str(b).strip() for b in (batch_ids or []) if str(b).strip()))
    if not ids:
        return {"ok": False, "error": "Select at least one batch."}
    v = variant if variant in DRF_VARIANTS else "Liquid Shampoo"
    vsafe = v.replace("'", "''")
    query = f"""
        SELECT b.s_batchid AS batch_id, b.batchdesc AS batchdesc,
               tr.paramid AS parameter,
               AVG(tr.enteredvalue) AS avg_value, STDDEV(tr.enteredvalue) AS std_dev,
               COUNT(*) AS n_replicates
        FROM {_BNX}.nexus_all_test_results_dim tr
        JOIN {_BNX}.nexus_batch_dim b ON tr.batchid = b.s_batchid
        WHERE tr.paramlistid = 'DRF - Summary Calculations'
          AND tr.variantid = '{vsafe}'
          AND tr.enteredvalue IS NOT NULL
          AND b.s_batchid IN ('{_sql_in(ids)}')
        GROUP BY b.s_batchid, b.batchdesc, tr.paramid
        ORDER BY b.s_batchid, tr.paramid
    """
    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    rows, found = [], {}
    for r in _records(df):
        bid = str(r.get("batch_id") or "")
        found.setdefault(bid, str(r.get("batchdesc") or ""))
        rows.append({"batch_id": bid, "parameter": str(r.get("parameter") or ""),
                     "avg_value": _num(r.get("avg_value")),
                     "std_dev": _num(r.get("std_dev")),
                     "n_replicates": int(r.get("n_replicates") or 0)})
    batches = [{"batch_id": b, "batchdesc": found.get(b, "")}
               for b in ids if b in found]
    return {"ok": True, "rows": rows, "batches": batches, "variant": v}


def iff_results(batch_ids: list[str]) -> dict[str, Any]:
    """Inter-fiber friction (Texture Analyzer) averages per batch."""
    ids = list(dict.fromkeys(str(b).strip() for b in (batch_ids or []) if str(b).strip()))
    if not ids:
        return {"ok": False, "error": "Select at least one batch."}
    query = f"""
        SELECT b.s_batchid AS batch_id, b.batchdesc AS batchdesc,
               tr.paramid AS parameter,
               AVG(tr.enteredvalue) AS avg_value, STDDEV(tr.enteredvalue) AS std_dev,
               COUNT(*) AS n_replicates
        FROM {_BNX}.nexus_all_test_results_dim tr
        JOIN {_BNX}.nexus_batch_dim b ON tr.batchid = b.s_batchid
        WHERE tr.paramlistid = 'Texture Analyzer - IFF'
          AND tr.enteredvalue IS NOT NULL
          AND b.s_batchid IN ('{_sql_in(ids)}')
        GROUP BY b.s_batchid, b.batchdesc, tr.paramid
        ORDER BY b.s_batchid, tr.paramid
    """
    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    rows, found = [], {}
    for r in _records(df):
        bid = str(r.get("batch_id") or "")
        found.setdefault(bid, str(r.get("batchdesc") or ""))
        rows.append({"batch_id": bid, "parameter": str(r.get("parameter") or ""),
                     "avg_value": _num(r.get("avg_value")),
                     "std_dev": _num(r.get("std_dev")),
                     "n_replicates": int(r.get("n_replicates") or 0)})
    batches = [{"batch_id": b, "batchdesc": found.get(b, "")}
               for b in ids if b in found]
    return {"ok": True, "rows": rows, "batches": batches}


# --------------------------------------------------------------------------- #
# Sample Lookup -- by Nexus Request / Worksheet (multi-sample, with test badges)
# --------------------------------------------------------------------------- #
# paramlistid -> friendly test badge for the "what data exists" chips.
_TEST_BADGES: list[tuple[tuple[str, ...], str]] = [
    (("ST SACS - Dry", "PTL DOC-0381411 Dry SACS"), "SACS Dry"),
    (("ST SACS - Wet", "PTL DOC-0381411 Wet SACS"), "SACS Wet"),
    (("DRF - Summary Calculations", "DRF - Sample Replicate Calculations",
      "DRF - Raw Data", "DRF"), "DRF"),
    (("Texture Analyzer - IFF", "IFF"), "IFF"),
    (("ST In Lab Screening (ILS) v1",), "ILS"),
    (("PTL MBC 95556956 Si Depo",), "Si depo"),
    (("PTL MBC 95523603 Fa Alc Depo",), "FaAlc depo"),
]


def _badges_for(paramlistids: set[str]) -> list[str]:
    return [label for keys, label in _TEST_BADGES
            if paramlistids.intersection(keys)]


def _tests_by_batch(batch_ids: list[str]) -> dict[str, list[str]]:
    """Map each batch id -> list of friendly test badges that have numeric data."""
    ids = list(dict.fromkeys(b for b in batch_ids if b))
    if not ids:
        return {}
    query = f"""
        SELECT batchid, paramlistid
        FROM {_BNX}.nexus_all_test_results_dim
        WHERE batchid IN ('{_sql_in(ids)}') AND enteredvalue IS NOT NULL
        GROUP BY batchid, paramlistid
    """
    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    acc: dict[str, set[str]] = {}
    for r in _records(df):
        acc.setdefault(str(r.get("batchid") or ""), set()).add(
            str(r.get("paramlistid") or ""))
    return {b: _badges_for(v) for b, v in acc.items()}


def detect_tests(batch_ids: list[str]) -> dict[str, Any]:
    return {"ok": True, "tests": _tests_by_batch(batch_ids or [])}


def search_worksheets(term: str, limit: int = 25) -> list[dict[str, Any]]:
    """Type-ahead over Nexus worksheets by id or description."""
    t = str(term or "").strip()
    if len(t) < 2:
        return []
    safe = t.replace("'", "''").replace("%", r"\%").replace("_", r"\_")
    lim = max(1, min(int(limit or 25), 100))
    query = f"""
        SELECT worksheetid, FIRST(worksheetdesc) AS wdesc
        FROM {_BNX}.nexus_worksheet_dim
        WHERE worksheetid ILIKE '%{safe}%' OR worksheetdesc ILIKE '%{safe}%'
        GROUP BY worksheetid ORDER BY worksheetid DESC LIMIT {lim}
    """
    conn = _connect()
    try:
        df = pd.read_sql(query, conn)
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return [{"worksheet_id": str(r.get("worksheetid") or ""),
             "desc": str(r.get("wdesc") or "")} for r in _records(df)]


def lookup_request(request_id: str) -> dict[str, Any]:
    """Request header + all samples/batches, with per-batch test-coverage badges."""
    rid = str(request_id or "").strip()
    if not rid:
        return {"ok": False, "error": "Enter a request id (R-...)."}
    safe = rid.replace("'", "''")
    conn = _connect()
    try:
        hdr = _records(pd.read_sql(
            f"""SELECT s_requestid, requestdesc, d_requester, requeststatus,
                       u_departmentid, createdt, itemcount
                FROM {_BNX}.nexus_requests WHERE s_requestid = '{safe}' LIMIT 1""", conn))
        samples = _records(pd.read_sql(
            f"""SELECT s.s_sampleid, s.sampledesc, s.samplestatus, s.batchid,
                       b.batchdesc, b.prod_id
                FROM {_BNX}.nexus_sample_dim s
                LEFT JOIN {_BNX}.nexus_batch_dim b ON s.batchid = b.s_batchid
                WHERE s.requestid = '{safe}' ORDER BY s.s_sampleid""", conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if not hdr and not samples:
        return {"ok": False, "error": f"No request found for {rid}."}
    h = hdr[0] if hdr else {}
    bids = [str(s.get("batchid") or "") for s in samples if s.get("batchid")]
    tests = _tests_by_batch(bids)
    rows = []
    for s in samples:
        bid = str(s.get("batchid") or "")
        rows.append({
            "sample_id": str(s.get("s_sampleid") or ""),
            "sample_desc": str(s.get("sampledesc") or ""),
            "sample_status": str(s.get("samplestatus") or ""),
            "batch_id": bid, "batchdesc": str(s.get("batchdesc") or ""),
            "badges": tests.get(bid, []),
        })
    return {"ok": True, "mode": "request",
            "header": {"id": rid, "desc": str(h.get("requestdesc") or ""),
                       "requester": str(h.get("d_requester") or ""),
                       "status": str(h.get("requeststatus") or ""),
                       "department": str(h.get("u_departmentid") or ""),
                       "created": str(h.get("createdt") or "")[:10],
                       "itemcount": h.get("itemcount")},
            "samples": rows}


def lookup_worksheet(ws_id: str) -> dict[str, Any]:
    """Worksheet header + all batches (via test results), with test-coverage badges."""
    wid = str(ws_id or "").strip()
    if not wid:
        return {"ok": False, "error": "Enter a worksheet id (WS-...)."}
    safe = wid.replace("'", "''")
    conn = _connect()
    try:
        hdr = _records(pd.read_sql(
            f"""SELECT worksheetid, FIRST(worksheetdesc) AS wdesc,
                       FIRST(d_ws_creator) AS creator, FIRST(worksheetstatus) AS wstatus,
                       FIRST(worksheet_experiment_type) AS exp_type,
                       FIRST(worksheet_type_of_work) AS tow,
                       FIRST(worksheet_location) AS loc,
                       FIRST(worksheet_business_unit) AS bu
                FROM {_BNX}.nexus_worksheet_dim WHERE worksheetid = '{safe}'
                GROUP BY worksheetid""", conn))
        batches = _records(pd.read_sql(
            f"""SELECT tr.batchid, FIRST(b.batchdesc) AS batchdesc,
                       COUNT(DISTINCT tr.paramlistid) AS n_types, COUNT(*) AS n_results
                FROM {_BNX}.nexus_worksheet_dim ws
                JOIN {_BNX}.nexus_all_test_results_dim tr ON ws.d_ws_version = tr.d_ws_version
                LEFT JOIN {_BNX}.nexus_batch_dim b ON tr.batchid = b.s_batchid
                WHERE ws.worksheetid = '{safe}' AND tr.enteredvalue IS NOT NULL
                GROUP BY tr.batchid ORDER BY tr.batchid""", conn))
    finally:
        try:
            conn.close()
        except Exception:
            pass
    if not hdr and not batches:
        return {"ok": False,
                "error": f"No worksheet found for {wid} (or it has no numeric results)."}
    h = hdr[0] if hdr else {}
    bids = [str(b.get("batchid") or "") for b in batches if b.get("batchid")]
    tests = _tests_by_batch(bids)
    rows = []
    for b in batches:
        bid = str(b.get("batchid") or "")
        rows.append({"batch_id": bid, "batchdesc": str(b.get("batchdesc") or ""),
                     "n_types": int(b.get("n_types") or 0),
                     "n_results": int(b.get("n_results") or 0),
                     "badges": tests.get(bid, [])})
    return {"ok": True, "mode": "worksheet",
            "header": {"id": wid, "desc": str(h.get("wdesc") or ""),
                       "creator": str(h.get("creator") or ""),
                       "status": str(h.get("wstatus") or ""),
                       "exp_type": str(h.get("exp_type") or ""),
                       "tow": str(h.get("tow") or ""),
                       "loc": str(h.get("loc") or ""), "bu": str(h.get("bu") or "")},
            "batches": rows}
