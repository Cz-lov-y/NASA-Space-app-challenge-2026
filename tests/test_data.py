import pandas as pd
import pytest

from src.nasa_data import get_timeseries
from src.preprocessing import validate_timeseries


def test_demo_dataset_is_explicitly_synthetic():
    frame = get_timeseries("demo-region", "ndvi")
    assert len(frame) >= 3
    assert frame["source"].str.contains("SYNTHETIC_DEMO").all()


def test_unknown_region_is_not_fake_nasa_data():
    with pytest.raises(ValueError, match="No timeseries"):
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


def test_real_global_loader_preserves_missing_and_provenance():
    frame = get_timeseries('whole_earth', 'ndvi')
    assert len(frame) == 287
    assert frame.unit.eq('1').all()
    assert frame.loc[frame.date == pd.Timestamp('2026-11-01'), 'value'].isna().all()
    assert frame.attrs['metadata']['dataset_version'] == 'MOD13A3.061'
    assert frame.attrs['metadata']['spatial_coverage']['bbox'] == [-180, -90, 180, 90]
    assert frame.quality_flag.notna().all()


def test_regional_sample_and_unknown_combination():
    frame = get_timeseries('central_us_sample', 'soil_water_0_10cm')
    assert len(frame) == 264 and frame.unit.eq('kg m-2').all()
    with pytest.raises(ValueError, match='No timeseries'):
        get_timeseries('central_us_sample', 'ndvi')


def test_allow_missing_still_rejects_bad_and_infinite_numbers():
    frame = get_timeseries('demo-region', 'ndvi')
    frame.loc[0, 'value'] = None
    assert validate_timeseries(frame, allow_missing=True).value.isna().sum() == 1
    for value in ('not a number', float('inf')):
        bad = frame.copy()
        bad['value'] = bad['value'].astype(object)
        bad.loc[0, 'value'] = value
        with pytest.raises(ValueError, match='Invalid'):
            validate_timeseries(bad, allow_missing=True)


def test_global_loader_connects_to_statistics():
    from src.statistics import analyze_region
    frames = [get_timeseries('whole_earth', v) for v in ('ndvi', 'soil_water_0_100cm')]
    records = pd.concat(frames, ignore_index=True)
    records = records[records.date < '2025-01-01']
    analysis = analyze_region(records, soil_moisture_variable='soil_water_0_100cm')
    assert len(analysis['observation_period']['years']) == 22
    assert len(analysis['divergence']['pairs']) == 1
    assert not analysis['data_quality']['qa_reviewed']
