"""Phase-diagram integration for the coacervation app.

Thin wrapper around the standalone Gamsky_Surf_Phase_Diagrams code (already
copied into this folder): reuses its SQLite store (phase_diagrams.db), the
validated ingestion (ingest_experiment) and the pure plotting functions in
phase_plotting.py. Heavy imports are lazy so the web server starts even if
sklearn/scipy extras are missing.

Data model (measurements table): experiment_id, experiment_name,
surfactant_name, polymer_name, timepoint_minutes, surfactant_pct, polymer_pct,
transmission_pct (one row per well per timepoint).
"""
from __future__ import annotations

import io
import base64
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DB_PATH = Path("phase_diagrams.db")


def available() -> bool:
    if not DB_PATH.exists():
        return False
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='measurements'")
        return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        conn.close()


def _ensure_schema():
    # create_database uses CREATE TABLE IF NOT EXISTS -> safe to call always
    from schema import create_database  # lazy
    create_database(str(DB_PATH))


def list_experiments() -> list[dict]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    try:
        df = pd.read_sql_query(
            """
            SELECT experiment_id,
                   MAX(experiment_name)  AS experiment_name,
                   MAX(surfactant_name)  AS surfactant,
                   MAX(polymer_name)     AS polymer,
                   COUNT(*)              AS n_points
            FROM measurements
            GROUP BY experiment_id
            ORDER BY experiment_id
            """, conn)
    except Exception:
        return []
    finally:
        conn.close()
    recs = df.to_dict("records")
    links = _load_nexus_links()
    meta = _load_meta()
    for r in recs:
        eid = str(r.get("experiment_id"))
        r["nexus_worksheet_id"] = links.get(eid, "")
        m = meta.get(eid, {})
        r["n_reads"] = m.get("n_reads", "")
        r["interval_min"] = m.get("interval_min", "")
    return recs


NEXUS_LINK_STORE = Path("phase_nexus_links.json")


def _load_nexus_links() -> dict:
    if NEXUS_LINK_STORE.exists():
        try:
            import json
            data = json.loads(NEXUS_LINK_STORE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save_nexus_links(links: dict) -> None:
    import json
    NEXUS_LINK_STORE.write_text(json.dumps(links, indent=2), encoding="utf-8")


def set_experiment_nexus(experiment_id: str, worksheet_id: str) -> bool:
    """Link (or clear) a phase-diagram experiment to a Nexus worksheet id."""
    experiment_id = (experiment_id or "").strip()
    if not experiment_id:
        return False
    links = _load_nexus_links()
    wid = (worksheet_id or "").strip()
    if wid:
        links[experiment_id] = wid
    else:
        links.pop(experiment_id, None)
    _save_nexus_links(links)
    return True


META_STORE = Path("phase_meta.json")


def _load_meta() -> dict:
    if META_STORE.exists():
        try:
            import json
            data = json.loads(META_STORE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:  # noqa: BLE001
            return {}
    return {}


def _save_meta(meta: dict) -> None:
    import json
    META_STORE.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def set_experiment_meta(experiment_id: str, n_reads=None, interval_min=None) -> bool:
    """Record acquisition metadata (number of UV reads, nominal interval min)."""
    experiment_id = (experiment_id or "").strip()
    if not experiment_id:
        return False
    meta = _load_meta()
    entry = meta.get(experiment_id, {})
    if n_reads not in (None, ""):
        try:
            entry["n_reads"] = int(float(n_reads))
        except (TypeError, ValueError):
            pass
    if interval_min not in (None, ""):
        try:
            entry["interval_min"] = float(interval_min)
        except (TypeError, ValueError):
            pass
    meta[experiment_id] = entry
    _save_meta(meta)
    return True


def rename_experiment(experiment_id: str, new_name: str) -> bool:
    """Rename the display name of a stored phase-diagram experiment."""
    experiment_id = (experiment_id or "").strip()
    new_name = (new_name or "").strip()
    if not experiment_id or not new_name or not DB_PATH.exists():
        return False
    conn = sqlite3.connect(str(DB_PATH))
    try:
        cur = conn.execute(
            "UPDATE measurements SET experiment_name = ? WHERE experiment_id = ?",
            (new_name, experiment_id))
        conn.commit()
        return cur.rowcount > 0
    except Exception:  # noqa: BLE001
        return False
    finally:
        conn.close()



def timepoints(experiment_id: str) -> list[float]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH))
    try:
        df = pd.read_sql_query(
            "SELECT DISTINCT timepoint_minutes FROM measurements "
            "WHERE experiment_id = ? ORDER BY timepoint_minutes",
            conn, params=(experiment_id,))
    except Exception:
        return []
    finally:
        conn.close()
    return [float(t) for t in df["timepoint_minutes"].tolist()]


def _measurements(experiment_id: str, timepoint: float) -> pd.DataFrame:
    cols = ["surfactant_pct", "polymer_pct", "transmission_pct"]
    if not DB_PATH.exists():
        return pd.DataFrame(columns=cols)
    conn = sqlite3.connect(str(DB_PATH))
    try:
        df = pd.read_sql_query(
            "SELECT * FROM measurements WHERE experiment_id = ? "
            "AND timepoint_minutes = ?",
            conn, params=(experiment_id, timepoint))
    except Exception:
        return pd.DataFrame(columns=cols)
    finally:
        conn.close()
    for c in cols:
        df = df[df[c].notna() & np.isfinite(df[c])]
    df = df.copy()
    MIN = 1e-4  # log-scale needs positive values (zero conc allowed in data)
    df.loc[df["surfactant_pct"] <= 0, "surfactant_pct"] = MIN
    df.loc[df["polymer_pct"] <= 0, "polymer_pct"] = MIN
    return df


def render(experiment_id: str, timepoint: float, threshold: float = 75.0,
          title: str = ""):
    """Return (base64_png, error). Two panels: continuous map + binary boundary."""
    from phase_plotting import (create_phase_diagram_grids,
                                 plot_continuous_map, plot_binary_boundary)
    df = _measurements(experiment_id, float(timepoint))
    if len(df) < 4:
        return None, ("No phase-diagram data for this selection yet \u2014 ingest an "
                      "experiment (Excel volumes + transmission .txt files) first.")
    surf = str(df["surfactant_name"].iloc[0]) if "surfactant_name" in df else "Surfactant"
    poly = str(df["polymer_name"].iloc[0]) if "polymer_name" in df else "Polymer"
    name = str(df["experiment_name"].iloc[0]) if "experiment_name" in df else experiment_id
    AS_grid, PS_grid, trans_grid = create_phase_diagram_grids(
        df, n_points=450, method="griddata", gaussian_sigma=3.0)
    fig, axes = plt.subplots(1, 2, figsize=(15, 6.4))
    plot_continuous_map(axes[0], AS_grid, PS_grid, trans_grid, df, float(threshold),
                        surf, poly, fig=fig)
    plot_binary_boundary(axes[1], AS_grid, PS_grid, trans_grid, df, float(threshold),
                         surf, poly, fig=fig)
    _ttl = (title or "").strip() or (
        f"Phase diagram \u2014 {name}   ({surf} \u00d7 {poly}, "
        f"t = {float(timepoint):.1f} min, {float(threshold):.0f}% threshold)")
    fig.suptitle(_ttl, fontsize=13, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii"), None


def _all_measurements(experiment_id: str) -> pd.DataFrame:
    """Every well x timepoint for one experiment (for kinetic analysis)."""
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(DB_PATH))
    try:
        df = pd.read_sql_query(
            "SELECT * FROM measurements WHERE experiment_id = ? "
            "ORDER BY timepoint_minutes", conn, params=(experiment_id,))
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()
    return df


def measurements_for_experiment(experiment_id: str) -> pd.DataFrame:
    """Return the complete raw measurement table for one exportable experiment."""
    return _all_measurements(str(experiment_id).strip())


def kinetics_stats(experiment_id: str, threshold: float = 75.0) -> dict:
    """Plate-average transmission convergence + t95 (kinetic equilibrium).

    t95 = first timepoint at which plate-average transmission reaches 95% of its
    final observed value (per the interpretation guardrails). Also returns the
    precipitated-well fraction (%T < threshold) at each read.
    """
    df = _all_measurements(experiment_id)
    if df.empty or "timepoint_minutes" not in df:
        return {}
    df = df[df["transmission_pct"].notna()]
    g = df.groupby("timepoint_minutes")["transmission_pct"]
    times = [float(t) for t in sorted(df["timepoint_minutes"].unique())]
    avg = [float(g.get_group(t).mean()) for t in times]
    frac_ppt = [float((g.get_group(t) < threshold).mean() * 100.0) for t in times]
    final = avg[-1] if avg else 0.0
    target = 0.95 * final
    t95 = next((t for t, a in zip(times, avg) if a >= target), times[-1] if times else None)
    return {"times": times, "avg_transmission": avg, "frac_precipitated": frac_ppt,
            "final_avg": final, "t95": t95, "threshold": float(threshold),
            "n_reads_observed": len(times)}


def _plate_metrics(sub: pd.DataFrame, threshold: float) -> dict:
    """Report-style metrics for ONE plate snapshot (single timepoint).

    precipitated_pct = % wells with %T < threshold; strength = mean(100 - %T)
    over precipitated wells only (distinguishes 'just-below-threshold' from
    'strongly turbid'); mean_t = plate-average %T across all sampled wells.
    """
    t = pd.to_numeric(sub.get("transmission_pct"), errors="coerce").dropna()
    n = int(len(t))
    if n == 0:
        return {"n_wells": 0, "n_precipitated": 0, "precipitated_pct": None,
                "strength": None, "mean_t": None}
    ppt = t[t < threshold]
    strength = float((100.0 - ppt).mean()) if len(ppt) else 0.0
    return {"n_wells": n, "n_precipitated": int(len(ppt)),
            "precipitated_pct": round(100.0 * len(ppt) / n, 1),
            "strength": round(strength, 1),
            "mean_t": round(float(t.mean()), 1)}


def phase_metrics(experiment_id: str, threshold: float = 75.0,
                  cutoff_min: float = 46.0, cutoff_tol: float = 1.5) -> dict:
    """Full report-style metrics for one experiment.

    Returns equilibrium (final observed read) and common-cutoff (nearest read to
    ``cutoff_min``) snapshots of precipitated-%, coacervation strength and mean
    %T, plus t95 kinetic-equilibrium. Mirrors the phase-mapping report:
    precipitated fraction, strength, mean T and t95 reported separately.
    """
    df = _all_measurements(experiment_id)
    if df.empty or "timepoint_minutes" not in df:
        return {}
    df = df[pd.to_numeric(df["transmission_pct"], errors="coerce").notna()]
    times = [float(t) for t in sorted(df["timepoint_minutes"].unique())]
    if not times:
        return {}
    name = str(df["experiment_name"].iloc[0]) if "experiment_name" in df else str(experiment_id)
    surf = str(df["surfactant_name"].iloc[0]) if "surfactant_name" in df else ""
    poly = str(df["polymer_name"].iloc[0]) if "polymer_name" in df else ""

    eq_t = times[-1]
    eq = _plate_metrics(df[df["timepoint_minutes"] == eq_t], threshold)
    eq["timepoint"] = round(float(eq_t), 1)

    nearest = min(times, key=lambda t: abs(t - cutoff_min))
    cutoff = _plate_metrics(df[df["timepoint_minutes"] == nearest], threshold)
    cutoff["observed_time"] = round(float(nearest), 1)
    cutoff["off_cutoff"] = bool(abs(nearest - cutoff_min) > cutoff_tol)

    kin = kinetics_stats(experiment_id, threshold)
    t95 = kin.get("t95")
    return {
        "experiment_id": str(experiment_id), "experiment_name": name,
        "surfactant": surf, "polymer": poly,
        "n_wells": eq.get("n_wells"), "n_timepoints": len(times),
        "max_time": round(float(eq_t), 1), "threshold": float(threshold),
        "cutoff_min": float(cutoff_min),
        "equilibrium": eq, "cutoff": cutoff,
        "t95": (round(float(t95), 1) if t95 is not None else None),
        # t95 slower than the common cutoff -> cutoff is a pre-equilibrium snapshot
        "pre_equilibrium_at_cutoff": bool(t95 is not None and t95 > cutoff_min),
    }


def phase_metrics_table(threshold: float = 75.0, cutoff_min: float = 46.0) -> list[dict]:
    """Report-style equilibrium metrics for EVERY ingested experiment, ranked
    by precipitated-well fraction then coacervation strength (Table 1/2 style)."""
    rows = []
    for e in list_experiments():
        m = phase_metrics(e["experiment_id"], threshold, cutoff_min)
        if not m:
            continue
        eq = m.get("equilibrium", {})
        co = m.get("cutoff", {})
        rows.append({
            "experiment_id": m["experiment_id"],
            "experiment_name": m["experiment_name"],
            "surfactant": m["surfactant"], "polymer": m["polymer"],
            "precipitated_pct": eq.get("precipitated_pct"),
            "strength": eq.get("strength"),
            "mean_t": eq.get("mean_t"),
            "t95": m.get("t95"),
            "cutoff_precipitated_pct": co.get("precipitated_pct"),
            "cutoff_strength": co.get("strength"),
            "cutoff_observed_time": co.get("observed_time"),
            "n_wells": m.get("n_wells"), "n_timepoints": m.get("n_timepoints"),
            "max_time": m.get("max_time"),
            "pre_equilibrium_at_cutoff": m.get("pre_equilibrium_at_cutoff"),
        })
    rows.sort(key=lambda r: (-(r.get("precipitated_pct") or 0),
                             -(r.get("strength") or 0)))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def kinetics(experiment_id: str, threshold: float = 75.0, title: str = ""):
    """Return (base64_png, error): plate-average %T convergence with t95 marked
    and the precipitated-well fraction vs read time."""
    s = kinetics_stats(experiment_id, threshold)
    if not s or not s.get("times"):
        return None, ("No phase-diagram data for this experiment yet \u2014 ingest first.")
    name = experiment_id
    dfn = _all_measurements(experiment_id)
    if "experiment_name" in dfn and len(dfn):
        name = str(dfn["experiment_name"].iloc[0])
    meta = _load_meta().get(str(experiment_id), {})
    times, avg, frac = s["times"], s["avg_transmission"], s["frac_precipitated"]
    t95, final, thr = s["t95"], s["final_avg"], s["threshold"]

    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.plot(times, avg, "-o", color="#2E75B6", lw=2.2, ms=5,
            label="plate-average %T")
    ax.axhline(thr, color="#c0392b", ls=":", lw=1.4,
               label=f"{thr:.0f}% clear threshold")
    ax.axhline(0.95 * final, color="#7a7f87", ls="--", lw=1.1,
               label="95% of final")
    if t95 is not None:
        ax.axvline(t95, color="#27ae60", lw=2.0)
        ax.annotate(f"t95 = {t95:.1f} min", xy=(t95, 0.95 * final),
                    xytext=(8, -14), textcoords="offset points",
                    color="#1e7d46", fontsize=10, fontweight="bold")
    ax.set_xlabel("Read time (min, actual elapsed)")
    ax.set_ylabel("Plate-average transmission (%)", color="#2E75B6")
    ax.set_ylim(0, 100)
    ax.grid(True, ls=":", alpha=0.5)

    ax2 = ax.twinx()
    ax2.plot(times, frac, "-s", color="#B97A00", lw=1.6, ms=4, alpha=0.85,
             label="% wells precipitated")
    ax2.set_ylabel("% wells precipitated (<threshold)", color="#B97A00")
    ax2.set_ylim(0, 100)

    nom = ""
    if meta.get("n_reads") or meta.get("interval_min"):
        nom = (f"   (nominal: {meta.get('n_reads', '?')} reads "
               f"@ {meta.get('interval_min', '?')} min)")
    _ttl = (title or "").strip() or (
        f"Kinetic convergence \u2014 {name}{nom}")
    fig.suptitle(_ttl, fontsize=12.5, fontweight="bold")
    l1, la1 = ax.get_legend_handles_labels()
    l2, la2 = ax2.get_legend_handles_labels()
    ax.legend(l1 + l2, la1 + la2, fontsize=8.5, loc="center right")
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii"), None


def compare_equilibrium(experiment_ids, threshold: float = 75.0, title: str = ""):
    """Side-by-side continuous transmission maps for several experiments at their
    kinetic equilibrium (t95 read). Shared 0-100% colour scale + 75% contour, to
    compare different systems at equilibrium (like the reference figures)."""
    from phase_plotting import create_phase_diagram_grids
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullFormatter
    ids = [str(e).strip() for e in (experiment_ids or []) if str(e).strip()]
    if not ids:
        return None, "Select at least one experiment to compare."
    panels = []
    for eid in ids:
        s = kinetics_stats(eid, threshold)
        if not s or not s.get("times"):
            continue
        times = s["times"]
        t95 = s["t95"]
        tp = min(times, key=lambda t: abs(t - (t95 if t95 is not None else times[-1])))
        df = _measurements(eid, tp)
        if len(df) < 4:
            continue
        surf = str(df["surfactant_name"].iloc[0]) if "surfactant_name" in df else "Surfactant"
        poly = str(df["polymer_name"].iloc[0]) if "polymer_name" in df else "Polymer"
        name = str(df["experiment_name"].iloc[0]) if "experiment_name" in df else eid
        AS_grid, PS_grid, trans_grid = create_phase_diagram_grids(
            df, n_points=450, method="griddata", gaussian_sigma=3.0)
        panels.append(dict(name=name, surf=surf, poly=poly, t95=t95,
                           AS=AS_grid, PS=PS_grid, T=trans_grid, df=df))
    if not panels:
        return None, "No phase-diagram data for the selected experiments."
    n = len(panels)
    ncol = 1 if n == 1 else (2 if n <= 4 else 3)
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(6.4 * ncol, 5.3 * nrow),
                             squeeze=False, constrained_layout=True)
    levels = np.linspace(0, 100, 21)
    x_ticks = [0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
    y_ticks = [0.004, 0.01, 0.02, 0.05, 0.1]
    cf = None
    polys = set()
    for i, p in enumerate(panels):
        ax = axes[i // ncol][i % ncol]
        cf = ax.contourf(p["AS"], p["PS"], p["T"], levels=levels, cmap="RdYlGn",
                         vmin=0, vmax=100, extend="both", alpha=0.9)
        ax.contour(p["AS"], p["PS"], p["T"], levels=[threshold],
                   colors="black", linewidths=2.0, antialiased=True)
        ax.scatter(p["df"]["surfactant_pct"], p["df"]["polymer_pct"],
                   c=p["df"]["transmission_pct"], cmap="RdYlGn", vmin=0, vmax=100,
                   s=14, edgecolors="#555", linewidth=0.3, alpha=0.55)
        ax.set_xscale("log"); ax.set_yscale("log")
        try:
            ax.set_xlim(float(p["df"]["surfactant_pct"].min()),
                        float(p["df"]["surfactant_pct"].max()))
            ax.set_ylim(float(p["df"]["polymer_pct"].min()),
                        float(p["df"]["polymer_pct"].max()))
        except Exception:  # noqa: BLE001
            pass
        ax.xaxis.set_major_locator(FixedLocator(x_ticks))
        ax.yaxis.set_major_locator(FixedLocator(y_ticks))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:.3g}"))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:.3g}"))
        ax.xaxis.set_minor_formatter(NullFormatter())
        ax.yaxis.set_minor_formatter(NullFormatter())
        ax.grid(True, alpha=0.3, which="both")
        ax.set_xlabel(f"{p['surf']} concentration (%)", fontsize=9)
        ax.set_ylabel(f"{p['poly']} concentration (%)", fontsize=9)
        t95txt = f"{p['t95']:.1f} min" if p["t95"] is not None else "n/a"
        ax.set_title(f"{p['name']}\n$t_{{95}}$ panel at {t95txt}",
                     fontsize=10, fontweight="bold")
        polys.add(p["poly"])
    for j in range(n, nrow * ncol):
        axes[j // ncol][j % ncol].axis("off")
    if cf is not None:
        cbar = fig.colorbar(cf, ax=list(axes.ravel()), shrink=0.85, pad=0.02)
        cbar.set_label("Transmission (%)")
    polytxt = next(iter(polys)) if len(polys) == 1 else "Systems"
    _ttl = (title or "").strip() or (
        f"{polytxt} continuous transmission contours\n"
        f"Shared color scale: 0 to 100% transmission; "
        f"black contour = {threshold:.0f}% threshold")
    fig.suptitle(_ttl, fontsize=13, fontweight="bold")
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii"), None


def ingest(excel_path, txt_folder, experiment_id: str, experiment_name: str,
           n_reads=None, interval_min=None):
    """Ingest one experiment (Excel volumes + folder of transmission .txt) into the DB."""
    _ensure_schema()
    from ingest_experiment import ingest_experiment as _ing
    _ing(str(DB_PATH), experiment_id, experiment_name, str(excel_path), str(txt_folder))
    if n_reads not in (None, "") or interval_min not in (None, ""):
        set_experiment_meta(experiment_id, n_reads, interval_min)
    return list_experiments()
