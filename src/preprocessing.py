"""Validation for the agreed B -> A tabular data contract.

NASA-specific QA flags, grid aggregation, and temporal alignment are TODOs
owned by the NASA data engineer; this generic layer rejects bad inputs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ("date", "value", "unit", "variable", "source", "region_id")


def validate_timeseries(data: pd.DataFrame, *, allow_missing: bool = False) -> pd.DataFrame:
    """Return a validated, date-sorted copy; do not silently drop records."""
    if not isinstance(data, pd.DataFrame):
        raise TypeError("Expected a pandas DataFrame")
    missing = [name for name in REQUIRED_COLUMNS if name not in data.columns]
    if missing:
        raise ValueError(f"Missing timeseries columns: {missing}")
    result = data.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    original_value = result["value"]
    result["value"] = pd.to_numeric(original_value, errors="coerce")
    if (original_value.notna() & result["value"].isna()).any() or np.isinf(result["value"]).any():
        raise ValueError("Invalid or missing date/value; handle QA before analysis")
    if result["date"].isna().any() or (not allow_missing and result["value"].isna().any()):
        raise ValueError("Invalid or missing date/value; handle QA before analysis")
    if result[list(("unit", "variable", "source", "region_id"))].isna().any().any():
        raise ValueError("Timeseries metadata contains null values")
    duplicate_keys = ["date", "region_id", "variable"]
    if result.duplicated(subset=duplicate_keys).any():
        raise ValueError("Duplicate region/variable/date observations")
    for col in ("unit", "variable", "source", "region_id"):
        if result[col].astype(str).str.strip().eq("").any():
            raise ValueError("Timeseries metadata contains blank values")
    if len(result) == 0:
        raise ValueError("No observations provided")
    return result.sort_values(duplicate_keys, kind="stable").reset_index(drop=True)
