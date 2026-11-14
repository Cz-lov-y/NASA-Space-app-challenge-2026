"""Pure, testable display helpers for the EarthRisk Streamlit interface.

These helpers never interpret candidate trend signs as causal evidence or
promote research suggestions to verified claims.
"""
from __future__ import annotations

import math
from urllib.parse import urlparse

INDICATOR_LABELS = {
    "ndvi": "Vegetation greenness (NDVI)",
    "soil_moisture": "Soil moisture",
    "soil_water_0_100cm": "Soil water storage (0–100 cm)",
    "soil_water_0_10cm": "Soil water storage (0–10 cm)",
}


def indicator_label(name: str) -> str:
    """Get a readable label without rejecting future NASA indicator names."""
    return INDICATOR_LABELS.get(str(name), str(name).replace("_", " ").title())


def number(value: object, digits: int = 3) -> str:
    """Format finite model outputs, avoiding NaN/inf in the UI."""
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError):
        return "N/A"
    if not math.isfinite(numeric):
        return "N/A"
    return f"{numeric:+.{digits}f}"


def p_value(value: object) -> str:
    """Display raw p-values, not corrected significance assertions."""
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError):
        return "N/A"
    if not math.isfinite(numeric) or not 0 <= numeric <= 1:
        return "N/A"
    return "< 0.001" if numeric < 0.001 else f"{numeric:.3f}"


def confidence_interval(value: object, digits: int = 3) -> str:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return "Unavailable"
    return f"[{number(value[0], digits)}, {number(value[1], digits)}]"


def screening_summary(analysis: dict) -> tuple[str, str, str]:
    """Return (status, headline, explanation) for the sign-only screen."""
    if analysis.get("schema_version") == "0.3":
        details = analysis.get("divergence") or {}
        category = details.get("category", "Uncertain Signal")
        reasons = details.get("reasons", []) + [r for p in details.get("pairs", []) for r in p.get("reasons", [])]
        explanation = "Statistical classification; source QA and spatial comparability require separate review."
        if reasons:
            explanation += " Reasons: " + ", ".join(reasons)
        return ("candidate" if category == "Supported Signal" else "incomplete" if category == "Uncertain Signal" else "not_detected", category, explanation)
    detected = analysis.get("divergence_detected")
    if detected is True:
        return (
            "candidate",
            "Candidate Green Mirage",
            "NDVI increases while soil moisture decreases. This is a "
            "screening signal from opposing trend signs, NOT a verified "
            "ecological impact or causal explanation.",
        )
    if detected is None:
        return (
            "incomplete",
            "Screening incomplete",
            "Both NDVI and soil moisture are needed to evaluate opposing trends.",
        )
    return (
        "not_detected",
        "No opposing trend signs detected",
        "These observations do not satisfy the sign-only Green Mirage "
        "screen. This does not establish environmental safety.",
    )


def is_synthetic(data, analysis: dict) -> bool:
    quality = analysis.get("data_quality") or {}
    if quality.get("synthetic_demo") is True:
        return True
    return (
        "source" in data
        and data["source"].astype(str).str.contains("SYNTHETIC", case=False, na=False).any()
    )


def safe_http_url(value: object) -> str | None:
    """Only offer clickable external URLs when they use HTTP(S)."""
    if not isinstance(value, str) or not value or any(c.isspace() for c in value):
        return None
    try:
        parsed = urlparse(value)
        if (
            parsed.scheme not in ("https", "http")
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            return None
    except ValueError:
        return None
    return value


def research_items(report: dict, key: str) -> list[dict]:
    """Gracefully accept C's future typed records or simple text suggestions."""
    raw = report.get(key, [])
    if not isinstance(raw, list):
        return []
    result = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            result.append({"title": item.strip()})
        elif isinstance(item, dict):
            result.append(item)
    return result


def research_title(item: dict, default: str = "Untitled record") -> str:
    for key in ("title", "name", "policy_title", "study_title", "action"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default
