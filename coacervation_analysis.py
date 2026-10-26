"""
Coacervation absorbance/AUC analysis.

Pipeline for the coacervation capability plots:
  1. Convert %Transmittance to Absorbance:  A = 2 - log10(%T)
  2. Plot Absorbance vs. Concentration (formula fraction), x-axis oriented
     from MOST concentrated (left) to LEAST concentrated (right).
  3. Fit a smooth best-fit curve through the points.
  4. Integrate Area-Under-Curve (AUC) over a user-selected dilution window.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

try:
    from scipy.interpolate import UnivariateSpline, PchipInterpolator, Akima1DInterpolator
    from scipy.integrate import quad
    _HAVE_SCIPY = True
except Exception:  # pragma: no cover
    _HAVE_SCIPY = False


# --------------------------------------------------------------------------- #
# Conversions
# --------------------------------------------------------------------------- #
def transmittance_to_absorbance(pct_t: np.ndarray | float) -> np.ndarray | float:
    """Convert percent transmittance to absorbance.

    A = -log10(T) with T = %T / 100  ->  A = 2 - log10(%T).
    %T values are clipped to a tiny positive floor to avoid log(0).
    """
    t = np.asarray(pct_t, dtype=float)
    t = np.clip(t, 1e-6, None)
    a = 2.0 - np.log10(t)
    return float(a) if np.isscalar(pct_t) else a


def dilution_ratio(formula_fraction: np.ndarray | float) -> np.ndarray | float:
    """Convert a formula fraction f to its dilution ratio X (i.e. 1:X).

    Derived from the master plate template: X = (1 - f) / f.
    f = 0.5 -> 1:1, f = 1/3 -> 1:2, f = 0.25 -> 1:3, f = 1/101 -> 1:100.
    """
    f = np.asarray(formula_fraction, dtype=float)
    f = np.clip(f, 1e-9, 0.999999)
    x = (1.0 - f) / f
    return float(x) if np.isscalar(formula_fraction) else x


# --------------------------------------------------------------------------- #
# Curve fitting
# --------------------------------------------------------------------------- #
@dataclass
class CurveFit:
    """A fitted curve callable over the concentration domain."""

    x: np.ndarray            # sorted ascending concentration
    y: np.ndarray            # absorbance at x (sorted with x)
    kind: str
    _fn: object              # callable f(conc) -> absorbance

    def __call__(self, xq: np.ndarray | float) -> np.ndarray | float:
        return self._fn(xq)

    def dense(self, n: int = 400) -> tuple[np.ndarray, np.ndarray]:
        xs = np.linspace(self.x.min(), self.x.max(), n)
        return xs, np.asarray(self(xs))


def _lowess_smooth(x, y, frac=0.3, n_iter=2, n_grid=240):
    """Robust locally-weighted regression (LOWESS).

    Follows genuine local structure (e.g. the coacervate trough) without the
    boundary overshoot / spurious wiggles a global smoothing spline produces on
    steep, unevenly-sampled data. Returns a dense (xd, yd) grid.

    frac    : fraction of points in each local window (bandwidth).
    n_iter  : robustifying (bisquare) iterations to reject outliers.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    k = max(2, int(np.ceil(frac * n)))

    def local_fit(x0, rob):
        d = np.abs(x - x0)
        h = np.sort(d)[min(k, n - 1)]
        h = max(h, 1e-12)
        w = np.clip(d / h, 0.0, 1.0)
        w = (1.0 - w ** 3) ** 3          # tricube kernel
        w = w * rob
        sw = w.sum()
        if sw <= 0:
            return float(np.interp(x0, x, y))
        wx = (w * x).sum() / sw
        wy = (w * y).sum() / sw
        sxx = (w * (x - wx) ** 2).sum()
        sxy = (w * (x - wx) * (y - wy)).sum()
        b = sxy / sxx if sxx > 1e-12 else 0.0
        a = wy - b * wx
        return a + b * x0

    rob = np.ones(n)
    for _ in range(max(0, n_iter)):
        fitted = np.array([local_fit(xi, rob) for xi in x])
        resid = y - fitted
        s = np.median(np.abs(resid))
        if s <= 1e-12:
            break
        u = np.clip(resid / (6.0 * s), -1.0, 1.0)
        rob = (1.0 - u ** 2) ** 2         # bisquare robustness weights

    xd = np.linspace(x.min(), x.max(), n_grid)
    yd = np.array([local_fit(xi, rob) for xi in xd])
    return xd, yd



def fit_curve(
    concentration: np.ndarray,
    absorbance: np.ndarray,
    kind: str = "spline",
    smoothing: Optional[float] = None,
) -> CurveFit:
    """Fit a smooth best-fit curve of absorbance vs. concentration.

    Args:
        concentration: formula-fraction / concentration values (any order).
        absorbance: absorbance values aligned with concentration.
        kind: 'spline' (smoothing spline, default), 'pchip' (monotone),
              'akima', or 'poly' (polynomial fallback).
        smoothing: smoothing factor for the spline. If None a heuristic based
                   on the data variance is used. Larger = smoother.

    Returns:
        CurveFit callable.
    """
    x = np.asarray(concentration, dtype=float)
    y = np.asarray(absorbance, dtype=float)

    # sort ascending and collapse duplicate x (spline requires strictly increasing x)
    order = np.argsort(x)
    x, y = x[order], y[order]
    ux, inv = np.unique(x, return_inverse=True)
    if len(ux) != len(x):
        uy = np.array([y[inv == i].mean() for i in range(len(ux))])
        x, y = ux, uy

    if not _HAVE_SCIPY or kind == "poly":
        deg = min(6, max(2, len(x) - 1))
        coeffs = np.polyfit(x, y, deg)
        fn = np.poly1d(coeffs)
        return CurveFit(x, y, "poly", fn)

    if kind == "lowess":
        # robust local regression - captures troughs, no boundary overshoot.
        frac = smoothing if (smoothing is not None and 0.0 < smoothing < 1.0) else 0.3
        xd, yd = _lowess_smooth(x, y, frac=frac)
        fn = PchipInterpolator(xd, yd, extrapolate=True)
        return CurveFit(x, y, "lowess", fn)

    if kind == "pchip":
        fn = PchipInterpolator(x, y)
    elif kind == "akima":
        fn = Akima1DInterpolator(x, y)
    else:  # smoothing spline
        if smoothing is None:
            # heuristic: scale with number of points and variance
            smoothing = len(x) * np.var(y) * 0.15
        k = min(3, len(x) - 1)
        fn = UnivariateSpline(x, y, k=k, s=smoothing)

    return CurveFit(x, y, kind, fn)


# --------------------------------------------------------------------------- #
# AUC over a dilution window
# --------------------------------------------------------------------------- #
def compute_auc(
    concentration: np.ndarray,
    absorbance: np.ndarray,
    window: Optional[tuple[float, float]] = None,
    use_fit: bool = True,
    kind: str = "spline",
    smoothing: Optional[float] = None,
) -> dict:
    """Integrate absorbance over a concentration window.

    Args:
        concentration: concentration values.
        absorbance: absorbance values.
        window: (low, high) concentration bounds to integrate between. If None,
                the full concentration range is used.
        use_fit: integrate the fitted curve (True) or the raw trapezoid (False).
        kind, smoothing: passed to fit_curve when use_fit is True.

    Returns:
        dict with keys: auc, low, high, width, mean_absorbance, method.
    """
    x = np.asarray(concentration, dtype=float)
    y = np.asarray(absorbance, dtype=float)

    lo, hi = (x.min(), x.max()) if window is None else window
    lo, hi = float(min(lo, hi)), float(max(lo, hi))
    lo = max(lo, x.min())
    hi = min(hi, x.max())
    width = hi - lo
    if width <= 0:
        return {"auc": 0.0, "low": lo, "high": hi, "width": 0.0,
                "mean_absorbance": 0.0, "method": "empty"}

    if use_fit and _HAVE_SCIPY:
        fit = fit_curve(x, y, kind=kind, smoothing=smoothing)
        auc, _ = quad(lambda t: float(fit(t)), lo, hi, limit=200)
        method = f"fit:{kind}"
    else:
        mask = (x >= lo) & (x <= hi)
        xs, ys = x[mask], y[mask]
        order = np.argsort(xs)
        auc = float(np.trapz(ys[order], xs[order]))
        method = "trapezoid"

    return {
        "auc": float(auc),
        "low": lo,
        "high": hi,
        "width": width,
        "mean_absorbance": float(auc / width) if width else 0.0,
        "method": method,
    }


# --------------------------------------------------------------------------- #
# Noise / data-quality assessment
# --------------------------------------------------------------------------- #
def assess_noise(concentration, pct_transmittance, *, kind: str = "spline") -> dict:
    """Assess how noisy a dilution curve is and suggest likely causes/actions.

    Fits a smooth trend (vs. log dilution) and analyses the residuals:
      - RMSE of residuals (overall scatter, in %T units)
      - isolated outlier points (|residual| beyond a robust threshold) -> often
        air bubbles / debris in the light path
      - point-to-point sign changes (jitter/roughness)

    Returns a dict with: noisy (bool), score (RMSE %T), n_outliers, jitter,
    message, recommendations (list).
    """
    conc = np.asarray(concentration, dtype=float)
    pct = np.asarray(pct_transmittance, dtype=float)
    if len(conc) < 5:
        return {"noisy": False, "score": 0.0, "n_outliers": 0, "jitter": 0.0,
                "message": "", "recommendations": []}

    x = np.log10(np.clip(dilution_ratio(conc), 1e-9, None))
    order = np.argsort(x)
    x, y = x[order], pct[order]

    smoothing = len(x) * (np.var(y) or 1.0) * 0.5  # heavier = true trend
    fit = fit_curve(x, y, kind="spline", smoothing=smoothing)
    resid = y - np.asarray(fit(x))

    rmse = float(np.sqrt(np.mean(resid ** 2)))
    std = float(np.std(resid)) or 1e-9
    thr = max(3.0 * std, 4.0)  # %T units
    outliers = np.where(np.abs(resid) > thr)[0]
    n_out = int(len(outliers))
    sign_changes = int(np.sum(np.diff(np.sign(resid)) != 0))
    jitter = sign_changes / max(1, len(resid) - 1)

    noisy = (rmse > 2.5) or (n_out >= 2) or (jitter > 0.6)

    recs = []
    message = ""
    if noisy:
        recs.append("Re-run this sample/trough to confirm the profile.")
        if n_out >= 1:
            recs.append(
                f"{n_out} isolated outlier point(s) — likely an air bubble or "
                "debris in the light path; degas/spin down and re-read the "
                "affected dilution wells."
            )
        if jitter > 0.6:
            recs.append(
                "High point-to-point scatter — check mixing, thermal "
                "equilibration, and instrument settling time before reading."
            )
        if rmse > 5:
            recs.append(
                "Large deviation from a smooth trend — verify dilution-series "
                "accuracy and pipetting/liquid handling."
            )
        message = (
            f"Noisy data: RMSE={rmse:.1f} %T, {n_out} outlier(s), "
            f"jitter={jitter:.2f}."
        )

    return {"noisy": noisy, "score": round(rmse, 2), "n_outliers": n_out,
            "jitter": round(jitter, 2), "message": message,
            "recommendations": recs}


# --------------------------------------------------------------------------- #
# Coacervation fingerprint
# --------------------------------------------------------------------------- #
def _dilution_label(x: Optional[float]) -> Optional[str]:
    """Format a dilution ratio X as '1:X' (or None)."""
    if x is None or not np.isfinite(x):
        return None
    return f"1:{x:.1f}"


def compute_fingerprint(
    concentration,
    pct_transmittance,
    *,
    kind: str = "spline",
    noise: Optional[dict] = None,
) -> Optional[dict]:
    """Summarise a dilution curve into a formulator-readable fingerprint.

    Works on the absorbance-vs-dilution curve (A = 2 - log10(%T)). As a shampoo
    is diluted the coacervate turbidity rises to a peak (maximum coacervation)
    then may fall again as droplets re-dissolve. This extracts:

      - onset_dilution     : 1:X where absorbance first rises off baseline
      - peak_dilution      : 1:X at maximum absorbance (peak coacervation)
      - recovery_dilution  : 1:X where absorbance falls back toward baseline
      - peak_absorbance    : absorbance at the peak
      - amplitude          : peak - baseline absorbance (signal strength)
      - width_decades      : half-max width in dilution decades
      - width_label        : narrow / moderate / broad
      - recovery_label     : strong / moderate / weak / none
      - strength_label     : strong / moderate / weak
      - interpretation     : heuristic conditioning / rinse read-out
      - confidence         : high / medium / low (data-quality aware)

    Categorical labels and the interpretation are heuristics for internal
    screening — not a validated performance model.

    Returns None if there are too few points to characterise.
    """
    conc = np.asarray(concentration, dtype=float)
    pct = np.asarray(pct_transmittance, dtype=float)
    ok = np.isfinite(conc) & np.isfinite(pct)
    conc, pct = conc[ok], pct[ok]
    if len(conc) < 5 or float(np.nanmax(pct)) < 1.0:
        return None

    absb = np.asarray(transmittance_to_absorbance(pct), dtype=float)

    # Dense, log-spaced dilution grid mapped back to formula fraction so the
    # peak/onset/width are measured evenly across the dilution axis.
    X = np.asarray(dilution_ratio(conc), dtype=float)
    xlo, xhi = float(np.min(X)), float(np.max(X))
    if not (xhi > xlo):
        return None
    try:
        fit = fit_curve(conc, absb, kind=kind)
        grid_X = np.logspace(np.log10(max(xlo, 1e-3)), np.log10(xhi), 400)
        grid_f = 1.0 / (1.0 + grid_X)
        grid_A = np.asarray(fit(grid_f), dtype=float)
    except Exception:  # noqa: BLE001 - fall back to raw points if the fit fails
        order = np.argsort(X)
        grid_X, grid_A = X[order], absb[order]

    grid_A = np.clip(grid_A, 0.0, None)
    baseline = float(np.min(grid_A))
    peak_idx = int(np.argmax(grid_A))
    peak_A = float(grid_A[peak_idx])
    peak_X = float(grid_X[peak_idx])
    amplitude = max(0.0, peak_A - baseline)

    # Flat / no meaningful transition.
    if amplitude < 0.03:
        return {
            "onset_dilution": None, "onset_label": None,
            "peak_dilution": round(peak_X, 1), "peak_label": _dilution_label(peak_X),
            "recovery_dilution": None, "recovery_label_dil": None,
            "peak_absorbance": round(peak_A, 3), "amplitude": round(amplitude, 3),
            "width_decades": 0.0, "width_label": "flat",
            "recovery_label": "none", "recovery_fraction": 0.0,
            "strength_label": "weak",
            "in_situ": False, "onset_mode": "none",
            "conc_end_fraction": 0.0, "preferred": False,
            "interpretation": "Minimal coacervation — light deposition / low "
                              "conditioning signal.",
            "confidence": "low",
            "notes": ["Curve is essentially flat; no clear coacervation "
                      "transition over this dilution range."],
        }

    onset_thr = baseline + 0.15 * amplitude
    half_thr = baseline + 0.5 * amplitude

    # Onset: first rise off baseline scanning from concentrated -> peak.
    onset_X = None
    for i in range(peak_idx + 1):
        if grid_A[i] >= onset_thr:
            onset_X = float(grid_X[i])
            break

    # Recovery point: first fall back toward baseline after the peak.
    recovery_X = None
    for i in range(peak_idx, len(grid_A)):
        if grid_A[i] <= onset_thr:
            recovery_X = float(grid_X[i])
            break

    # Half-max width in dilution decades.
    above = np.where(grid_A >= half_thr)[0]
    if len(above) >= 2:
        x_left, x_right = float(grid_X[above[0]]), float(grid_X[above[-1]])
        width_decades = float(np.log10(max(x_right, 1e-6) / max(x_left, 1e-6)))
    else:
        width_decades = 0.0

    # How far the curve recovers by the most-dilute end.
    end_A = float(grid_A[-1])
    recovery_fraction = float(np.clip((peak_A - end_A) / amplitude, 0.0, 1.0))

    # ---- In-situ (pre-formed) vs in-use (dilution-triggered) ----
    # The most concentrated point tested is 1:1 (already the first dilution).
    # If the curve is already substantially turbid there with no clear->cloudy
    # rise on dilution, the coacervate was very likely formed in the bottle
    # (in-situ) rather than triggered by dilution (in-use). In-situ coacervation
    # is LESS preferred: it gives small pre-formed particles and higher, poorly
    # targeted small-particle deposition. In-use (dilution-triggered)
    # coacervation is what we want. Optical data alone can't fully prove it, so
    # this is flagged as "suspected" and should be confirmed on the neat vial.
    conc_end_A = float(grid_A[0])
    conc_end_fraction = float(np.clip((conc_end_A - baseline) / amplitude, 0.0, 1.0)) \
        if amplitude > 0 else 0.0
    conc_end_pct = float(100.0 * 10 ** (-conc_end_A))  # %T at the concentrated end
    in_situ = bool((onset_X is None or onset_X <= 1.3)
                   and conc_end_fraction >= 0.5
                   and conc_end_pct < 80.0)
    if in_situ:
        onset_mode = "in-situ (suspected, pre-formed)"
    elif onset_X is not None:
        onset_mode = "in-use (dilution-triggered)"
    else:
        onset_mode = "none"

    # ---- Categorical labels ----
    if amplitude >= 0.25:
        strength_label = "strong"
    elif amplitude >= 0.10:
        strength_label = "moderate"
    else:
        strength_label = "weak"

    if width_decades >= 0.9:
        width_label = "broad"
    elif width_decades >= 0.45:
        width_label = "moderate"
    else:
        width_label = "narrow"

    if recovery_fraction >= 0.6:
        recovery_label = "strong"
    elif recovery_fraction >= 0.35:
        recovery_label = "moderate"
    else:
        recovery_label = "weak"

    # ---- Interpretation heuristic ----
    if strength_label == "weak":
        interpretation = ("Minimal coacervation — light deposition / low "
                          "conditioning signal.")
    else:
        cond = f"{strength_label} conditioning"
        if recovery_label == "weak":
            rinse = "slower rinse"
        elif recovery_label == "strong":
            rinse = "cleaner rinse"
        else:
            rinse = "moderate rinse"
        interpretation = f"{cond.capitalize()} / {rinse}"
        if width_label == "broad":
            interpretation += "; broad dilution tolerance"
    if in_situ and strength_label != "weak":
        interpretation += " \u2014 IN-SITU (pre-formed) coacervate: less preferred"

    # ---- Confidence (data-quality aware) ----
    confidence = "high"
    notes: list[str] = []
    if amplitude < 0.06:
        confidence = "low"
        notes.append("Weak signal amplitude — interpret with caution.")
    if noise and noise.get("noisy"):
        score = float(noise.get("score", 0) or 0)
        confidence = "low" if score > 5 or confidence == "low" else "medium"
        notes.append("Curve flagged as noisy; fingerprint may be unreliable.")
    if onset_X is None:
        notes.append("Onset falls at or below the most concentrated point tested.")
    if recovery_X is None:
        notes.append("No recovery within the tested dilution range "
                     "(coacervate persists when diluted).")
    if in_situ:
        notes.append("Already turbid at 1:1 with no clear\u2192cloudy rise on dilution: "
                     "coacervate likely formed IN THE BOTTLE (in-situ), which is less "
                     "preferred than in-use (dilution-triggered) coacervation. "
                     "Confirm on the neat product vial.")

    return {
        "onset_dilution": round(onset_X, 1) if onset_X else None,
        "onset_label": _dilution_label(onset_X),
        "peak_dilution": round(peak_X, 1),
        "peak_label": _dilution_label(peak_X),
        "recovery_dilution": round(recovery_X, 1) if recovery_X else None,
        "recovery_label_dil": _dilution_label(recovery_X),
        "peak_absorbance": round(peak_A, 3),
        "amplitude": round(amplitude, 3),
        "width_decades": round(width_decades, 2),
        "width_label": width_label,
        "recovery_label": recovery_label,
        "recovery_fraction": round(recovery_fraction, 2),
        "strength_label": strength_label,
        "in_situ": in_situ,
        "onset_mode": onset_mode,
        "conc_end_fraction": round(conc_end_fraction, 2),
        "preferred": bool(not in_situ and strength_label != "weak"),
        "interpretation": interpretation,
        "confidence": confidence,
        "notes": notes,
    }

