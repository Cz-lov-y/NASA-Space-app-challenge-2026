"""A -> C/D scientific-analysis interface: preliminary divergence screening."""
from __future__ import annotations

from src.preprocessing import validate_timeseries
from src.statistics import estimate_trend

VEGETATION_VARIABLE = "ndvi"
WATER_VARIABLE = "soil_moisture"


def analyze_region(data) -> dict:
    """Return serializable findings, with conservative interpretation.

    A sign-only discrepancy is a CANDIDATE signal, not a confirmed ecological
    mechanism. Authentic source provenance and scientific review are required.
    """
    frame = validate_timeseries(data)
    regions = frame["region_id"].unique()
    if len(regions) != 1:
        raise ValueError("analyze_region expects data for exactly one region")
    trends = {
        variable: estimate_trend(group)
        for variable, group in frame.groupby("variable", sort=True)
    }
    is_demo = frame["source"].astype(str).str.contains("SYNTHETIC_DEMO").any()
    both = VEGETATION_VARIABLE in trends and WATER_VARIABLE in trends
    divergence = None
    if both:
        v = trends[VEGETATION_VARIABLE]["slope_per_year"]
        w = trends[WATER_VARIABLE]["slope_per_year"]
        divergence = bool(v is not None and w is not None and v > 0 and w < 0)
    limitations = [
        "Initial trend tests do not correct for seasonality or autocorrelation.",
        "Opposite trend signs are screening signals, not proof of environmental harm.",
        "Match geographic support and dates before interpreting real datasets.",
    ]
    if is_demo:
        limitations.insert(0, "Synthetic demonstration data — NOT NASA observations.")
    if not both:
        limitations.append("Both NDVI and soil moisture are required for divergence screening.")
    return {
        "region": str(regions[0]),
        "observation_period": {
            "start": frame["date"].min().date().isoformat(),
            "end": frame["date"].max().date().isoformat(),
        },
        "variables": sorted(trends),
        "trends": trends,
        "trend_slopes": {name: t["slope_per_year"] for name, t in trends.items()},
        "confidence_intervals": {name: t["slope_95ci"] for name, t in trends.items()},
        "p_values": {name: t["p_value"] for name, t in trends.items()},
        "data_quality": {
            "n_observations": int(len(frame)),
            "sources": sorted(frame["source"].unique().astype(str).tolist()),
            "synthetic_demo": bool(is_demo),
            "qa_reviewed": False,
        },
        "divergence_detected": divergence,
        "divergence_status": "candidate_only" if divergence else "not_detected_or_unavailable",
        "limitations": limitations,
    }
