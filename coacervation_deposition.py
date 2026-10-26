"""
Deposition insights: turn coacervation measurements into a predicted
performance number (e.g. Piroctone Olamine / PO deposition) using uploadable
correlation models.

Seeded with the two correlations from the Project Zorro SLR (Shah/Schubert,
2024), which link measured formula properties to in-vivo PO deposition in a
5/5/2 AOS/SLS/CAPB chassis:

  * PO depo = 0.0019 * (MW[kDa] * charge_density) + 0.5462   (R^2 = 0.858)
  * PO depo = 0.0005 * (coacervate particles > 30 um)  + 0.5199 (R^2 = 0.923)

Both extrapolate to ~0.52-0.55 ug/cm^2 at zero polymer (chassis-only baseline).

Models are simple linear fits `y = slope * x + intercept` over a named
`predictor`, so users can add their own as new studies land. This is a
directional screening aid, NOT a validated predictor outside the study context.
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Predictors: how to compute x for a sample dict
# --------------------------------------------------------------------------- #
def _num(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def predictor_value(sample: dict, predictor: str):
    """Compute the model's x-value for a sample, or None if unavailable."""
    if predictor == "mw_cd":
        mw, cd = _num(sample.get("mw_kda")), _num(sample.get("charge"))
        if mw is None or cd is None:
            return None
        return mw * cd
    if predictor == "particles_gt_30um":
        return _num(sample.get("particles_gt_30um"))
    if predictor == "coacervate_size_um":
        return _num(sample.get("coacervate_size_um"))
    if predictor == "auc":
        return _num(sample.get("auc"))
    # custom: read a same-named field
    return _num(sample.get(predictor))


PREDICTOR_LABELS = {
    "mw_cd": "MW x charge density",
    "particles_gt_30um": "coacervate particles > 30 um",
    "coacervate_size_um": "coacervate size (um)",
    "auc": "AUC",
}


# --------------------------------------------------------------------------- #
# Default models (Project Zorro SLR)
# --------------------------------------------------------------------------- #
DEFAULT_MODELS = [
    {
        "name": "Zorro: MW x CD (5/5/2 AOS/SLS/CAPB)",
        "outcome": "PO deposition",
        "predictor": "mw_cd",
        "slope": 0.0019,
        "intercept": 0.5462,
        "r2": 0.858,
        "units": "ug/cm^2",
        "baseline": 0.55,
        "chassis_context": "5/5/2 AOS/SLS/CAPB, 0.5% polymer, 0.5% PO",
        "source": "Project Zorro SLR (Shah/Schubert, 2024), Fig 1b",
        "priority": 1,
    },
    {
        "name": "Zorro: coacervate particles > 30 um (5/5/2)",
        "outcome": "PO deposition",
        "predictor": "particles_gt_30um",
        "slope": 0.0005,
        "intercept": 0.5199,
        "r2": 0.923,
        "units": "ug/cm^2",
        "baseline": 0.52,
        "chassis_context": "5/5/2 AOS/SLS/CAPB, 0.5% polymer, 0.5% PO",
        "source": "Project Zorro SLR (Shah/Schubert, 2024), Fig 2",
        "priority": 2,  # stronger R^2 -> preferred when data is available
    },
]


def depo_class(value: float | None) -> str:
    """Coarse 1x / 1.5x / 2x class relative to the ~0.55 chassis baseline."""
    if value is None:
        return ""
    if value < 0.75:
        return "sub-baseline"
    if value < 1.3:
        return "~1x"
    if value < 1.8:
        return "~1.5x"
    return "~2x"


def predict_one(sample: dict, model: dict) -> dict | None:
    """Apply a single model to a sample. Returns None if the predictor value
    is unavailable for this sample."""
    x = predictor_value(sample, model.get("predictor", "mw_cd"))
    if x is None:
        return None
    slope = _num(model.get("slope")) or 0.0
    intercept = _num(model.get("intercept")) or 0.0
    value = slope * x + intercept
    return {
        "value": round(value, 3),
        "x": round(x, 3),
        "predictor": model.get("predictor"),
        "predictor_label": PREDICTOR_LABELS.get(model.get("predictor"),
                                                model.get("predictor")),
        "model": model.get("name"),
        "outcome": model.get("outcome", "PO deposition"),
        "units": model.get("units", "ug/cm^2"),
        "r2": model.get("r2"),
        "chassis_context": model.get("chassis_context", ""),
        "source": model.get("source", ""),
        "depo_class": depo_class(value),
    }


def predict_best(sample: dict, models: list[dict]) -> dict | None:
    """Pick the highest-priority (then highest-R^2) model whose predictor is
    available for this sample, and apply it."""
    applicable = []
    for m in models:
        if predictor_value(sample, m.get("predictor", "mw_cd")) is not None:
            applicable.append(m)
    if not applicable:
        return None
    applicable.sort(key=lambda m: (m.get("priority", 0), m.get("r2") or 0),
                    reverse=True)
    return predict_one(sample, applicable[0])
