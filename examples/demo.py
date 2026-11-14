"""Reproducible SYNTHETIC demo; run from the project root: python -m examples.demo."""

import json

import numpy as np
import pandas as pd

from src.statistics import analyze_region


def make_synthetic_data() -> pd.DataFrame:
    dates = pd.date_range("2000-01-01", "2015-12-01", freq="MS")
    year = dates.year.to_numpy() - 2000
    season = np.sin(2 * np.pi * (dates.month.to_numpy() - 1) / 12)
    frames = []
    for variable, values, unit in [
        ("NDVI", 0.3 + 0.01 * year + 0.05 * season, "1"),
        ("soil_moisture", 30 - 0.4 * year + 2 * season, "kg m-2"),
    ]:
        frames.append(pd.DataFrame({"date": dates, "value": values, "variable": variable,
                                    "unit": unit, "source": "SYNTHETIC_DEMO_NOT_NASA",
                                    "region_id": "synthetic_region"}))
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    print(json.dumps(analyze_region(make_synthetic_data()), indent=2, allow_nan=False))
