import pandas as pd
import pytest

from src.nasa_data import get_timeseries
from src.preprocessing import validate_timeseries


def test_demo_dataset_is_explicitly_synthetic():
    frame = get_timeseries("demo-region", "ndvi")
    assert len(frame) >= 3
    assert frame["source"].str.contains("SYNTHETIC_DEMO").all()


def test_unknown_region_is_not_fake_nasa_data():
    with pytest.raises(ValueError, match="No demo timeseries"):
        get_timeseries("unknown-region", "ndvi")


def test_reject_duplicate_observations():
    frame = get_timeseries("demo-region", "ndvi")
    with pytest.raises(ValueError, match="Duplicate"):
        validate_timeseries(pd.concat([frame, frame.iloc[:1]], ignore_index=True))


def test_reject_missing_values():
    frame = get_timeseries("demo-region", "ndvi")
    frame.loc[0, "value"] = None
    with pytest.raises(ValueError, match="Invalid or missing"):
        validate_timeseries(frame)
