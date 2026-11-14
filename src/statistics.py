"""Statistical trend estimates (Member A starting point).

Illustrative non-seasonal tests: not yet corrected for temporal
autocorrelation, seasonality, multiple comparisons, or spatial uncertainty.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import stats

from src.preprocessing import validate_timeseries


def _finite(value: float) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def estimate_trend(data) -> dict:
    """Fit a year-scaled linear trend plus robust Theil-Sen and Kendall estimates."""
    frame = validate_timeseries(data)
    if len(frame) < 3:
        raise ValueError("At least three observations are required")
    if frame["variable"].nunique() != 1 or frame["region_id"].nunique() != 1:
        raise ValueError("estimate_trend requires one region and one variable")
    if frame["unit"].nunique() != 1:
        raise ValueError("Mixed units within a variable are not allowed")
    x = ((frame["date"] - frame["date"].min()).dt.total_seconds() / (365.25 * 86400)).to_numpy()
    y = frame["value"].to_numpy(dtype=float)
    if np.ptp(x) <= 0:
        raise ValueError("Need distinct observation dates")
    linear = stats.linregress(x, y)
    critical = stats.t.ppf(0.975, len(x) - 2)
    err = critical * linear.stderr
    theil = stats.theilslopes(y, x, alpha=0.95)
    tau, kendall_p = stats.kendalltau(x, y)
    return {
        "variable": str(frame["variable"].iloc[0]),
        "unit": str(frame["unit"].iloc[0]),
        "n_observations": len(frame),
        "slope_per_year": _finite(linear.slope),
        "slope_95ci": [_finite(linear.slope - err), _finite(linear.slope + err)],
        "p_value": _finite(linear.pvalue),
        "theil_sen_slope_per_year": _finite(theil.slope),
        "theil_sen_95ci": [_finite(theil.low_slope), _finite(theil.high_slope)],
        "kendall_tau": _finite(tau),
        "kendall_p_value": _finite(kendall_p),
    }
