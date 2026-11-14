"""Transparent evidence categories for vegetation/soil-moisture divergence."""


def analyze_region(data, **kwargs) -> dict:
    """Preserve the import path used by the existing Streamlit app and agent."""
    from .statistics import analyze_region as analyze
    return analyze(data, **kwargs)


def detect_divergence(analyses: dict, *, alpha: float = 0.05,
                      vegetation_variables: tuple[str, ...] = ("NDVI", "EVI"),
                      soil_moisture_variable: str = "soil_moisture") -> dict:
    """Consume aligned analyze_region analyses, including BH-adjusted MK values.

    Supported Signal requires positive greenness, negative moisture, marginal
    Sen intervals excluding zero, adjusted MK significance and reliability.
    """
    if not 0 < alpha < 0.5:
        raise ValueError("alpha must lie strictly between 0 and 0.5")
    names = {v.casefold(): v for v in analyses}
    if len(names) != len(analyses):
        raise ValueError("variable names collide when compared case-insensitively")
    soil = names.get(soil_moisture_variable.casefold())
    vegetation = list(dict.fromkeys(names[v.casefold()] for v in vegetation_variables if v.casefold() in names))
    if soil in vegetation:
        raise ValueError("vegetation and soil moisture must be different variables")
    if soil is None or not vegetation:
        return {"category": "Uncertain Signal", "pairs": [],
                "reasons": ["required_vegetation_or_soil_moisture_missing"]}
    pairs = []
    for name in vegetation:
        green, water = analyses[name], analyses[soil]
        reasons = []
        aligned = green["data_quality"]["analyzed_years"] == water["data_quality"]["analyzed_years"]
        if not aligned:
            reasons.append("unmatched_observation_years")
        if green["status"] != "ok" or water["status"] != "ok":
            reasons.append("insufficient_data")
            category = "Uncertain Signal"
        else:
            directional = green["theil_sen"]["slope"] > 0 and water["theil_sen"]["slope"] < 0
            significant = all(r.get("adjusted_p_value") is not None and r["adjusted_p_value"] < alpha
                              for r in (green, water))
            intervals = green["theil_sen"]["confidence_interval"][0] > 0 and water["theil_sen"]["confidence_interval"][1] < 0
            reliable = green["reliable"] and water["reliable"] and aligned
            if not reliable:
                reasons.append("quality_or_robustness_checks_failed")
            if directional and significant and intervals and reliable:
                category = "Supported Signal"
            elif directional or not reliable:
                category = "Uncertain Signal"
                if not significant:
                    reasons.append("adjusted_significance_not_established")
                if not intervals:
                    reasons.append("directional_confidence_intervals_not_established")
            else:
                category = "No Detected Divergence"
                reasons.append("required_opposing_directions_absent")
        pairs.append({"vegetation": name, "soil_moisture": soil, "category": category, "reasons": reasons})
    categories = {p["category"] for p in pairs}
    # Conflicting vegetation indicators are retained and downgrade the result.
    category = next(iter(categories)) if len(categories) == 1 else "Uncertain Signal"
    return {"category": category, "pairs": pairs,
            "reasons": ["vegetation_indicators_disagree"] if len(categories) > 1 else []}
