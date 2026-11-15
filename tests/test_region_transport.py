"""Stored annual fit transport; synthetic test fixtures never claim NASA data."""
from copy import deepcopy
import json

import pandas as pd
import pytest

from src.region_transport import build_region_detail
from src.regional_statistics import build_regional_screening


def bundle(years=range(2003, 2025), paired=False):
    dates = pd.date_range('2003-01-01', '2024-12-01', freq='MS')
    dates = dates[dates.year.isin(years)]
    data = pd.DataFrame({'date': dates, 'value': 100 - 2 * (dates.year - 2003),
                         'unit': 'kg m-2', 'variable': 'soil_water_0_100cm',
                         'source': 'SYNTHETIC_TEST_ONLY', 'region_id': 'test'})
    if paired:
        green = data.copy()
        green['variable'], green['unit'] = 'ndvi', '1'
        green['value'] = .2 + .01 * (dates.year - 2003)
        data = pd.concat([data, green], ignore_index=True)
    record = build_regional_screening(data)['regions'][0]
    return {'region_id': 'test', 'feature': {'type': 'Feature', 'geometry': None, 'properties': {'region_id': 'test'}},
            'research_context': {'dataset_version': 'synthetic-test'}, 'screening_status': 'current',
            'screening': record, 'observations': data, 'provenance': {'source': 'SYNTHETIC_TEST_ONLY'}}


def test_standalone_fit_uses_original_annual_coefficients_and_units():
    source = bundle()
    original = source['observations'].copy(deep=True)
    detail = build_region_detail(source)
    fit = detail['annual_fits']['soil_water_0_100cm']
    assert detail['scientific_display']['analysis_kind'] == 'available_indicator'
    assert detail['scientific_display']['classification'] == 'pending'
    assert detail['scientific_display']['category'] is None
    assert not detail['scientific_display']['qa_reviewed']
    assert fit['slope_per_year'] == pytest.approx(-2)
    assert fit['unit'] == 'kg m-2'
    assert fit['points'][0] == {'date': '2003-01-01', 'year': 2003, 'value': 100}
    assert len(fit['points']) == 22
    assert fit['points'][-1]['value'] == pytest.approx(58)
    assert len(detail['observations']) == 264
    pd.testing.assert_frame_equal(source['observations'], original)
    json.dumps(detail, allow_nan=False)


def test_paired_fit_points_only_use_actual_common_years_not_gap_fill():
    source = bundle(years=[2003, 2004, 2005, 2006, 2021, 2022, 2023, 2024], paired=True)
    detail = build_region_detail(source)
    assert detail['scientific_display']['analysis_kind'] == 'paired'
    assert len(detail['annual_fits']['ndvi']['points']) == 8
    assert [p['year'] for p in detail['annual_fits']['ndvi']['points']] == [2003, 2004, 2005, 2006, 2021, 2022, 2023, 2024]
    assert detail['annual_fits']['ndvi']['analysis_period'] == {'start': '2003-01-01', 'end': '2024-12-31'}


def test_null_missing_observation_and_insufficient_fit_are_preserved():
    source = bundle(years=range(2003, 2010))
    source['observations'].loc[0, 'value'] = float('nan')
    detail = build_region_detail(source)
    assert detail['annual_fits']['soil_water_0_100cm'] is None
    assert detail['observations'][0]['value'] is None
    json.dumps(detail, allow_nan=False)


def test_stale_analysis_is_not_exported_as_authoritative():
    source = bundle()
    source['screening_status'] = 'stale_rebuild_required'
    detail = build_region_detail(source)
    assert not detail['annual_fits']
    assert detail['paired_analysis'] is None
    assert detail['available_indicator_analysis'] is None
    assert detail['screening'] is None
    assert detail['scientific_display']['analysis_kind'] == 'none'


def test_invalid_stored_fit_coefficients_fail_instead_of_inventing_values():
    source = bundle()
    source['screening']['available_indicator_analysis']['analysis']['soil_water_0_100cm']['linear_regression']['slope'] = float('nan')
    with pytest.raises(ValueError, match='coefficients'):
        build_region_detail(source)


def test_partial_pair_does_not_truncate_available_soil_fit():
    source = bundle(paired=True)
    data = source['observations']
    data = data[(data.variable != 'ndvi') | (pd.to_datetime(data.date).dt.year == 2003)]
    source['observations'] = data
    source['screening'] = build_regional_screening(data)['regions'][0]
    detail = build_region_detail(source)
    assert detail['paired_analysis']['observation_period']['years'] == [2003]
    assert detail['scientific_display']['classification'] == 'insufficient'
    assert detail['scientific_display']['category'] is None
    assert detail['scientific_display']['analysis_kind'] == 'available_indicator'
    assert detail['scientific_display']['analysis_period']['years'] == list(range(2003, 2025))
    assert len(detail['annual_fits']['soil_water_0_100cm']['points']) == 22
    assert detail['annual_fits']['soil_water_0_100cm']['slope_per_year'] == pytest.approx(-2)
    assert 'ndvi' not in detail['annual_fits']
