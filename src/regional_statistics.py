"""Provisional regional screening with a declared worldwide test family.

The original per-region statistical response is retained verbatim. Worldwide
adjustment is a separate map-screening result, never source-QA approval.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math

import pandas as pd

from .divergence import detect_divergence
from .statistics import adjust_p_values, analyze_region

PRIMARY_VARIABLES = ("ndvi", "soil_water_0_100cm")
REQUIRED_COLUMNS = ("date", "value", "unit", "variable", "source", "region_id")
START, END = "2003-01-01", "2024-12-31"
REJECT_FLAGS = frozenset({"low_coverage", "missing", "invalid", "qa_rejected", "no_valid_data", "no_valid_pixels", "negative_value"})


def _features(catalog, region_ids):
    if catalog is None:
        return [{"type": "Feature", "properties": {"region_id": r}, "geometry": None}
                for r in sorted(region_ids)]
    if isinstance(catalog, dict):
        if catalog.get("type") != "FeatureCollection":
            raise ValueError("catalog must be a GeoJSON FeatureCollection or list of features")
        catalog = catalog["features"]
    if not isinstance(catalog, list):
        raise ValueError("catalog must be a GeoJSON FeatureCollection or list of features")
    return deepcopy(catalog)


def build_regional_screening(monthly: pd.DataFrame, catalog=None, *, alpha: float = 0.05,
                             min_years: int = 8, dataset_version: str | None = None) -> dict:
    """Analyze the frozen 2003–2024 primary pair without geographic fabrication.

    Worldwide BH includes both finite MK tests from every region with enough
    common complete years, irrespective of trend direction or reliability.
    Missing primary series remain pending. Explicitly unsupported cells remain
    visible. Known rejected QA rows become missing for analysis only.
    """
    if not 0 < alpha < 0.5:
        raise ValueError("alpha must lie strictly between 0 and 0.5")
    if not isinstance(min_years, int) or isinstance(min_years, bool) or min_years < 8:
        raise ValueError("min_years must be an integer >= 8")
    if not isinstance(monthly, pd.DataFrame) or not set(REQUIRED_COLUMNS).issubset(monthly):
        raise ValueError("monthly must contain the six required timeseries columns")
    frame = monthly.copy(deep=True)
    for column in ("unit", "variable", "source", "region_id"):
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"{column} cannot contain missing/blank metadata")
    if not frame.empty and pd.api.types.is_numeric_dtype(frame.date):
        raise ValueError("date must contain dates, not epoch numbers")
    frame["date"] = pd.to_datetime(frame.date, errors="coerce", utc=True)
    if frame.date.isna().any():
        raise ValueError("invalid or missing dates")
    numeric = pd.to_numeric(frame.value, errors="coerce")
    if (frame.value.notna() & numeric.isna()).any() or numeric.isin([float("inf"), -float("inf")]).any():
        raise ValueError("invalid numeric value")
    frame["value"] = numeric
    frame = frame[(frame.date >= START) & (frame.date < "2025-01-01")].copy()
    frame["region_id"] = frame.region_id.astype(str)
    if frame.assign(month=frame.date.dt.strftime("%Y-%m")).duplicated(["region_id", "variable", "month"]).any():
        raise ValueError("duplicate region/variable/month observations")
    features = _features(catalog, set(frame.region_id))
    records, seen, family = [], set(), []
    for feature in features:
        props = deepcopy(feature.get("properties") or {})
        region_id = props.get("region_id", feature.get("id", props.get("id")))
        if not isinstance(region_id, str) or not region_id.strip() or region_id in seen:
            raise ValueError("catalog requires unique nonblank string region_id values")
        seen.add(region_id)
        selected = frame[(frame.region_id == region_id) & frame.variable.isin(PRIMARY_VARIABLES)].copy()
        flags = sorted(set(selected.quality_flag.dropna().astype(str))) if "quality_flag" in selected else []
        rejected = selected.quality_flag.isin(REJECT_FLAGS) if "quality_flag" in selected else pd.Series(False, index=selected.index)
        selected.loc[rejected, "value"] = float("nan")
        for name, unit in (("ndvi", "1"), ("soil_water_0_100cm", "kg m-2")):
            values = set(selected.loc[selected.variable == name, "unit"].astype(str))
            if values and values != {unit}:
                raise ValueError(f"{region_id}/{name}: expected unit {unit!r}")
        missing = sorted(set(PRIMARY_VARIABLES) - set(selected.variable))
        # The regional merger emits placeholder rows for requested exports.
        # Those rows do not make an unreceived primary indicator available.
        if "quality_flag" in selected:
            for name, group in selected.groupby("variable"):
                if group.value.isna().all() and group.quality_flag.eq("pending_export").all():
                    missing.append(name)
            missing = sorted(set(missing))
        explicit = props.get("data_status", props.get("support_status"))
        unsupported = explicit in {"unsupported", "unsupported_gldas", "no_data", "outside_product_support"}
        record = {"region_id": region_id, "geometry": deepcopy(feature.get("geometry")),
                  "bbox": deepcopy(props.get("bbox", feature.get("bbox"))),
                  "centroid": deepcopy(props.get("centroid")), "properties": props,
                  "status": "pending", "analysis": None, "available_indicator_analysis": None,
                  "screening": {"category": None, "classification": "pending",
                                "adjusted_p_values": {}, "reasons": [],
                                "qa_reviewed": False, "provisional": True,
                                "quality_flags": flags, "qa_rejected_rows": int(rejected.sum())}}
        if unsupported:
            record["status"] = "unsupported"
            record["screening"].update(classification="unsupported", reasons=["outside_product_support"])
        elif missing:
            record["screening"]["reasons"] = [f"missing_primary_variable:{v}" for v in missing]
            available = selected.groupby("variable")["value"].count().gt(0)
            available_names = available[available].index.tolist()
            if available_names:
                record["available_indicator_analysis"] = analyze_region(
                    selected[selected.variable.isin(available_names)],
                    vegetation_variables=("ndvi",), soil_moisture_variable="soil_water_0_100cm",
                    alpha=alpha, min_years=min_years)
                record["available_indicator_analysis"]["limitations"].insert(0,
                    "Available-indicator diagnostic only: paired regional screening remains pending; "
                    "these p-values have not been adjusted across regions and must not color the divergence map.")
        else:
            result = analyze_region(selected, vegetation_variables=("ndvi",),
                                    soil_moisture_variable="soil_water_0_100cm",
                                    alpha=alpha, min_years=min_years)
            record["analysis"] = result
            eligible = all(result["analysis"][v]["status"] == "ok" for v in PRIMARY_VARIABLES)
            record["status"] = "eligible" if eligible else "insufficient"
            record["screening"].update(classification="insufficient", reasons=["insufficient_common_complete_years"])
            if eligible:
                for variable in PRIMARY_VARIABLES:
                    p = result["analysis"][variable]["mann_kendall"]["p_value"]
                    if not math.isfinite(p):
                        raise ValueError("eligible MK result must have a finite p-value")
                    family.append((record, variable, p))
        records.append(record)
    if set(frame.region_id) - seen:
        raise ValueError("monthly input contains region IDs absent from catalog")
    for (record, variable, _), q in zip(family, adjust_p_values(p for _, _, p in family)):
        record["screening"]["adjusted_p_values"][variable] = q
    for record in records:
        if record["status"] != "eligible":
            continue
        analyses = deepcopy(record["analysis"]["analysis"])
        for variable, q in record["screening"]["adjusted_p_values"].items():
            analyses[variable]["adjusted_p_value"] = q
        detection = detect_divergence(analyses, alpha=alpha, vegetation_variables=("ndvi",),
                                      soil_moisture_variable="soil_water_0_100cm")
        reasons = list(detection["reasons"])
        for pair in detection["pairs"]:
            reasons.extend(pair["reasons"])
        record["screening"].update(category=detection["category"],
            classification={"Supported Signal": "supported_signal", "Uncertain Signal": "uncertain_signal",
                            "No Detected Divergence": "no_detected_divergence"}[detection["category"]],
            reasons=sorted(set(reasons)), divergence=detection,
            synthetic_demo=record["analysis"]["data_quality"]["synthetic_demo"])
    digest_frame = frame.sort_values(["region_id", "variable", "date"])
    digest = hashlib.sha256(digest_frame.to_csv(index=False).encode()).hexdigest()
    report = {"schema_version": "regional-screening-1", "dataset_version": dataset_version or digest,
              "input_sha256": digest, "observation_period": {"start": START, "end": END},
              "primary_variables": list(PRIMARY_VARIABLES),
              "settings": {"alpha": alpha, "min_years": min_years, "min_months_per_year": 12},
              "multiple_testing": {"method": "benjamini_hochberg", "family_size": len(family),
                  "eligible_regions": sum(r["status"] == "eligible" for r in records),
                  "family_definition": "Both finite primary-indicator MK tests for every region with sufficient common complete years; no direction/significance/reliability selection.",
                  "scope": "All eligible regions supplied in this catalog; changes to catalog or data require recomputing the entire family."},
              "limitations": ["Provisional statistical screening; source QA and common spatial footprints remain unreviewed.",
                  "BH assumes independence or suitable positive dependence; spatial dependence has not been validated.",
                  "Worldwide-adjusted map classifications are separate from unchanged within-region analysis results.",
                  "No detected divergence does not establish environmental safety; opposing trends do not establish causation.",
                  "No missing observations are interpolated. Known low-coverage/rejected rows are excluded only in the analysis copy.",
                  "Grid cells without both primary indicators remain pending; global means are never assigned to cells.",
                  "Available-indicator diagnostics are not part of the paired worldwide family; their significance is exploratory across regions."],
              "regions": records}
    json.dumps(report, allow_nan=False)
    return report
