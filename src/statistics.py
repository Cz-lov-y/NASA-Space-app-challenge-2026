"""Trend analysis on annual observations or complete monthly calendar years.

Public results contain JSON-compatible Python values. Slopes from high-level
functions are in input units per calendar year. No observations are imputed.
"""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import stats


def _alpha(alpha: float) -> None:
    if not 0 < alpha < 0.5:
        raise ValueError("alpha must lie strictly between 0 and 0.5")


def _numerical_tolerance(values: np.ndarray) -> float:
    """Relative floating-point noise threshold, not a domain effect-size cutoff.

    Do not impose a unit-sized floor: scientifically valid small-unit series
    must not be flattened merely because their absolute values are small.
    """
    scale = max(float(np.max(np.abs(values))), np.finfo(float).tiny)
    return float(100 * np.finfo(float).eps * scale)


def _numerically_constant(values: np.ndarray) -> bool:
    return bool(np.ptp(values) <= _numerical_tolerance(values))


def _xy(x: Iterable[float], y: Iterable[float]) -> tuple[np.ndarray, np.ndarray]:
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if x.ndim != 1 or y.ndim != 1 or len(x) != len(y) or len(x) < 3:
        raise ValueError("x and y must be equal-length 1-D arrays with at least 3 points")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("low-level functions require finite observations")
    order = np.argsort(x)
    x, y = x[order], y[order]
    if np.any(np.diff(x) <= 0):
        raise ValueError("timestamps must be unique")
    return x, y


def linear_regression(x: Iterable[float], y: Iterable[float], alpha: float = 0.05) -> dict:
    """OLS with a two-sided Student-t slope interval; independent errors assumed."""
    _alpha(alpha)
    x, y = _xy(x, y)
    # Center time to avoid an unnecessarily large fitted intercept.
    origin = float(x[0])
    if _numerically_constant(y):
        return {"slope": 0.0, "intercept": float(y[0]), "time_origin": origin,
                "p_value": 1.0, "r_squared": 0.0, "standard_error": 0.0,
                "confidence_interval": [0.0, 0.0], "confidence_level": 1 - alpha}
    fit = stats.linregress(x - origin, y)
    margin = float(stats.t.ppf(1 - alpha / 2, len(x) - 2) * fit.stderr)
    return {"slope": float(fit.slope), "intercept": float(fit.intercept),
            "time_origin": origin, "p_value": float(fit.pvalue),
            "r_squared": float(fit.rvalue ** 2), "standard_error": float(fit.stderr),
            "confidence_interval": [float(fit.slope - margin), float(fit.slope + margin)],
            "confidence_level": 1 - alpha}


def theil_sen(x: Iterable[float], y: Iterable[float], alpha: float = 0.05) -> dict:
    """Median pairwise slope; the interval describes the slope, not predictions."""
    _alpha(alpha)
    x, y = _xy(x, y)
    if _numerically_constant(y):
        return {"slope": 0.0, "intercept": float(y[0]), "time_origin": float(x[0]),
                "confidence_level": 1 - alpha, "confidence_interval": [0.0, 0.0]}
    fit = stats.theilslopes(y, x - x[0], alpha=1 - alpha, method="separate")
    return {"slope": float(fit.slope), "intercept": float(fit.intercept),
            "time_origin": float(x[0]), "confidence_level": 1 - alpha,
            "confidence_interval": [float(fit.low_slope), float(fit.high_slope)]}


def mann_kendall(values: Iterable[float], alpha: float = 0.05) -> dict:
    """Two-sided, tie-corrected, continuity-corrected asymptotic MK test.

    Input must already be in chronological order. This does NOT correct for
    seasonality or serial dependence. Small samples have weak approximation.
    """
    _alpha(alpha)
    y = np.asarray(values, dtype=float)
    if y.ndim != 1 or len(y) < 3 or not np.isfinite(y).all():
        raise ValueError("MK requires at least 3 finite chronological values")
    if _numerically_constant(y):
        y = np.full_like(y, y[0])
    n = len(y)
    s = int(sum(np.sign(y[i + 1:] - y[i]).sum() for i in range(n - 1)))
    _, counts = np.unique(y, return_counts=True)
    variance = float((n * (n - 1) * (2 * n + 5)
                      - np.sum(counts * (counts - 1) * (2 * counts + 5))) / 18)
    z = (s - int(np.sign(s))) / math.sqrt(variance) if variance > 0 else 0.0
    p = float(2 * stats.norm.sf(abs(z)))
    significant = p < alpha
    return {"s": s, "variance": variance, "z": float(z), "p_value": p,
            "tau_a": float(s / (n * (n - 1) / 2)), "significant": significant,
            "direction": ("increasing" if s > 0 else "decreasing") if significant else "no_significant_trend",
            "method": "asymptotic_mann_kendall_ties_continuity_corrected"}


def adjust_p_values(p_values: Iterable[float]) -> list[float | None]:
    """Benjamini-Hochberg adjusted p-values; missing tests count in family size.

    None/NaN tests return None and are treated as p=1 during adjustment.
    BH assumes independence or suitable positive dependence among tests.
    """
    p = np.array([np.nan if v is None else float(v) for v in p_values])
    if p.ndim != 1 or np.isinf(p).any() or np.any((p < 0) | (p > 1)):
        raise ValueError("p-values must be in [0, 1] or missing")
    if len(p) == 0:
        return []
    missing = np.isnan(p)
    p[missing] = 1.0
    order = np.argsort(p)
    ranked = p[order] * len(p) / np.arange(1, len(p) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1].clip(0, 1)
    adjusted = np.empty_like(p)
    adjusted[order] = ranked
    return [None if absent else float(v) for v, absent in zip(adjusted, missing)]


def _legacy_trend(result: dict, variable: str | None, unit: str | None, n_observations: int) -> dict:
    """Retain the team's existing flat estimate fields alongside detailed results."""
    ols, sen, mk = (result[k] for k in ("linear_regression", "theil_sen", "mann_kendall"))
    return {"variable": variable, "unit": unit, "n_observations": n_observations,
            "slope_per_year": ols["slope"] if ols else None,
            "slope_95ci": ols["confidence_interval"] if ols else None,
            "p_value": ols["p_value"] if ols else None,
            "theil_sen_slope_per_year": sen["slope"] if sen else None,
            "theil_sen_95ci": sen["confidence_interval"] if sen else None,
            "kendall_tau": mk["tau_a"] if mk else None,
            "kendall_p_value": mk["p_value"] if mk else None,
            "kendall_method": "asymptotic_mann_kendall_ties_continuity_corrected",
            "kendall_tau_variant": "tau_a"}


def estimate_trend(data: pd.DataFrame) -> dict:
    """Compatibility API: exploratory fit to raw observations, not a risk classifier.

    Fits require >=3 finite observations and retain the 365.25-day slope unit.
    Nonfinite values are excluded without imputation. Too few usable points
    return status='insufficient_data' and null estimates, including empty input.
    Use analyze_region for annual aggregation, reliability and multiple testing.
    """
    required = {"date", "value", "unit", "variable", "source", "region_id"}
    if not isinstance(data, pd.DataFrame) or not required.issubset(data.columns):
        raise ValueError("estimate_trend requires all six standard input columns")
    for column in ("variable", "region_id", "unit", "source"):
        if not data.empty and (data[column].isna().any() or data[column].nunique() != 1
                               or data[column].astype(str).str.strip().eq("").any()):
            raise ValueError(f"estimate_trend requires one nonmissing {column}")
    if not data.empty and pd.api.types.is_numeric_dtype(data["date"]):
        raise ValueError("date must contain dates, not integer years")
    dates = pd.to_datetime(data["date"], errors="coerce", utc=True)
    if dates.isna().any():
        raise ValueError("invalid dates")
    if dates.duplicated().any():
        raise ValueError("timestamps must be unique, including rows with missing values")
    numeric = pd.to_numeric(data["value"], errors="coerce")
    if (data["value"].notna() & numeric.isna()).any():
        raise ValueError("value contains nonnumeric text; encode missing values as null/NaN")
    values = numeric.to_numpy(dtype=float, na_value=np.nan)
    finite = np.isfinite(values)
    n_valid = int(finite.sum())
    fitted = {"linear_regression": None, "theil_sen": None, "mann_kendall": None}
    if n_valid >= 3:
        retained_dates = dates.loc[finite]
        elapsed = ((retained_dates - retained_dates.min()).dt.total_seconds() / (365.25 * 86400)).to_numpy()
        x, y = _xy(elapsed, values[finite])
        fitted = _trend_estimates(x, y, alpha=0.05)
    limitations = ["Raw observations are not corrected for seasonality, serial dependence or multiple comparisons."]
    if n_valid < len(data):
        limitations.append("Nonfinite observations were excluded without imputation; elapsed times are preserved.")
    if n_valid < 3:
        limitations.append("At least three finite observations are required for trend estimation.")
    return {**_legacy_trend(fitted, str(data.variable.iloc[0]) if len(data) else None,
                           str(data.unit.iloc[0]) if len(data) else None, n_valid),
            "status": "ok" if n_valid >= 3 else "insufficient_data",
            "inference_status": "exploratory_only" if n_valid >= 3 else "insufficient_data",
            "data_quality": {"n_raw_rows": len(data), "valid_observations": n_valid,
                             "dropped_observations": len(data) - n_valid,
                             "nonfinite_fraction": float(1 - n_valid / len(data)) if len(data) else None},
            "limitations": limitations}


def _prepare(data: pd.DataFrame, frequency: str, min_months: int) -> tuple[pd.Series, dict]:
    if frequency not in {"monthly", "annual"}:
        raise ValueError("frequency must be 'monthly' or 'annual'")
    if not isinstance(min_months, int) or isinstance(min_months, bool) or not 1 <= min_months <= 12:
        raise ValueError("min_months_per_year must be an integer from 1 to 12")
    if not isinstance(data, pd.DataFrame) or not {"date", "value"}.issubset(data.columns):
        raise ValueError("data must be a DataFrame with date and value columns")
    if data.empty:
        return pd.Series(dtype=float), {"input_rows": 0, "valid_observations": 0,
                "raw_expected_observations": 0, "raw_missing_fraction": None,
                "raw_excluded_years": [], "available_years": [], "raw_incomplete_retained_years": [],
                "_valid_counts_by_year": {}, "_slots_per_year": 12 if frequency == "monthly" else 1,
                "input_period": None}
    if pd.api.types.is_numeric_dtype(data["date"]):
        raise ValueError("date must contain dates, not integer years or epoch numbers")
    dates = pd.to_datetime(data["date"], errors="coerce", utc=True)
    if dates.isna().any():
        raise ValueError("invalid or missing dates; fix timestamps before analysis")
    values = pd.to_numeric(data["value"], errors="coerce")
    if (data["value"].notna() & values.isna()).any():
        raise ValueError("value contains nonnumeric text; encode missing values as null/NaN")
    values = values.to_numpy(dtype=float, na_value=np.nan, copy=True)
    values[~np.isfinite(values)] = np.nan
    periods = dates.dt.year if frequency == "annual" else dates.dt.strftime("%Y-%m")
    if periods.duplicated().any():
        raise ValueError(f"duplicate {frequency} observations; aggregate and quality-control upstream")
    frame = pd.DataFrame({"year": dates.dt.year.to_numpy(), "value": values})
    first, last = int(frame.year.min()), int(frame.year.max())
    if last - first > 499:
        raise ValueError("v0 supports at most 500 calendar years")
    years = list(range(first, last + 1))
    counts = frame.groupby("year").value.count().reindex(years, fill_value=0)
    means = frame.groupby("year").value.mean().reindex(years)
    threshold = min_months if frequency == "monthly" else 1
    annual = means[counts >= threshold].dropna()
    expected = len(years) * (12 if frequency == "monthly" else 1)
    return annual, {"input_rows": len(data), "valid_observations": int(np.isfinite(values).sum()),
            "raw_expected_observations": expected,
            "raw_missing_fraction": float(1 - np.isfinite(values).sum() / expected),
            "raw_excluded_years": [int(y) for y in counts.index[counts < threshold]],
            "available_years": [int(y) for y in annual.index],
            "raw_incomplete_retained_years": [int(y) for y in annual.index
                                             if frequency == "monthly" and counts[y] < 12],
            "_valid_counts_by_year": {int(y): int(n) for y, n in counts.items()},
            "_slots_per_year": 12 if frequency == "monthly" else 1,
            "input_period": {"start": dates.min().date().isoformat(),
                             "end": dates.max().date().isoformat()}}


def _autocorrelation(x: np.ndarray, y: np.ndarray, fit: dict) -> dict:
    residual = y - (fit["intercept"] + fit["slope"] * (x - x[0]))
    adjacent = np.diff(x) == 1
    pairs = int(adjacent.sum())
    threshold = float(1.96 / math.sqrt(pairs)) if pairs else None
    # Exact deterministic lines have no residual variability to diagnose.
    tolerance = _numerical_tolerance(y)
    if np.max(np.abs(residual)) <= tolerance:
        return {"lag1": 0.0, "adjacent_pairs": pairs, "threshold": threshold,
                "flagged": False, "status": "zero_residual_variance"}
    left, right = residual[:-1][adjacent], residual[1:][adjacent]
    if pairs < 5 or np.std(left) <= tolerance or np.std(right) <= tolerance:
        return {"lag1": None, "adjacent_pairs": pairs, "threshold": threshold,
                "flagged": True, "status": "not_assessable"}
    rho = float(np.corrcoef(left, right)[0, 1])
    return {"lag1": rho, "adjacent_pairs": pairs, "threshold": threshold,
            "flagged": bool(abs(rho) > threshold), "status": "screen_only"}


def _quality_gate(annual: pd.Series, quality: dict, min_years: int,
                  max_missing_fraction: float) -> tuple[dict, list[str]]:
    """Recompute final-window coverage and collect input-quality failures."""
    years = [int(y) for y in annual.index]
    quality = dict(quality)
    counts = quality.pop("_valid_counts_by_year")
    slots_per_year = quality.pop("_slots_per_year")
    # Crop only outside the actual analysis bounds. Interior unusable years
    # remain gaps; counting only len(years) would hide missing entire years.
    window = set(range(min(years), max(years) + 1)) if years else set()
    expected = len(window) * slots_per_year
    contributing = sum(counts[y] for y in years)
    quality.update({
        "analyzed_years": years, "n_years": len(years),
        "analysis_period": {"start": f"{min(years)}-01-01", "end": f"{max(years)}-12-31"} if years else None,
        "expected_observations": expected,
        "analyzed_valid_observations": contributing,
        "missing_fraction": float(1 - contributing / expected) if expected else None,
        "excluded_years": [y for y in quality["raw_excluded_years"] if y in window],
        "incomplete_retained_years": [y for y in quality["raw_incomplete_retained_years"] if y in years],
        "missing_analysis_years": sorted(window - set(years)),
        "alignment_excluded_years": sorted(set(quality["available_years"]) - set(years)),
    })
    reasons = []
    if quality["missing_fraction"] is not None and quality["missing_fraction"] > max_missing_fraction:
        reasons.append("excess_missing_observations")
    if quality["incomplete_retained_years"]:
        reasons.append("incomplete_seasonal_coverage")
    if len(annual) < min_years:
        reasons.append("insufficient_years")
    return quality, reasons


def _trend_estimates(x: np.ndarray, y: np.ndarray, alpha: float) -> dict:
    """Estimate trends from finite observations ordered by increasing time."""
    return {"linear_regression": linear_regression(x, y, alpha),
            "theil_sen": theil_sen(x, y, alpha), "mann_kendall": mann_kendall(y, alpha)}


def _sensitivity(x: np.ndarray, y: np.ndarray, estimates: dict, alpha: float) -> dict:
    """Measure leave-one-year-out sign stability and agreement of estimators."""
    ols, sen = estimates["linear_regression"], estimates["theil_sen"]
    # Leave-one-year-out slopes detect sign sensitivity to single observations.
    slopes = [theil_sen(np.delete(x, i), np.delete(y, i), alpha)["slope"] for i in range(len(x))]
    stable = bool(all(np.sign(s) == np.sign(sen["slope"]) for s in slopes))
    agreement = bool(np.sign(ols["slope"]) == np.sign(sen["slope"]))
    return {"leave_one_year_out_slope_range": [float(min(slopes)), float(max(slopes))],
            "direction_stable": stable, "ols_sen_direction_agree": agreement}


def _reliability(n_years: int, quality_reasons: list[str], sensitivity: dict,
                 autocorrelation: dict) -> dict:
    """Combine diagnostics without modifying their results or quality reasons."""
    reasons = list(quality_reasons)
    if not sensitivity["direction_stable"]:
        reasons.append("leave_one_year_out_direction_unstable")
    if not sensitivity["ols_sen_direction_agree"]:
        reasons.append("trend_methods_disagree")
    if autocorrelation["flagged"]:
        reasons.append("autocorrelation_flagged_or_not_assessable")
    # The normal approximation is fragile on very short records.
    if n_years < 8:
        reasons.append("short_record_mk_approximation")
    return {"reliable": not reasons, "reliability_reasons": reasons}


def _analyze(annual: pd.Series, quality: dict, alpha: float, min_years: int,
             max_missing_fraction: float) -> dict:
    """Coordinate quality, estimation and diagnostics into the public result."""
    quality, reasons = _quality_gate(annual, quality, min_years, max_missing_fraction)
    base = {"status": "insufficient_data", "data_quality": quality,
            "linear_regression": None, "theil_sen": None, "mann_kendall": None,
            "sensitivity": None, "autocorrelation": None, "reliable": False,
            "reliability_reasons": reasons}
    if len(annual) < min_years:
        return base
    x, y = annual.index.to_numpy(dtype=float), annual.to_numpy(dtype=float)
    estimates = _trend_estimates(x, y, alpha)
    sensitivity = _sensitivity(x, y, estimates, alpha)
    autocorrelation = _autocorrelation(x, y, estimates["linear_regression"])
    return {**base, "status": "ok", **estimates,
            "sensitivity": sensitivity, "autocorrelation": autocorrelation,
            **_reliability(len(annual), reasons, sensitivity, autocorrelation)}


def _settings(alpha: float, min_years: int, max_missing_fraction: float) -> None:
    _alpha(alpha)
    if not isinstance(min_years, int) or isinstance(min_years, bool) or min_years < 5:
        raise ValueError("min_years must be an integer >= 5")
    if not 0 <= max_missing_fraction <= 1:
        raise ValueError("max_missing_fraction must be in [0, 1]")


def analyze_timeseries(data: pd.DataFrame, *, frequency: str = "monthly", alpha: float = 0.05,
                       min_years: int = 8, min_months_per_year: int = 12,
                       max_missing_fraction: float = 0.2) -> dict:
    """Analyze one date/value series; default complete-year means remove season cycles."""
    _settings(alpha, min_years, max_missing_fraction)
    annual, quality = _prepare(data, frequency, min_months_per_year)
    return _analyze(annual, quality, alpha, min_years, max_missing_fraction)


def analyze_region(data: pd.DataFrame, *, frequency: str = "monthly", alpha: float = 0.05,
                   min_years: int = 8, min_months_per_year: int = 12,
                   max_missing_fraction: float = 0.2,
                   vegetation_variables: tuple[str, ...] = ("NDVI", "EVI"),
                   soil_moisture_variable: str = "soil_moisture") -> dict:
    """B -> A -> C/D contract for one region in long-table format.

    Required columns: date, value, unit, variable, source, region_id. All
    variables are analyzed on their intersection of valid annual years.
    Variable names are case-insensitive; explicit aliases can be configured.
    """
    from .divergence import detect_divergence

    _settings(alpha, min_years, max_missing_fraction)
    required = {"date", "value", "unit", "variable", "source", "region_id"}
    if not isinstance(data, pd.DataFrame) or not required.issubset(data.columns):
        raise ValueError("required columns: " + ", ".join(sorted(required)))
    if data.empty:
        raise ValueError("region data is empty")
    for column in ("unit", "variable", "source", "region_id"):
        if data[column].isna().any() or data[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"{column} cannot contain missing/blank metadata")
    if data.region_id.nunique() != 1:
        raise ValueError("analyze_region accepts exactly one region")
    prepared, metadata = {}, {}
    for name, group in data.groupby("variable", sort=True):
        name = str(name)
        if group.unit.nunique() != 1 or group.source.nunique() != 1:
            raise ValueError(f"{name}: mixed units or sources; harmonize upstream")
        prepared[name] = _prepare(group, frequency, min_months_per_year)
        metadata[name] = {"unit": str(group.unit.iloc[0]), "slope_unit": str(group.unit.iloc[0]) + "/year",
                          "source": str(group.source.iloc[0])}
    if len({v.casefold() for v in prepared}) != len(prepared):
        raise ValueError("variable names collide when compared case-insensitively")
    common = sorted(set.intersection(*(set(a.index) for a, _ in prepared.values())))
    results = {name: {**_analyze(a.reindex(common), q, alpha, min_years, max_missing_fraction), **metadata[name]}
               for name, (a, q) in prepared.items()}
    p = [r["mann_kendall"]["p_value"] if r["mann_kendall"] else None for r in results.values()]
    for r, adjusted in zip(results.values(), adjust_p_values(p)):
        r["adjusted_p_value"] = adjusted
    detection = detect_divergence(results, alpha=alpha, vegetation_variables=vegetation_variables,
                                  soil_moisture_variable=soil_moisture_variable)
    limitations = [
        "Greenness is not ecosystem health; divergence does not establish degradation or causation.",
        "Monthly inputs use equal-weight calendar-year means; default requires all 12 months. No imputation.",
        "All indicators share valid calendar years; extra indicators can reduce the common record.",
        "P-values and slope intervals assume independent annual observations. Residual lag-1 is only a screen, not a correction or proof of independence.",
        "BH correction covers MK tests for indicators in this call, not regions or repeated exploratory analyses; it assumes independence or suitable positive dependence.",
        "Confidence intervals are marginal, not simultaneous, prediction, or ecological-damage intervals.",
        "Sensitivity checks assess direction, not significance stability or alternate spatial aggregation.",
        "Source strings are supplied by the caller; NASA provenance, QA flags, spatial comparability and physical units must be verified upstream.",
        "If any source label contains SYNTHETIC (case-insensitive), the entire result is marked synthetic_demo=true, including mixtures of real and synthetic sources; this is a label heuristic, not provenance verification.",
        "Raw coverage uses supplied calendar years. Reliability uses contributing observations within final analysis bounds, including unusable interior years as gaps; unobserved endpoint years cannot be inferred.",
        "Numerically constant series use a 100-epsilon relative tolerance across trend methods and residual checks; this is not an ecological effect-size threshold.",
    ]
    synthetic = bool(data.source.astype(str).str.contains("SYNTHETIC", case=False).any())
    if synthetic:
        limitations.insert(0, "Synthetic demonstration/test observations are included; this is NOT a verified NASA finding.")
    trends = {v: _legacy_trend(r, v, r["unit"], r["data_quality"]["n_years"]) for v, r in results.items()}
    unavailable = not detection["pairs"] or any("insufficient_data" in p["reasons"] for p in detection["pairs"])
    return {"schema_version": "0.3", "region": str(data.region_id.iloc[0]),
            "observation_period": {"start": f"{common[0]}-01-01" if common else None,
                                   "end": f"{common[-1]}-12-31" if common else None,
                                   "years": [int(y) for y in common], "aggregation": "annual_mean"},
            "variables": list(results), "analysis": results, "trends": trends,
            "trend_slopes": {v: t["slope_per_year"] for v, t in trends.items()},
            "confidence_intervals": {v: t["slope_95ci"] for v, t in trends.items()},
            "p_values": {v: t["p_value"] for v, t in trends.items()},
            "adjusted_p_values": {v: r["adjusted_p_value"] for v, r in results.items()},
            "data_quality": {"n_raw_rows": len(data), "sources": sorted(data.source.astype(str).unique().tolist()),
                             "synthetic_demo": synthetic, "qa_reviewed": False,
                             "by_variable": {v: r["data_quality"] for v, r in results.items()}},
            "divergence_detected": None if unavailable else detection["category"] == "Supported Signal",
            "divergence_status": {"Supported Signal": "supported_signal", "Uncertain Signal": "uncertain_signal",
                                  "No Detected Divergence": "no_detected_divergence"}[detection["category"]],
            "divergence": detection, "limitations": limitations,
            "settings": {"frequency": frequency, "alpha": alpha, "min_years": min_years,
                         "min_months_per_year": min_months_per_year,
                         "max_missing_fraction": max_missing_fraction}}
