"""Synthetic-only B-to-A time-series stub; never represents NASA observations."""

import numpy as np
import pandas as pd


def mock_timeseries(region: str, variable: str) -> pd.DataFrame:
    """Return deterministic monthly mock observations and contract metadata."""
    if region != "synthetic_region":
        raise ValueError("Only synthetic_region is available in the mock")
    if not isinstance(variable, str) or variable.casefold() not in {"ndvi", "soil_moisture"}:
        raise ValueError("Mock variables are NDVI and soil_moisture")
    name = "NDVI" if variable.casefold() == "ndvi" else "soil_moisture"
    dates = pd.date_range("2000-01-01", "2015-12-01", freq="MS")
    year = dates.year.to_numpy() - 2000
    seasonal = np.sin(2 * np.pi * (dates.month.to_numpy() - 1) / 12)
    if name == "NDVI":
        values, unit = 0.3 + 0.01 * year + 0.05 * seasonal, "1"
    else:
        values, unit = 30 - 0.4 * year + 2 * seasonal, "kg m-2"
    result = pd.DataFrame({"date": dates, "value": values, "unit": unit,
                           "variable": name, "source": "SYNTHETIC_DEMO_NOT_NASA",
                           "region_id": region})
    result.attrs["metadata"] = {
        "spatial_coverage": {"description": "Fictitious region; no real spatial coverage", "geometry": None},
        "time_range": {"start": "2000-01-01", "end": "2015-12-31"},
        "temporal_resolution": "monthly calendar mean (synthetic)",
        "dataset_version": "synthetic-mock-1",
        "quality_control": {"description": "Generated values; no real product QA", "missing_value_encoding": "NaN", "missing_count": 0},
    }
    return result
