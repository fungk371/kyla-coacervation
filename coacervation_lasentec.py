"""Lasentec (FBRM) + microscopy data layer for the coacervation app.

Decoupled, server-safe module (no Flask import). Provides:
  * parse_fbrm(path)            -> (mids, counts) from an iC FBRM csv export
  * compute_metrics(mids,counts)-> size/count fingerprint (peak, %>30um, bins,
                                   square-weighted mean, modality)
  * predict_deposition(metrics) -> deposition/fragrance read-out from floc size
  * suggest_next(pct_fp, has_lasentec, has_microscopy) -> workflow guidance
  * JSON store helpers (lasentec_store.json), keyed by sample id.

Workflow this supports:
  1) %T = screening (does coacervation occur? at what dilution / how much)
  2) Lasentec = coacervate floc SIZE (predicts deposition + fragrance longevity)
  3) Microscopy = coacervate MORPHOLOGY (droplets vs network; confirms flocs)
"""
from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from scipy.signal import find_peaks
except Exception:  # noqa: BLE001
    find_peaks = None

LASENTEC_STORE = Path("lasentec_store.json")
LASENTEC_DIR = Path("lasentec_data")           # raw FBRM csvs
MICROSCOPY_DIR = Path("microscopy_images")     # uploaded images


# --------------------------------------------------------------------------- #
# Parsing + metrics
# --------------------------------------------------------------------------- #
def parse_fbrm(path):
    """Parse an iC FBRM csv export -> (mids, counts).

    mids   = 100 chord-length bin midpoints (microns)
    counts = (n_scans, 100) counts per timepoint
    """
    mids = None
    counts = []
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.reader(f):
            if not row:
                continue
            tag = (row[0] or "").strip()
            if tag == "Ch. Midpoints":
                mids = np.array([float(x) for x in row[4:104]])
            elif tag.isdigit() and len(row) >= 104:
                vals = [float(x) if str(x).strip() not in ("", "nan") else 0.0
                        for x in row[4:104]]
                counts.append(vals)
    if mids is None or not counts:
        raise ValueError("Not a recognized FBRM export (no 'Ch. Midpoints' row / data).")
    return mids, np.array(counts)


def _steady_mask(counts):
    tot = counts.sum(axis=1)
    if tot.max() <= 0:
        return np.ones(len(tot), bool)
    add = int(np.argmax(tot > 0.4 * tot.max()))
    steady = (tot >= 0.5 * tot.max()) & (np.arange(len(tot)) > add + 2)
    return steady if steady.any() else (np.arange(len(tot)) > add)


def _sqrwt_mean(mids, dist):
    num = (dist * mids ** 3).sum()
    den = (dist * mids ** 2).sum()
    return float(num / den) if den > 0 else float("nan")


def _metrics_from_dist(mids, dist):
    """Size/count fingerprint from a single (already steady-state) chord distribution."""
    total = float(dist.sum())
    fine = float(dist[mids < 10].sum())
    med = float(dist[(mids >= 10) & (mids < 100)].sum())
    coarse = float(dist[mids >= 100].sum())
    frac_gt30 = float(dist[mids >= 30].sum() / total * 100) if total else 0.0
    peak_um = float(mids[int(np.argmax(dist))]) if total else 0.0
    sqrwt = _sqrwt_mean(mids, dist)

    # modality: peaks on lightly smoothed normalized distribution
    n_modes, modes = 1, [peak_um]
    if find_peaks is not None and total:
        y = dist / dist.max()
        k = np.array([1, 2, 3, 2, 1], float); k /= k.sum()
        ys = np.convolve(y, k, mode="same")
        pk, _ = find_peaks(ys, prominence=0.08, distance=6)
        if len(pk):
            n_modes = int(len(pk))
            modes = [round(float(mids[i]), 1) for i in pk]

    return {
        "total_counts": round(total, 1),
        "peak_um": round(peak_um, 1),
        "frac_gt30": round(frac_gt30, 1),
        "sqrwt_um": round(sqrwt, 1) if sqrwt == sqrwt else None,
        "bin_fine": round(fine, 1),
        "bin_med": round(med, 1),
        "bin_coarse": round(coarse, 1),
        "n_modes": n_modes,
        "modes_um": modes,
        "dist": [round(float(v), 3) for v in dist],
        "mids": [round(float(v), 3) for v in mids],
    }


def compute_metrics(mids, counts):
    """Size/count fingerprint from the steady-state chord-length distribution
    of a multi-scan iC FBRM export (counts shape = n_scans x n_bins)."""
    steady = _steady_mask(counts)
    dist = counts[steady].mean(axis=0)
    m = _metrics_from_dist(mids, dist)
    m["n_scans"] = int(len(counts))
    m["n_steady"] = int(steady.sum())
    return m


def parse_wide_chord_csv(path):
    """Parse a 'wide' pre-averaged chord distribution csv: first column = chord
    length (um), every other column = one sample's Response at that chord.
    (This is the format exported from a merged Lasentec results workbook, e.g.
    raw_data/lasentec_brandon.csv - one already-steady-state distribution per
    sample, NOT raw per-scan iC data.)
    """
    df = pd.read_csv(path)
    mids = df.iloc[:, 0].to_numpy(dtype=float)
    samples = {col: df[col].to_numpy(dtype=float) for col in df.columns[1:]}
    return mids, samples


def ingest_wide_chord_csv(path, name_of=None, chassis_of=None, batch_of=None):
    """Ingest every sample column of a wide chord-distribution csv into the
    Lasentec store as its own record (raw Response, not normalized).

    name_of/chassis_of/batch_of: optional callables col_name -> str (defaults
    to using the raw column name as both name and chassis-less record).
    Returns the list of upserted records.
    """
    mids, samples = parse_wide_chord_csv(path)
    out = []
    for col, dist in samples.items():
        metrics = _metrics_from_dist(mids, dist)
        metrics["n_scans"] = 1
        metrics["n_steady"] = 1
        name = name_of(col) if name_of else col
        chassis = chassis_of(col) if chassis_of else ""
        batch_id = batch_of(col) if batch_of else ""
        rec = upsert_record(sample_id="", batch_id=batch_id, name=name,
                            csv_name=Path(path).name, metrics=metrics,
                            chassis=chassis, raw_response=True)
        out.append(rec)
    return out


# --------------------------------------------------------------------------- #
# Interpretation: deposition / fragrance read-out from floc size
# --------------------------------------------------------------------------- #
# Literature grounding (from the platform's deposition-literature review, see
# repo notes "DEPOSITION LIT 2026-09-07"):
#   [1] Shah et al., "Decoding coacervate-aided PO deposition" (Project Zorro
#       SLR, 2024) - 5/5/2 AOS/SLS/CAPB + 0.5% polymer: active(PO) deposition
#       scales with MW*charge-density AND with FBRM floc count >30 um (big
#       50-100 um flocs ~2x depo vs small 10-20 um ~1-1.5x); SIZE > raw amount;
#       big flocs trade off feel (residue/weigh-down/clumping).
#   [2] Faizi & Miller, Langmuir (2024) - cationic dextran forms NANOMETRIC
#       polymer-surfactant complexes (not micron coacervate flocs like cat.
#       guar/HEC); deposits THROUGHOUT dilution incl. undiluted, giving high
#       silicone deposition WITHOUT large flocs (a "nanocarrier" route).
#   [3] Parth Shah, Clear Mint/Herbal SLR (microscopy, ~2025) - silicone
#       deposition is DECOUPLED from coacervate floc size: small (<5 um)
#       coacervate can still coat & carry 10-20 um silicone droplets to the
#       fiber at 1:49, giving a clean/free-flowing feel with good Si depo.
#   [4] Kamo, Mori & Yoshida, ACS Sustainable Chem/ACST (2025), non-sulfate
#       systems - coacervate structure shifts hexagonal->lamellar on dilution
#       (more elastic); floc-size sensory risk anchored to lather/wash/rinse
#       dilution stages (see STAGE_ANCHORS below).
REFERENCES = [
    "[1] Shah et al. 2024, Project Zorro SLR - 'Decoding coacervate-aided PO deposition' "
    "(floc >30\u00b5m count + MW*charge-density predict active/PO deposition; size>amount).",
    "[2] Faizi & Miller, Langmuir 2024 - cationic dextran nanometric complexes deposit "
    "silicone throughout dilution WITHOUT forming large flocs (nanocarrier route).",
    "[3] Shah, Clear Mint/Herbal SLR (microscopy) - silicone deposition decoupled from "
    "floc size; small coacervate can still coat/carry large Si droplets (clean feel).",
    "[4] Kamo, Mori & Yoshida 2025 (ACST) - coacervate structure (hexagonal->lamellar) "
    "and sensory risk are dilution-stage dependent (lather/wash/rinse).",
]


def predict_deposition(metrics):
    """Read-out from coacervate floc size (% counts > 30 um).

    Floc SIZE governs FEEL/residue + particulate-active (e.g. PO/ZPT) carrier
    strength, per the Zorro SLR [1]: bigger flocs correlate with MORE active
    deposition (up to ~2x for 50-100 um flocs) but at a feel cost (residue/
    weigh-down/clumping). Silicone deposition, by contrast, is NOT floc-size-
    locked [2][3]: small coacervate/nanometric complexes can still coat and
    carry silicone droplets to the fiber, decoupling silicone depo from floc
    size. So "larger flocs = more deposition" is TRUE for particulate actives
    (PO/ZPT) captured/carried by the floc itself, but NOT a universal rule for
    silicone conditioning agents. Directional (SLR-grounded), not a calibrated
    model - see REFERENCES.
    """
    f = float(metrics.get("frac_gt30") or 0)
    peak = float(metrics.get("peak_um") or 0)
    if f >= 20 or peak >= 15:
        level, cls, feel = "High", "2x", "Rich but residue / weigh-down risk"
        why = (f"Large flocs ({f:.0f}% > 30 \u00b5m, peak {peak:.0f} \u00b5m) \u2192 strong PO/fragrance "
               "carrier (~2x PO space per Zorro SLR [1]) but heavier feel + clumping risk "
               "(what Clear MH avoids [3]).")
    elif f >= 8 or peak >= 8:
        level, cls, feel = "Moderate", "1.5x", "Balanced"
        why = (f"Medium flocs ({f:.0f}% > 30 \u00b5m, peak {peak:.0f} \u00b5m) \u2192 moderate PO/fragrance "
               "carry per Zorro SLR [1]; watch clean-feel trade-off.")
    else:
        level, cls, feel = "Low", "1x", "Clean / free-flowing (Clear MH-like)"
        why = (f"Fine particles ({f:.0f}% > 30 \u00b5m, peak {peak:.0f} \u00b5m) \u2192 light, clean, "
               "free-flowing feel + low residue. Low coacervate-mediated PO carry [1], BUT "
               "silicone can still deposit well via the nanocarrier/small-coacervate route "
               "[2][3] (see note).")
    silicone_note = ("Silicone deposition is NOT floc-size-locked [2][3]: small coacervate can coat & "
                     "deposit large silicone droplets (Clear MH: 10\u201320 \u00b5m Si adhering at 1:49). Decouple via "
                     "silicone particle size (large+small), low pH, and droplet-coating polymer.")
    return {"deposition_level": level, "depo_class": cls, "feel_class": feel,
            "rationale": why, "silicone_note": silicone_note}


# --------------------------------------------------------------------------- #
# Dilution stage + sensory read-out (Kamo, Mori & Yoshida 2025, non-sulfate)
# --------------------------------------------------------------------------- #
# Relative shampoo concentration -> dilution 1:X (X = 1/rel_conc). The 2025
# study anchored: 0.3 = application/early lather (~1:3), 0.1 = washing (~1:10),
# 0.05 = rinsing (~1:20). Deeper dilutions (1:49+) probe late-rinse clearing.
STAGE_ANCHORS = [
    ("lather", 1, 6, "Application / early lather (rel. conc ~0.3, ~1:3)"),
    ("wash", 6, 15, "Washing / lathering (rel. conc ~0.1, ~1:10)"),
    ("early_rinse", 15, 30, "Early rinse (rel. conc ~0.05, ~1:20)"),
    ("late_rinse", 30, 1e9, "Late rinse / clearing (rel. conc <0.03, 1:30+)"),
]


def stage_for(dilution_x):
    """Map a dilution ratio (1:X) to the study's sensory-relevant stage."""
    try:
        x = float(dilution_x)
    except (TypeError, ValueError):
        return None
    for key, lo, hi, label in STAGE_ANCHORS:
        if lo <= x < hi:
            return {"stage": key, "label": label, "dilution": x}
    return None


def sensory_readout(metrics, dilution_x):
    """Translate coacervate size at a dilution stage into sensory hypotheses.

    Grounded in Kamo/Mori/Yoshida 2025 (4 non-sulfate shampoos, n=10 panel):
    directional signs only, NOT calibrated predictions. Flags are 'risk' or
    'benefit' the user can test against their consumer data.
    """
    st = stage_for(dilution_x)
    if not st:
        return {"stage": None, "flags": [], "verdict": "Set the measurement dilution to read sensory hypotheses."}
    stage = st["stage"]
    f = float(metrics.get("frac_gt30") or 0)
    peak = float(metrics.get("peak_um") or 0)
    total = float(metrics.get("total_counts") or 0)
    big = f >= 8 or peak >= 10
    flags = []

    if stage in ("wash", "lather"):
        if big:
            flags.append({"kind": "risk", "label": "Sliminess / coated feel",
                          "why": "Large wash-stage coacervate \u2194 more sliminess "
                                 "(Kamo: DLS size r=\u22120.94, turbidity r=\u22120.91, amount r=\u22120.92)."})
        else:
            flags.append({"kind": "benefit", "label": "Cleaner, less-slimy wash",
                          "why": "Small/low wash-stage coacervate \u2194 less sliminess (cleaner feel side of the trade-off)."})
    if stage in ("early_rinse", "late_rinse"):
        if total and f >= 4:
            flags.append({"kind": "benefit", "label": "Wet glide during rinse",
                          "why": "Some rinse-stage coacervate \u2194 smoother finger passage (Kamo amount r=+0.92)."})
        if stage == "late_rinse" and big:
            flags.append({"kind": "risk", "label": "Clean-feel / weigh-down risk",
                          "why": "Coacervate persisting into late rinse \u2194 more sliminess (r=\u22120.95), "
                                 "slower rinse (turbidity r=\u22120.99), worse DRY smoothness (r=\u22120.90)."})
        elif stage == "late_rinse" and not big and total < 5000:
            flags.append({"kind": "benefit", "label": "Efficient clearing",
                          "why": "Low residual late-rinse structure \u2194 faster rinse + better dry feel."})
    verdict = ("Target trajectory: enough wash-stage coacervate for delivery, transient wet glide "
               "early-rinse, then CLEAR efficiently late-rinse (avoid residue/weigh-down/poor dry feel).")
    return {"stage": stage, "stage_label": st["label"], "flags": flags, "verdict": verdict}


def _pct_has_coacervation(fp):
    """Does the %T fingerprint indicate coacervation worth imaging?"""
    if not fp:
        return None
    strength = str(fp.get("strength") or "").lower()
    amp = fp.get("amplitude")
    try:
        amp = float(amp)
    except (TypeError, ValueError):
        amp = None
    if strength in ("strong", "moderate"):
        return True
    if amp is not None:
        return amp >= 0.05
    return None


# --------------------------------------------------------------------------- #
# Appearance -> which techniques even apply
# --------------------------------------------------------------------------- #
def technique_fit(appearance):
    """Which techniques work for a clear / translucent / opaque system.

    FBRM needs phase-contrast particles: a CLEAR coacervate is invisible to it
    unless particles are trapped inside. %T (transmittance) needs light through
    the sample, so an OPAQUE shampoo saturates it. Translucent = borderline.
    """
    a = (appearance or "").lower()
    if a == "clear":
        return {"pct": "works", "lasentec": "no", "microscopy": "maybe",
                "note": "Clear system: %T works. FBRM needs phase-contrast particles \u2014 a clear "
                        "coacervate is invisible to it unless particles are trapped inside. "
                        "Confirm structure with phase/DIC microscopy."}
    if a == "translucent":
        return {"pct": "maybe", "lasentec": "maybe", "microscopy": "works",
                "note": "Translucent: borderline for BOTH %T and FBRM. FBRM only sees particles "
                        "with enough refractive-index contrast; %T partly transmits. Lean on "
                        "microscopy to interpret."}
    if a == "opaque":
        return {"pct": "inverse", "lasentec": "works", "microscopy": "works",
                "note": "Opaque system: standard %T saturates. Use INVERSE %T (Eric Johnson): "
                        "dilute \u2192 centrifuge \u2192 read the clarified upper phase at 370 nm "
                        "(coacervation shows as a %T PEAK, not a trough). FBRM + microscopy also work."}
    return {"pct": "?", "lasentec": "?", "microscopy": "?", "note": ""}


def suggest_next(fp, has_lasentec, has_microscopy, metrics=None, appearance=None):
    """Recommend the next experiment given what data exists for a sample.

    Returns {priority, action, why, appearance_note}. Appearance gates which
    techniques even apply (clear -> no FBRM; opaque -> no %T).
    """
    has_pct = fp is not None
    coac = _pct_has_coacervation(fp)
    fit = technique_fit(appearance)

    def _wrap(sug):
        sug["appearance_note"] = fit["note"]
        # gate impossible techniques by appearance
        if sug["action"] == "Run Lasentec" and fit["lasentec"] == "no":
            sug.update(priority="medium", action="FBRM won't see this",
                       why="Clear coacervate has no phase contrast for FBRM. Use %T + "
                           "phase/DIC microscopy (or NMR) instead.")
        elif sug["action"] == "Run %T screen" and fit["pct"] == "inverse":
            sug.update(priority="high", action="Run inverse %T (opaque)",
                       why="Opaque system: use inverse %T (dilute \u2192 centrifuge \u2192 read "
                           "clarified upper phase). Coacervation appears as a %T peak.")
        elif sug["action"] == "Run %T screen" and fit["pct"] == "no":
            sug.update(priority="medium", action="Skip %T (opaque)",
                       why="Opaque system saturates %T. Go straight to FBRM + microscopy.")
        return sug

    if not has_pct and not has_lasentec:
        return _wrap({"priority": "high", "action": "Run %T screen",
                      "why": "No data yet. Start with %T to see IF/where/how much coacervation occurs."})

    if has_pct and coac is False and not has_lasentec:
        return _wrap({"priority": "low", "action": "Lasentec optional",
                      "why": "%T shows little coacervation \u2014 low priority. Run 1 Lasentec only "
                             "if deposition/feel is unexpectedly strong."})

    if has_pct and (coac or coac is None) and not has_lasentec:
        onset = fp.get("onset_dilution") or fp.get("onset")
        st = fp.get("strength", "")
        tail = f" (strength {st}, onset ~1:{onset:g})" if onset else f" (strength {st})"
        return _wrap({"priority": "high", "action": "Run Lasentec",
                      "why": f"%T confirms coacervation{tail}. Measure floc SIZE to predict "
                             "deposition + fragrance longevity."})

    if has_lasentec and not has_microscopy:
        big = metrics and float(metrics.get("frac_gt30") or 0) >= 8
        if big:
            return _wrap({"priority": "high", "action": "Run microscopy",
                          "why": f"Large flocs detected ({metrics.get('frac_gt30')}% > 30 \u00b5m). "
                                 "Image to confirm morphology (discrete droplets vs network) and rule "
                                 "out bubble artifacts."})
        return _wrap({"priority": "medium", "action": "Microscopy optional",
                      "why": "Flocs are small; morphology likely fine droplets. Image if you need "
                             "to confirm structure."})

    if has_pct and has_lasentec and has_microscopy:
        return _wrap({"priority": "done", "action": "Complete",
                      "why": "%T + Lasentec + microscopy all present \u2014 full coacervate picture."})

    # lasentec present but no %T
    if has_lasentec and not has_pct:
        return _wrap({"priority": "medium", "action": "Add %T screen",
                      "why": "Lasentec size known, but no %T. Run %T to place the dilution window "
                             "(onset/strength) behind the size."})
    return _wrap({"priority": "medium", "action": "Review", "why": "Partial data."})


# --------------------------------------------------------------------------- #
# Stage-anchored %T descriptors (turbidity across the rinse)
# --------------------------------------------------------------------------- #
def pct_stage_descriptors(conc, pct):
    """Turbidity-vs-dilution read-out anchored to the study's sensory stages.

    conc = formula-fraction array (0..0.5), pct = %T array. Turbidity = 100-%T.
    Returns wash/early-rinse/late-rinse turbidity, trough, and CLEARING dilution
    (where %T recovers to >=90% of its high-dilution baseline after the trough).
    """
    conc = np.asarray(conc, float)
    pct = np.asarray(pct, float)
    ok = np.isfinite(conc) & np.isfinite(pct) & (conc > 0)
    conc, pct = conc[ok], pct[ok]
    if len(conc) < 3:
        return None
    dil = (1 - conc) / conc               # dilution ratio 1:X
    order = np.argsort(dil)
    dil, pct = dil[order], pct[order]
    turb = 100 - pct

    def _turb_at(x):
        if x < dil.min() or x > dil.max():
            return None
        return round(float(np.interp(x, dil, turb)), 1)

    trough_i = int(np.argmin(pct))
    trough_dil = float(dil[trough_i])
    # baseline = mean %T of the two most-dilute points
    baseline = float(np.mean(pct[-2:]))
    thresh = 0.9 * baseline
    clearing = None
    for i in range(trough_i, len(dil)):
        if pct[i] >= thresh:
            clearing = round(float(dil[i]), 1)
            break
    return {
        "wash_turbidity": _turb_at(10),          # ~1:10 washing
        "early_rinse_turbidity": _turb_at(20),   # ~1:20 rinsing
        "late_rinse_turbidity": _turb_at(49),    # deep rinse
        "trough_dilution": round(trough_dil, 1),
        "trough_pct": round(float(pct[trough_i]), 1),
        "clearing_dilution": clearing,
    }


# --------------------------------------------------------------------------- #
# Inverse-%T fingerprint (opaque shampoos; Eric Johnson method)
# --------------------------------------------------------------------------- #
def inverse_pct_fingerprint(x, y, base_frac=0.15, lo=None, hi=None):
    """Coacervation fingerprint for an OPAQUE inverse-%T dilution curve.

    Method (Eric S. Johnson, SWIC): an opaque shampoo is opaque when concentrated;
    on dilution the coacervate forms and SEGREGATES the opacifier particles so the
    upper phase CLARIFIES -> %T rises to a HUMP, then falls again at re-dissolution.
    The AREA UNDER THE HUMP ranks coacervate formation.

    x = dilution 1:X, y = upper-phase %T. Optional lo/hi bound the analysis to a
    dilution WINDOW (1:lo .. 1:hi) so the AUC captures only the coacervation
    region, not the pure-dilution clear tail. Returns fingerprint features:
      baseline_pct, peak_pct, peak_dilution, amplitude (clarification),
      onset_dilution (phase separation begins), redissolution_dilution,
      width_decades (log10 redis/onset), inverse_auc (area under hump,
      %T x decades), curve (x,y for plotting), and a note.
    """
    x = np.asarray(x, float); y = np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y) & (x > 0)
    x, y = x[ok], y[ok]
    if lo is not None:
        m = x >= float(lo); x, y = x[m], y[m]
    if hi is not None:
        m = x <= float(hi); x, y = x[m], y[m]
    if len(x) < 6:
        return None
    o = np.argsort(x); x, y = x[o], y[o]
    u = np.log10(x)

    # opaque floor = %T at the concentrated end (first ~10% of points)
    k = max(3, len(y) // 10)
    baseline = float(np.min(y[:k]))

    # coacervation clarification peak = MOST PROMINENT interior local max (not
    # the fully diluted clear tail / endpoint). If the biggest max is the last
    # point, the curve is a monotone clearing (no hump) -> flag it.
    peak_i = int(np.argmax(y))
    monotone = peak_i >= len(y) - 2
    if find_peaks is not None:
        span = max(1.0, float(np.nanmax(y) - baseline))
        pk, props = find_peaks(y, prominence=0.10 * span, distance=3)
        if len(pk):
            peak_i = int(pk[int(np.argmax(props["prominences"]))])
            monotone = False
    peak_pct = float(y[peak_i]); peak_dil = float(x[peak_i])
    amp = peak_pct - baseline
    thr = baseline + base_frac * amp

    onset_i = next((i for i in range(peak_i + 1) if y[i] >= thr), 0)
    redis_i = next((i for i in range(peak_i, len(y)) if y[i] <= thr), None)
    onset = float(x[onset_i])
    redis = float(x[redis_i]) if redis_i is not None else None

    hi = redis_i if redis_i is not None else len(y) - 1
    seg = slice(onset_i, hi + 1)
    _trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))
    inverse_auc = float(_trapz(np.clip(y[seg] - baseline, 0, None), u[seg]))
    width = float(round(np.log10(redis / onset), 2)) if redis and onset else None

    if monotone:
        note = ("No clarification HUMP - %T rises monotonically to the dilute end "
                "(stays clear). Expected for a proper inverse run is a hump that "
                "returns toward opaque at high dilution: confirm the sample was "
                "CENTRIFUGED (supernatant read) and re-opacifies when very dilute.")
    elif redis is None:
        note = ("Hump found but does NOT re-dissolve within the measured range "
                "(dilute end stays clear) - AUC integrated to range end; set a "
                "dilution window if needed.")
    else:
        note = ""

    return {
        "baseline_pct": round(baseline, 1),
        "peak_pct": round(peak_pct, 1),
        "peak_dilution": round(peak_dil, 1),
        "amplitude": round(amp, 1),
        "onset_dilution": round(onset, 1),
        "redissolution_dilution": round(redis, 1) if redis else None,
        "width_decades": width,
        "inverse_auc": round(inverse_auc, 2),
        "monotone": bool(monotone),
        "note": note,
        # region under the hump that was integrated (for shading the plot)
        "auc_lo": round(float(x[onset_i]), 2),
        "auc_hi": round(float(x[hi]), 2),
        "baseline": round(baseline, 2),
    }


# --------------------------------------------------------------------------- #
# JSON store
# --------------------------------------------------------------------------- #
def load_store() -> list:
    if LASENTEC_STORE.exists():
        try:
            data = json.loads(LASENTEC_STORE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:  # noqa: BLE001
            return []
    return []


def save_store(records: list) -> None:
    LASENTEC_STORE.write_text(json.dumps(records, indent=2), encoding="utf-8")


def _rec_key(sample_id: str, name: str, dilution=None) -> str:
    base = (sample_id or "").strip() or ("name:" + (name or "").strip().lower())
    if dilution:
        try:
            return f"{base}@1:{float(dilution):g}"
        except (TypeError, ValueError):
            pass
    return base


def upsert_record(*, sample_id, batch_id, name, csv_name, metrics, dilution=None,
                  chassis="", raw_response=False):
    """Insert/replace a Lasentec record.

    Key = (sample_id or name) + '@1:X' so the SAME sample can hold a SERIES of
    measurements at different dilutions (wash / rinse stages).
    chassis: optional formula/chassis label (groups records for overlay plots).
    raw_response: True when metrics.dist is an already-averaged Response curve
    (e.g. from ingest_wide_chord_csv) rather than a live per-scan FBRM export -
    such records default to un-normalized plotting.
    """
    recs = load_store()
    key = _rec_key(sample_id, name, dilution)
    depo = predict_deposition(metrics)
    sensory = sensory_readout(metrics, dilution) if dilution else {
        "stage": None, "flags": [], "verdict": ""}
    rec = {
        "key": key,
        "sample_id": sample_id or "",
        "batch_id": batch_id or "",
        "name": name or "",
        "chassis": chassis or "",
        "csv": csv_name or "",
        "dilution": dilution or "",
        "stage": sensory.get("stage") or "",
        "raw_response": bool(raw_response),
        "metrics": metrics,
        "deposition": depo,
        "sensory": sensory,
        "microscopy": [],
        "created": datetime.now().isoformat(timespec="seconds"),
    }
    existing = next((r for r in recs if r.get("key") == key), None)
    if existing:
        rec["microscopy"] = existing.get("microscopy", [])
        recs = [rec if r.get("key") == key else r for r in recs]
    else:
        recs.append(rec)
    save_store(recs)
    return rec


def records_by_sample_id(sample_id: str) -> list:
    """All Lasentec measurements (dilution series) for one sample, deepest last."""
    def _dil(r):
        try:
            return float(r.get("dilution") or 0)
        except (TypeError, ValueError):
            return 0.0
    return sorted([r for r in load_store() if r.get("sample_id") == sample_id],
                  key=_dil)


def delete_record(key: str) -> bool:
    recs = load_store()
    new = [r for r in recs if r.get("key") != key]
    if len(new) != len(recs):
        save_store(new)
        return True
    return False


def rename_record(key: str, new_name: str) -> bool:
    """Rename the display name of a stored Lasentec record (key unchanged)."""
    new_name = (new_name or "").strip()
    if not new_name:
        return False
    recs = load_store()
    for r in recs:
        if r.get("key") == key:
            r["name"] = new_name
            save_store(recs)
            return True
    return False


def attach_microscopy(key: str, image_name: str, caption: str = "") -> bool:
    recs = load_store()
    for r in recs:
        if r.get("key") == key:
            r.setdefault("microscopy", []).append(
                {"image": image_name, "caption": caption})
            save_store(recs)
            return True
    return False


def record_by_sample_id(sample_id: str):
    for r in load_store():
        if r.get("sample_id") and r["sample_id"] == sample_id:
            return r
    return None
