"""B -> A data interface.

The initial reader is SYNTHETIC-ONLY. Member B must replace/extend it with
NASA MODIS/GLDAS ingestion, QA masking, geographic aggregation, and provenance.
"""
from pathlib import Path

import pandas as pd

from src.preprocessing import validate_timeseries

SAMPLE_PATH = Path(__file__).resolve().parents[1] / "data" / "sample" / "demo_timeseries.csv"


def get_timeseries(region: str, variable: str) -> pd.DataFrame:
    """Retrieve standardized demo observations for one region and variable.

    Raises rather than implicitly pretending to fetch real NASA observations.
    """
    frame = pd.read_csv(SAMPLE_PATH)
    subset = frame.loc[
        (frame["region_id"] == region) & (frame["variable"] == variable)
    ]
    if subset.empty:
        raise ValueError(f"No demo timeseries for region={region!r}, variable={variable!r}")
    return validate_timeseries(subset)
