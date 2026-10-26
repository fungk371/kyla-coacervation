"""
Coacervation analysis web app.

A focused Flask app for the coacervation workflow:
  - Load a kinetic plate .txt (from raw_data/ or uploaded)
  - Auto-parse and map wells to concentration for both troughs (samples)
  - Absorbance-vs-concentration plot with best-fit curve
  - User-selectable dilution window -> highlighted AUC
  - Timepoints read dynamically from the file
  - Config-driven submission metadata with required-field validation
  - Export critical parameters in flex-driver / nexus_xy format

Run:  python coacervation_app.py   ->  http://localhost:5001
"""

from __future__ import annotations

import base64
import functools
import io
import json
import os
import re
import sqlite3
import tempfile
import traceback
import datetime
from pathlib import Path

from coacervation_storage import DATA_DIR, install_storage, prepare_runtime

prepare_runtime()

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from flask import Flask, jsonify, render_template, request, send_file  # noqa: E402
from werkzeug.utils import secure_filename  # noqa: E402

from coacervation_parser import (  # noqa: E402
    parse_kinetic_plate_file,
    parse_plate1_sheet,
    find_kinetic_sheet,
    parse_plate1_sample_info,
)
from coacervation_layout import annotate_concentration  # noqa: E402
from coacervation_sampleinfo import list_run_sheets, parse_run_sheet  # noqa: E402
from coacervation_plotting import (  # noqa: E402
    plot_coacervation,
    plot_time_course,
    plot_3d_surface,
    plot_comparison,
    plot_small_multiples,
    plot_deposition,
)
from coacervation_analysis import (  # noqa: E402
    transmittance_to_absorbance,
    compute_auc,
    assess_noise,
    compute_fingerprint,
    dilution_ratio,
)
from coacervation_properties import (  # noqa: E402
    load_properties,
    polymer_key,
    canon_key,
)
from coacervation_config import (  # noqa: E402
    METADATA_FIELDS,
    NEXUS_XY_TARGET,
    SUBMISSIONS_DB,
)
from coacervation_experiment import build_nexus_workbook  # noqa: E402
from coacervation_intake import (  # noqa: E402
    build_intake_template,
    parse_intake_workbook,
    build_intake_store,
    norm_plate,
    plate_code,
    parse_metadata_sheet,
    parse_description,
)
from coacervation_deposition import (  # noqa: E402
    DEFAULT_MODELS,
    predict_best,
    predict_one,
)
import coacervation_blob as cblob  # noqa: E402
import coacervation_nexus as cnx  # noqa: E402
import coacervation_mintel as cmintel  # noqa: E402
import coacervation_composition as ccomp  # noqa: E402
import coacervation_lasentec as clas  # noqa: E402
import coacervation_auc_explorer as auc_x  # noqa: E402
import coacervation_phase as cphase  # noqa: E402
import coacervation_fingerprint_store as cfp  # noqa: E402
import coacervation_perfdata as cperf  # noqa: E402
import coacervation_sample_formula as csf  # noqa: E402

from flask.json.provider import DefaultJSONProvider  # noqa: E402


def _nan_to_none(o):
    if isinstance(o, float) and o != o:
        return None
    if isinstance(o, dict):
        return {k: _nan_to_none(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_nan_to_none(v) for v in o]
    return o


class _SafeJSONProvider(DefaultJSONProvider):
    # Browser JSON.parse rejects NaN; emit null instead.
    def dumps(self, obj, **kwargs):
        return super().dumps(_nan_to_none(obj), **kwargs)


app = Flask(__name__)
app.json = _SafeJSONProvider(app)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024

RAW_DIR = Path("raw_data")
UPLOAD_DIR = Path(tempfile.gettempdir()) / "coac_uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def list_raw_txt() -> list[str]:
    """List selectable sources: raw .txt kinetic files + Sample Info workbook(s).

    Other Excel data files and reference documents in raw_data are hidden from
    the app list (they are not deleted from disk).
    """
    if not RAW_DIR.exists():
        return []
    out = []
    for p in RAW_DIR.iterdir():
        if p.name.startswith("~$") or "%20" in p.name:
            continue
        suffix = p.suffix.lower()
        if suffix == ".txt":
            out.append(p.name)
        elif suffix in (".xlsx", ".xlsm") and (
            "sample info" in p.name.lower() or has_plate1(p)):
            out.append(p.name)
    return sorted(out)


def is_excel(path) -> bool:
    return Path(path).suffix.lower() in (".xlsx", ".xlsm")


@functools.lru_cache(maxsize=256)
def _has_plate1_cached(path_str: str, _mtime: float) -> bool:
    try:
        return find_kinetic_sheet(path_str) is not None
    except Exception:  # noqa: BLE001
        return False


def has_plate1(path) -> bool:
    """True if an Excel file has a raw-kinetic sheet ('Plate 1', 'plate reader',
    or any tab with a Time + A1..H12 header) — a result .xlsm."""
    if not is_excel(path):
        return False
    try:
        mt = os.path.getmtime(path)
    except OSError:
        mt = 0.0
    return _has_plate1_cached(str(path), mt)


NAMES_STORE = Path("sample_names_store.json")


def _names_key(filename: str, sheet: str | None) -> str:
    return f"{filename}|{sheet}" if sheet else str(filename)


def load_names_store() -> dict:
    if NAMES_STORE.exists():
        try:
            return json.loads(NAMES_STORE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_names_store(store: dict) -> None:
    NAMES_STORE.write_text(json.dumps(store, indent=2), encoding="utf-8")


def resolve_names(filename: str, sheet: str | None) -> dict:
    """Display names for the two samples, derived from structured details."""
    d = resolve_details(filename, sheet)
    names = {t: display_name(d[t]) for t in ("1", "2")}
    if not names["1"] and not names["2"]:
        old = load_names_store().get(_names_key(filename, sheet or ""))
        if old:
            return {"1": old.get("1", ""), "2": old.get("2", "")}
    return names


DETAILS_STORE = Path("sample_details_store.json")


def load_details_store() -> dict:
    if DETAILS_STORE.exists():
        try:
            return json.loads(DETAILS_STORE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_details_store(store: dict) -> None:
    DETAILS_STORE.write_text(json.dumps(store, indent=2), encoding="utf-8")


CONTROLS_STORE = Path("controls_store.json")


def load_controls_store() -> list:
    """Persistent database of named control / benchmark profiles.

    Each entry: {name, file, sheet, trough, category, notes}. Grows as the user
    runs and saves reference shampoos (e.g. Herbal Essences, NATIVE clear).
    """
    if CONTROLS_STORE.exists():
        try:
            data = json.loads(CONTROLS_STORE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:  # noqa: BLE001
            return []
    return []


def save_controls_store(controls: list) -> None:
    CONTROLS_STORE.write_text(json.dumps(controls, indent=2), encoding="utf-8")


PRODUCTS_STORE = Path("products_store.json")

# Categories a sample/product can be tagged with (label + short hint).
PRODUCT_CATEGORIES = [
    {"key": "in_market", "label": "In-market (P&G launched)"},
    {"key": "competitor", "label": "Competitor product"},
    {"key": "benchmark", "label": "Benchmark"},
    {"key": "control", "label": "Control"},
    {"key": "development", "label": "Development / experimental"},
]
_PRODUCT_CATEGORY_KEYS = {c["key"] for c in PRODUCT_CATEGORIES}


def load_products_store() -> list:
    """Persistent catalog of named products / shampoos with tags & context.

    Each entry: {name, brand, category, ingredients, consumer_feedback, notes,
    file, sheet, trough}. Products can be catalogued before any plate data
    exists (file/sheet/trough optional) and linked to a run later.
    """
    if PRODUCTS_STORE.exists():
        try:
            data = json.loads(PRODUCTS_STORE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:  # noqa: BLE001
            return []
    return []


def save_products_store(products: list) -> None:
    PRODUCTS_STORE.write_text(json.dumps(products, indent=2), encoding="utf-8")


INTAKE_STORE = Path("intake_store.json")


def load_intake_store() -> dict:
    """Per-sample metadata from the intake workbook, keyed by norm_plate ->
    {"1": {...}, "2": {...}}. Overrides component_properties.csv for MW/CD."""
    if INTAKE_STORE.exists():
        try:
            return json.loads(INTAKE_STORE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_intake_store(store: dict) -> None:
    INTAKE_STORE.write_text(json.dumps(store, indent=2), encoding="utf-8")


PLATE_KIND_STORE = Path("plate_kind_store.json")


def load_plate_kind_store() -> dict:
    """Which measurement each plate belongs to: norm_plate -> 'clear' | 'opaque'.
    %T (clear) and Inverse %T (opaque) run different samples, so each tab only
    shows/organizes its own plates."""
    if PLATE_KIND_STORE.exists():
        try:
            return json.loads(PLATE_KIND_STORE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_plate_kind_store(store: dict) -> None:
    PLATE_KIND_STORE.write_text(json.dumps(store, indent=2), encoding="utf-8")


def set_plate_kind(plate_name, kind) -> None:
    kind = (kind or "").strip().lower()
    if kind not in ("clear", "opaque") or not plate_name:
        return
    ks = load_plate_kind_store()
    ks[norm_plate(plate_name)] = kind
    save_plate_kind_store(ks)


DEPO_MODELS_STORE = Path("deposition_models.json")


def load_depo_models() -> list:
    """Deposition correlation models (seeded with the Project Zorro SLR fits)."""
    if DEPO_MODELS_STORE.exists():
        try:
            data = json.loads(DEPO_MODELS_STORE.read_text(encoding="utf-8"))
            if isinstance(data, list) and data:
                return data
        except Exception:  # noqa: BLE001
            pass
    save_depo_models(list(DEFAULT_MODELS))
    return list(DEFAULT_MODELS)


def save_depo_models(models: list) -> None:
    DEPO_MODELS_STORE.write_text(json.dumps(models, indent=2), encoding="utf-8")


def intake_for(filename: str) -> dict:
    """Intake record {"1":..,"2":..} for a raw file (matched by normalized name)."""
    return load_intake_store().get(norm_plate(filename), {})


def _num(v):
    """Best-effort float, else None."""
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def component_props(d: dict, props: dict) -> tuple:
    """(mw_kda, charge_density) for the varying component: intake values win,
    else fall back to component_properties.csv."""
    if d.get("variable") == "surfactant":
        mw, cd = _num(d.get("surf_mw")), _num(d.get("surf_cd"))
    else:
        mw, cd = _num(d.get("poly_mw")), _num(d.get("poly_cd"))
    if mw is None or cd is None:
        pr = props.get(canon_key(component_of(d)), {}) if component_of(d) else {}
        if mw is None:
            mw = pr.get("mw_kda")
        if cd is None:
            cd = pr.get("charge_density_meq_g")
    return mw, cd




def _blank_details() -> dict:
    return {"sample_type": "prototype", "chassis": "", "polymer": "", "surfactant": "",
            "co_surfactant": "", "co_surfactant_pct": "",
            "concentration": "", "variable": "polymer", "ebr_batch_id": "",
            "enovia_id": "", "poly_mw": "", "poly_cd": "", "surf_mw": "",
            "surf_cd": ""}


def component_of(d: dict) -> str:
    """The component being varied for this sample (surfactant or polymer)."""
    if d.get("variable") == "surfactant":
        return d.get("surfactant") or ""
    return d.get("polymer") or ""


def split_conc_polymer(s) -> tuple[str, str]:
    """'0.4% 3196' -> ('0.4%', '3196');  'Dex-K' -> ('', 'Dex-K')."""
    s = str(s or "").strip()
    m = re.match(r"^\s*([\d.]+\s*%)\s*(.*)$", s)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", s


def display_name(d: dict) -> str:
    cosurf = " ".join(x for x in (d.get("co_surfactant_pct"), d.get("co_surfactant")) if x)
    return " ".join(
        x for x in (d.get("chassis"), cosurf, d.get("concentration"), component_of(d)) if x
    ).strip()


def resolve_details(filename: str, sheet: str | None) -> dict:
    """Stored per-sample details, else intake workbook, else Excel-derived, else blank."""
    stored = load_details_store().get(_names_key(filename, sheet or ""))
    if stored:
        return {t: {**_blank_details(), **(stored.get(t) or {})} for t in ("1", "2")}

    # intake workbook (metadata-only) matched by normalized plate id
    intake = intake_for(filename)
    if intake:
        out = {}
        for t in ("1", "2"):
            rec = intake.get(t) or {}
            out[t] = {**_blank_details(),
                      "sample_type": str(rec.get("sample_type", "prototype") or "prototype").strip(),
                      "chassis": str(rec.get("chassis", "")).strip(),
                      "polymer": str(rec.get("polymer", "")).strip(),
                      "surfactant": str(rec.get("surfactant", "")).strip(),
                      "co_surfactant": str(rec.get("co_surfactant", "")).strip(),
                      "co_surfactant_pct": str(rec.get("co_surfactant_pct", "")).strip(),
                      "concentration": str(rec.get("concentration", "")).strip(),
                      "variable": rec.get("variable", "polymer") or "polymer",
                      "batch_id": str(rec.get("batch_id", "") or "").strip(),
                      "sample_id": str(rec.get("sample_id", "") or "").strip(),
                      "ebr_batch_id": str(rec.get("ebr_batch_id", rec.get("batch_id", "")) or "").strip(),
                      "enovia_id": str(rec.get("enovia_id", "") or "").strip(),
                      "poly_mw": rec.get("poly_mw", ""), "poly_cd": rec.get("poly_cd", ""),
                      "surf_mw": rec.get("surf_mw", ""), "surf_cd": rec.get("surf_cd", "")}
        return out

    details = {"1": _blank_details(), "2": _blank_details()}
    try:
        p = resolve_file(filename)
        if is_excel(p) and sheet:
            cp = parse_run_sheet(p, sheet).get("trough_cp", {})
            for t in ("1", "2"):
                chassis = cp.get(t, {}).get("chassis") or ""
                conc, poly = split_conc_polymer(cp.get(t, {}).get("polymer"))
                details[t] = {**_blank_details(), "chassis": str(chassis).strip(),
                              "polymer": poly, "concentration": conc}
    except Exception:  # noqa: BLE001
        pass
    return details


def resolve_file(filename: str) -> Path:
    """Resolve a filename to a path inside raw_data or the upload dir (safe)."""
    safe = secure_filename(filename)
    for base in (RAW_DIR, UPLOAD_DIR):
        # try exact name first (raw files may contain spaces secure_filename strips)
        candidate = base / filename
        if candidate.exists():
            return candidate
        candidate = base / safe
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"File not found: {filename}")


def fig_to_base64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def parse_and_annotate(path: Path, sheet: str | None = None):
    if is_excel(path):
        if has_plate1(path):
            return annotate_concentration(parse_plate1_sheet(path))
        return cached_run_sheet(path, sheet)["long_df"]
    long_df = parse_kinetic_plate_file(path)
    return annotate_concentration(long_df)


@functools.lru_cache(maxsize=128)
def _cached_run_sheet(path_str: str, sheet: str, _mtime: float):
    return parse_run_sheet(path_str, sheet)


def cached_run_sheet(path, sheet: str | None):
    """parse_run_sheet with an mtime-keyed cache (avoids re-parsing the same
    workbook sheet many times within a request). Invalidates when the file
    changes on disk."""
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0.0
    return _cached_run_sheet(str(path), sheet, mtime)


def _slug(value: str) -> str:
    """Sanitize a token for use in a filename."""
    s = str(value).strip().replace(" ", "-")
    return re.sub(r"[^A-Za-z0-9.+-]+", "", s)


def convention_name(chassis: str, polymer: str, concentration: str, ext: str = ".txt") -> str:
    """Build a searchable filename: {chassis}_{polymer}_{concentration}.txt."""
    parts = [_slug(p) for p in (chassis, polymer, concentration) if str(p).strip()]
    return ("_".join(parts) + ext) if parts else ""


def safe_filename(name: str, ext: str = ".txt") -> str:
    """Sanitize a free-text filename (keeps spaces), ensuring the extension."""
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(name)).strip().strip(".")
    if not name:
        return ""
    if not name.lower().endswith(ext.lower()):
        name += ext
    return name


def curve_for(df, trough: int, timepoint: float):
    sel = df[df["trough"] == trough].dropna(subset=["formula_fraction"])
    times = sorted(sel["timepoint_minutes"].unique())
    tp = min(times, key=lambda t: abs(t - timepoint))
    sel = sel[sel["timepoint_minutes"] == tp].sort_values(
        "formula_fraction", ascending=False
    )
    return sel, tp


def ensure_submissions_db():
    conn = sqlite3.connect(SUBMISSIONS_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT (datetime('now')),
            source_file TEXT,
            trough INTEGER,
            timepoint_minutes REAL,
            auc REAL,
            auc_low REAL,
            auc_high REAL,
            metadata_json TEXT
        )
        """
    )
    conn.commit()
    conn.close()


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    return render_template(
        "coacervation.html",
        files=list_raw_txt(),
        metadata_fields=METADATA_FIELDS,
        nexus_target=NEXUS_XY_TARGET,
    )


@app.route("/names")
def get_names():
    """Return the trough names associated with a file (+ sheet)."""
    filename = request.args.get("filename", "")
    sheet = request.args.get("sheet") or ""
    try:
        return jsonify({"ok": True, "names": resolve_names(filename, sheet)})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/set_names", methods=["POST"])
def set_names():
    """Persist Trough 1/2 names for a file (+ sheet)."""
    try:
        data = request.get_json(force=True)
        filename = data.get("filename")
        if not filename:
            return jsonify({"ok": False, "error": "No file selected."})
        sheet = data.get("sheet") or ""
        names = data.get("names") or {}
        store = load_names_store()
        store[_names_key(filename, sheet)] = {
            "1": str(names.get("1", "")).strip(),
            "2": str(names.get("2", "")).strip(),
        }
        save_names_store(store)
        return jsonify({"ok": True, "message": "Sample names saved."})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/details")
def get_details():
    """Return per-sample structured details (chassis/polymer/concentration)."""
    filename = request.args.get("filename", "")
    sheet = request.args.get("sheet") or ""
    try:
        return jsonify({"ok": True, "details": resolve_details(filename, sheet)})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/set_details", methods=["POST"])
def set_details():
    """Persist per-sample chassis/polymer/concentration for a file (+ sheet)."""
    try:
        data = request.get_json(force=True)
        filename = data.get("filename")
        if not filename:
            return jsonify({"ok": False, "error": "No file selected."})
        sheet = data.get("sheet") or ""
        det = data.get("details") or {}
        store = load_details_store()
        store[_names_key(filename, sheet)] = {
            t: {
                "sample_type": str((det.get(t) or {}).get("sample_type", "prototype")).strip(),
                "chassis": str((det.get(t) or {}).get("chassis", "")).strip(),
                "polymer": str((det.get(t) or {}).get("polymer", "")).strip(),
                "surfactant": str((det.get(t) or {}).get("surfactant", "")).strip(),
                "co_surfactant": str((det.get(t) or {}).get("co_surfactant", "")).strip(),
                "co_surfactant_pct": str((det.get(t) or {}).get("co_surfactant_pct", "")).strip(),
                "concentration": str((det.get(t) or {}).get("concentration", "")).strip(),
                "ebr_batch_id": str((det.get(t) or {}).get("ebr_batch_id", "")).strip(),
                "enovia_id": str((det.get(t) or {}).get("enovia_id", "")).strip(),
                "variable": ("surfactant"
                             if str((det.get(t) or {}).get("variable", "")).strip().lower()
                             == "surfactant" else "polymer"),
            }
            for t in ("1", "2")
        }
        save_details_store(store)
        return jsonify({"ok": True, "message": "Sample details saved."})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/sheets")
def sheets():
    """Return the run tabs (with a Sample Info block) for an Excel workbook."""
    filename = request.args.get("filename", "")
    try:
        path = resolve_file(filename)
        if not is_excel(path):
            return jsonify({"ok": True, "sheets": []})
        return jsonify({"ok": True, "sheets": list_run_sheets(path)})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/file_info")
def file_info():
    """Return timepoints, troughs, dilutions for a file (and sample info for Excel)."""
    filename = request.args.get("filename", "")
    sheet = request.args.get("sheet") or None
    try:
        path = resolve_file(filename)

        sample_names, metadata = {}, {}
        if is_excel(path):
            if not sheet:
                # need a sheet choice first
                return jsonify({"ok": True, "is_excel": True,
                                "sheets": list_run_sheets(path)})
            info = parse_run_sheet(path, sheet)
            df = info["long_df"]
            metadata = info["metadata"]
        else:
            df = parse_and_annotate(path)
        # stored names override sheet-derived; falls back to sheet names / empty
        sample_names = resolve_names(filename, sheet)

        timepoints = sorted(df["timepoint_minutes"].unique().tolist())
        troughs = sorted(int(t) for t in df["trough"].dropna().unique().tolist())
        fractions = sorted(
            df["formula_fraction"].dropna().unique().tolist(), reverse=True
        )
        min_f = min(fractions) if fractions else 0.001
        max_dilution = round((1.0 - min_f) / min_f)
        return jsonify(
            {
                "ok": True,
                "is_excel": is_excel(path),
                "sample_names": sample_names,
                "metadata": metadata,
                "timepoints": timepoints,
                "troughs": troughs,
                "fractions": fractions,
                "max_dilution": max_dilution,
                "temperature_c": round(float(df["temperature_c"].dropna().mean()), 2)
                if df["temperature_c"].notna().any()
                else None,
            }
        )
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/analyze", methods=["POST"])
def analyze():
    """Parse, map, and return the plot for selected samples.

    mode='single'     -> one timepoint, %T/Absorbance/both vs dilution.
    mode='timecourse' -> overlay of several timepoints per sample (colored by time).
    """
    try:
        data = request.get_json(force=True)
        sources = data.get("sources")
        filename = data.get("filename")
        troughs = [int(t) for t in data.get("troughs", [1])]
        mode = data.get("mode", "single")
        kind = data.get("kind", "spline")
        view = data.get("view", "both")
        sample_names = data.get("sample_names", {}) or {}
        custom_title = str(data.get("title", "")).strip()

        # AUC window given as dilution ratios (1:X); convert to formula fraction
        x1 = float(data.get("auc_dil_1", 1))
        x2 = float(data.get("auc_dil_2", 10))
        f1, f2 = 1.0 / (1.0 + x1), 1.0 / (1.0 + x2)
        auc_low, auc_high = min(f1, f2), max(f1, f2)
        window_dilution = f"1:{min(x1, x2):g} → 1:{max(x1, x2):g}"

        # Single-file dataframe is only needed when not using cross-file sources.
        df = None
        if not sources:
            if not filename:
                return jsonify({"ok": False, "error": "No file selected."})
            df = parse_and_annotate(resolve_file(filename), data.get("sheet") or None)

        def label_for(tr):
            name = str(sample_names.get(str(tr), "")).strip()
            return name if name else f"Trough {tr}"

        def noise_flags(sample_list):
            fl = []
            for s in sample_list:
                nz = assess_noise(s["concentration"], s["pct_transmittance"])
                if nz["noisy"]:
                    fl.append({"label": s["label"], "message": nz["message"],
                               "recommendations": nz["recommendations"],
                               "score": nz["score"], "n_outliers": nz["n_outliers"]})
            return fl

        def fingerprints(sample_list):
            fp = []
            for s in sample_list:
                nz = assess_noise(s["concentration"], s["pct_transmittance"])
                f = compute_fingerprint(s["concentration"], s["pct_transmittance"],
                                        kind=kind, noise=nz)
                if f:
                    row = {"label": s["label"], **f}
                    try:
                        m = cfp.record_and_match("pct", s["label"], f, batch_id="", top=3)
                        row["similar_to"] = m
                    except Exception:  # noqa: BLE001
                        row["similar_to"] = []
                    fp.append(row)
            return fp

        # Optional cross-file comparison: a list of {filename, sheet, trough, name}.
        # When present, each source contributes one curve; otherwise use the
        # troughs of the single selected file.
        sources = data.get("sources")
        if sources:
            selectors = []
            for src in sources:
                sp = resolve_file(src["filename"])
                sdf = parse_and_annotate(sp, src.get("sheet") or None)
                lbl = (src.get("name") or "").strip() or \
                    f"{Path(src['filename']).stem} T{int(src.get('trough', 1))}"
                selectors.append((sdf, int(src.get("trough", 1)), lbl))
        else:
            selectors = [(df, tr, label_for(tr)) for tr in troughs]

        # ---------------- 3D surface (dilution x time) ----------------
        if mode == "3d":
            troughs_data = []
            for sdf, tr, lbl in selectors:
                sub = sdf[sdf["trough"] == tr].dropna(subset=["formula_fraction"])
                if sub.empty:
                    continue
                series = []
                for tp in sorted(sub["timepoint_minutes"].unique()):
                    cur = sub[sub["timepoint_minutes"] == tp].sort_values(
                        "formula_fraction", ascending=False)
                    series.append({"time": tp,
                                   "concentration": cur["formula_fraction"].to_numpy(),
                                   "pct_transmittance": cur["transmission_pct"].to_numpy()})
                troughs_data.append({"label": lbl, "series": series})
            if not troughs_data:
                return jsonify({"ok": False, "error": "No data for selected troughs."})
            names = ", ".join(t["label"] for t in troughs_data)
            fig = plot_3d_surface(
                troughs_data, view=("pct" if view == "both" else view),
                title=custom_title or f"Coacervation Data \u2014 3D Surface \u2014 {names}")
            img = fig_to_base64(fig)
            results, rep = [], []
            for trd in troughs_data:
                s3 = min(trd["series"], key=lambda z: abs(z["time"] - 3))
                conc, pct = s3["concentration"], s3["pct_transmittance"]
                auc = compute_auc(conc, transmittance_to_absorbance(pct),
                                  window=(auc_low, auc_high), use_fit=True, kind=kind)
                results.append({"label": f"{trd['label']} @ {s3['time']:g} min",
                                "auc": round(auc["auc"], 5),
                                "mean_absorbance": round(auc["mean_absorbance"], 4),
                                "low": round(auc["low"], 5), "high": round(auc["high"], 5)})
                rep.append({"label": trd["label"], "concentration": conc,
                            "pct_transmittance": pct})
            return jsonify({"ok": True, "image": img, "timepoint": None,
                            "window_dilution": window_dilution,
                            "results": results, "flags": noise_flags(rep)})

        # ---------------- Time-course overlay ----------------
        if mode == "timecourse":
            want_times = [float(t) for t in (data.get("timepoints") or [0, 1, 3, 5, 10, 15])]
            troughs_data = []
            results = []
            for sdf, tr, lbl in selectors:
                sub = sdf[sdf["trough"] == tr].dropna(subset=["formula_fraction"])
                if sub.empty:
                    continue
                avail = sorted(sub["timepoint_minutes"].unique())
                seen = set()
                series = []
                for want in want_times:
                    tp = min(avail, key=lambda t: abs(t - want))
                    if tp in seen:
                        continue
                    seen.add(tp)
                    cur = sub[sub["timepoint_minutes"] == tp].sort_values(
                        "formula_fraction", ascending=False
                    )
                    conc = cur["formula_fraction"].to_numpy()
                    pct = cur["transmission_pct"].to_numpy()
                    series.append({"time": tp, "concentration": conc,
                                   "pct_transmittance": pct})
                    auc = compute_auc(conc, transmittance_to_absorbance(pct),
                                      window=(auc_low, auc_high), use_fit=True, kind=kind)
                    results.append({
                        "label": f"{lbl} @ {tp:g} min",
                        "auc": round(auc["auc"], 5),
                        "mean_absorbance": round(auc["mean_absorbance"], 4),
                        "low": round(auc["low"], 5), "high": round(auc["high"], 5),
                    })
                troughs_data.append({"label": lbl, "series": series})

            if not troughs_data:
                return jsonify({"ok": False, "error": "No data for selected troughs."})

            names = ", ".join(t["label"] for t in troughs_data)
            rep = []
            for trd in troughs_data:
                s3 = min(trd["series"], key=lambda z: abs(z["time"] - 3))
                rep.append({"label": trd["label"], "concentration": s3["concentration"],
                            "pct_transmittance": s3["pct_transmittance"]})
            fig = plot_time_course(
                troughs_data,
                view=("pct" if view == "both" else view),
                auc_window=(auc_low, auc_high), kind=kind,
                title=custom_title or f"Coacervation Data \u2014 Time Course \u2014 {names}",
            )
            img = fig_to_base64(fig)
            return jsonify({"ok": True, "image": img, "timepoint": None,
                            "window_dilution": window_dilution, "results": results,
                            "flags": noise_flags(rep)})

        # ---------------- Single timepoint ----------------
        timepoint = float(data.get("timepoint", 3.0))
        samples = []
        used_tp = None
        for sdf, tr, lbl in selectors:
            sel, tp = curve_for(sdf, tr, timepoint)
            used_tp = tp
            if sel.empty:
                continue
            samples.append(
                {
                    "label": lbl,
                    "concentration": sel["formula_fraction"].to_numpy(),
                    "pct_transmittance": sel["transmission_pct"].to_numpy(),
                }
            )

        if not samples:
            return jsonify({"ok": False, "error": "No data for selected troughs."})

        names = ", ".join(s["label"] for s in samples)
        flags = noise_flags(samples)
        fig, results = plot_coacervation(
            samples,
            view=view,
            auc_window=(auc_low, auc_high),
            kind=kind,
            title=custom_title or f"Coacervation Data \u2014 {names} @ {used_tp:g} min",
        )
        img = fig_to_base64(fig)

        return jsonify(
            {
                "ok": True,
                "image": img,
                "timepoint": used_tp,
                "window_dilution": window_dilution,
                "flags": flags,
                "fingerprints": fingerprints(samples),
                "results": [
                    {
                        "label": r["label"],
                        "auc": round(r["auc"], 5),
                        "total_auc": round(r.get("total_auc", r["auc"]), 5),
                        "mean_absorbance": round(r["mean_absorbance"], 4),
                        "low": round(r["low"], 5),
                        "high": round(r["high"], 5),
                    }
                    for r in results
                ],
            }
        )
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/save", methods=["POST"])
def save():
    """Validate required metadata and store the submission locally."""
    try:
        data = request.get_json(force=True)
        metadata = data.get("metadata", {})

        missing = [
            f["label"]
            for f in METADATA_FIELDS
            if f.get("required") and not str(metadata.get(f["key"], "")).strip()
        ]
        if missing:
            return jsonify(
                {"ok": False, "error": "Missing required fields: " + ", ".join(missing)}
            )

        ensure_submissions_db()
        conn = sqlite3.connect(SUBMISSIONS_DB)
        conn.execute(
            """INSERT INTO submissions
               (source_file, trough, timepoint_minutes, auc, auc_low, auc_high, metadata_json)
               VALUES (?,?,?,?,?,?,?)""",
            (
                data.get("filename"),
                data.get("trough"),
                data.get("timepoint"),
                data.get("auc"),
                data.get("auc_low"),
                data.get("auc_high"),
                json.dumps(metadata),
            ),
        )
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "message": "Submission saved."})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/export_flex", methods=["POST"])
def export_flex():
    """Export critical parameters in the exact nexus_xy schema (long/EAV format).

    NOTE: nexus_xy is populated by an automated ingestion pipeline. We do NOT
    write directly to it. This produces a schema-matched CSV for submission
    through the official dropoff / LabVantage route.
    """
    try:
        data = request.get_json(force=True)
        metadata = data.get("metadata", {})
        sample_id = str(metadata.get("sample_id", "")).strip() or "<SAMPLE_ID>"
        rows = []
        for r in data.get("results", []):
            params = [
                ("AUC_absorbance", r.get("auc"), "A*fraction"),
                ("mean_absorbance", r.get("mean_absorbance"), "A"),
            ]
            for param_id, value, unit in params:
                rows.append(
                    {
                        "key_id1": sample_id,
                        "param_list_id": "Coacervation Data",
                        "param_list_version_id": 1,
                        "variant_id": r.get("label"),
                        "dataset": 1,
                        "replicate_id": 1,
                        "param_id": param_id,
                        "entered_value": value,
                        "entered_units": unit,
                        "_source_file": data.get("filename"),
                    }
                )

        # write a schema-matched CSV for the official pipeline submission
        exports = Path("exports")
        exports.mkdir(exist_ok=True)
        csv_path = exports / f"nexus_xy_{Path(str(sample_id)).name}.csv"
        pd.DataFrame(rows).to_csv(csv_path, index=False)

        return jsonify(
            {
                "ok": True,
                "target": NEXUS_XY_TARGET,
                "note": "nexus_xy is pipeline-managed; submit this CSV via the "
                        "official dropoff/LabVantage route (no direct INSERT).",
                "csv_path": str(csv_path),
                "rows": rows,
            }
        )
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


def _library_samples(rows, fname, sheet, path, timepoint, window, props, depo_models=None):
    if depo_models is None:
        depo_models = load_depo_models()
    # Parse the sheet once and derive both data and details (avoids re-opening).
    trough_meta = {}
    try:
        if is_excel(path) and sheet:
            info = cached_run_sheet(path, sheet)
            df = info["long_df"]
            trough_meta = info.get("trough_meta", {}) or {}
            stored = load_details_store().get(_names_key(fname, sheet))
            if stored:
                details = {t: {**_blank_details(), **(stored.get(t) or {})} for t in ("1", "2")}
            else:
                cp = info.get("trough_cp", {})
                details = {}
                for t in ("1", "2"):
                    chassis = cp.get(t, {}).get("chassis") or ""
                    conc, poly = split_conc_polymer(cp.get(t, {}).get("polymer"))
                    details[t] = {**_blank_details(), "chassis": str(chassis).strip(),
                                  "polymer": poly, "concentration": conc}
        else:
            df = parse_and_annotate(path, sheet)
            details = resolve_details(fname, sheet)
    except Exception:  # noqa: BLE001
        return
    intake = intake_for(fname)
    for tr in (1, 2):
        sub = df[df["trough"] == tr].dropna(subset=["formula_fraction"])
        if sub.empty:
            continue
        avail = sorted(sub["timepoint_minutes"].unique())
        tp = min(avail, key=lambda t: abs(t - timepoint))
        cur = sub[sub["timepoint_minutes"] == tp].sort_values(
            "formula_fraction", ascending=False)
        conc = cur["formula_fraction"].to_numpy()
        pct = cur["transmission_pct"].to_numpy()
        if len(pct) < 5 or float(np.nanmax(pct)) < 1.0:
            continue
        auc = compute_auc(conc, transmittance_to_absorbance(pct),
                          window=window, use_fit=True)
        # trough position: dilution (1:X) at minimum %T (maximum coacervation)
        imin = int(np.argmin(pct))
        trough_dil = round(float(dilution_ratio(conc[imin])), 1)
        # coacervation fingerprint (onset/peak/recovery/width/strength + read-out)
        nz = assess_noise(conc, pct)
        fp = compute_fingerprint(conc, pct, noise=nz) or {}
        d = details.get(str(tr), {})
        intk = intake.get(str(tr)) or {}
        if intk:
            # intake workbook supplies MW/CD + which component is varied
            d = {**d,
                 "poly_mw": intk.get("poly_mw", d.get("poly_mw")),
                 "poly_cd": intk.get("poly_cd", d.get("poly_cd")),
                 "surf_mw": intk.get("surf_mw", d.get("surf_mw")),
                 "surf_cd": intk.get("surf_cd", d.get("surf_cd")),
                 "variable": d.get("variable") or intk.get("variable", "polymer")}
        comp = component_of(d)
        mw_kda, charge = component_props(d, props)
        # per-trough Nexus sample key + prep metadata: intake first, else workbook
        tmeta = trough_meta.get(f"Trough_0{tr}") or trough_meta.get(f"Trough_{tr}") or {}
        sample_key = str(intk.get("batch_id") or tmeta.get("BatchID") or "").strip()
        hardness = str(intk.get("hardness") or tmeta.get("Hardness") or "").strip()
        shake_speed = intk.get("shake_speed") or tmeta.get("HHS Shake Speed (rpm)")
        shake_temp = intk.get("shake_temp") or tmeta.get("HHS Shake Temp (C)")
        shake_time = intk.get("shake_time") or tmeta.get("HHS Shake Time (sec)")
        row = {
            "run": sheet or Path(fname).stem,
            "file": fname, "sheet": sheet or "", "sample": f"Sample {tr}",
            "trough": tr, "sample_key": sample_key,
            "sample_name": str(intk.get("name") or "").strip(),
            "tag": str(intk.get("tag") or "").strip(),
            "sample_type": str(intk.get("sample_type") or d.get("sample_type") or "").strip(),
            "hardness": hardness,
            "shake_speed_rpm": shake_speed,
            "shake_temp_c": shake_temp,
            "shake_time_s": shake_time,
            "temperature_c": round(float(cur["temperature_c"].iloc[0]), 2)
                if "temperature_c" in cur and cur["temperature_c"].notna().any() else None,
            "chassis": d.get("chassis", ""), "polymer": d.get("polymer", ""),
            "surfactant": d.get("surfactant", ""),
            "co_surfactant": d.get("co_surfactant", ""),
            "co_surfactant_pct": d.get("co_surfactant_pct", ""),
            "variable": d.get("variable", "polymer"), "component": comp,
            "concentration": d.get("concentration", ""),
            "ebr_batch_id": str(intk.get("ebr_batch_id") or d.get("ebr_batch_id") or "").strip(),
            "enovia_id": str(intk.get("enovia_id") or d.get("enovia_id") or "").strip(),
            "mw_kda": mw_kda, "charge": charge,
            "particles_gt_30um": intk.get("particles_gt_30um"),
            "coacervate_size_um": intk.get("coacervate_size_um"),
            "auc": round(float(auc["auc"]), 5), "trough_dilution": trough_dil,
            "onset": fp.get("onset_dilution"), "peak": fp.get("peak_dilution"),
            "recovery": fp.get("recovery_label"), "width": fp.get("width_label"),
            "strength": fp.get("strength_label"),
            "interpretation": fp.get("interpretation", ""),
            "confidence": fp.get("confidence", ""),
            "timepoint": tp,
        }
        # predicted deposition (from uploadable correlation models)
        pred = predict_best(row, depo_models) if depo_models else None
        row["pred_depo"] = pred["value"] if pred else None
        row["depo_class"] = pred["depo_class"] if pred else ""
        row["depo_model"] = pred["model"] if pred else ""
        rows.append(row)


@app.route("/library", methods=["POST"])
def library():
    """Build a table of every sample across all files/run tabs."""
    try:
        data = request.get_json(force=True)
        timepoint = float(data.get("timepoint", 3.0))
        x1 = float(data.get("auc_dil_1", 1))
        x2 = float(data.get("auc_dil_2", 10))
        f1, f2 = 1.0 / (1.0 + x1), 1.0 / (1.0 + x2)
        window = (min(f1, f2), max(f1, f2))
        props = load_properties()
        rows = []
        for fname in list_raw_txt():
            path = resolve_file(fname)
            sheets = list_run_sheets(path) if is_excel(path) else []
            # multi-run workbooks (e.g. "Sample Info_24 shampoo formulas") expose
            # every run tab; single-plate result files parse the plate directly.
            if sheets and (len(sheets) > 1 or not has_plate1(path)):
                for sh in sheets:
                    _library_samples(rows, fname, sh, path, timepoint, window, props)
            else:
                _library_samples(rows, fname, None, path, timepoint, window, props)
        _overlay_products(rows)
        return jsonify({"ok": True, "rows": rows})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


def _build_library(timepoint, window, props, only_file=None):
    """Build library rows, optionally scoped to a single source file."""
    rows = []
    for fname in list_raw_txt():
        if only_file and fname != only_file:
            continue
        path = resolve_file(fname)
        sheets = list_run_sheets(path) if is_excel(path) else []
        if sheets and (len(sheets) > 1 or not has_plate1(path)):
            for sh in sheets:
                _library_samples(rows, fname, sh, path, timepoint, window, props)
        else:
            _library_samples(rows, fname, None, path, timepoint, window, props)
    return rows


def _overlay_products(rows):
    """Tag library rows with any catalogued product linked to that plate/trough.

    Adds 'product', 'category' and 'consumer_feedback' columns where a product
    in the catalog points at the same (file, sheet, trough).
    """
    prod_by_link = {}
    for p in load_products_store():
        if p.get("file") and p.get("trough"):
            key = (str(p["file"]), str(p.get("sheet") or ""), str(p["trough"]))
            prod_by_link[key] = p
    for r in rows:
        link = (str(r.get("file") or ""), str(r.get("sheet") or ""),
                str(r.get("trough") or ""))
        p = prod_by_link.get(link)
        r["product"] = p.get("name", "") if p else ""
        r["category"] = p.get("category", "") if p else ""
        r["consumer_feedback"] = p.get("consumer_feedback", "") if p else ""


def sample_display_name(row) -> str:
    """Human-friendly, searchable sample name.

    Prefers an explicit user-set Sample name (from Organize), then
    'Chassis · Component · %', then the batch id, then run/sheet + trough.
    """
    explicit = str(row.get("sample_name") or "").strip()
    if explicit:
        return explicit
    chassis = str(row.get("chassis") or "").strip()
    comp = str(row.get("component") or row.get("polymer")
               or row.get("surfactant") or "").strip()
    conc = str(row.get("concentration") or "").strip()
    parts = [p for p in (chassis, comp, conc) if p]
    if parts:
        return " · ".join(parts)
    bid = str(row.get("sample_key") or "").strip()
    if bid:
        return bid
    run = str(row.get("run") or row.get("sheet") or Path(row.get("file", "")).stem)
    return f"{run} · T{row.get('trough')}".strip(" ·")


def formulation_identity(row: dict) -> str:
    """Compact searchable formulation identity for prototype/internal samples."""
    cosurf = " ".join(x for x in (row.get("co_surfactant_pct"), row.get("co_surfactant")) if x)
    polymer = " ".join(x for x in (row.get("concentration"), row.get("polymer") or row.get("component")) if x)
    return " · ".join(x for x in (row.get("chassis"), cosurf, polymer) if x)


def _organized_sample_lookup() -> dict:
    """Lookup organized prototype metadata by sample id, batch id, and display name."""
    out = {}
    for plate_key, troughs in load_intake_store().items():
        for tr in ("1", "2"):
            rec = (troughs or {}).get(tr) or {}
            if not rec:
                continue
            row = {
                "name": rec.get("name", ""),
                "batch_id": rec.get("batch_id", ""),
                "sample_id": rec.get("sample_id", ""),
                "chassis": rec.get("chassis", ""),
                "polymer": rec.get("polymer") or rec.get("component", ""),
                "surfactant": rec.get("surfactant", ""),
                "component": rec.get("polymer") or rec.get("surfactant") or rec.get("component", ""),
                "concentration": rec.get("concentration", ""),
                "co_surfactant": rec.get("co_surfactant", ""),
                "co_surfactant_pct": rec.get("co_surfactant_pct", ""),
                "sample_type": rec.get("sample_type", ""),
                "ebr_batch_id": rec.get("ebr_batch_id", ""),
                "enovia_id": rec.get("enovia_id", ""),
            }
            row["identity"] = formulation_identity(row)
            keys = [rec.get("sample_id"), rec.get("batch_id"), rec.get("name"),
                    f"{plate_key}|{tr}", f"{rec.get('plate_id', plate_key)}||{tr}"]
            for key in keys:
                key = str(key or "").strip().lower()
                if key:
                    out[key] = row
    return out


@app.route("/samples", methods=["GET"])
def samples():
    """Every named sample across all plates, for type-to-search selection.

    Each entry links back to (file, sheet, trough) so it can be plotted.
    `search` combines the display name, batch id, chassis, component and any
    linked product name so users can find a sample by name OR by batch id.
    Product-catalog entries linked to a run overlay their product name +
    category onto the matching sample.
    """
    try:
        timepoint = float(request.args.get("timepoint", 3) or 3)
        props = load_properties()
        rows = _build_library(timepoint, None, props)
        # index catalogued products by their plate link (file, sheet, trough)
        prod_by_link = {}
        for p in load_products_store():
            if p.get("file") and p.get("trough"):
                key = (str(p["file"]), str(p.get("sheet") or ""), str(p["trough"]))
                prod_by_link[key] = p
        out = []
        for r in rows:
            name = sample_display_name(r)
            identity = formulation_identity(r)
            link = (str(r.get("file") or ""), str(r.get("sheet") or ""),
                    str(r.get("trough") or ""))
            prod = prod_by_link.get(link)
            product_name = prod.get("name") if prod else ""
            category = prod.get("category") if prod else ""
            display = product_name or name
            search = " ".join(str(x) for x in (
                display, name, identity, r.get("sample_key"), r.get("chassis"),
                r.get("component"), r.get("polymer"), r.get("surfactant"),
                r.get("co_surfactant"), r.get("co_surfactant_pct"),
                r.get("concentration"), product_name, r.get("run"),
                r.get("tag"), r.get("sample_type"), r.get("ebr_batch_id"),
                r.get("enovia_id"),
            ) if x).lower()
            out.append({
                "id": "|".join(link),
                "name": display,
                "auto_name": name,
                "identity": identity,
                "product_name": product_name,
                "category": category,
                "tag": r.get("tag", ""),
                "sample_type": r.get("sample_type", ""),
                "batch_id": r.get("sample_key", ""),
                "ebr_batch_id": r.get("ebr_batch_id", ""),
                "enovia_id": r.get("enovia_id", ""),
                "file": r.get("file", ""),
                "sheet": r.get("sheet", ""),
                "trough": r.get("trough"),
                "chassis": r.get("chassis", ""),
                "component": r.get("component", ""),
                "polymer": r.get("polymer", ""),
                "surfactant": r.get("surfactant", ""),
                "co_surfactant": r.get("co_surfactant", ""),
                "co_surfactant_pct": r.get("co_surfactant_pct", ""),
                "concentration": r.get("concentration", ""),
                "auc": r.get("auc"),
                "search": search,
            })
        out.sort(key=lambda s: s["name"].lower())
        return jsonify({"ok": True, "samples": out})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/controls", methods=["GET", "POST"])
def controls():
    """List or add/update saved control / benchmark profiles (persistent DB)."""
    try:
        store = load_controls_store()
        if request.method == "GET":
            return jsonify({"ok": True, "controls": store})
        data = request.get_json(force=True)
        name = str(data.get("name", "")).strip()
        if not name:
            return jsonify({"ok": False, "error": "Control name is required."})
        entry = {
            "name": name,
            "file": data.get("file", ""),
            "sheet": data.get("sheet", ""),
            "trough": int(data.get("trough", 1)),
            "category": data.get("category", "control"),
            "notes": data.get("notes", ""),
        }
        store = [c for c in store if c.get("name") != name]  # upsert by name
        store.append(entry)
        save_controls_store(store)
        return jsonify({"ok": True, "controls": store})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/controls_delete", methods=["POST"])
def controls_delete():
    """Remove a saved control by name."""
    try:
        name = str(request.get_json(force=True).get("name", "")).strip()
        store = [c for c in load_controls_store() if c.get("name") != name]
        save_controls_store(store)
        return jsonify({"ok": True, "controls": store})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/products", methods=["GET", "POST"])
def products():
    """List or add/update catalogued products / shampoos with tags & context.

    Upsert by name. Fields: name, brand, category, ingredients,
    consumer_feedback, notes, and optional plate link (file/sheet/trough).
    """
    try:
        store = load_products_store()
        if request.method == "GET":
            return jsonify({"ok": True, "products": store,
                            "categories": PRODUCT_CATEGORIES})
        data = request.get_json(force=True) or {}
        name = str(data.get("name", "")).strip()
        if not name:
            return jsonify({"ok": False, "error": "Product name is required."})
        category = str(data.get("category", "competitor")).strip()
        if category not in _PRODUCT_CATEGORY_KEYS:
            category = "competitor"
        trough_raw = str(data.get("trough", "")).strip()
        existing = next((p for p in store
                         if str(p.get("name", "")).lower() == name.lower()), {})
        entry = {
            "name": name,
            "brand": str(data.get("brand", "")).strip(),
            "category": category,
            "ingredients": str(data.get("ingredients", "")).strip(),
            "claims": str(data.get("claims", existing.get("claims", ""))).strip(),
            "consumer_feedback": str(data.get("consumer_feedback", "")).strip(),
            "notes": str(data.get("notes", "")).strip(),
            "gtin": str(data.get("gtin", existing.get("gtin", ""))).strip(),
            "file": str(data.get("file", "")).strip(),
            "sheet": str(data.get("sheet", "")).strip(),
            "trough": int(trough_raw) if trough_raw in ("1", "2") else "",
        }
        # upsert by name (case-insensitive), preserving list order
        key = name.lower()
        store = [p for p in store if str(p.get("name", "")).lower() != key]
        store.append(entry)
        store.sort(key=lambda p: (p.get("category", ""), p.get("name", "").lower()))
        save_products_store(store)
        return jsonify({"ok": True, "products": store,
                        "categories": PRODUCT_CATEGORIES})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


def _map_gnpd_columns(headers: list[str]) -> dict:
    """Best-effort map of a GNPD/product CSV's headers to catalog fields."""
    low = {h.lower().strip(): h for h in (headers or [])}

    def find(*keys):
        for k in keys:
            for hl, h in low.items():
                if k in hl:
                    return h
        return ""
    return {
        "name": find("product name", "product", "name"),
        "brand": find("brand", "company", "manufacturer"),
        "category": find("sub-category", "category"),
        "claims": find("claim", "positioning"),
        "ingredients": find("ingredient"),
        "consumer_feedback": find("consumer", "review", "rating", "feedback",
                                  "sensory", "perception"),
        "gtin": find("gtin", "barcode", "bar code", "upc", "ean"),
    }


@app.route("/products_import", methods=["POST"])
def products_import():
    """Bulk-import product data from a CSV / Mintel GNPD export.

    Auto-detects columns (product / brand / category / claims / ingredients /
    GTIN), matches to catalogued products by GTIN then name, and fills
    ingredients + claims + brand WITHOUT disturbing plate links. Unmatched rows
    are added as new competitor products when ``add_new`` is set.
    """
    try:
        import csv as _csv
        f = request.files.get("file")
        if not f:
            return jsonify({"ok": False, "error": "Choose a CSV file to import."})
        add_new = str(request.form.get("add_new", "true")).lower() != "false"
        raw = f.read()
        text = None
        for enc in ("utf-8-sig", "utf-16", "latin-1"):
            try:
                text = raw.decode(enc)
                break
            except Exception:  # noqa: BLE001
                continue
        if text is None:
            return jsonify({"ok": False, "error": "Could not decode file (save as UTF-8 CSV)."})
        sample = text[:4096]
        delim = "\t" if sample.count("\t") > sample.count(",") else ","
        reader = _csv.DictReader(io.StringIO(text), delimiter=delim)
        headers = reader.fieldnames or []
        col = _map_gnpd_columns(headers)
        if not (col.get("name") or col.get("gtin")):
            return jsonify({"ok": False, "error":
                            "No product-name or GTIN column found. Headers seen: "
                            + ", ".join(headers)})
        store = load_products_store()

        def _digits(s):
            return re.sub(r"\D", "", str(s or ""))

        by_gtin, by_name = {}, {}
        for p in store:
            g = _digits(p.get("gtin") or "")
            if not g:
                m = re.search(r"GTIN\s*([0-9]{6,})", p.get("notes") or "", re.I)
                g = m.group(1) if m else ""
            if g:
                by_gtin[g] = p
            by_name[canon_key(p.get("name", ""))] = p

        matched = added = 0
        for row in reader:
            name = str(row.get(col.get("name", ""), "") or "").strip()
            gtin = _digits(row.get(col.get("gtin", ""), "")) if col.get("gtin") else ""
            ingredients = (str(row.get(col.get("ingredients", ""), "") or "").strip()
                           if col.get("ingredients") else "")
            claims = (str(row.get(col.get("claims", ""), "") or "").strip()
                      if col.get("claims") else "")
            feedback = (str(row.get(col.get("consumer_feedback", ""), "") or "").strip()
                        if col.get("consumer_feedback") else "")
            brand = (str(row.get(col.get("brand", ""), "") or "").strip()
                     if col.get("brand") else "")
            if not name and not gtin:
                continue
            p = (by_gtin.get(gtin) if gtin else None) or by_name.get(canon_key(name))
            if p:
                matched += 1
                if ingredients:
                    p["ingredients"] = ingredients
                if claims:
                    p["claims"] = claims
                if feedback:
                    p["consumer_feedback"] = feedback
                if brand and not p.get("brand"):
                    p["brand"] = brand
                if gtin and not p.get("gtin"):
                    p["gtin"] = gtin
            elif add_new and name:
                p = {"name": name, "brand": brand, "category": "competitor",
                     "ingredients": ingredients, "claims": claims,
                     "consumer_feedback": feedback,
                     "notes": (f"GTIN {gtin}" if gtin else ""), "gtin": gtin,
                     "file": "", "sheet": "", "trough": ""}
                store.append(p)
                by_name[canon_key(name)] = p
                if gtin:
                    by_gtin[gtin] = p
                added += 1
        store.sort(key=lambda p: (p.get("category", ""), p.get("name", "").lower()))
        save_products_store(store)
        return jsonify({"ok": True, "matched": matched, "added": added,
                        "columns": col, "headers": headers,
                        "products": store, "categories": PRODUCT_CATEGORIES})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/products_delete", methods=["POST"])
def products_delete():
    """Remove a catalogued product by name."""
    try:
        name = str(request.get_json(force=True).get("name", "")).strip().lower()
        store = [p for p in load_products_store()
                 if str(p.get("name", "")).lower() != name]
        save_products_store(store)
        return jsonify({"ok": True, "products": store,
                        "categories": PRODUCT_CATEGORIES})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


def _norm_polymers(polymers):
    """Accept polymers as strings or {name, role} dicts -> list of dicts."""
    out = []
    for p in polymers or []:
        if isinstance(p, dict):
            name = str(p.get("name", "")).strip()
            role = p.get("role", "variant")
        else:
            name, role = str(p).strip(), "variant"
        if name:
            out.append({"name": name, "role": role})
    return out


@app.route("/experiment_build", methods=["POST"])
def experiment_build():
    """Build a design grid from USER-TYPED axes (chassis x polymers), matching
    each cell to plate data, plus any selected control profiles.

    Returns matched cells, resolved controls, and autocomplete suggestions.
    """
    try:
        data = request.get_json(force=True)
        timepoint = float(data.get("timepoint", 3.0))
        x1 = float(data.get("auc_dil_1", 1))
        x2 = float(data.get("auc_dil_2", 10))
        f1, f2 = 1.0 / (1.0 + x1), 1.0 / (1.0 + x2)
        window = (min(f1, f2), max(f1, f2))
        props = load_properties()

        rows = _build_library(timepoint, window, props)
        # index by canonical (chassis, polymer) for matching typed axes
        index = {}
        for r in rows:
            key = (canon_key(r.get("chassis", "")), canon_key(r.get("polymer", "")))
            index.setdefault(key, r)

        chassis_axis = [str(c).strip() for c in (data.get("chassis") or []) if str(c).strip()]
        polymer_axis = _norm_polymers(data.get("polymers"))

        cells = []
        for ch in chassis_axis:
            for p in polymer_axis:
                r = index.get((canon_key(ch), canon_key(p["name"])))
                cell = {"chassis": ch, "polymer": p["name"], "role": p["role"],
                        "matched": bool(r)}
                if r:
                    cell.update({
                        "file": r.get("file"), "sheet": r.get("sheet"),
                        "trough": r.get("trough"), "sample_key": r.get("sample_key"),
                        "auc": r.get("auc"), "trough_dilution": r.get("trough_dilution"),
                        "onset": r.get("onset"), "peak": r.get("peak"),
                        "recovery": r.get("recovery"), "width": r.get("width"),
                        "strength": r.get("strength"),
                    })
                cells.append(cell)

        # resolve selected controls (from inline profiles) into metric rows
        controls_out = []
        for c in data.get("controls") or []:
            s = _experiment_sample(c.get("file"), c.get("sheet"), c.get("trough", 1),
                                   timepoint, window, props)
            entry = {"name": c.get("name", ""), "file": c.get("file"),
                     "sheet": c.get("sheet"), "trough": int(c.get("trough", 1)),
                     "role": "control", "matched": bool(s)}
            if s:
                entry.update({
                    "sample_key": s.get("sample_key"), "auc": s.get("auc"),
                    "trough_dilution": s.get("trough_dilution"), "onset": s.get("onset"),
                    "peak": s.get("peak"), "recovery": s.get("recovery"),
                    "width": s.get("width"), "strength": s.get("strength"),
                })
            controls_out.append(entry)

        suggest = {
            "chassis": sorted({r["chassis"] for r in rows if r.get("chassis")}),
            "polymers": sorted({r["polymer"] for r in rows if r.get("polymer")}),
            "files": list_raw_txt(),
        }
        return jsonify({"ok": True, "cells": cells, "controls": controls_out,
                        "suggest": suggest, "saved_controls": load_controls_store()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


def _experiment_sample(fname, sheet, trough, timepoint, window, props):
    """Parse one cell (file/sheet/trough) into a full sample dict with curve."""
    path = resolve_file(fname)
    rows = []
    _library_samples(rows, fname, sheet or None, path, timepoint, window, props)
    match = next((r for r in rows if int(r.get("trough", 0)) == int(trough)), None)
    if not match:
        return None
    # rebuild the curve at the chosen timepoint for the raw X-Y tab
    df = parse_and_annotate(path, sheet or None)
    sub = df[df["trough"] == int(trough)].dropna(subset=["formula_fraction"])
    curve = []
    if not sub.empty:
        avail = sorted(sub["timepoint_minutes"].unique())
        tp = min(avail, key=lambda t: abs(t - timepoint))
        cur = sub[sub["timepoint_minutes"] == tp].sort_values(
            "formula_fraction", ascending=False)
        conc = cur["formula_fraction"].to_numpy()
        pct = cur["transmission_pct"].to_numpy()
        absb = transmittance_to_absorbance(pct)
        for i in range(len(conc)):
            curve.append({"dilution": round(float(dilution_ratio(conc[i])), 3),
                          "pct": round(float(pct[i]), 3),
                          "absorbance": round(float(absb[i]), 4)})
    match["curve"] = curve
    return match


@app.route("/export_experiment_nexus", methods=["POST"])
def export_experiment_nexus():
    """Build the filled Nexus flex-driver workbook (+ flat nexus_xy CSV) for a
    whole experiment (e.g. a 3x8 chassis x polymer design)."""
    try:
        data = request.get_json(force=True)
        exp_meta = data.get("meta", {}) or {}
        timepoint = float(data.get("timepoint", 3.0))
        x1 = float(data.get("auc_dil_1", 1))
        x2 = float(data.get("auc_dil_2", 10))
        f1, f2 = 1.0 / (1.0 + x1), 1.0 / (1.0 + x2)
        window = (min(f1, f2), max(f1, f2))
        cells = data.get("cells", [])
        if not cells:
            return jsonify({"ok": False, "error": "No samples selected for the experiment."})
        exp_meta.setdefault("timepoint", timepoint)
        exp_meta.setdefault("window", f"1:{min(x1, x2):g} - 1:{max(x1, x2):g}")
        props = load_properties()
        samples, missing = [], []
        for c in cells:
            s = _experiment_sample(c.get("file"), c.get("sheet"), c.get("trough", 1),
                                   timepoint, window, props)
            if s:
                if not s.get("sample_key"):
                    missing.append(c.get("name") or f"{s.get('chassis')} / {s.get('polymer')}")
                s["sample_id"] = s.get("sample_key") or "<NO_BATCHID>"
                s["role"] = c.get("role", "variant")
                if c.get("name"):
                    s["control_name"] = c.get("name")
                samples.append(s)
        if not samples:
            return jsonify({"ok": False, "error": "No matching plate data for selected cells."})
        result = build_nexus_workbook(exp_meta, samples, out_dir="exports")
        result["ok"] = True
        result["target"] = NEXUS_XY_TARGET
        result["missing_keys"] = missing
        result["note"] = ("nexus_xy is pipeline-managed; submit the workbook via the "
                          "official dropoff / LabVantage route (no direct INSERT).")
        return jsonify(result)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})



@app.route("/small_multiples", methods=["POST"])
def small_multiples():
    """Grid of time-course panels (one per selected sample) — capability-slide style."""
    try:
        data = request.get_json(force=True)
        sources = data.get("sources") or []
        timepoints = [float(t) for t in (data.get("timepoints") or [0, 1, 3, 5, 10, 15])]
        view = data.get("view", "pct")
        kind = data.get("kind", "spline")
        x1 = float(data.get("auc_dil_1", 1))
        x2 = float(data.get("auc_dil_2", 10))
        f1, f2 = 1.0 / (1.0 + x1), 1.0 / (1.0 + x2)
        window = (min(f1, f2), max(f1, f2))

        panels = []
        for src in sources:
            path = resolve_file(src["filename"])
            df = parse_and_annotate(path, src.get("sheet") or None)
            tr = int(src.get("trough", 1))
            sub = df[df["trough"] == tr].dropna(subset=["formula_fraction"])
            if sub.empty:
                continue
            avail = sorted(sub["timepoint_minutes"].unique())
            seen, series = set(), []
            for want in timepoints:
                tp = min(avail, key=lambda t: abs(t - want))
                if tp in seen:
                    continue
                seen.add(tp)
                cur = sub[sub["timepoint_minutes"] == tp].sort_values(
                    "formula_fraction", ascending=False)
                series.append({"time": tp,
                               "concentration": cur["formula_fraction"].to_numpy(),
                               "pct_transmittance": cur["transmission_pct"].to_numpy()})
            label = src.get("name") or f"{Path(src['filename']).stem} T{tr}"
            panels.append({"label": label, "series": series})

        if not panels:
            return jsonify({"ok": False, "error": "No samples selected."})

        fig = plot_small_multiples(
            panels, view=("pct" if view == "both" else view),
            auc_window=window, kind=kind,
            title=data.get("title", "Coacervation Data — 0–15 min time-course grid"),
        )
        return jsonify({"ok": True, "image": fig_to_base64(fig)})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/compare", methods=["POST"])
def compare():
    """Compare polymers across ALL files: AUC ranking + AUC vs MW / charge density.

    Supports group_by ('none'|'chassis'|'polymer') and substring filters.
    """
    try:
        data = request.get_json(force=True)
        timepoint = float(data.get("timepoint", 3.0))
        x1 = float(data.get("auc_dil_1", 1))
        x2 = float(data.get("auc_dil_2", 10))
        f1, f2 = 1.0 / (1.0 + x1), 1.0 / (1.0 + x2)
        window = (min(f1, f2), max(f1, f2))
        group_by = data.get("group_by", "none")
        filters = data.get("filters", {}) or {}

        props = load_properties()
        rows = []
        for fname in list_raw_txt():
            path = resolve_file(fname)
            if is_excel(path) and not has_plate1(path):
                for sh in list_run_sheets(path):
                    _library_samples(rows, fname, sh, path, timepoint, window, props)
            else:
                _library_samples(rows, fname, None, path, timepoint, window, props)

        def match(r):
            for k in ("chassis", "polymer", "surfactant", "concentration"):
                v = str(filters.get(k, "")).strip().lower()
                if v and v not in str(r.get(k, "")).lower():
                    return False
            return True

        items = [r for r in rows if match(r)]
        if not items:
            return jsonify({"ok": False, "error": "No samples match the filters."})
        for r in items:
            r["label"] = (f"{r.get('component', '?') or '?'} {r.get('concentration', '')} "
                          f"[{r['run']}]").strip()

        gsuffix = f" by {group_by}" if group_by in ("chassis", "polymer", "surfactant") else ""
        fig = plot_comparison(items, group_by=group_by,
                              title=f"Coacervation Data — Comparison{gsuffix}")
        return jsonify({"ok": True, "image": fig_to_base64(fig), "items": items})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/upload", methods=["POST"])
def upload():
    """Upload a raw kinetic .txt and save it under a searchable convention name."""
    try:
        file = request.files.get("file")
        if file is None or not file.filename:
            return jsonify({"ok": False, "error": "No file provided."})
        ext = Path(file.filename).suffix or ".txt"
        name = safe_filename(request.form.get("name", ""), ext) or secure_filename(file.filename)
        RAW_DIR.mkdir(exist_ok=True)
        file.save(RAW_DIR / name)
        return jsonify({"ok": True, "filename": name, "files": list_raw_txt()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/intake_template")
def intake_template():
    """Download a blank intake workbook template."""
    exports = Path("exports")
    exports.mkdir(exist_ok=True)
    path = exports / "coacervation_intake_template.xlsx"
    build_intake_template(path)
    return send_file(path, as_attachment=True,
                     download_name="coacervation_intake_template.xlsx")


@app.route("/intake_upload", methods=["POST"])
def intake_upload():
    """Parse an uploaded intake workbook and store its per-sample metadata."""
    try:
        file = request.files.get("file")
        if file is None or not file.filename:
            return jsonify({"ok": False, "error": "No file provided."})
        tmp = UPLOAD_DIR / secure_filename(file.filename)
        file.save(tmp)
        rows = parse_intake_workbook(tmp)
        if not rows:
            return jsonify({"ok": False, "error": "No sample rows found. Check the "
                            "'Samples' sheet has Plate ID / Batch ID filled."})
        store = build_intake_store(rows)
        save_intake_store(store)
        # helpful summary: which plate ids have a matching raw file
        raw_norm = {norm_plate(f): f for f in list_raw_txt()}
        plates = []
        for key, troughs in store.items():
            plates.append({"plate": key, "n_samples": len(troughs),
                           "matched_raw": raw_norm.get(key, "")})
        matched = sum(1 for p in plates if p["matched_raw"])
        return jsonify({"ok": True, "n_samples": len(rows), "n_plates": len(store),
                        "matched_plates": matched, "plates": plates})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/intake_status")
def intake_status():
    """Report the current intake store (plates, sample counts, raw matches)."""
    store = load_intake_store()
    raw_norm = {norm_plate(f): f for f in list_raw_txt()}
    plates = [{"plate": k, "n_samples": len(v), "matched_raw": raw_norm.get(k, "")}
              for k, v in store.items()]
    return jsonify({"ok": True, "n_plates": len(store),
                    "n_samples": sum(len(v) for v in store.values()),
                    "plates": plates})


def _intake_samples_list():
    """Flatten the intake store to one record per sample (for the manual UI)."""
    raw_norm = {norm_plate(f): f for f in list_raw_txt()}
    out = []
    for key, troughs in load_intake_store().items():
        for tr, rec in troughs.items():
            out.append({**rec, "trough": tr, "matched_raw": raw_norm.get(key, "")})
    return out


@app.route("/intake_samples")
def intake_samples():
    """List every intake sample record (manual + uploaded)."""
    return jsonify({"ok": True, "samples": _intake_samples_list()})


@app.route("/intake_add", methods=["POST"])
def intake_add():
    """Add / update a single intake sample record entered by hand."""
    try:
        rec = request.get_json(force=True) or {}
        plate = str(rec.get("plate_id", "")).strip()
        if not plate:
            return jsonify({"ok": False, "error": "Plate ID (raw file) is required."})
        if not str(rec.get("batch_id", "")).strip():
            return jsonify({"ok": False, "error": "Batch ID is required."})
        tr = "2" if str(rec.get("trough", "1")).strip().endswith("2") else "1"
        rec["trough"] = tr
        rec.setdefault("variable", "polymer")
        store = load_intake_store()
        store.setdefault(norm_plate(plate), {})[tr] = rec
        save_intake_store(store)
        return jsonify({"ok": True, "samples": _intake_samples_list()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/intake_delete", methods=["POST"])
def intake_delete():
    """Remove one intake sample record by plate id + trough."""
    try:
        data = request.get_json(force=True) or {}
        key = norm_plate(data.get("plate_id", ""))
        tr = "2" if str(data.get("trough", "1")).strip().endswith("2") else "1"
        store = load_intake_store()
        if key in store:
            store[key].pop(tr, None)
            if not store[key]:
                del store[key]
            save_intake_store(store)
        return jsonify({"ok": True, "samples": _intake_samples_list()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/pt_plates")
def pt_plates():
    """List raw plate files with their organize state (per trough). Optional
    ?kind=clear|opaque restricts to that measurement's plates (plus any plate
    not yet assigned to a kind, which shows in both tabs until organized)."""
    try:
        want_kind = (request.args.get("kind") or "").strip().lower()
        kinds = load_plate_kind_store()
        store = load_intake_store()
        out = []
        for fname in list_raw_txt():
            path = resolve_file(fname)
            if is_excel(path) and not has_plate1(path):
                continue  # %T plates = raw .txt or result .xlsm (kinetic tab)
            pkind = kinds.get(norm_plate(fname), "")
            if want_kind and (pkind or "clear") != want_kind:
                continue  # this plate belongs to the other measurement
            rec = store.get(norm_plate(fname), {})
            # auto-read sample names/batch from below the grid on result .xlsm
            auto = {}
            if is_excel(path) and has_plate1(path):
                try:
                    auto = parse_plate1_sample_info(path)
                except Exception:  # noqa: BLE001
                    auto = {}
            troughs = {}
            for t in ("1", "2"):
                r = rec.get(t) or {}
                a = auto.get(t) or {}
                troughs[t] = {
                    "batch_id": r.get("batch_id") or a.get("batch_id", ""),
                    "sample_id": r.get("sample_id", ""),
                    "name": r.get("name", ""),
                    "tag": r.get("tag", ""),
                    "sample_type": r.get("sample_type", "prototype"),
                    "description": r.get("description") or a.get("description", ""),
                    "chassis": r.get("chassis", ""),
                    "co_surfactant": r.get("co_surfactant", ""),
                    "co_surfactant_pct": r.get("co_surfactant_pct", ""),
                    "component": r.get("surfactant") or r.get("polymer") or "",
                    "concentration": r.get("concentration", ""),
                    "ebr_batch_id": r.get("ebr_batch_id", ""),
                    "enovia_id": r.get("enovia_id", ""),
                    "auto": bool(a.get("batch_id") or a.get("description")) and not r,
                }
            try:
                mtime = os.path.getmtime(path)
                mstr = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
            except Exception:  # noqa: BLE001
                mtime, mstr = 0, ""
            out.append({"plate": fname, "troughs": troughs,
                        "kind": kinds.get(norm_plate(fname), ""),
                        "modified": mtime, "modified_str": mstr})
        out.sort(key=lambda z: z.get("modified", 0), reverse=True)
        return jsonify({"ok": True, "plates": out})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/pt_parse_desc", methods=["POST"])
def pt_parse_desc():
    """Auto-split a Description into chassis / component / concentration."""
    data = request.get_json(force=True) or {}
    return jsonify({"ok": True,
                    **parse_description(data.get("description", ""),
                                        data.get("component", ""))})


@app.route("/pt_rename", methods=["POST"])
def pt_rename():
    """Rename a raw plate file to a searchable name and migrate its metadata."""
    try:
        data = request.get_json(force=True) or {}
        old = data.get("old", "")
        if not old:
            return jsonify({"ok": False, "error": "No plate selected."})
        src = resolve_file(old)
        ext = src.suffix or ".txt"
        newname = safe_filename(data.get("name", ""), ext)
        if not newname:
            return jsonify({"ok": False, "error": "Enter a new name."})
        dest = RAW_DIR / newname
        if dest.exists() and dest.resolve() != src.resolve():
            return jsonify({"ok": False, "error": f"'{newname}' already exists."})
        src.rename(dest)
        # migrate intake metadata to the new plate key
        store = load_intake_store()
        ok, nk = norm_plate(old), norm_plate(newname)
        if ok in store and ok != nk:
            rec = store.pop(ok)
            for t in rec:
                if isinstance(rec[t], dict):
                    rec[t]["plate_id"] = newname
            store[nk] = rec
            save_intake_store(store)
        # migrate stored per-file sample details/names if present
        for loader, saver in ((load_details_store, save_details_store),
                              (load_names_store, save_names_store)):
            st = loader()
            if old in st:
                st[newname] = st.pop(old)
                saver(st)
        return jsonify({"ok": True, "filename": newname})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/pt_delete", methods=["POST"])
def pt_delete():
    """Delete an uploaded raw plate file (e.g. an accidental duplicate/repeat)
    and clean up any metadata stored under its key."""
    try:
        data = request.get_json(force=True) or {}
        name = data.get("plate", "")
        if not name:
            return jsonify({"ok": False, "error": "No plate selected."})
        src = resolve_file(name)
        # only allow deleting files that actually live in raw_data / uploads
        allowed = any(
            src.resolve() == (base / src.name).resolve() and src.exists()
            for base in (RAW_DIR, UPLOAD_DIR)
        )
        if not src.exists() or not allowed:
            return jsonify({"ok": False, "error": f"'{name}' not found."})
        src.unlink()
        # remove intake metadata under this plate key
        store = load_intake_store()
        k = norm_plate(name)
        if k in store:
            store.pop(k)
            save_intake_store(store)
        # remove stored per-file sample details/names if present
        for loader, saver in ((load_details_store, save_details_store),
                              (load_names_store, save_names_store)):
            st = loader()
            if name in st:
                st.pop(name)
                saver(st)
        return jsonify({"ok": True, "deleted": name})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/pt_save", methods=["POST"])
def pt_save():
    """Save one organized trough (plate + trough) into the intake store."""
    try:
        d = request.get_json(force=True) or {}
        plate = str(d.get("plate_id", "")).strip()
        if not plate:
            return jsonify({"ok": False, "error": "Plate is required."})
        tr = "2" if str(d.get("trough", "1")).strip().endswith("2") else "1"
        comp_type = d.get("comp_type") or "surfactant"
        rec = {
            "plate_id": plate, "trough": tr,
            "batch_id": str(d.get("batch_id", "")).strip(),
            "sample_id": str(d.get("sample_id", "")).strip(),
            "name": (str(d.get("name", "")).strip()
                     or str(d.get("description", "")).strip()),
            "tag": str(d.get("tag", "")).strip(),
            "sample_type": str(d.get("sample_type", "prototype")).strip() or "prototype",
            "description": str(d.get("description", "")).strip(),
            "chassis": str(d.get("chassis", "")).strip(),
            "co_surfactant": str(d.get("co_surfactant", "")).strip(),
            "co_surfactant_pct": str(d.get("co_surfactant_pct", "")).strip(),
            "concentration": str(d.get("concentration", "")).strip(),
            "ebr_batch_id": str(d.get("ebr_batch_id", "")).strip(),
            "enovia_id": str(d.get("enovia_id", "")).strip(),
            "variable": comp_type,
        }
        comp = str(d.get("component", "")).strip()
        if comp_type == "surfactant":
            rec["surfactant"] = comp
        else:
            rec["polymer"] = comp
        store = load_intake_store()
        store.setdefault(norm_plate(plate), {})[tr] = rec
        save_intake_store(store)
        set_plate_kind(plate, d.get("kind"))
        return jsonify({"ok": True})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/export_nexus")
def export_nexus():
    """Build the Nexus 'Beauty ANA PercentT Coacervation Profile' Flex Template
    (Reportable Data sheet) from every organized trough that has a Sample ID,
    and stream it for drop-in to the SDMS Import folder."""
    try:
        from nexus_fingerprint import export_nexus_template
        samples = []
        seen = set()

        # 1) explicitly organized troughs (intake store) -- Sample ID or Batch ID
        store = load_intake_store()
        for key, rec in store.items():
            for t in ("1", "2"):
                r = rec.get(t) or {}
                # prefer the Nexus Sample ID; fall back to Batch ID until S-ids exist
                sid = str(r.get("sample_id", "")).strip() or str(r.get("batch_id", "")).strip()
                if not sid:
                    continue
                plate = r.get("plate_id") or key
                try:
                    path = resolve_file(plate)
                except Exception:  # noqa: BLE001
                    continue
                if not path.exists():
                    continue
                dedup = (sid, str(path), int(t))
                if dedup in seen:
                    continue
                seen.add(dedup)
                samples.append({"sample_id": sid, "path": str(path), "trough": int(t)})

        # 2) every library sample that carries a Batch ID (e.g. the 24 0.4%
        #    shampoo formulas) -- exported straight from the run sheets, no
        #    re-entry needed. Nexus Sample IDs will supersede these once added.
        try:
            props = load_properties()
        except Exception:  # noqa: BLE001
            props = {}
        for row in _build_library(3.0, (1 / 11, 1 / 2), props):
            sid = str(row.get("sample_key", "")).strip()
            if not sid:
                continue
            try:
                path = resolve_file(row.get("file", ""))
            except Exception:  # noqa: BLE001
                continue
            if not path.exists():
                continue
            tr = int(row.get("trough", 1))
            dedup = (sid, str(path), tr)
            if dedup in seen:
                continue
            seen.add(dedup)
            samples.append({"sample_id": sid, "path": str(path), "trough": tr,
                            "sheet": row.get("sheet") or None})

        if not samples:
            return jsonify({"ok": False, "error": "No samples have a Sample ID or Batch ID yet. "
                            "Add IDs in Organize samples, Save all, then export."})
        exports = Path("exports"); exports.mkdir(exist_ok=True)
        out = exports / "nexus_percentT_export.xlsx"
        export_nexus_template(samples, str(out))
        return send_file(out, as_attachment=True,
                         download_name="nexus_percentT_export.xlsx")
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


def _match_norm_stem(name):
    """Normalise a raw/plate or input-sheet file name for matching:
    drop an 'in '/'out ' prefix, the YYYYMMDD date, an 'opaque' tag and any
    non-alphanumerics -> 'in 20260915_BC128o_3196_NatCaready_200uL.xlsx' and
    'BC128o_3196_NatCaready_200uL.txt' both collapse to the same key."""
    s = os.path.splitext(str(name))[0].lower()
    s = re.sub(r"^(in|out|raw)[\s_]+", "", s)
    s = re.sub(r"\b20\d{6}\b", "", s)
    s = re.sub(r"\bopaque\b", "", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s


def _match_raw_to_meta(meta_name, raw_names, raw_by_code):
    """Pair an input-sheet (metadata) file with its raw plate file. Tries, in
    order: normalised-stem exact match, plate-code match, then best fuzzy match
    (difflib) above 0.55. Returns the raw file name or None."""
    import difflib
    target = _match_norm_stem(meta_name)
    stems = {_match_norm_stem(r): r for r in raw_names}
    if target in stems:
        return stems[target]
    code_hit = raw_by_code.get(plate_code(meta_name))
    if code_hit:
        return code_hit
    if raw_names:
        best = max(raw_names, key=lambda r: difflib.SequenceMatcher(
            None, target, _match_norm_stem(r)).ratio())
        ratio = difflib.SequenceMatcher(None, target, _match_norm_stem(best)).ratio()
        if ratio >= 0.55:
            return best
    return None


@app.route("/ingest_pt", methods=["POST"])
def ingest_pt():
    """Digitized %T ingest: upload raw .txt plate file(s) + their metadata
    sheet(s). Pairs them by plate code, auto-parses each Description into
    chassis / component / %, and stores the metadata (no intake workbook)."""
    try:
        component = (request.form.get("component") or "").strip()
        comp_type = request.form.get("comp_type") or "surfactant"
        kind = (request.form.get("kind") or "").strip().lower()
        files = request.files.getlist("files")
        if not files:
            return jsonify({"ok": False, "error": "No files provided."})
        RAW_DIR.mkdir(exist_ok=True)
        saved_raw, saved_meta = [], []
        for f in files:
            if not f or not f.filename:
                continue
            name = f.filename
            dest = RAW_DIR / name
            f.save(dest)
            if name.lower().endswith(".txt"):
                saved_raw.append(name)
                set_plate_kind(name, kind)
            elif name.lower().endswith((".xlsx", ".xlsm")):
                saved_meta.append(name)

        # index every raw .txt in raw_data by plate code (uploaded + existing)
        raw_names_all = [p.name for p in RAW_DIR.iterdir() if p.suffix.lower() == ".txt"]
        raw_by_code = {}
        for name in raw_names_all:
            raw_by_code.setdefault(plate_code(name), name)

        store = load_intake_store()
        review, warnings = [], []
        for meta_name in saved_meta:
            raw_name = _match_raw_to_meta(meta_name, raw_names_all, raw_by_code)
            if not raw_name:
                warnings.append(f"'{meta_name}': no matching raw plate file found "
                                f"(upload the .txt too, or rename so the names align).")
                continue
            try:
                samples = parse_metadata_sheet(RAW_DIR / meta_name, component, comp_type)
            except Exception as ex:  # noqa: BLE001
                warnings.append(f"'{meta_name}': {ex}")
                continue
            key = norm_plate(raw_name)
            store.setdefault(key, {})
            set_plate_kind(raw_name, kind)
            for s in samples:
                s["plate_id"] = raw_name
                store[key][s["trough"]] = s
                review.append({"raw_file": raw_name, "trough": s["trough"],
                               "batch_id": s.get("batch_id", ""),
                               "chassis": s.get("chassis", ""),
                               "component": s.get("surfactant") or s.get("polymer") or "",
                               "concentration": s.get("concentration", ""),
                               "description": s.get("description", "")})
        save_intake_store(store)
        return jsonify({"ok": True, "review": review, "warnings": warnings,
                        "n_raw": len(saved_raw), "n_meta": len(saved_meta),
                        "files": list_raw_txt()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/deposition_models", methods=["GET", "POST"])
def deposition_models():
    """List or add/update deposition correlation models (upsert by name)."""
    try:
        if request.method == "GET":
            return jsonify({"ok": True, "models": load_depo_models()})
        data = request.get_json(force=True)
        name = str(data.get("name", "")).strip()
        if not name:
            return jsonify({"ok": False, "error": "Model name is required."})
        entry = {
            "name": name,
            "outcome": data.get("outcome", "PO deposition"),
            "predictor": data.get("predictor", "mw_cd"),
            "slope": float(data.get("slope", 0) or 0),
            "intercept": float(data.get("intercept", 0) or 0),
            "r2": (float(data["r2"]) if str(data.get("r2", "")).strip() != "" else None),
            "units": data.get("units", "ug/cm^2"),
            "baseline": (float(data["baseline"]) if str(data.get("baseline", "")).strip() != "" else None),
            "chassis_context": data.get("chassis_context", ""),
            "source": data.get("source", ""),
            "priority": int(data.get("priority", 1) or 1),
        }
        models = [m for m in load_depo_models() if m.get("name") != name]
        models.append(entry)
        save_depo_models(models)
        return jsonify({"ok": True, "models": models})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/deposition_models_delete", methods=["POST"])
def deposition_models_delete():
    """Remove a deposition model by name."""
    try:
        name = str(request.get_json(force=True).get("name", "")).strip()
        models = [m for m in load_depo_models() if m.get("name") != name]
        save_depo_models(models)
        return jsonify({"ok": True, "models": models})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/deposition_reset", methods=["POST"])
def deposition_reset():
    """Restore the default (Project Zorro) deposition models."""
    save_depo_models(list(DEFAULT_MODELS))
    return jsonify({"ok": True, "models": load_depo_models()})


@app.route("/deposition_plot", methods=["POST"])
def deposition_plot():
    """Render a deposition visualization across the whole sample library."""
    try:
        data = request.get_json(force=True)
        timepoint = float(data.get("timepoint", 3.0))
        x1 = float(data.get("auc_dil_1", 1))
        x2 = float(data.get("auc_dil_2", 10))
        f1, f2 = 1.0 / (1.0 + x1), 1.0 / (1.0 + x2)
        window = (min(f1, f2), max(f1, f2))
        kind = data.get("kind", "ranking")
        props = load_properties()
        models = load_depo_models()
        rows = _build_library(timepoint, window, props)
        outcome = models[0].get("outcome", "PO deposition") if models else "PO deposition"
        fig = plot_deposition(rows, models, kind=kind, outcome_label=outcome)
        img = fig_to_base64(fig)
        n_pred = sum(1 for r in rows if r.get("pred_depo") is not None)
        return jsonify({"ok": True, "image": img, "n_samples": len(rows),
                        "n_predicted": n_pred})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/rename", methods=["POST"])
def rename():
    """Rename an existing raw file to {chassis}_{polymer}_{concentration}."""
    try:
        data = request.get_json(force=True)
        old = data.get("old", "")
        if not old:
            return jsonify({"ok": False, "error": "No file selected."})
        src = resolve_file(old)
        ext = src.suffix or ".txt"
        name = safe_filename(data.get("name", ""), ext)
        if not name:
            return jsonify(
                {"ok": False, "error": "Enter a file name."}
            )
        dest = RAW_DIR / name
        if dest.exists() and dest.resolve() != src.resolve():
            return jsonify({"ok": False, "error": f"'{name}' already exists."})
        src.rename(dest)
        return jsonify({"ok": True, "filename": name, "files": list_raw_txt()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


# --------------------------------------------------------------------------- #
# Cloud storage (Azure Blob) - shared data + upload workflow
# --------------------------------------------------------------------------- #
def _experiment_frames(fname, sheet, timepoint, window, props):
    """Build (well_df, sample_df) for one plate/run, ready for blob upload.

    * ``sample_df`` - one row per trough (reuses the library builder: AUC,
      fingerprint, chassis/polymer, batch id, deposition prediction).
    * ``well_df`` - well-level long table with the full curves (all timepoints),
      %T and absorbance, joined to each trough's sample metadata.
    """
    path = resolve_file(fname)
    sample_rows: list[dict] = []
    _library_samples(sample_rows, fname, sheet, path, timepoint, window, props)
    _overlay_products(sample_rows)
    sample_df = pd.DataFrame(sample_rows)

    try:
        df = parse_and_annotate(path, sheet)
    except Exception:  # noqa: BLE001
        df = None
    well_rows: list[dict] = []
    if df is not None and not df.empty:
        meta_by_trough = {int(r["trough"]): r for r in sample_rows if r.get("trough")}
        sub = df.dropna(subset=["formula_fraction"]).copy()
        sub["absorbance"] = transmittance_to_absorbance(
            sub["transmission_pct"].to_numpy())
        for _, w in sub.iterrows():
            tr = int(w["trough"])
            m = meta_by_trough.get(tr, {})
            ff = float(w["formula_fraction"])
            temp = w.get("temperature_c")
            well_rows.append({
                "file": fname, "sheet": sheet or "", "trough": tr,
                "sample_name": sample_display_name(m) if m else f"Sample {tr}",
                "batch_id": m.get("sample_key", ""),
                "chassis": m.get("chassis", ""),
                "component": m.get("component", ""),
                "concentration": m.get("concentration", ""),
                "well": w.get("well", ""),
                "timepoint_min": round(float(w["timepoint_minutes"]), 3),
                "formula_fraction": round(ff, 6),
                "dilution_ratio": round(float(dilution_ratio(ff)), 3),
                "transmission_pct": round(float(w["transmission_pct"]), 4),
                "absorbance": round(float(w["absorbance"]), 5),
                "temperature_c": round(float(temp), 2) if pd.notna(temp) else None,
            })
    well_df = pd.DataFrame(well_rows)
    return well_df, sample_df


@app.route("/blob_status")
def blob_status():
    """Report whether Azure Blob is configured and list uploaded experiments."""
    try:
        client = cblob.AzureBlobClient()
        st = client.status()
        st["experiments"] = cblob.list_experiments(client) if st["configured"] else []
        return jsonify({"ok": True, **st})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/blob_experiments")
def blob_experiments():
    """List uploaded experiments (manifest, newest first)."""
    try:
        return jsonify({"ok": True, "experiments": cblob.list_experiments()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/blob_upload", methods=["POST"])
def blob_upload():
    """Upload one plate/run to Azure Blob (append-merged, manifest-guarded)."""
    try:
        data = request.get_json(force=True)
        fname = data.get("file", "")
        if not fname:
            return jsonify({"ok": False, "error": "Choose a plate file to upload."})
        sheet = data.get("sheet") or None
        timepoint = float(data.get("timepoint", 3.0))
        x1 = float(data.get("auc_dil_1", 1))
        x2 = float(data.get("auc_dil_2", 20))
        f1, f2 = 1.0 / (1.0 + x1), 1.0 / (1.0 + x2)
        window = (min(f1, f2), max(f1, f2))
        props = load_properties()
        well_df, sample_df = _experiment_frames(fname, sheet, timepoint, window, props)
        if sample_df.empty and well_df.empty:
            return jsonify({"ok": False,
                            "error": "No parseable samples found in that file."})
        exp_id = str(data.get("experiment_id") or "").strip()
        if not exp_id:
            stem = Path(fname).stem
            exp_id = f"{stem}|{sheet}" if sheet else stem
        samples = ", ".join(sorted({
            str(r.get("sample_key") or sample_display_name(r))
            for r in sample_df.to_dict("records")
        })) if not sample_df.empty else ""
        meta = {
            "source_file": fname, "sheet": sheet or "",
            "purpose": data.get("purpose", ""),
            "submitter": data.get("submitter", ""),
            "worksheet_id": data.get("worksheet_id", ""),
            "samples": samples,
        }
        res = cblob.merge_and_upload_experiment(exp_id, well_df, sample_df, meta)
        return jsonify({
            "ok": True,
            "skipped": res.get("skipped", False),
            "message": res.get("message", ""),
            "entry": res.get("entry"),
            "experiments": cblob.list_experiments(),
        })
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


@app.route("/blob_delete", methods=["POST"])
def blob_delete():
    """Delete one experiment's rows + manifest entry from Azure Blob."""
    try:
        data = request.get_json(force=True)
        exp_id = str(data.get("experiment_id", "")).strip()
        if not exp_id:
            return jsonify({"ok": False, "error": "No experiment id provided."})
        res = cblob.delete_experiment(exp_id)
        res["experiments"] = cblob.list_experiments()
        return jsonify(res)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


@app.route("/blob_preview")
def blob_preview():
    """Retrieve the stored cloud tables and return a small JSON preview.

    Optional query args: ``experiment_id`` (filter to one experiment) and
    ``limit`` (max preview rows per table, default 25).
    """
    try:
        client = cblob.AzureBlobClient()
        if not client.configured:
            return jsonify({"ok": False, "error": "Azure Blob not configured."})
        well_df, sample_df = cblob.download_tables(client)
        exp_id = str(request.args.get("experiment_id", "")).strip()
        if exp_id:
            if not well_df.empty and "Experiment_ID" in well_df.columns:
                well_df = well_df[well_df["Experiment_ID"].astype(str) == exp_id]
            if not sample_df.empty and "Experiment_ID" in sample_df.columns:
                sample_df = sample_df[sample_df["Experiment_ID"].astype(str) == exp_id]
        try:
            limit = max(1, int(request.args.get("limit", 25)))
        except (TypeError, ValueError):
            limit = 25

        def _frame(df):
            if df is None or df.empty:
                return {"columns": [], "rows": [], "total": 0}
            safe = df.head(limit).where(pd.notna(df.head(limit)), None)
            return {
                "columns": list(df.columns),
                "rows": safe.to_dict("records"),
                "total": int(len(df)),
            }

        return jsonify({
            "ok": True,
            "experiment_id": exp_id,
            "wells": _frame(well_df),
            "samples": _frame(sample_df),
        })
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


@app.route("/blob_download")
def blob_download():
    """Retrieve all stored cloud data as a two-sheet Excel workbook.

    Optional query arg ``experiment_id`` scopes the download to one experiment.
    """
    try:
        client = cblob.AzureBlobClient()
        if not client.configured:
            return jsonify({"ok": False, "error": "Azure Blob not configured."})
        well_df, sample_df = cblob.download_tables(client)
        exp_id = str(request.args.get("experiment_id", "")).strip()
        if exp_id:
            if not well_df.empty and "Experiment_ID" in well_df.columns:
                well_df = well_df[well_df["Experiment_ID"].astype(str) == exp_id]
            if not sample_df.empty and "Experiment_ID" in sample_df.columns:
                sample_df = sample_df[sample_df["Experiment_ID"].astype(str) == exp_id]
        if well_df.empty and sample_df.empty:
            return jsonify({"ok": False,
                            "error": "No cloud data to download yet."})
        out = io.BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as writer:
            (well_df if not well_df.empty else pd.DataFrame()).to_excel(
                writer, sheet_name="CoacervationData", index=False)
            (sample_df if not sample_df.empty else pd.DataFrame()).to_excel(
                writer, sheet_name="CoacervationSamples", index=False)
        out.seek(0)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{exp_id}" if exp_id else ""
        fname = f"CoacervationCloud{suffix}_{stamp}.xlsx"
        return send_file(
            out, as_attachment=True, download_name=fname,
            mimetype="application/vnd.openxmlformats-officedocument."
                     "spreadsheetml.sheet")
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


# --------------------------------------------------------------------------- #
# Databricks / Nexus reagent + sample lookup
# --------------------------------------------------------------------------- #
@app.route("/nexus_status")
def nexus_status():
    """Report Databricks/Nexus readiness (does not open a connection)."""
    try:
        return jsonify({"ok": True, **cnx.status()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/nexus_lookup", methods=["POST"])
def nexus_lookup():
    """Look up Nexus-recorded parameters for sample BatchIDs.

    Body: ``{"batch_ids": [...]}`` and/or ``{"from_library": true}`` to pull every
    BatchID currently known to the sample library.
    """
    try:
        data = request.get_json(force=True)
        batch_ids = list(data.get("batch_ids") or [])
        if data.get("from_library"):
            props = load_properties()
            for r in _build_library(3.0, None, props):
                bid = str(r.get("sample_key") or "").strip()
                if bid:
                    batch_ids.append(bid)
        batch_ids = sorted({str(b).strip() for b in batch_ids if str(b).strip()})
        if not batch_ids:
            return jsonify({"ok": False,
                            "error": "No BatchIDs to look up (none provided and "
                                     "none found in the library)."})
        grouped = cnx.lookup_batches(batch_ids)
        flat = [{"batch_id": b, **p}
                for b, info in grouped.items() for p in info["params"]]
        found = sorted(grouped.keys())
        missing = [b for b in batch_ids if b not in grouped]
        return jsonify({"ok": True, "requested": batch_ids, "found": found,
                        "missing": missing, "rows": flat, "grouped": grouped})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


@app.route("/nexus_batch_report", methods=["POST"])
def nexus_batch_report():
    """Full Nexus report (details/samples/test results/QA/genealogy) for a BatchID."""
    try:
        batch_id = str(request.get_json(force=True).get("batch_id", "")).strip()
        if not batch_id:
            return jsonify({"ok": False, "error": "Enter a Batch ID (B-...)."})
        if not cnx.status().get("ready"):
            return jsonify({"ok": False,
                            "error": "Databricks/Nexus not configured (no token)."})
        return jsonify(cnx.batch_report(batch_id))
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


@app.route("/formula_composition", methods=["POST"])
def formula_composition():
    """Nexus->Enovia ingredient breakdown for a BatchID (for the donut panel)."""
    try:
        batch_id = str(request.get_json(force=True).get("batch_id", "")).strip()
        if not batch_id:
            return jsonify({"ok": False, "error": "Enter a Batch ID (B-...)."})
        if not cnx.status().get("ready"):
            return jsonify({"ok": False,
                            "error": "Databricks/Nexus not configured (no token)."})
        return jsonify(cnx.formula_composition(batch_id))
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


@app.route("/batch_overview", methods=["POST"])
def batch_overview():
    """One-stop lookup for a Batch ID: formula, Nexus test coverage, and which
    in-app data (%T, Lasentec, ILS/PTL/consumer) exists for it."""
    try:
        bid = str(request.get_json(force=True).get("batch_id", "")).strip()
        if not bid:
            return jsonify({"ok": False, "error": "Enter a Batch ID (B-...)."})
        ready = cnx.status().get("ready")
        out = {"ok": True, "batch_id": bid, "nexus_ready": bool(ready)}

        # Nexus -> Enovia formula
        try:
            out["formula"] = (cnx.formula_composition(bid) if ready
                              else {"ok": False, "note": "Databricks/Nexus not configured."})
        except Exception as e:  # noqa: BLE001
            out["formula"] = {"ok": False, "note": str(e)}

        # Nexus batch report = authoritative "what tests exist"
        try:
            rep = cnx.batch_report(bid) if ready else {"ok": False}
            out["report"] = {
                "ok": rep.get("ok", False),
                "counts": rep.get("counts", {}),
                "test_summary": rep.get("test_summary", []),
                "samples": (rep.get("samples") or [])[:25],
                "genealogy": (rep.get("genealogy") or [])[:25],
                "qa_results": (rep.get("qa_results") or [])[:25],
                "note": rep.get("note", ""),
            }
        except Exception as e:  # noqa: BLE001
            out["report"] = {"ok": False, "note": str(e)}

        # In-app data coverage
        coverage = {}
        try:
            props = load_properties()
            runs = [{"name": sample_display_name(r), "file": r.get("file", ""),
                     "sheet": r.get("sheet", ""), "trough": r.get("trough"),
                     "auc": r.get("auc"), "onset": r.get("onset")}
                    for r in _build_library(3.0, None, props)
                    if str(r.get("sample_key") or "").strip() == bid]
            coverage["pct"] = {"n": len(runs), "runs": runs}
        except Exception:  # noqa: BLE001
            coverage["pct"] = {"n": 0, "runs": []}
        try:
            las = [{"name": r.get("name", ""), "key": r.get("key", "")}
                   for r in clas.load_store()
                   if str(r.get("batch_id") or "").strip() == bid]
            coverage["lasentec"] = {"n": len(las), "records": las}
        except Exception:  # noqa: BLE001
            coverage["lasentec"] = {"n": 0, "records": []}
        try:
            jb = cperf.joined_by_batch()
            rec = jb.get(bid.strip().lower(), {})
            coverage["perf"] = {k: (k in rec) for k in cperf.KINDS}
        except Exception:  # noqa: BLE001
            coverage["perf"] = {}
        out["coverage"] = coverage
        return jsonify(out)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


@app.route("/perf/search_batches", methods=["GET"])
def perf_search_batches():
    """Type-ahead search over Nexus batches (id or description)."""
    try:
        if not cnx.status().get("ready"):
            return jsonify({"ok": False, "results": [],
                            "error": "Databricks/Nexus not configured (no token)."})
        term = request.args.get("q", "")
        return jsonify({"ok": True, "results": cnx.search_batches(term)})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "results": [], "error": str(e)})


@app.route("/perf/batch_comparison", methods=["POST"])
def perf_batch_comparison():
    """Average Nexus test parameters per batch for the chosen test groups."""
    try:
        if not cnx.status().get("ready"):
            return jsonify({"ok": False,
                            "error": "Databricks/Nexus not configured (no token)."})
        body = request.get_json(force=True) or {}
        batch_ids = body.get("batch_ids") or []
        test_groups = body.get("test_groups") or []
        return jsonify(cnx.batch_comparison(batch_ids, test_groups))
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


@app.route("/perf/search_ingredients", methods=["GET"])
def perf_search_ingredients():
    """Type-ahead search over Enovia raw materials (GCAS or title)."""
    try:
        if not cnx.status().get("ready"):
            return jsonify({"ok": False, "results": [],
                            "error": "Databricks/Nexus not configured (no token)."})
        return jsonify({"ok": True,
                        "results": cnx.search_ingredients(request.args.get("q", ""))})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "results": [], "error": str(e)})


@app.route("/perf/search_requests", methods=["GET"])
def perf_search_requests():
    """Type-ahead search over Nexus request ids."""
    try:
        if not cnx.status().get("ready"):
            return jsonify({"ok": False, "results": [],
                            "error": "Databricks/Nexus not configured (no token)."})
        return jsonify({"ok": True,
                        "results": cnx.search_requests(request.args.get("q", ""))})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "results": [], "error": str(e)})


@app.route("/perf/ingredient_comparison", methods=["POST"])
def perf_ingredient_comparison():
    """Average test parameters across all formulations with each ingredient."""
    try:
        if not cnx.status().get("ready"):
            return jsonify({"ok": False,
                            "error": "Databricks/Nexus not configured (no token)."})
        body = request.get_json(force=True) or {}
        return jsonify(cnx.ingredient_comparison(
            body.get("gcas_list") or [], body.get("test_groups") or []))
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


@app.route("/perf/ingredient_dose_response", methods=["POST"])
def perf_ingredient_dose_response():
    """Dose-response: ingredient level (%) vs each performance parameter."""
    try:
        if not cnx.status().get("ready"):
            return jsonify({"ok": False,
                            "error": "Databricks/Nexus not configured (no token)."})
        body = request.get_json(force=True) or {}
        return jsonify(cnx.ingredient_dose_response(
            body.get("gcas"), body.get("test_groups") or [],
            min_pct=body.get("min_pct"), max_pct=body.get("max_pct")))
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


@app.route("/perf/chassis_comparison", methods=["POST"])
def perf_chassis_comparison():
    """Average test parameters per chassis family (batch-description patterns)."""
    try:
        if not cnx.status().get("ready"):
            return jsonify({"ok": False,
                            "error": "Databricks/Nexus not configured (no token)."})
        body = request.get_json(force=True) or {}
        return jsonify(cnx.chassis_comparison(
            body.get("chassis_keys") or [], body.get("test_groups") or [],
            ingredient_gcas=body.get("ingredient_gcas"),
            custom_patterns=body.get("custom_patterns") or []))
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


@app.route("/perf/request_results", methods=["POST"])
def perf_request_results():
    """All batches + test results under one or more Nexus request ids."""
    try:
        if not cnx.status().get("ready"):
            return jsonify({"ok": False,
                            "error": "Databricks/Nexus not configured (no token)."})
        body = request.get_json(force=True) or {}
        return jsonify(cnx.request_results(
            body.get("request_ids") or [], body.get("test_groups") or []))
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


@app.route("/perf/corr_test_types", methods=["GET"])
def perf_corr_test_types():
    """Test types available for the X / Y axes of a correlation."""
    return jsonify({"ok": True,
                    "results": [{"id": t, "label": l} for t, l in cnx.CORR_TEST_TYPES],
                    "presets": cnx.CORR_PRESETS})


@app.route("/perf/parameters", methods=["GET"])
def perf_parameters():
    """Distinct numeric parameters for a given test type (for dropdowns)."""
    try:
        if not cnx.status().get("ready"):
            return jsonify({"ok": False, "results": [],
                            "error": "Databricks/Nexus not configured (no token)."})
        return jsonify({"ok": True,
                        "results": cnx.list_parameters(request.args.get("test_type", ""))})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "results": [], "error": str(e)})


@app.route("/perf/correlation", methods=["POST"])
def perf_correlation():
    """Scatter of one parameter vs another per batch, with regression stats."""
    try:
        if not cnx.status().get("ready"):
            return jsonify({"ok": False,
                            "error": "Databricks/Nexus not configured (no token)."})
        b = request.get_json(force=True) or {}
        return jsonify(cnx.correlation(b.get("x_test_type"), b.get("x_param"),
                                       b.get("y_test_type"), b.get("y_param")))
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


def _perf_dashboard(fn, *extra_keys):
    """Shared wrapper for the ILS/PTL dashboard endpoints."""
    if not cnx.status().get("ready"):
        return jsonify({"ok": False,
                        "error": "Databricks/Nexus not configured (no token)."})
    body = request.get_json(force=True) or {}
    args = [body.get("batch_ids") or []]
    for k in extra_keys:
        args.append(body.get(k))
    return jsonify(fn(*args))


@app.route("/perf/ils_results", methods=["POST"])
def perf_ils_results():
    """All ILS sensory data (Prep / Wet / Dry) for a set of batches."""
    try:
        return _perf_dashboard(cnx.ils_results)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/perf/sacs_results", methods=["POST"])
def perf_sacs_results():
    """Replicate-level SACS Dry/Wet data for a set of batches."""
    try:
        return _perf_dashboard(cnx.sacs_results)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/perf/drf_profile", methods=["POST"])
def perf_drf_profile():
    """DRF rinse-friction / wet-feel profile for a set of batches + variant."""
    try:
        body = request.get_json(force=True) or {}
        if not cnx.status().get("ready"):
            return jsonify({"ok": False,
                            "error": "Databricks/Nexus not configured (no token)."})
        return jsonify(cnx.drf_profile(body.get("batch_ids") or [],
                                       body.get("variant") or "Liquid Shampoo"))
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/perf/iff_results", methods=["POST"])
def perf_iff_results():
    """Inter-fiber friction (Texture Analyzer) for a set of batches."""
    try:
        return _perf_dashboard(cnx.iff_results)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/perf/search_worksheets", methods=["GET"])
def perf_search_worksheets():
    """Type-ahead search over Nexus worksheets."""
    try:
        if not cnx.status().get("ready"):
            return jsonify({"ok": False, "results": [],
                            "error": "Databricks/Nexus not configured (no token)."})
        return jsonify({"ok": True,
                        "results": cnx.search_worksheets(request.args.get("q", ""))})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "results": [], "error": str(e)})


@app.route("/lookup/request", methods=["POST"])
def lookup_request_route():
    """Request header + all samples/batches with test-coverage badges."""
    try:
        if not cnx.status().get("ready"):
            return jsonify({"ok": False,
                            "error": "Databricks/Nexus not configured (no token)."})
        rid = str((request.get_json(force=True) or {}).get("id", "")).strip()
        return jsonify(cnx.lookup_request(rid))
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/lookup/worksheet", methods=["POST"])
def lookup_worksheet_route():
    """Worksheet header + all batches with test-coverage badges."""
    try:
        if not cnx.status().get("ready"):
            return jsonify({"ok": False,
                            "error": "Databricks/Nexus not configured (no token)."})
        wid = str((request.get_json(force=True) or {}).get("id", "")).strip()
        return jsonify(cnx.lookup_worksheet(wid))
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


def _library_batch_ids(timepoint: float = 3.0):
    """All distinct Batch IDs in the sample library (for formula indexing)."""
    props = load_properties()
    ids = []
    for r in _build_library(timepoint, None, props):
        bid = str(r.get("sample_key") or "").strip()
        if bid:
            ids.append(bid)
    return sorted(set(ids))


@app.route("/ingredient_refresh", methods=["POST"])
def ingredient_refresh():
    """Cache Enovia formulas for library batch ids, then return the index."""
    try:
        if not cnx.status().get("ready"):
            return jsonify({"ok": False,
                            "error": "Databricks/Nexus not configured (no token)."})
        limit = int((request.get_json(silent=True) or {}).get("limit", 40))
        stats = csf.ensure_for_batches(_library_batch_ids(), limit=limit)
        return jsonify({"ok": True, **stats, "index": csf.ingredient_index()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


@app.route("/ingredient_index", methods=["GET"])
def ingredient_index_route():
    """Return the cached ingredient index (name + how many batches have it)."""
    try:
        return jsonify({"ok": True, "index": csf.ingredient_index()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/samples_by_ingredient", methods=["POST"])
def samples_by_ingredient():
    """Return library samples whose formula contains the selected ingredient(s).

    Body: ``{"ingredients": [...], "mode": "and"|"or"}``. Each returned sample
    includes its coacervation fingerprint metrics (auc, onset, breadth) so the
    user can see whether a given ingredient set yields similar %T profiles.
    """
    try:
        data = request.get_json(force=True) or {}
        selected = list(data.get("ingredients") or [])
        mode = str(data.get("mode", "and")).lower()
        if not selected:
            return jsonify({"ok": False, "error": "Select at least one ingredient."})
        store = csf.load_store()
        batch_set = csf.batches_with_ingredients(selected, mode, store=store)
        if not batch_set:
            return jsonify({"ok": True, "n": 0, "samples": [], "mode": mode,
                            "ingredients": selected})
        props = load_properties()
        out = []
        for r in _build_library(3.0, None, props):
            bid = str(r.get("sample_key") or "").strip()
            if bid not in batch_set:
                continue
            fp = (store.get(bid) or {})
            matched = [i for i in (fp.get("ingredients") or [])
                       if csf._norm(i) in {csf._norm(s) for s in selected}]
            link = (str(r.get("file") or ""), str(r.get("sheet") or ""),
                    str(r.get("trough") or ""))
            out.append({
                "id": "|".join(link),
                "name": sample_display_name(r),
                "identity": formulation_identity(r),
                "batch_id": bid,
                "product": fp.get("product", ""),
                "file": r.get("file", ""), "sheet": r.get("sheet", ""),
                "trough": r.get("trough"),
                "matched_ingredients": matched,
                "auc": r.get("auc"), "onset": r.get("onset"),
                "peak": r.get("peak"), "width": r.get("width"),
                "strength": r.get("strength"),
            })
        # sort by AUC desc so similar strong coacervators group visually
        out.sort(key=lambda s: (s.get("auc") is None, -(s.get("auc") or 0)))
        return jsonify({"ok": True, "n": len(out), "samples": out,
                        "mode": mode, "ingredients": selected})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


@app.route("/composition_status")
def composition_status():
    """Readiness of the composition resolver (EBR/Enovia/Mintel). No connection."""
    try:
        return jsonify({"ok": True, **ccomp.status()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/composition_lookup", methods=["POST"])
def composition_lookup():
    """Resolve composition for one product/sample, routed internal vs external.

    Body: a product dict (category/tag, batch_id, sample_id, ebr_ref, gtin,
    brand, name) OR ``{"product_name": "..."}`` to pull it from the catalog.
    """
    try:
        data = request.get_json(force=True) or {}
        prod = data
        pname = str(data.get("product_name", "")).strip()
        link_file = str(data.get("file", "")).strip()
        link_sheet = str(data.get("sheet", "")).strip()
        link_trough = str(data.get("trough", "")).strip()
        if pname:
            match = next((p for p in load_products_store()
                          if canon_key(p.get("name", "")) == canon_key(pname)), None)
            # Fallback: a catalogued product linked to this plotted file/trough,
            # so INCI resolves even when the trough name differs from the product.
            if not match and link_file and link_trough:
                match = next((p for p in load_products_store()
                              if str(p.get("file") or "") == link_file
                              and str(p.get("sheet") or "") == link_sheet
                              and str(p.get("trough") or "") == link_trough), None)
            if not match:
                # Internal %T / prototype sample: resolve by the plotted
                # file/trough. If it carries a Batch ID, pull its EBR as-made
                # formula; otherwise return its identity with guidance.
                if link_file and link_trough in ("1", "2"):
                    try:
                        det = (resolve_details(link_file, link_sheet or None)
                               or {}).get(link_trough) or {}
                    except Exception:  # noqa: BLE001
                        det = {}
                    bid = (str(det.get("ebr_batch_id") or "").strip()
                           or str(det.get("batch_id") or "").strip())
                    sid = str(det.get("sample_id") or "").strip()
                    identity = formulation_identity(det)
                    if bid or sid:
                        res = ccomp.resolve_composition(
                            {"category": "development", "name": pname,
                             "batch_id": bid or sid, "sample_id": sid,
                             "ebr_ref": bid},
                            worksheet=bool(data.get("worksheet")))
                        out = {"ok": res.get("ok", False), **res,
                               "identity": identity}
                        if bid:
                            out["batch_id"] = bid
                        if not res.get("rows"):
                            out["note"] = (
                                f"Internal prototype linked to Batch {bid or sid}; "
                                "no EBR as-made rows, but the formula composition "
                                "below pulls from Nexus/Enovia.")
                        return jsonify(out)
                    if identity:
                        return jsonify({
                            "ok": True, "route": "organized",
                            "source": "sample_details", "name": pname,
                            "identity": identity,
                            "chassis": det.get("chassis", ""),
                            "polymer": det.get("polymer", ""),
                            "surfactant": det.get("surfactant", ""),
                            "co_surfactant": det.get("co_surfactant", ""),
                            "co_surfactant_pct": det.get("co_surfactant_pct", ""),
                            "concentration": det.get("concentration", ""),
                            "sample_type": det.get("sample_type", "prototype"),
                            "note": ("Internal prototype — no Batch ID or Nexus "
                                     "Sample ID linked yet. Add a Batch ID in "
                                     "Manage data to pull its EBR as-made formula."),
                        })
                lookup = _organized_sample_lookup()
                meta = lookup.get(pname.lower())
                if not meta:
                    meta = next((v for k, v in lookup.items()
                                 if canon_key(k) == canon_key(pname)), None)
                if meta:
                    return jsonify({
                        "ok": True,
                        "route": "organized",
                        "source": "intake_store",
                        "name": pname,
                        "note": "Organized prototype/R&D sample metadata from Manage data; not a finished-product catalog entry.",
                        **meta,
                    })
                return jsonify({"ok": False, "error": f"Product '{pname}' not in catalog."})
            prod = {**match, "name": match.get("name", pname)}
        res = ccomp.resolve_composition(prod, worksheet=bool(data.get("worksheet")))
        return jsonify({"ok": res.get("ok", False), **res})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/pt_nexus_batch", methods=["POST"])
def pt_nexus_batch():
    """Pull composition for ONE BatchID during Organize (inline lookup).

    Returns the recorded Nexus parameters for the batch plus best-effort
    suggestions to fill Description/Chassis. Degrades gracefully when Nexus
    (Databricks) is not configured so the Organize table still works offline.
    """
    try:
        batch_id = str(request.get_json(force=True).get("batch_id", "")).strip()
        if not batch_id:
            return jsonify({"ok": False, "error": "No BatchID provided."})
        st = cnx.status()
        if not st.get("ready"):
            return jsonify({"ok": False, "configured": False,
                            "error": "Nexus (Databricks) not configured \u2014 set "
                                     "DATABRICKS_ACCESS_TOKEN to enable composition pull."})
        grouped = cnx.lookup_batches([batch_id])
        info = grouped.get(batch_id)
        if not info:
            return jsonify({"ok": True, "configured": True, "found": False,
                            "batch_id": batch_id, "params": []})
        params = info["params"]
        # best-effort suggestions from recorded params
        suggest = {}
        for p in params:
            name = str(p.get("parameter", "")).lower()
            val = str(p.get("value", "")).strip()
            if not val:
                continue
            if "chassis" in name or "base" in name:
                suggest.setdefault("chassis", val)
            if "description" in name or "formula" in name or "product" in name:
                suggest.setdefault("description", val)
            if "polymer" in name or "component" in name:
                suggest.setdefault("component", val)
            if "concentration" in name or name.endswith("%") or "level" in name:
                suggest.setdefault("concentration", val)
        return jsonify({"ok": True, "configured": True, "found": True,
                        "batch_id": batch_id, "params": params,
                        "n_params": info.get("n_params", len(params)),
                        "suggest": suggest})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e),
                        "trace": traceback.format_exc()})


# --------------------------------------------------------------------------- #
# Trends: coacervation features vs claims / consumer feel
# --------------------------------------------------------------------------- #
# Controlled vocabulary (keyword -> canonical tag) so free-text claims and
# consumer-feel notes become analyzable categories.
CLAIM_TAGS = {
    "clarifying": ["clarif", "detox", "deep clean", "deep-clean", "deep cleans",
                   "buildup", "build-up", "purif", "chelat", "hard water",
                   "hard-water", "remove"],
    "volumizing": ["volum", "fullness", "body", "thickening", "densif"],
    "moisturizing": ["moistur", "hydrat", "nourish"],
    "smoothing/repair": ["smooth", "frizz", "sleek", "keratin", "repair",
                         "bond", "peptide"],
    "curl": ["curl", "coil", "textured"],
    "sulfate-free": ["sulfate-free", "sulphate-free", "sulfate free", "sulphate free"],
    "color-safe": ["color-safe", "colour-safe", "color safe", "color protect",
                   "color-treated", "colour"],
    "gentle/sensitive": ["gentle", "sensitive", "mild", "non-comedogenic",
                         "dermatolog", "fragrance-free", "free of", "free-of"],
    "scalp": ["scalp", "dandruff", "seborrh", "psoriasis", "exfoliat", "salicylic"],
}
FEEL_TAGS = {
    "clean/refreshing": ["clean", "refresh", "squeaky"],
    "lightweight": ["light", "weightless", "airy", "non-weighing", "not heavy"],
    "silky/smooth": ["silk", "smooth", "sleek"],
    "soft/conditioned": ["soft", "condition", "nourish"],
    "voluminous": ["volum", "full", "bouncy", "body"],
    "stripping/drying": ["strip", "drying", "dry ", "stripped"],
    "moisturized": ["moistur", "hydrat"],
}


def derive_tags(text: str, vocab: dict) -> set:
    """Return the set of canonical tags whose keywords appear in ``text``."""
    low = (text or "").lower()
    return {tag for tag, kws in vocab.items() if any(k in low for k in kws)}


def _trend_metric(row: dict, metric: str):
    """Extract a numeric coacervation feature from a library row."""
    if metric == "trough_dilution":
        return row.get("trough_dilution")
    if metric == "width_ord":
        w = str(row.get("width") or "").lower()
        return {"narrow": 1, "moderate": 2, "broad": 3}.get(w)
    if metric == "onset":
        m = re.search(r"1:\s*([0-9.]+)", str(row.get("onset") or ""))
        return float(m.group(1)) if m else None
    return row.get("auc")


_TREND_METRIC_LABELS = {
    "auc": "Coacervation AUC",
    "trough_dilution": "Trough dilution (1:X at max coacervation)",
    "width_ord": "Coacervation breadth (narrow=1 / moderate=2 / broad=3)",
    "onset": "Onset dilution (1:X)",
}


@app.route("/trends", methods=["POST"])
def trends():
    """Aggregate a coacervation feature across products grouped by claim / feel tag.

    Joins the sample library (coacervation features per run product) with the
    product catalog (claims + consumer feel) by (file, sheet, trough), derives
    controlled-vocabulary tags, and returns per-tag mean +/- spread plus a plot
    and the per-product detail. Only run products with a catalog link and the
    chosen metric are included.
    """
    try:
        data = request.get_json(force=True) or {}
        metric = data.get("metric", "auc")
        source = data.get("source", "all")  # all | claims | feel
        timepoint = float(data.get("timepoint", 3.0))
        x1 = float(data.get("auc_dil_1", 1))
        x2 = float(data.get("auc_dil_2", 20))
        window = (min(1.0 / (1 + x1), 1.0 / (1 + x2)),
                  max(1.0 / (1 + x1), 1.0 / (1 + x2)))
        props = load_properties()
        rows = _build_library(timepoint, window, props)
        prod_by_link = {}
        for p in load_products_store():
            if p.get("file") and p.get("trough"):
                prod_by_link[(str(p["file"]), str(p.get("sheet") or ""),
                              str(p["trough"]))] = p
        items = []
        for r in rows:
            link = (str(r.get("file") or ""), str(r.get("sheet") or ""),
                    str(r.get("trough") or ""))
            p = prod_by_link.get(link)
            if not p:
                continue
            mv = _trend_metric(r, metric)
            if mv is None:
                continue
            text = " ".join([p.get("claims", ""), p.get("consumer_feedback", ""),
                             p.get("name", "")])
            tags = set()
            if source in ("all", "claims"):
                tags |= {"claim:" + t for t in derive_tags(text, CLAIM_TAGS)}
            if source in ("all", "feel"):
                tags |= {"feel:" + t for t in derive_tags(text, FEEL_TAGS)}
            items.append({"name": p.get("name", ""), "category": p.get("category", ""),
                          "value": float(mv), "tags": sorted(tags)})
        # aggregate per tag
        agg = {}
        for it in items:
            for t in it["tags"]:
                agg.setdefault(t, []).append(it["value"])
        table = []
        for t, vals in agg.items():
            arr = np.array(vals, dtype=float)
            table.append({"tag": t, "n": len(vals),
                          "mean": round(float(arr.mean()), 5),
                          "std": round(float(arr.std(ddof=0)), 5),
                          "min": round(float(arr.min()), 5),
                          "max": round(float(arr.max()), 5)})
        table.sort(key=lambda d: -d["mean"])
        items.sort(key=lambda d: -d["value"])

        # plot: mean metric per tag (claim vs feel colored), n annotated
        label = _TREND_METRIC_LABELS.get(metric, metric)
        fig = None
        if table:
            fig, ax = plt.subplots(figsize=(9.2, max(2.6, 0.45 * len(table) + 1.4)))
            y = np.arange(len(table))
            colors = ["#2e75b6" if d["tag"].startswith("claim:") else "#2e9e5b"
                      for d in table]
            means = [d["mean"] for d in table]
            errs = [d["std"] for d in table]
            ax.barh(y, means, xerr=errs, color=colors, edgecolor="#33404d",
                    linewidth=0.6, error_kw={"elinewidth": 0.8, "capsize": 3})
            ax.set_yticks(y)
            ax.set_yticklabels([d["tag"] for d in table], fontsize=9)
            for i, d in enumerate(table):
                ax.text(d["mean"] + (max(means) * 0.01 if max(means) else 0.001),
                        i, f"  n={d['n']}", va="center", fontsize=8, color="#555")
            ax.set_xlabel(f"Mean {label}")
            ax.set_title(f"{label} by product tag", fontsize=12, fontweight="bold")
            ax.grid(True, axis="x", ls=":", alpha=0.5)
            from matplotlib.patches import Patch
            ax.legend(handles=[Patch(facecolor="#2e75b6", label="Claim"),
                               Patch(facecolor="#2e9e5b", label="Consumer feel")],
                      fontsize=8, loc="lower right")
            fig.tight_layout()
        image = fig_to_base64(fig) if fig is not None else ""
        return jsonify({"ok": True, "image": image, "table": table,
                        "items": items, "n_products": len(items),
                        "metric": metric, "metric_label": label})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


# --------------------------------------------------------------------------- #
# Mintel GNPD product enrichment (ingredients / claims / image)
# --------------------------------------------------------------------------- #
@app.route("/mintel_status")
def mintel_status():
    """Report Mintel connector readiness (does not open a connection)."""
    try:
        return jsonify({"ok": True, **cmintel.status()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/mintel_lookup", methods=["POST"])
def mintel_lookup():
    """Look up one product in Mintel by GTIN (preferred) or name.

    Returns normalized {name, brand, ingredients, claims, image} for the UI to
    drop into the product form (user reviews, then Saves).
    """
    try:
        data = request.get_json(force=True)
        gtin = str(data.get("gtin", "")).strip()
        name = str(data.get("name", "")).strip()
        if gtin:
            res = cmintel.lookup_gtin(gtin)
        elif name:
            res = cmintel.search(name)
        else:
            return jsonify({"ok": False, "error": "Provide a GTIN or product name."})
        return jsonify({"ok": True, "result": res})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


# --------------------------------------------------------------------------- #
# Lasentec (FBRM) + microscopy
# --------------------------------------------------------------------------- #
APPEARANCE_STORE = Path("appearance_store.json")


def load_appearance_store() -> dict:
    if APPEARANCE_STORE.exists():
        try:
            data = json.loads(APPEARANCE_STORE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_appearance_store(store: dict) -> None:
    APPEARANCE_STORE.write_text(json.dumps(store, indent=2), encoding="utf-8")


@app.route("/appearance", methods=["GET"])
def appearance():
    """Map of sample_id -> clear|translucent|opaque (drives technique fit)."""
    return jsonify({"ok": True, "appearance": load_appearance_store()})


@app.route("/set_appearance", methods=["POST"])
def set_appearance():
    try:
        d = request.get_json(force=True)
        sid = str(d.get("sample_id", "")).strip()
        val = str(d.get("appearance", "")).strip().lower()
        if not sid:
            return jsonify({"ok": False, "error": "sample_id required."})
        store = load_appearance_store()
        if val in ("clear", "translucent", "opaque"):
            store[sid] = val
        else:
            store.pop(sid, None)
        save_appearance_store(store)
        return jsonify({"ok": True})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


NMR_STORE = Path("nmr_store.json")


def load_nmr_store() -> dict:
    if NMR_STORE.exists():
        try:
            data = json.loads(NMR_STORE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def save_nmr_store(store: dict) -> None:
    NMR_STORE.write_text(json.dumps(store, indent=2), encoding="utf-8")


@app.route("/nmr", methods=["GET"])
def nmr_get():
    """Per-sample NMR composition (silicone %, PO %, surfactant %, pH)."""
    return jsonify({"ok": True, "nmr": load_nmr_store()})


@app.route("/set_nmr", methods=["POST"])
def set_nmr():
    """Store NMR composition for a sample. Empty payload clears the record."""
    try:
        d = request.get_json(force=True)
        sid = str(d.get("sample_id", "")).strip()
        if not sid:
            return jsonify({"ok": False, "error": "sample_id required."})
        store = load_nmr_store()

        def _num(k):
            v = str(d.get(k, "")).strip()
            try:
                return float(v) if v != "" else None
            except ValueError:
                return None
        rec = {"silicone_pct": _num("silicone_pct"), "po_pct": _num("po_pct"),
               "surfactant_pct": _num("surfactant_pct"), "ph": _num("ph"),
               "notes": str(d.get("notes", "")).strip()}
        if any(v not in (None, "") for v in rec.values()):
            store[sid] = rec
        else:
            store.pop(sid, None)
        save_nmr_store(store)
        return jsonify({"ok": True})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


def _pct_fp_map():
    """Map sample_id ('file|sheet|trough') -> library row (%T fingerprint)."""
    props = load_properties()
    rows = _build_library(3.0, None, props)
    out = {}
    for r in rows:
        sid = "|".join((str(r.get("file") or ""), str(r.get("sheet") or ""),
                        str(r.get("trough") or "")))
        out[sid] = r
    return out


def _row_to_fp(row):
    """Adapt a library row into the fingerprint dict suggest_next expects."""
    if not row:
        return None
    return {
        "strength": row.get("strength"),
        "onset_dilution": row.get("onset"),
        "interpretation": row.get("interpretation"),
        "auc": row.get("auc"),
    }


@app.route("/lasentec_samples", methods=["GET"])
def lasentec_samples():
    """List stored Lasentec records (metrics + deposition read-out + microscopy)."""
    try:
        lookup = _organized_sample_lookup()
        records = []
        for rec in clas.load_store():
            r = dict(rec)
            meta = None
            for key in (r.get("sample_id"), r.get("batch_id"), r.get("name")):
                meta = lookup.get(str(key or "").strip().lower())
                if meta:
                    break
            if meta:
                for field in ("identity", "sample_type", "polymer", "surfactant",
                              "co_surfactant", "co_surfactant_pct", "concentration",
                              "ebr_batch_id", "enovia_id"):
                    r[field] = r.get(field) or meta.get(field, "")
                r["chassis"] = r.get("chassis") or meta.get("chassis", "")
            else:
                r["identity"] = formulation_identity(r)
            records.append(r)
        return jsonify({"ok": True, "records": records})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/lasentec_upload", methods=["POST"])
def lasentec_upload():
    """Upload an FBRM csv and link it to a sample. multipart: file + fields."""
    try:
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify({"ok": False, "error": "No FBRM csv uploaded."})
        sample_id = str(request.form.get("sample_id", "")).strip()
        batch_id = str(request.form.get("batch_id", "")).strip()
        name = str(request.form.get("name", "")).strip()
        dilution = request.form.get("dilution", "").strip()
        try:
            dilution = float(dilution) if dilution else None
        except ValueError:
            dilution = None
        clas.LASENTEC_DIR.mkdir(parents=True, exist_ok=True)
        safe = secure_filename(f.filename) or "fbrm.csv"
        dest = clas.LASENTEC_DIR / safe
        f.save(dest)
        mids, counts = clas.parse_fbrm(dest)
        metrics = clas.compute_metrics(mids, counts)
        rec = clas.upsert_record(sample_id=sample_id, batch_id=batch_id,
                                 name=name or safe, csv_name=safe, metrics=metrics,
                                 dilution=dilution)
        return jsonify({"ok": True, "record": rec})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/lasentec_delete", methods=["POST"])
def lasentec_delete():
    try:
        key = str(request.get_json(force=True).get("key", "")).strip()
        return jsonify({"ok": clas.delete_record(key)})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/lasentec_rename", methods=["POST"])
def lasentec_rename():
    """Rename the display name of a stored Lasentec record."""
    try:
        data = request.get_json(force=True)
        key = str(data.get("key", "")).strip()
        name = str(data.get("name", "")).strip()
        if not name:
            return jsonify({"ok": False, "error": "New name is empty."})
        ok = clas.rename_record(key, name)
        return jsonify({"ok": ok, "error": "" if ok else "Record not found."})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/microscopy_upload", methods=["POST"])
def microscopy_upload():
    """Attach a microscopy image to a Lasentec record (multipart: image + key)."""
    try:
        img = request.files.get("image")
        key = str(request.form.get("key", "")).strip()
        caption = str(request.form.get("caption", "")).strip()
        if not img or not img.filename:
            return jsonify({"ok": False, "error": "No image uploaded."})
        clas.MICROSCOPY_DIR.mkdir(parents=True, exist_ok=True)
        safe = secure_filename(img.filename) or "image.png"
        img.save(clas.MICROSCOPY_DIR / safe)
        ok = clas.attach_microscopy(key, safe, caption)
        return jsonify({"ok": ok, "image": safe})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/microscopy_image/<path:name>")
def microscopy_image(name):
    """Serve an uploaded microscopy image (path-guarded to the images folder)."""
    safe = secure_filename(name)
    p = (clas.MICROSCOPY_DIR / safe).resolve()
    root = clas.MICROSCOPY_DIR.resolve()
    if root not in p.parents or not p.exists():
        return ("Not found", 404)
    return send_file(p)


# --------------------------------------------------------------------------- #
# Microscopy gallery (standalone, keyed by Batch ID)
# --------------------------------------------------------------------------- #
MICRO_GALLERY = DATA_DIR / "microscopy_gallery.json"


def _micro_load() -> list:
    try:
        return json.loads(MICRO_GALLERY.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return []


def _micro_save(recs: list) -> None:
    MICRO_GALLERY.write_text(json.dumps(recs, indent=2), encoding="utf-8")


@app.route("/micro/list", methods=["GET"])
def micro_list():
    """All stored micrographs (optionally filtered by Batch ID / name / notes)."""
    q = str(request.args.get("q", "")).strip().lower()
    recs = _micro_load()
    if q:
        recs = [r for r in recs if q in (f"{r.get('batch_id','')} "
                f"{r.get('display_name','')} {r.get('notes','')}").lower()]
    recs = sorted(recs, key=lambda r: r.get("created", ""), reverse=True)
    return jsonify({"ok": True, "records": recs})


@app.route("/micro/upload", methods=["POST"])
def micro_upload():
    """Save a micrograph tied to a Batch ID with optional capture metadata."""
    try:
        img = request.files.get("image")
        if not img or not img.filename:
            return jsonify({"ok": False, "error": "Choose a microscopy image to upload."})
        batch_id = str(request.form.get("batch_id", "")).strip()
        if not batch_id:
            return jsonify({"ok": False, "error": "Enter the Batch ID this image belongs to."})
        clas.MICROSCOPY_DIR.mkdir(parents=True, exist_ok=True)
        ext = Path(img.filename).suffix.lower() or ".png"
        stem = secure_filename(Path(img.filename).stem) or "micrograph"
        fname = f"micro_{datetime.datetime.now():%Y%m%d%H%M%S}_{stem}{ext}"
        img.save(clas.MICROSCOPY_DIR / fname)
        rec = {
            "id": f"m{datetime.datetime.now():%Y%m%d%H%M%S%f}",
            "batch_id": batch_id,
            "display_name": str(request.form.get("display_name", "")).strip(),
            "dilution": str(request.form.get("dilution", "")).strip(),
            "water_type": str(request.form.get("water_type", "")).strip(),
            "magnification": str(request.form.get("magnification", "")).strip(),
            "microscope": str(request.form.get("microscope", "")).strip(),
            "notes": str(request.form.get("notes", "")).strip(),
            "image": fname,
            "created": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        recs = _micro_load()
        recs.append(rec)
        _micro_save(recs)
        return jsonify({"ok": True, "record": rec})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/micro/delete", methods=["POST"])
def micro_delete():
    """Delete a micrograph record and its image file."""
    try:
        rid = str((request.get_json(force=True) or {}).get("id", "")).strip()
        recs = _micro_load()
        removed = [r for r in recs if r.get("id") == rid]
        _micro_save([r for r in recs if r.get("id") != rid])
        for r in removed:
            try:
                p = (clas.MICROSCOPY_DIR / secure_filename(r.get("image", ""))).resolve()
                if clas.MICROSCOPY_DIR.resolve() in p.parents and p.exists():
                    p.unlink()
            except Exception:  # noqa: BLE001
                pass
        return jsonify({"ok": True})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/lasentec_plot", methods=["POST"])
def lasentec_plot():
    """Plot chord-length distributions for selected records.

    Records tagged raw_response (from ingest_wide_chord_csv, e.g. the merged
    Lasentec workbook exports) default to RAW Response vs Ch. Midpoints, one
    panel per chassis group - matching the source instrument plots. Live
    per-scan FBRM uploads default to peak-normalized overlay (comparable
    across very different total particle counts). `normalize` in the request
    forces one behavior for all selected records. `combine: true` forces ALL
    selected records into a single overlay panel, ignoring chassis grouping.
    """
    try:
        data = request.get_json(force=True)
        keys = data.get("keys", [])
        recs = [r for r in clas.load_store() if r.get("key") in keys]
        if not recs:
            return jsonify({"ok": False, "error": "No records selected."})
        colours = ["#2E75B6", "#c0392b", "#27ae60", "#8E44AD", "#B97A00",
                   "#16A085", "#E67E22", "#34495E"]
        force_norm = data.get("normalize")
        combine = bool(data.get("combine"))
        _ttl = str(data.get("title", "")).strip()

        if combine:
            groups = {"": recs}
        else:
            groups = {}
            for r in recs:
                groups.setdefault(r.get("chassis") or "", []).append(r)
        multi_group = len([g for g in groups if g]) > 1

        fig, axes = plt.subplots(len(groups), 1, figsize=(8.5, 5.0 * len(groups)), squeeze=False)
        sims = []
        for gi, (chassis, grecs) in enumerate(groups.items()):
            ax = axes[gi][0]
            for i, r in enumerate(grecs):
                m = np.array(r["metrics"]["mids"]); d = np.array(r["metrics"]["dist"])
                normalize = (not r.get("raw_response")) if force_norm is None else bool(force_norm)
                y = (d / d.max() if d.max() > 0 else d) if normalize else d
                ax.plot(m, y, "-", lw=2.3, color=colours[i % len(colours)],
                        label=r.get("name") or r.get("key"))
                nm = r.get("name") or r.get("key")
                try:
                    mm = cfp.record_and_match("lasentec", nm, r.get("metrics", {}),
                                              batch_id=r.get("batch_id", ""), top=1)
                    if mm:
                        sims.append({"name": nm, "match": mm[0]})
                except Exception:  # noqa: BLE001
                    pass
            ax.set_xscale("log"); ax.set_xlim(1, 1000)
            ax.set_xlabel("Ch. Midpoints (\u00b5m)")
            any_raw = any(r.get("raw_response") for r in grecs)
            if force_norm is True or (force_norm is None and not any_raw):
                ax.set_ylim(0, 1.05)
                ax.set_ylabel("Counts (normalized to peak)")
            else:
                ax.set_ylabel("Response")
            ax.grid(True, which="both", ls=":", alpha=0.5)
            default_title = f"{chassis} \u2014 Response by Ch. Midpoints" if chassis else \
                "Lasentec FBRM \u2014 particle size distribution"
            ax.set_title(_ttl if (_ttl and not multi_group) else default_title)
            ax.legend(fontsize=9)
        fig.tight_layout()

        # deposition/floc-size interpretation per selected record (grounded in
        # predict_deposition; literature refs surfaced to the UI as citations)
        interp = [{"name": r.get("name") or r.get("key"),
                   "frac_gt30": r["metrics"].get("frac_gt30"),
                   "peak_um": r["metrics"].get("peak_um"),
                   "sqrwt_um": r["metrics"].get("sqrwt_um"),
                   "total_counts": r["metrics"].get("total_counts"),
                   **clas.predict_deposition(r["metrics"])}
                  for r in recs]
        return jsonify({"ok": True, "image": fig_to_base64(fig), "similar": sims,
                        "interpretation": interp, "references": clas.REFERENCES})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/lasentec_correlate", methods=["POST"])
def lasentec_correlate():
    """Correlate %T fingerprint (AUC) with Lasentec floc size across samples
    that have BOTH datasets. Returns a scatter + Pearson r."""
    try:
        metric = str(request.get_json(force=True).get("metric", "auc"))
        fp = _pct_fp_map()
        xs, ys, labels = [], [], []
        for r in clas.load_store():
            row = fp.get(r.get("sample_id"))
            if not row:
                continue
            yv = row.get(metric)
            if yv is None:
                continue
            xs.append(float(r["metrics"].get("frac_gt30") or 0))
            ys.append(float(yv))
            labels.append(r.get("name") or r.get("sample_id"))
        if len(xs) < 2:
            return jsonify({"ok": False,
                            "error": "Need \u22652 samples with BOTH %T and Lasentec data."})
        x = np.array(xs); y = np.array(ys)
        rr = float(np.corrcoef(x, y)[0, 1]) if x.std() and y.std() else float("nan")
        fig, ax = plt.subplots(figsize=(7.5, 5.5))
        ax.scatter(x, y, s=90, color="#2E75B6", zorder=3)
        for xi, yi, lb in zip(x, y, labels):
            ax.annotate(lb, (xi, yi), fontsize=8, xytext=(5, 4),
                        textcoords="offset points")
        if x.std():
            z = np.polyfit(x, y, 1); xs2 = np.linspace(x.min(), x.max(), 40)
            ax.plot(xs2, np.polyval(z, xs2), "--", color="#888", lw=1)
        ax.set_xlabel("Lasentec floc size (% counts > 30 \u00b5m)")
        ax.set_ylabel(f"%T {metric}")
        ax.set_title(f"%T {metric} vs coacervate floc size  (r = {rr:+.2f}, n = {len(xs)})")
        ax.grid(True, ls=":", alpha=0.5)
        return jsonify({"ok": True, "image": fig_to_base64(fig), "r": round(rr, 3),
                        "n": len(xs)})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/sample_360", methods=["GET"])
def sample_360():
    """One row per sample: what data exists (%T / Lasentec / microscopy),
    appearance tag, and the suggested next experiment. Handles a Lasentec
    dilution SERIES per sample (multiple measurements)."""
    try:
        fp_map = _pct_fp_map()
        appear = load_appearance_store()
        nmr = load_nmr_store()
        store = clas.load_store()
        las_by_sid = {}
        for r in store:
            if r.get("sample_id"):
                las_by_sid.setdefault(r["sample_id"], []).append(r)
        las_unlinked = [r for r in store if not r.get("sample_id")]
        out = []

        def _primary(recs):
            """Pick the most sensory-relevant record: largest floc fraction."""
            return max(recs, key=lambda r: float(r["metrics"].get("frac_gt30") or 0))

        def build(sid, row, recs):
            fp = _row_to_fp(row)
            rec = _primary(recs) if recs else None
            metrics = rec["metrics"] if rec else None
            has_mic = any(r.get("microscopy") for r in (recs or []))
            app_tag = appear.get(sid or "")
            sug = clas.suggest_next(fp, bool(recs), has_mic, metrics, appearance=app_tag)
            dils = sorted({str(r.get("dilution")) for r in (recs or []) if r.get("dilution")})
            mic0 = next((m for r in (recs or []) for m in r.get("microscopy", [])), None)
            return {
                "sample_id": sid,
                "name": (sample_display_name(row) if row
                         else (rec.get("name") if rec else sid)),
                "batch_id": (row.get("sample_key") if row
                             else (rec.get("batch_id") if rec else "")),
                "appearance": app_tag or "",
                "has_pct": row is not None,
                "auc": row.get("auc") if row else None,
                "strength": row.get("strength") if row else None,
                "onset": row.get("onset") if row else None,
                "has_lasentec": bool(recs),
                "n_dilutions": len(dils),
                "dilutions": dils,
                "las_key": rec.get("key") if rec else None,
                "peak_um": metrics.get("peak_um") if metrics else None,
                "frac_gt30": metrics.get("frac_gt30") if metrics else None,
                "deposition": (rec.get("deposition", {}).get("deposition_level")
                               if rec else None),
                "feel_class": (rec.get("deposition", {}).get("feel_class")
                               if rec else None),
                "has_microscopy": has_mic,
                "microscopy_img": mic0.get("image") if mic0 else None,
                "nmr": nmr.get(sid or ""),
                "priority": sug["priority"], "action": sug["action"], "why": sug["why"],
                "appearance_note": sug.get("appearance_note", ""),
            }

        for sid, row in fp_map.items():
            out.append(build(sid, row, las_by_sid.get(sid)))
        for rec in las_unlinked:
            out.append(build(rec.get("key"), None, [rec]))

        order = {"high": 0, "medium": 1, "low": 2, "done": 3}
        out.sort(key=lambda s: (order.get(s["priority"], 9), (s["name"] or "").lower()))
        return jsonify({"ok": True, "rows": out})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/pct_stages", methods=["GET"])
def pct_stages():
    """Stage-anchored %T turbidity descriptors (wash/rinse/clearing) per sample,
    computed from the raw %T-vs-dilution curve. Keyed by sample_id."""
    try:
        out = {}
        for fname in list_raw_txt():
            path = resolve_file(fname)
            sheets = list_run_sheets(path) if is_excel(path) else []
            sheet_list = (sheets if sheets and (len(sheets) > 1 or not has_plate1(path))
                          else [None])
            for sh in sheet_list:
                try:
                    df = parse_and_annotate(path, sh)
                except Exception:  # noqa: BLE001
                    continue
                for tr in (1, 2):
                    sub = df[df["trough"] == tr].dropna(subset=["formula_fraction"])
                    if sub.empty:
                        continue
                    tp = sorted(sub["timepoint_minutes"].unique())
                    tmid = tp[len(tp) // 2] if tp else None
                    cur = sub[sub["timepoint_minutes"] == tmid].sort_values(
                        "formula_fraction", ascending=False)
                    desc = clas.pct_stage_descriptors(
                        cur["formula_fraction"].to_numpy(),
                        cur["transmission_pct"].to_numpy())
                    if desc:
                        sid = "|".join((fname, sh or "", str(tr)))
                        out[sid] = desc
        return jsonify({"ok": True, "stages": out})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


# --------------------------------------------------------------------------- #
# Consumer scoreboard (blind Controls Performance Overview) + correlation
# --------------------------------------------------------------------------- #
# Hardcoded top-box scores. Columns align to CONSUMER_PRODUCTS order.
# Our product = Pantene (DMR control). Data from the blind Controls study.
CONSUMER_PRODUCTS = ["Pantene M10", "L'Oreal Hyaluron Plump",
                     "Kerastase Nutritive", "Dove Intensive Repair"]
CONSUMER_CANON = ["pantene", "loreal", "kerastase", "dove"]
CONSUMER_OUR = 0  # index of our product
CONSUMER_SCORES = {
    "Overall system (TB)":       [38, 40, 31, 42],
    "Overall conditioner (TB)":  [35, 36, 28, 37],
    "Star rating (%5-star)":     [46, 51, 33, 47],
    "Likelihood recommend (TB)": [53, 54, 46, 54],
    "Moisturized (TB)":          [40, 38, 25, 42],
    "No weigh-down (TB)":        [37, 35, 28, 43],
    "Hair health (TB)":          [33, 33, 25, 36],
    "Fragrance first-dry":       [59, 58, 53, 71],
    "Fragrance 4-8h just-right": [43, 51, 52, 60],
    "Fragrance 10h just-right":  [40, 42, 48, 55],
    "Clean/not weighed (TB)":    [75, 76, 69, 76],
}


def _canon_prod(name):
    n = (name or "").lower()
    if "pantene" in n or "dmr" in n:
        return "pantene"
    if "dove" in n:
        return "dove"
    if "kerast" in n:
        return "kerastase"
    if "oreal" in n or "hyaluron" in n:
        return "loreal"
    return n


def _consumer_axis_values(axis):
    """For each consumer product, pull a data value (by name match) for `axis`.

    axis: frac_gt30 | peak_um (Lasentec) ; silicone_pct | po_pct (NMR via the
    matched Lasentec record's sample_id).
    """
    las = clas.load_store()
    nmr = load_nmr_store()
    las_by_canon = {}
    for r in las:
        c = _canon_prod(r.get("name"))
        prev = las_by_canon.get(c)
        if not prev or float(r["metrics"].get("frac_gt30") or 0) > float(
                prev["metrics"].get("frac_gt30") or 0):
            las_by_canon[c] = r
    vals = []
    for canon in CONSUMER_CANON:
        rec = las_by_canon.get(canon)
        v = None
        if rec:
            if axis in ("frac_gt30", "peak_um"):
                v = rec["metrics"].get(axis)
            elif axis in ("silicone_pct", "po_pct"):
                nrec = nmr.get(rec.get("sample_id") or "")
                v = nrec.get(axis) if nrec else None
        vals.append(v)
    return vals


@app.route("/consumer_scores", methods=["GET"])
def consumer_scores():
    """Blind scoreboard: products x metrics + who beats our product per metric."""
    beats = {}
    for metric, row in CONSUMER_SCORES.items():
        ours = row[CONSUMER_OUR]
        beats[metric] = [i for i, v in enumerate(row)
                         if i != CONSUMER_OUR and v > ours]
    return jsonify({"ok": True, "products": CONSUMER_PRODUCTS,
                    "our_index": CONSUMER_OUR, "scores": CONSUMER_SCORES,
                    "beats_us": beats})


@app.route("/consumer_correlate", methods=["POST"])
def consumer_correlate():
    """Correlate a consumer metric against a lab axis (Lasentec / NMR), matched
    by product name. Returns a labeled scatter + Pearson r."""
    try:
        d = request.get_json(force=True)
        metric = str(d.get("metric", "Fragrance 10h just-right"))
        axis = str(d.get("axis", "frac_gt30"))
        if metric not in CONSUMER_SCORES:
            return jsonify({"ok": False, "error": "Unknown metric."})
        yvals = CONSUMER_SCORES[metric]
        xvals = _consumer_axis_values(axis)
        xs, ys, labels = [], [], []
        for i, (xv, yv) in enumerate(zip(xvals, yvals)):
            if xv is None:
                continue
            xs.append(float(xv)); ys.append(float(yv))
            labels.append(CONSUMER_PRODUCTS[i].split()[0])
        if len(xs) < 2:
            return jsonify({"ok": False, "error": f"Need \u22652 products with {axis} data "
                            "(upload Lasentec/NMR for these products first)."})
        x = np.array(xs); y = np.array(ys)
        r = float(np.corrcoef(x, y)[0, 1]) if x.std() and y.std() else float("nan")
        axis_label = {"frac_gt30": "Coacervate floc size (% > 30 \u00b5m)",
                      "peak_um": "Coacervate peak size (\u00b5m)",
                      "silicone_pct": "NMR silicone %", "po_pct": "NMR PO %"}.get(axis, axis)
        fig, ax = plt.subplots(figsize=(7.5, 5.5))
        ax.scatter(x, y, s=110, color="#2E75B6", zorder=3)
        for xi, yi, lb in zip(x, y, labels):
            ax.annotate(lb, (xi, yi), fontsize=9, fontweight="bold",
                        xytext=(6, 4), textcoords="offset points")
        if x.std():
            z = np.polyfit(x, y, 1); xs2 = np.linspace(x.min(), x.max(), 40)
            ax.plot(xs2, np.polyval(z, xs2), "--", color="#888", lw=1)
        ax.set_xlabel(axis_label); ax.set_ylabel(metric)
        ax.set_title(f"{metric} vs {axis_label}  (r = {r:+.2f}, n = {len(xs)})")
        ax.grid(True, ls=":", alpha=0.5)
        return jsonify({"ok": True, "image": fig_to_base64(fig),
                        "r": round(r, 3), "n": len(xs)})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


def _opaque_curves(tp, only_sids=None):
    """Yield (sid, name, x_dilution, y_pct) for OPAQUE-tagged samples at time tp.

    only_sids (set) limits to specific sample_ids; else all opaque-tagged.
    """
    opaque = {sid for sid, v in load_appearance_store().items() if v == "opaque"}
    # also treat every trough of an OPAQUE-kind plate as inverse-%T (opaque)
    kinds = load_plate_kind_store()
    for fname in list_raw_txt():
        if kinds.get(norm_plate(fname)) == "opaque":
            for tr in (1, 2):
                opaque.add("|".join((fname, "", str(tr))))
    if only_sids:
        opaque &= set(only_sids)
    out = []
    for fname in list_raw_txt():
        path = resolve_file(fname)
        sheets = list_run_sheets(path) if is_excel(path) else []
        sheet_list = (sheets if sheets and (len(sheets) > 1 or not has_plate1(path))
                      else [None])
        for sh in sheet_list:
            if not any("|".join((fname, sh or "", str(tr))) in opaque for tr in (1, 2)):
                continue
            try:
                df = parse_and_annotate(path, sh)
            except Exception:  # noqa: BLE001
                continue
            for tr in (1, 2):
                sid = "|".join((fname, sh or "", str(tr)))
                if sid not in opaque:
                    continue
                sub = df[df["trough"] == tr].dropna(subset=["formula_fraction"])
                if sub.empty:
                    continue
                times = sorted(sub["timepoint_minutes"].unique())
                t = min(times, key=lambda z: abs(z - tp)) if times else None
                cur = sub[sub["timepoint_minutes"] == t].sort_values(
                    "formula_fraction", ascending=False)
                x = np.asarray(dilution_ratio(cur["formula_fraction"].to_numpy(float)), float)
                y = cur["transmission_pct"].to_numpy(float)
                names = resolve_names(fname, sh)
                out.append((sid, names.get(str(tr)) or f"{Path(fname).stem} T{tr}", x, y))
    return out


@app.route("/ipct_samples", methods=["GET"])
def ipct_samples():
    """List inverse-%T (opaque) samples for the Analyze search box: every trough
    of an opaque-kind plate (plus any appearance-tagged opaque), with a search
    string over name / chassis / component / batch id."""
    try:
        kinds = load_plate_kind_store()
        store = load_intake_store()
        appr = {sid for sid, v in load_appearance_store().items() if v == "opaque"}
        out = []
        for fname in list_raw_txt():
            path = resolve_file(fname)
            if is_excel(path) and not has_plate1(path):
                continue
            is_opaque_plate = kinds.get(norm_plate(fname)) == "opaque"
            rec = store.get(norm_plate(fname), {})
            names = resolve_names(fname, None)
            for tr in ("1", "2"):
                sid = "|".join((fname, "", tr))
                if not (is_opaque_plate or sid in appr):
                    continue
                r = rec.get(tr) or {}
                nm = (r.get("name") or names.get(tr)
                      or f"{Path(fname).stem} T{tr}")
                chassis = r.get("chassis", "")
                comp = r.get("polymer") or r.get("surfactant") or r.get("component", "")
                batch = r.get("batch_id", "")
                identity = formulation_identity({
                    "chassis": chassis,
                    "polymer": r.get("polymer") or r.get("component", ""),
                    "component": comp,
                    "concentration": r.get("concentration", ""),
                    "co_surfactant": r.get("co_surfactant", ""),
                    "co_surfactant_pct": r.get("co_surfactant_pct", ""),
                })
                search = " ".join(str(x) for x in [
                    nm, identity, chassis, comp, r.get("polymer", ""),
                    r.get("surfactant", ""), r.get("co_surfactant", ""),
                    r.get("co_surfactant_pct", ""), r.get("concentration", ""),
                    batch, r.get("sample_type", ""), r.get("ebr_batch_id", ""),
                    r.get("enovia_id", ""), fname,
                ] if x).lower()
                out.append({"id": sid, "name": nm, "chassis": chassis,
                            "identity": identity, "component": comp,
                            "polymer": r.get("polymer", ""),
                            "surfactant": r.get("surfactant", ""),
                            "co_surfactant": r.get("co_surfactant", ""),
                            "co_surfactant_pct": r.get("co_surfactant_pct", ""),
                            "concentration": r.get("concentration", ""),
                            "sample_type": r.get("sample_type", ""),
                            "batch_id": batch,
                            "ebr_batch_id": r.get("ebr_batch_id", ""),
                            "enovia_id": r.get("enovia_id", ""),
                            "search": search})
        out.sort(key=lambda z: z["name"].lower())
        return jsonify({"ok": True, "samples": out})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/ipct_fingerprints", methods=["GET"])
def ipct_fingerprints():
    """Inverse-%T coacervation fingerprints for OPAQUE-tagged samples (Eric
    Johnson method): onset / peak / re-dissolution / width / inverse AUC.
    Ranked by inverse AUC (coacervate formation). Timepoint via ?t= (default 0);
    optional window via ?lo= &hi= (dilution 1:X bounds)."""
    try:
        tp = float(request.args.get("t", 0) or 0)
        lo = request.args.get("lo"); hi = request.args.get("hi")
        lo = float(lo) if lo else None
        hi = float(hi) if hi else None
        rows = []
        for sid, name, x, y in _opaque_curves(tp):
            fp = clas.inverse_pct_fingerprint(x, y, lo=lo, hi=hi)
            if fp:
                rows.append({"sample_id": sid, "name": name, **fp})
        rows.sort(key=lambda r: -(r.get("inverse_auc") or 0))
        return jsonify({"ok": True, "rows": rows})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/ipct_plot", methods=["POST"])
def ipct_plot():
    """Overlay inverse-%T curves for selected opaque samples: raw points + smooth
    curve, shaded AUC (coacervation region), onset/peak/re-dissolution markers.
    Returns the image + fingerprint rows (ranked by inverse AUC)."""
    try:
        d = request.get_json(force=True)
        tp = float(d.get("t", 0) or 0)
        lo = float(d["lo"]) if d.get("lo") else None
        hi = float(d["hi"]) if d.get("hi") else None
        sids = d.get("sample_ids") or None
        data = _opaque_curves(tp, set(sids) if sids else None)
        if not data:
            return jsonify({"ok": False, "error": "No opaque-tagged samples "
                            "(tag them in Sample 360 -> Look)."})
        try:
            from make_dextran_figs import clean_curve as _clean_curve
            from make_dextran_timepoint_analysis import (
                smooth_hybrid as _smooth_hybrid, _dil_axis)
        except Exception:  # noqa: BLE001
            _clean_curve = _smooth_hybrid = _dil_axis = None
        colours = ["#2E75B6", "#c0392b", "#27ae60", "#8E44AD", "#B97A00",
                   "#16A085", "#E67E22", "#34495E"]
        fig, ax = plt.subplots(figsize=(10, 6))
        rows = []
        for i, (sid, name, x, y) in enumerate(data):
            col = colours[i % len(colours)]
            fp = clas.inverse_pct_fingerprint(x, y, lo=lo, hi=hi)
            # raw points + smooth curve overlaid on top
            o = np.argsort(x); xs, ys = x[o], y[o]
            ax.plot(xs, ys, "o", color=col, ms=3, alpha=0.35)
            try:
                cx, cy, _ = _clean_curve(xs, ys)
                fx, fy = _smooth_hybrid(cx, cy)
            except Exception:  # noqa: BLE001
                fx, fy = xs, ys
            ax.plot(fx, fy, "-", color=col, lw=2.2, label=name)
            if fp:
                # shade AUC region + mark onset / peak / re-dissolution
                base = fp.get("baseline", 0)
                reg = (fx >= fp["auc_lo"]) & (fx <= fp["auc_hi"])
                ax.fill_between(fx[reg], base, fy[reg], color=col, alpha=0.15)
                ax.axvline(fp["onset_dilution"], color=col, ls=":", lw=1, alpha=0.6)
                if fp.get("redissolution_dilution"):
                    ax.axvline(fp["redissolution_dilution"], color=col, ls="--", lw=1, alpha=0.6)
                row = {"sample_id": sid, "name": name, **fp}
                try:
                    _m = cfp.record_and_match("ipct", name, fp, batch_id="", top=1)
                    row["similar_to"] = _m[0] if _m else None
                except Exception:  # noqa: BLE001
                    row["similar_to"] = None
                rows.append(row)
        try:
            _dil_axis(ax, min(x.min() for _, _, x, _ in data),
                      max(x.max() for _, _, x, _ in data), fs=9)
        except Exception:  # noqa: BLE001
            ax.set_xscale("log")
        ax.set_ylim(0, 100)
        ax.set_xlabel("Dilution (1:X)")
        ax.set_ylabel("%T (upper phase)")
        ax.grid(True, which="both", ls=":", alpha=0.5)
        _ttl = str(d.get("title", "")).strip()
        ax.set_title(_ttl or ("Inverse %T \u2014 coacervate phase-separation region "
                     "(shaded = AUC; \u25bc peak, \u00b7\u00b7\u00b7 onset, -- re-dissolve)"),
                     fontsize=11, fontweight="bold")
        ax.legend(fontsize=9)
        rows.sort(key=lambda r: -(r.get("inverse_auc") or 0))
        return jsonify({"ok": True, "image": fig_to_base64(fig), "rows": rows})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/ipct_lasentec_correlate", methods=["POST"])
def ipct_lasentec_correlate():
    """Correlate inverse-%T AUC with Lasentec floc size across opaque samples
    that have BOTH (matched by sample_id or product name)."""
    try:
        tp = float(request.get_json(force=True).get("t", 0) or 0)
        # inverse AUC per opaque sample
        auc_by_sid, auc_by_canon = {}, {}
        for sid, name, x, y in _opaque_curves(tp):
            fp = clas.inverse_pct_fingerprint(x, y)
            if fp:
                auc_by_sid[sid] = (name, fp["inverse_auc"])
                auc_by_canon[_canon_prod(name)] = (name, fp["inverse_auc"])
        # match to Lasentec floc size
        xs, ys, labels = [], [], []
        for r in clas.load_store():
            frac = r["metrics"].get("frac_gt30")
            if frac is None:
                continue
            hit = auc_by_sid.get(r.get("sample_id")) or auc_by_canon.get(_canon_prod(r.get("name")))
            if not hit:
                continue
            xs.append(float(frac)); ys.append(float(hit[1])); labels.append(hit[0])
        if len(xs) < 2:
            return jsonify({"ok": False, "error": "Need \u22652 opaque samples with "
                            "BOTH inverse-%T and Lasentec data."})
        x = np.array(xs); y = np.array(ys)
        rr = float(np.corrcoef(x, y)[0, 1]) if x.std() and y.std() else float("nan")
        fig, ax = plt.subplots(figsize=(7.5, 5.5))
        ax.scatter(x, y, s=100, color="#8E44AD", zorder=3)
        for xi, yi, lb in zip(x, y, labels):
            ax.annotate(lb, (xi, yi), fontsize=8, xytext=(5, 4), textcoords="offset points")
        if x.std():
            z = np.polyfit(x, y, 1); xg = np.linspace(x.min(), x.max(), 40)
            ax.plot(xg, np.polyval(z, xg), "--", color="#888", lw=1)
        ax.set_xlabel("Lasentec floc size (% counts > 30 \u00b5m)")
        ax.set_ylabel("Inverse-%T AUC (coacervate formation)")
        ax.set_title(f"Inverse-%T AUC vs Lasentec floc size  (r = {rr:+.2f}, n = {len(xs)})")
        ax.grid(True, ls=":", alpha=0.5)
        return jsonify({"ok": True, "image": fig_to_base64(fig), "r": round(rr, 3), "n": len(xs)})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


# --------------------------------------------------------------------------- #
# AUC Explorer  (interactive bar-graph builder over all registered plates)
# --------------------------------------------------------------------------- #
AUCX_COLORS = ["#2E75B6", "#c0392b", "#27ae60", "#8E44AD", "#e67e22",
               "#16A085", "#B97A00", "#34495E", "#7f8c8d", "#d35400"]


def _aucx_series_label(plate, tr, rec_t, auto_t):
    parts = []
    desc = (rec_t.get("description") or auto_t.get("description") or "").strip()
    comp = (rec_t.get("component") or rec_t.get("polymer")
            or rec_t.get("surfactant") or "").strip()
    chas = (rec_t.get("chassis") or "").strip()
    conc = (rec_t.get("concentration") or "").strip()
    base = desc or comp or f"{Path(plate).stem}"
    if conc and conc not in base:
        parts.append(conc)
    parts.append(base)
    tail = f"  ({chas})" if chas else ""
    return f"{' '.join(parts)}{tail}  \u00b7 T{tr}"


def _aucx_catalog():
    """Enumerate every registered %T plate trough as a selectable series."""
    store = load_intake_store()
    items = []
    for fname in list_raw_txt():
        try:
            path = resolve_file(fname)
            if is_excel(path) and not has_plate1(path):
                continue
            df = parse_and_annotate(path)
            troughs = sorted(int(t) for t in df["trough"].dropna().unique())
            if not troughs:
                continue
            times = sorted(float(t) for t in df["timepoint_minutes"].unique())
            rec = store.get(norm_plate(fname), {})
            auto = {}
            if is_excel(path) and has_plate1(path):
                try:
                    auto = parse_plate1_sample_info(path)
                except Exception:  # noqa: BLE001
                    auto = {}
            for tr in troughs:
                rt = rec.get(str(tr)) or {}
                at = auto.get(str(tr)) or {}
                items.append({
                    "id": f"{fname}::{tr}",
                    "plate": fname,
                    "trough": tr,
                    "label": _aucx_series_label(fname, tr, rt, at),
                    "chassis": (rt.get("chassis") or "").strip(),
                    "polymer": (rt.get("component") or rt.get("polymer") or "").strip(),
                    "concentration": (rt.get("concentration") or "").strip(),
                    "times": times,
                })
        except Exception:  # noqa: BLE001
            continue
    items.sort(key=lambda z: z["label"].lower())
    return items


@app.route("/auc_catalog")
def auc_catalog():
    try:
        items = _aucx_catalog()
        chassis = sorted({i["chassis"] for i in items if i["chassis"]})
        conc = sorted({i["concentration"] for i in items if i["concentration"]})
        times = sorted({int(round(t)) for i in items for t in i["times"]})
        return jsonify({"ok": True, "series": items, "chassis": chassis,
                        "concentrations": conc, "timepoints": times})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


def _aucx_group_key(entry, group_by):
    return {"chassis": entry.get("chassis"), "polymer": entry.get("polymer"),
            "concentration": entry.get("concentration")}.get(group_by) or "\u2014"


@app.route("/auc_bars", methods=["POST"])
def auc_bars():
    """Compute the chosen AUC metric for selected series and render bar chart."""
    try:
        d = request.get_json(force=True)
        ids = d.get("ids", [])
        mode = d.get("mode", "full")
        timepoint = float(d.get("timepoint", 0))
        avg02 = bool(d.get("avg02", False))
        use_pct = bool(d.get("use_pct", False))
        lo = float(d.get("lo", 1)); hi = float(d.get("hi", 0)) or None
        split = float(d.get("split", 20))
        group_by = d.get("group_by", "chassis")
        if not ids:
            return jsonify({"ok": False, "error": "No series selected."})

        cat = {i["id"]: i for i in _aucx_catalog()}
        parsed = {}
        rows, labels, colours, primary, secondary = [], [], [], [], []
        gcolor, order = {}, []
        for sid in ids:
            entry = cat.get(sid)
            if not entry:
                continue
            plate = entry["plate"]
            if plate not in parsed:
                parsed[plate] = parse_and_annotate(resolve_file(plate))
            m = auc_x.metric_for_series(
                parsed[plate], entry["trough"], timepoint, mode=mode,
                lo=lo, hi=hi, split=split, use_pct=use_pct, avg02=avg02)
            if m is None:
                continue
            g = _aucx_group_key(entry, group_by)
            if g not in gcolor:
                gcolor[g] = AUCX_COLORS[len(gcolor) % len(AUCX_COLORS)]
                order.append(g)
            labels.append(entry["label"])
            colours.append(gcolor[g])
            if mode == "early_late":
                primary.append(m["early"]); secondary.append(m["late"])
                rows.append({"series": entry["label"], "group": g,
                             "early": m["early"], "late": m["late"]})
            else:
                primary.append(m["value"])
                rows.append({"series": entry["label"], "group": g, "auc": m["value"]})
        if not primary:
            return jsonify({"ok": False, "error": "No AUC could be computed."})

        unit = "(100\u2212%T)\u00b7dec" if use_pct else "abs\u00b7dec"
        tp_txt = "0\u20132 min avg" if avg02 else f"t={timepoint:g} min"
        mode_txt = {"full": "Full (whole curve)", "consumer": "Consumer 1:1\u20131:20",
                    "window": f"Window 1:{lo:g}\u20131:{hi:g}" if hi else f"Window \u22651:{lo:g}",
                    "early_late": f"Early vs Late (split 1:{split:g})",
                    "trough": "Peak turbidity (min %T)"}.get(mode, mode)
        ylab = "Peak turbidity" if mode == "trough" else f"AUC  [{unit}]"

        n = len(labels)
        fig, ax = plt.subplots(figsize=(max(8, 0.62 * n + 3), 5.6))
        xpos = np.arange(n)
        if mode == "early_late":
            w = 0.4
            ax.bar(xpos - w / 2, primary, w, color=colours, edgecolor="#33404d",
                   lw=0.5, label="early (1:1\u2192split)")
            ax.bar(xpos + w / 2, secondary, w, color=colours, edgecolor="#33404d",
                   lw=0.5, alpha=0.55, hatch="//", label="late (split\u2192max)")
            ax.legend(fontsize=9)
        else:
            ax.bar(xpos, primary, 0.72, color=colours, edgecolor="#33404d", lw=0.5)
        ax.set_xticks(xpos)
        ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=8)
        ax.set_ylabel(ylab)
        ax.set_title(f"Coacervation AUC \u2014 {mode_txt} \u2014 {tp_txt}",
                     fontsize=12, fontweight="bold")
        ax.grid(True, axis="y", ls=":", alpha=0.5)
        # group-colour legend (when grouping is meaningful)
        if group_by != "none" and len(order) > 1:
            from matplotlib.patches import Patch
            handles = [Patch(color=gcolor[g], label=g) for g in order]
            leg = ax.legend(handles=handles, title=group_by.title(), fontsize=8,
                            loc="upper right")
            if mode == "early_late":
                ax.add_artist(leg)
        fig.tight_layout()

        # CSV text
        if mode == "early_late":
            csv = "series,group,early,late\n" + "\n".join(
                f"\"{r['series']}\",{r['group']},{r['early']:.4f},{r['late']:.4f}" for r in rows)
        else:
            csv = "series,group,auc\n" + "\n".join(
                f"\"{r['series']}\",{r['group']},{r['auc']:.4f}" for r in rows)
        return jsonify({"ok": True, "image": fig_to_base64(fig), "rows": rows,
                        "csv": csv})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/auc_curve", methods=["POST"])
def auc_curve():
    """Return the %T-vs-dilution curve for one series (click-a-bar drill-down)."""
    try:
        d = request.get_json(force=True)
        sid = d.get("id", "")
        timepoint = float(d.get("timepoint", 0))
        avg02 = bool(d.get("avg02", False))
        entry = {i["id"]: i for i in _aucx_catalog()}.get(sid)
        if not entry:
            return jsonify({"ok": False, "error": "Series not found."})
        df = parse_and_annotate(resolve_file(entry["plate"]))
        tps = [0.0, 1.0, 2.0] if avg02 else [timepoint]
        fig, ax = plt.subplots(figsize=(8, 5))
        for tp in tps:
            c = auc_x.curve_at(df, entry["trough"], tp)
            if c is None:
                continue
            x, y = c
            ax.plot(x, y, "-o", ms=3, lw=1.8, label=f"t={tp:g} min")
        ax.set_xscale("log")
        ticks = [1, 2, 3, 5, 10, 20, 50, 100, 200, 500]
        xl = ax.get_xlim()
        tk = [t for t in ticks if xl[0] * 0.9 <= t <= xl[1] * 1.15]
        ax.set_xticks(tk); ax.set_xticklabels([f"1:{t}" for t in tk], rotation=45, ha="right")
        ax.set_ylim(0, 100); ax.set_xlabel("Dilution (1:X)"); ax.set_ylabel("%T")
        ax.set_title(entry["label"], fontsize=11, fontweight="bold")
        ax.grid(True, which="both", ls=":", alpha=0.5)
        if len(tps) > 1:
            ax.legend(fontsize=8)
        fig.tight_layout()
        return jsonify({"ok": True, "image": fig_to_base64(fig)})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


# --------------------------------------------------------------------------- #
# Phase diagrams (surfactant/polymer/hardness maps)
# --------------------------------------------------------------------------- #
@app.route("/phase_experiments")
def phase_experiments():
    try:
        return jsonify({"ok": True, "available": cphase.available(),
                        "experiments": cphase.list_experiments()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/phase_timepoints")
def phase_timepoints():
    try:
        eid = request.args.get("experiment_id", "")
        return jsonify({"ok": True, "timepoints": cphase.timepoints(eid)})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/phase_rename", methods=["POST"])
def phase_rename():
    """Rename the display name of a stored phase-diagram experiment."""
    try:
        d = request.get_json(force=True)
        eid = str(d.get("experiment_id", "")).strip()
        name = str(d.get("name", "")).strip()
        if not name:
            return jsonify({"ok": False, "error": "New name is empty."})
        ok = cphase.rename_experiment(eid, name)
        return jsonify({"ok": ok, "error": "" if ok else "Experiment not found."})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/phase_nexus_link", methods=["POST"])
def phase_nexus_link():
    """Link (or clear) a phase-diagram experiment to a Nexus worksheet id."""
    try:
        d = request.get_json(force=True)
        eid = str(d.get("experiment_id", "")).strip()
        wid = str(d.get("worksheet_id", "")).strip()
        ok = cphase.set_experiment_nexus(eid, wid)
        return jsonify({"ok": ok, "error": "" if ok else "Experiment id missing."})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


# --------------------------------------------------------------------------- #
# Performance Library (ILS / PTL / Deposition / Consumer) + fingerprint store
# --------------------------------------------------------------------------- #
@app.route("/perf_upload", methods=["POST"])
def perf_upload():
    """Upload a CSV of performance data (ILS/PTL/Consumer), keyed by batch id."""
    try:
        kind = str(request.form.get("kind", "")).strip().lower()
        if kind not in cperf.KINDS:
            return jsonify({"ok": False, "error": f"Unknown kind '{kind}'."})
        f = request.files.get("file")
        if not f or not f.filename:
            return jsonify({"ok": False, "error": "No CSV uploaded."})
        ds = cperf.ingest_csv(kind, f.stream, filename=secure_filename(f.filename))
        return jsonify({"ok": True, "dataset": ds})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/perf_data")
def perf_data():
    try:
        kind = str(request.args.get("kind", "")).strip().lower()
        if kind:
            return jsonify({"ok": True, "dataset": cperf.get_dataset(kind)})
        return jsonify({"ok": True, "datasets": cperf.all_datasets()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/perf_clear", methods=["POST"])
def perf_clear():
    try:
        kind = str(request.get_json(force=True).get("kind", "")).strip().lower()
        return jsonify({"ok": cperf.clear(kind)})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/perf_correlate", methods=["POST"])
def perf_correlate():
    """Scatter + Pearson r of two numeric columns within a performance dataset."""
    try:
        d = request.get_json(force=True)
        kind = str(d.get("kind", "")).strip().lower()
        x_col = str(d.get("x_col", ""))
        y_col = str(d.get("y_col", ""))
        res = cperf.correlate(kind, x_col, y_col)
        if not res.get("ok"):
            return jsonify(res)
        fig, ax = plt.subplots(figsize=(7.5, 5.5))
        ax.scatter(res["xs"], res["ys"], s=70, color="#2E75B6",
                   edgecolor="white", zorder=3)
        import numpy as _np
        b1, b0 = _np.polyfit(res["xs"], res["ys"], 1)
        xs = _np.linspace(min(res["xs"]), max(res["xs"]), 50)
        ax.plot(xs, b0 + b1 * xs, "--", color="#c0392b", lw=2,
                label=f"r = {res['r']:+.2f}  (n={res['n']})")
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        ax.set_title(f"{kind.upper()}:  {y_col}  vs  {x_col}",
                     fontweight="bold", fontsize=11)
        ax.grid(True, ls=":", alpha=0.5)
        ax.legend(fontsize=9)
        return jsonify({"ok": True, "image": fig_to_base64(fig),
                        "r": res["r"], "n": res["n"]})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/perf_overview")
def perf_overview():
    """One row per batch id showing which datasets exist for that formula."""
    try:
        joined = cperf.joined_by_batch()
        rows = []
        for bid, parts in sorted(joined.items()):
            rows.append({"batch_id": bid,
                         "ils": "ils" in parts, "ptl": "ptl" in parts,
                         "consumer": "consumer" in parts})
        return jsonify({"ok": True, "rows": rows})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/fingerprint_store")
def fingerprint_store():
    try:
        import coacervation_fingerprint_store as _c
        return jsonify({"ok": True, "store": _c._load()})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/phase_plot", methods=["POST"])
def phase_plot():
    try:
        d = request.get_json(force=True)
        img, err = cphase.render(d.get("experiment_id", ""),
                                 float(d.get("timepoint", 0)),
                                 float(d.get("threshold", 75)),
                                 title=str(d.get("title", "")).strip())
        if err:
            return jsonify({"ok": False, "error": err})
        return jsonify({"ok": True, "image": img})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/phase_ingest", methods=["POST"])
def phase_ingest():
    """Ingest a phase-diagram experiment: an Excel volumes file + transmission .txt files."""
    try:
        excel = request.files.get("excel")
        txts = request.files.getlist("txts")
        name = (request.form.get("experiment_name") or "").strip()
        if not excel or not excel.filename:
            return jsonify({"ok": False, "error": "Excel volumes file is required."})
        if not txts:
            return jsonify({"ok": False, "error": "At least one transmission .txt file is required."})
        exp_id = (request.form.get("experiment_id") or
                  Path(excel.filename).stem).strip()
        name = name or exp_id
        workdir = Path(tempfile.mkdtemp(prefix="phase_"))
        txt_dir = workdir / "transmission"
        txt_dir.mkdir(parents=True, exist_ok=True)

        # Preserve original file names (the ingester parses timepoints from them);
        # only strip any directory components to avoid path traversal.
        def _safe_name(fn: str) -> str:
            base = Path(str(fn)).name
            return base if base and ".." not in base else "upload.dat"

        xl_path = workdir / _safe_name(excel.filename)
        excel.save(xl_path)
        for f in txts:
            if f and f.filename:
                f.save(txt_dir / _safe_name(f.filename))
        exps = cphase.ingest(xl_path, txt_dir, exp_id, name,
                             n_reads=request.form.get("n_reads"),
                             interval_min=request.form.get("interval_min"))
        return jsonify({"ok": True, "experiment_id": exp_id, "experiments": exps})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/phase_kinetics", methods=["POST"])
def phase_kinetics():
    """Plate-average transmission convergence (t95) + precipitated-well fraction."""
    try:
        d = request.get_json(force=True)
        eid = str(d.get("experiment_id", "")).strip()
        thr = float(d.get("threshold", 75))
        img, err = cphase.kinetics(eid, thr, title=str(d.get("title", "")).strip())
        if err:
            return jsonify({"ok": False, "error": err})
        return jsonify({"ok": True, "image": img, "stats": cphase.kinetics_stats(eid, thr)})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/phase_metrics", methods=["POST"])
def phase_metrics():
    """Report-style analysis: precipitated %, coacervation strength, mean %T,
    t95 and a common-cutoff snapshot. Pass experiment_id for a single-experiment
    breakdown, or omit it for a ranked table across all ingested experiments."""
    try:
        d = request.get_json(force=True) or {}
        eid = str(d.get("experiment_id", "")).strip()
        thr = float(d.get("threshold", 75))
        cutoff = float(d.get("cutoff_min", 46))
        if eid:
            m = cphase.phase_metrics(eid, thr, cutoff)
            if not m:
                return jsonify({"ok": False,
                                "error": "No phase-diagram data for this experiment yet."})
            return jsonify({"ok": True, "metrics": m})
        rows = cphase.phase_metrics_table(thr, cutoff)
        return jsonify({"ok": True, "table": rows,
                        "threshold": thr, "cutoff_min": cutoff})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/phase_blob_status")
def phase_blob_status():
    try:
        client = cblob.AzureBlobClient()
        status = client.status()
        status["ok"] = True
        status["experiments"] = (cblob.list_phase_experiments(client)
                                 if status["configured"] else [])
        return jsonify(status)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/phase_blob_upload", methods=["POST"])
def phase_blob_upload():
    try:
        data = request.get_json(force=True) or {}
        experiment_id = str(data.get("experiment_id", "")).strip()
        if not experiment_id:
            return jsonify({"ok": False, "error": "Select a phase experiment to upload."})
        experiments = {str(row["experiment_id"]): row for row in cphase.list_experiments()}
        experiment = experiments.get(experiment_id)
        measurements = cphase.measurements_for_experiment(experiment_id)
        if experiment is None or measurements.empty:
            return jsonify({"ok": False, "error": "No local measurements found for that experiment."})
        result = cblob.merge_and_upload_phase_experiment(
            experiment_id, measurements,
            meta={key: experiment.get(key, "")
                  for key in ("experiment_name", "surfactant", "polymer")})
        result["experiments"] = cblob.list_phase_experiments()
        return jsonify(result)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


@app.route("/phase_blob_delete", methods=["POST"])
def phase_blob_delete():
    try:
        data = request.get_json(force=True) or {}
        result = cblob.delete_phase_experiment(data.get("experiment_id", ""))
        result["experiments"] = cblob.list_phase_experiments()
        return jsonify(result)
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/phase_blob_preview")
def phase_blob_preview():
    try:
        client = cblob.AzureBlobClient()
        if not client.configured:
            return jsonify({"ok": False, "error": "Azure Blob not configured."})
        rows = cblob.download_phase_measurements(client)
        try:
            limit = max(1, min(int(request.args.get("limit", 25)), 100))
        except (TypeError, ValueError):
            limit = 25
        return jsonify({"ok": True, "measurements": {
            "columns": list(rows.columns),
            "rows": rows.head(limit).where(pd.notna(rows), None).to_dict("records"),
            "total": int(len(rows)),
        }})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)})


@app.route("/phase_blob_download")
def phase_blob_download():
    try:
        client = cblob.AzureBlobClient()
        if not client.configured:
            return jsonify({"ok": False, "error": "Azure Blob not configured."}), 503
        measurements = cblob.download_phase_measurements(client)
        experiments = pd.DataFrame(cblob.list_phase_experiments(client))
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            measurements.to_excel(writer, index=False, sheet_name="Measurements")
            experiments.to_excel(writer, index=False, sheet_name="Experiments")
        output.seek(0)
        return send_file(output, mimetype=("application/vnd.openxmlformats-officedocument."
                                           "spreadsheetml.sheet"),
                         as_attachment=True, download_name="phase_diagram_cloud_data.xlsx")
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/phase_compare", methods=["POST"])
def phase_compare():
    """Side-by-side continuous transmission maps for several experiments at t95."""
    try:
        d = request.get_json(force=True)
        ids = d.get("experiment_ids") or []
        thr = float(d.get("threshold", 75))
        img, err = cphase.compare_equilibrium(ids, thr, title=str(d.get("title", "")).strip())
        if err:
            return jsonify({"ok": False, "error": err})
        return jsonify({"ok": True, "image": img})
    except Exception as e:  # noqa: BLE001
        return jsonify({"ok": False, "error": str(e), "trace": traceback.format_exc()})


install_storage(app)


if __name__ == "__main__":
    # Serve via waitress: the werkzeug dev server fails to dispatch requests
    # that make blocking Databricks calls on this platform (lookups hang).
    # waitress' real thread pool handles them reliably. Falls back to the dev
    # server (with a warning) if waitress is not installed.
    try:
        from waitress import serve
        print("Coacervation app (waitress) -> http://localhost:5001")
        serve(app, host="127.0.0.1", port=5001, threads=8)
    except ImportError:
        print("Coacervation app (dev server) -> http://localhost:5001")
        print("NOTE: install 'waitress' for reliable Nexus/Mintel lookups: "
              "pip install waitress")
        app.run(host="127.0.0.1", port=5001, debug=True)
