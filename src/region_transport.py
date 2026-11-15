"""Add authoritative annual fit coordinates to the existing region detail export.

Transport adapters can use this payload for HTTP or static JSON. This module
never estimates a new trend or turns a fitted value into an observation.
"""
from copy import deepcopy
import json
import math

from .regional_workflow import export_region


def build_region_detail(bundle: dict) -> dict:
    """Export original observations plus annual OLS points from stored fits.

    Fit dates are UTC calendar-year anchors (January 1), not monthly readings.
    Points exist only at analyzed years, including any real gaps. Filtering a
    chart window must not change the stored fit or its documented analysis period.
    """
    detail = export_region(bundle)
    # Stale analyses are withheld even if a caller supplied a hand-built bundle.
    current = detail["screening_status"] == "current"
    paired = detail["paired_analysis"] if current else None
    available = detail["available_indicator_analysis"] if current else None
    if not current:
        detail.update(paired_analysis=None, available_indicator_analysis=None, screening=None)
    analysis = available or paired
    fits = {}
    for variable, result in (analysis or {}).get("analysis", {}).items():
        fit = result.get("linear_regression")
        if result.get("status") != "ok" or fit is None:
            fits[variable] = None
            continue
        coefficients = [fit.get(key) for key in ("slope", "intercept", "time_origin")]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in coefficients):
            raise ValueError("stored annual fit has invalid coefficients")
        slope, intercept, origin = coefficients
        years = result["data_quality"]["analyzed_years"]
        if not all(isinstance(year, int) and not isinstance(year, bool) and 1 <= year <= 9999 for year in years):
            raise ValueError("stored annual fit has invalid analyzed years")
        if years != sorted(set(years)):
            raise ValueError("stored annual fit requires unique increasing analyzed years")
        fits[variable] = {
            "kind": "annual_ols_fitted", "unit": result["unit"],
            "slope_unit": result["slope_unit"], "slope_per_year": slope,
            "intercept": intercept, "time_origin": origin,
            "confidence_level": fit["confidence_level"],
            "analysis_period": deepcopy(result["data_quality"]["analysis_period"]),
            "points": [{"date": f"{year:04d}-01-01", "year": year,
                        "value": intercept + slope * (year - origin)} for year in years],
        }
    screening = detail.get("screening") or {}
    detail["annual_fits"] = fits
    detail["scientific_display"] = {
        "analysis_kind": "available_indicator" if available else "paired" if paired else "none",
        "analysis_period": deepcopy((analysis or {}).get("observation_period")),
        "category": screening.get("category"),
        "classification": screening.get("classification", "unavailable"),
        "qa_reviewed": (analysis or {}).get("data_quality", {}).get("qa_reviewed", False),
        "synthetic_demo": (analysis or {}).get("data_quality", {}).get("synthetic_demo", False),
        "limitations": ["Annual fit points are fitted values at analyzed calendar years, not additional observations.",
                        "Chart-window filtering does not recompute the fit or statistical significance."]
                        + deepcopy((analysis or {}).get("limitations", [])),
    }
    json.dumps(detail, allow_nan=False)
    return detail
