"""Exploratory global trends without interpreting divergent spatial footprints."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .statistics import analyze_region

_LIMITATIONS = [
    "Exploratory global aggregates only: Green Mirage, co-located divergence, ecological damage and causality are not assessed.",
    "NDVI and soil-water averages can cover different places and change footprint over time; calendar alignment does not establish spatial overlap.",
    "Coverage fractions describe each source independently, not their spatial intersection; their denominator and QA rules must be verified from provenance.",
    "Quality flags and coverage are reported, not automatically filtered or used to determine statistical reliability; review and apply a documented QA policy upstream.",
    "Descriptive slopes are not evidence of a co-located divergence; opposite signs alone do not establish a Green Mirage.",
    "Inferential results and reliability diagnostics are withheld from this consumer-facing exploratory output; use a separately reviewed analysis for inference.",
]


def _coverage_summary(frame: pd.DataFrame) -> dict:
    """Describe provided data on its input window, without implying QA approval."""
    valid_values = pd.to_numeric(frame["value"], errors="coerce").to_numpy(dtype=float, na_value=np.nan)
    present = np.isfinite(valid_values)
    if "quality_flag" in frame:
        flags = frame["quality_flag"].fillna("<missing>").astype(str).str.strip().replace("", "<missing>")
        counts = {str(k): int(v) for k, v in flags.value_counts().sort_index().items()}
        available = True
    else:
        counts, available = {}, False
    coverage = None
    if "valid_area_fraction" in frame:
        raw = frame["valid_area_fraction"]
        values = pd.to_numeric(raw, errors="coerce")
        if (raw.notna() & values.isna()).any():
            raise ValueError("valid_area_fraction must contain numeric values or null")
        c = values.to_numpy(dtype=float, na_value=np.nan)
        if np.isinf(c).any() or np.any((c[np.isfinite(c)] < 0) | (c[np.isfinite(c)] > 1)):
            raise ValueError("valid_area_fraction must be between 0 and 1 or null")
        c = c[np.isfinite(c)]
        coverage = {"reported_count": int(len(c)), "unreported_count": int(len(frame) - len(c)),
                    "minimum": float(np.min(c)) if len(c) else None,
                    "maximum": float(np.max(c)) if len(c) else None,
                    "mean": float(np.mean(c)) if len(c) else None}
    return {"input_rows": len(frame), "finite_value_rows": int(present.sum()),
            "quality_flag_column_present": available, "quality_flag_counts": counts,
            "valid_area_fraction": coverage,
            "coverage_scope": "all_input_rows_before_annual_filtering_and_alignment"}


def analyze_global_exploratory(data: pd.DataFrame, *, soil_moisture_variable: str = "soil_water_0_10cm",
                               frequency: str = "monthly", alpha: float = 0.05,
                               min_years: int = 8, min_months_per_year: int = 12,
                               max_missing_fraction: float = 0.2) -> dict:
    """Wrap the region engine for one global table; return no divergence finding.

    Caller must review and handle QA flags before use. Fraction and flag
    summaries describe the supplied input, not approved or overlapping areas.
    Data must explicitly use region_id='whole_earth'.
    """
    if not isinstance(data, pd.DataFrame) or "region_id" not in data:
        raise ValueError("global data must be a DataFrame with region_id")
    if data.empty or data["region_id"].isna().any() or not data["region_id"].eq("whole_earth").all():
        raise ValueError("global exploratory analysis requires region_id='whole_earth' on every row")
    if not isinstance(soil_moisture_variable, str) or not soil_moisture_variable.strip():
        raise ValueError("soil_moisture_variable must be a nonempty variable name")
    if "variable" not in data:
        raise ValueError("global data requires variable column")
    available = sorted({str(v) for v in data["variable"].dropna().unique()})
    if soil_moisture_variable.casefold() not in {v.casefold() for v in available}:
        raise ValueError(f"selected soil_moisture_variable {soil_moisture_variable!r} is missing; "
                         f"available variables: {available}")
    result = analyze_region(data, frequency=frequency, alpha=alpha, min_years=min_years,
                            min_months_per_year=min_months_per_year,
                            max_missing_fraction=max_missing_fraction,
                            soil_moisture_variable=soil_moisture_variable)
    coverage = {str(name): _coverage_summary(group) for name, group in data.groupby("variable", sort=True)}
    # Whitelist fields rather than copying the underlying result: new engine
    # inference fields must not silently cross this consumer-facing boundary.
    descriptive = {}
    for name, analysis in result["analysis"].items():
        ols, sen = analysis["linear_regression"], analysis["theil_sen"]
        descriptive[name] = {"status": analysis["status"], "unit": analysis["unit"],
                             "slope_unit": analysis["slope_unit"], "source": analysis["source"],
                             "data_quality": analysis["data_quality"],
                             "linear_slope": ols["slope"] if ols else None,
                             "theil_sen_slope": sen["slope"] if sen else None}
    return {"schema_version": "global-exploratory-0.2", "scope": "global_exploratory",
            "region": result["region"], "observation_period": result["observation_period"],
            "variables": result["variables"], "analysis": descriptive,
            "data_quality": result["data_quality"],
            "divergence_detected": None, "divergence_status": "not_assessed",
            "divergence": {"category": "Not assessed", "pairs": [],
                           "reasons": ["global_spatial_footprints_not_verified"]},
            "global_exploratory": {"spatial_overlap": "not_established",
                                   "green_mirage_assessed": False,
                                   "quality_flags_applied": False,
                                   "inferential_results_exposed": False,
                                   "coverage_by_variable": coverage},
            "limitations": list(_LIMITATIONS) + result["limitations"]}
