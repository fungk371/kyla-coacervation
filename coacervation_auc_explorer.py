"""AUC Explorer - server-safe compute helpers for the interactive bar-graph tab.

Lets the web UI compute a coacervation AUC per (plate, trough) series under a
user-chosen timepoint and AUC mode, so bar graphs like the dextran
concentration-response figure can be built interactively.

All AUC modes integrate the turbidity signal over LOG-dilution (equal weight per
decade) so the late high-dilution trough is captured:
  * full      - whole curve (min..max dilution)
  * window    - user dilution window [lo, hi] (1:X)
  * consumer  - 1:1 .. 1:20 preset
  * early_late- early (1:1..split) vs late (split..max) as a pair
  * trough    - peak turbidity (= min %T), not an integral

Signal: absorbance A = -log10(T/100)  (default, turbidity)  OR
        %T-based turbidity = (100 - %T)   (use_pct=True).
"""
from __future__ import annotations

import numpy as np

from coacervation_analysis import dilution_ratio, transmittance_to_absorbance

_trapz = getattr(np, "trapezoid", getattr(np, "trapz", None))
CONSUMER = (1.0, 20.0)


def _clean(x, y):
    """Conservative single-well bubble/spike removal (rolling-median MAD)."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    n = len(y)
    if n < 7:
        return x, y
    half, med = 2, np.empty(n)
    for i in range(n):
        med[i] = np.median(y[max(0, i - half):min(n, i + half + 1)])
    resid = y - med
    mad = np.median(np.abs(resid - np.median(resid)))
    sigma = 1.4826 * mad if mad > 0 else 1e-9
    keep = np.abs(resid) <= max(4.5 * sigma, 6.0)
    return x[keep], y[keep]


def curve_at(df, trough, timepoint, clean=True):
    """Return (x_dilution ascending, y_pct) for one trough at nearest timepoint.

    df must be an annotated long dataframe (columns: trough, timepoint_minutes,
    formula_fraction, transmission_pct).
    """
    sel = df[df["trough"] == trough].dropna(subset=["formula_fraction"])
    if sel.empty:
        return None
    times = sorted(sel["timepoint_minutes"].unique())
    t = min(times, key=lambda z: abs(z - timepoint))
    cur = sel[sel["timepoint_minutes"] == t].sort_values(
        "formula_fraction", ascending=False)
    x = np.asarray(dilution_ratio(cur["formula_fraction"].to_numpy(float)), float)
    y = cur["transmission_pct"].to_numpy(float)
    o = np.argsort(x)
    x, y = x[o], y[o]
    if clean:
        x, y = _clean(x, y)
    return (x, y) if len(x) >= 2 else None


def available_timepoints(df, trough):
    sel = df[df["trough"] == trough].dropna(subset=["formula_fraction"])
    return sorted(float(t) for t in sel["timepoint_minutes"].unique())


def _signal(y, use_pct):
    return (100.0 - np.asarray(y, float)) if use_pct else \
        transmittance_to_absorbance(np.asarray(y, float))


def _integ(x, sig, lo, hi):
    """Integrate signal over log10(dilution) within dilution [lo, hi]."""
    x = np.asarray(x, float)
    lx = np.log10(np.clip(x, 1e-9, None))
    mask = (x >= lo) & (x <= hi)
    if mask.sum() < 2:
        return 0.0
    o = np.argsort(lx[mask])
    return float(_trapz(sig[mask][o], lx[mask][o]))


def auc_value(x, y, mode="full", lo=1.0, hi=None, split=20.0, use_pct=False):
    """Return a single AUC number (or for 'trough', peak turbidity).

    For 'early_late' use early_late() instead (returns a pair).
    """
    x = np.asarray(x, float)
    sig = _signal(y, use_pct)
    xmax = float(x.max()); xmin = float(x.min())
    if mode == "full":
        return _integ(x, sig, xmin, xmax)
    if mode == "consumer":
        return _integ(x, sig, *CONSUMER)
    if mode == "window":
        return _integ(x, sig, float(lo), float(hi) if hi else xmax)
    if mode == "trough":
        return float(np.max(sig))
    return _integ(x, sig, xmin, xmax)


def early_late(x, y, split=20.0, use_pct=False):
    x = np.asarray(x, float)
    sig = _signal(y, use_pct)
    early = _integ(x, sig, float(x.min()), float(split))
    late = _integ(x, sig, float(split), float(x.max()))
    return early, late


def metric_for_series(df, trough, timepoint, *, mode="full", lo=1.0, hi=None,
                      split=20.0, use_pct=False, avg02=False):
    """Compute the chosen metric for one series.

    avg02=True averages the metric over t=0,1,2 (the '0-2 min avg' option).
    Returns {'value': float} or {'early': .., 'late': ..} for early_late,
    or None if the series is unavailable.
    """
    def _one(tp):
        c = curve_at(df, trough, tp)
        if c is None:
            return None
        x, y = c
        if mode == "early_late":
            return early_late(x, y, split=split, use_pct=use_pct)
        return auc_value(x, y, mode=mode, lo=lo, hi=hi, split=split, use_pct=use_pct)

    tps = [0.0, 1.0, 2.0] if avg02 else [timepoint]
    vals = [_one(t) for t in tps]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    if mode == "early_late":
        e = float(np.mean([v[0] for v in vals]))
        la = float(np.mean([v[1] for v in vals]))
        return {"early": e, "late": la}
    return {"value": float(np.mean(vals))}
