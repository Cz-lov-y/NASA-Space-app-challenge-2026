"""Verify the produced Member B data against the integration contract."""
from pathlib import Path
import pandas as pd
from src.preprocessing import validate_timeseries

DATA = Path(__file__).resolve().parents[1] / 'data/processed/global_combined/monthly_timeseries.csv'


def test_required_period_passes_statistics_input_contract():
    data = pd.read_csv(DATA)
    expected = pd.date_range('2003-01-01', '2024-12-01', freq='MS')
    required = data[data.date.between('2003-01-01', '2024-12-01')]
    assert len(required) == 792
    for name in ('ndvi', 'soil_water_0_10cm', 'soil_water_0_100cm'):
        rows = validate_timeseries(required[required.variable == name])
        assert pd.DatetimeIndex(rows.date).equals(expected)
        assert (rows.region_id == 'whole_earth').all()
        assert rows.valid_area_fraction.between(0, 1).all()
        assert (rows.quality_flag == 'coverage_review_required').all()
        assert (rows.unit == ('1' if name == 'ndvi' else 'kg m-2')).all()


def test_extended_missing_months_are_preserved():
    data = pd.read_csv(DATA)
    assert len(data) == 861
    assert not data.duplicated(['date', 'region_id', 'variable']).any()
    missing = data[data.value.isna()]
    assert len(missing) == 11
    assert missing.valid_area_fraction.isna().all()
    assert (missing.quality_flag == 'missing').all()
