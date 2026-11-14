import pandas as pd
import pytest

from src.divergence import analyze_region
from src.statistics import estimate_trend


def points(values, variable="ndvi"):
    return pd.DataFrame({
        "date": ["2019-01-01", "2020-01-01", "2021-01-01", "2022-01-01"],
        "value": values,
        "unit": ["index"] * 4,
        "variable": [variable] * 4,
        "source": ["TEST"] * 4,
        "region_id": ["test"] * 4,
    })


def test_positive_trend():
    result = estimate_trend(points([0.1, 0.2, 0.3, 0.4]))
    assert result["slope_per_year"] > 0
    assert result["n_observations"] == 4


def test_negative_trend():
    assert estimate_trend(points([4, 3, 2, 1]))["slope_per_year"] < 0


def test_flat_trend():
    assert estimate_trend(points([2, 2, 2, 2]))["slope_per_year"] == pytest.approx(0.0)


def test_insufficient_samples():
    with pytest.raises(ValueError, match="three observations"):
        estimate_trend(points([1, 2, 3, 4]).iloc[:2])


def test_sign_only_divergence_is_candidate():
    frame = pd.concat([
        points([1, 2, 3, 4], variable="ndvi"),
        points([4, 3, 2, 1], variable="soil_moisture"),
    ], ignore_index=True)
    result = analyze_region(frame)
    assert result["divergence_detected"] is True
    assert result["divergence_status"] == "candidate_only"


def test_missing_indicator_is_unavailable():
    result = analyze_region(points([1, 2, 3, 4]))
    assert result["divergence_detected"] is None
