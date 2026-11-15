"""Real native-cell handoff checks; fixtures copy data only into temporary storage.

No screening refit or network request is needed. Independent annual OLS below
uses the actual reported GLDAS annual record to check stored fit aggregation/units
while allowing genuine regional NDVI imports to extend the release.
"""
import hashlib
import json
import shutil

import numpy as np
import pandas as pd
import pytest

from src.fine_grid import cell_bbox, parse_cell_id
from src.fine_workflow import FINE, fine_map, load_fine_region
from src.region_transport import build_region_detail

FIRST = 'gldas025_r388_c0328'


@pytest.fixture
def copied_release(tmp_path):
    for name in ('catalog.json', 'monthly_timeseries.csv', 'metadata.json',
                 'source_manifest.json', 'screening.json', 'map_screening.geojson'):
        shutil.copyfile(FINE / name, tmp_path / name)
    return tmp_path


def _complete_annual(frame, variable):
    """Independent complete-month annual means from actual supplied observations."""
    single = frame[frame.variable == variable].copy()
    if single.empty:
        return pd.Series(dtype=float)
    values = pd.to_numeric(single.value, errors='raise')
    rejected = single.quality_flag.isin({'low_coverage', 'negative_value', 'missing', 'invalid',
        'qa_rejected', 'no_valid_data', 'no_valid_pixels'}) if 'quality_flag' in single else False
    single['value'] = values.mask(rejected) if isinstance(rejected, pd.Series) else values
    years = pd.to_datetime(single.date, utc=True).dt.year
    grouped = single.groupby(years).value
    return grouped.mean()[grouped.count() == 12]


def test_real_native_detail_preserves_both_soil_series_and_received_ndvi():
    bundle = load_fine_region(FIRST)
    detail = build_region_detail(bundle)
    assert detail['screening_status'] == 'current'
    obs = pd.DataFrame(detail['observations'])
    soil_names = {'soil_water_0_10cm', 'soil_water_0_100cm'}
    assert soil_names <= set(obs.variable) <= soil_names | {'ndvi'}
    soil = obs[obs.variable.isin(soil_names)]
    assert len(soil) == 528
    assert soil.unit.eq('kg m-2').all()
    assert soil.source.eq('GLDAS_NOAH025_M.2.1').all()
    assert soil.quality_flag.eq('coverage_review_required').all()
    assert soil.value.notna().all()
    assert set(obs.region_id) == {FIRST}
    months = pd.date_range('2003-01-01', '2024-12-01', freq='MS')
    for _, group in obs.groupby('variable'):
        dates = pd.to_datetime(group.date, utc=True)
        assert dates.dt.strftime('%Y-%m-%d').tolist() == months.strftime('%Y-%m-%d').tolist()
    original = pd.read_csv(FINE / 'gldas_monthly_timeseries.csv', dtype={'unit': str})
    original = original[original.region_id == FIRST].sort_values(['date', 'variable'])
    actual_soil = soil.assign(date=pd.to_datetime(soil.date, utc=True).dt.strftime('%Y-%m-%d')).sort_values(['date', 'variable'])
    np.testing.assert_allclose(actual_soil.value.to_numpy(), original.value.to_numpy(), rtol=0, atol=1e-12)
    actual = pd.read_csv(FINE / 'monthly_timeseries.csv', dtype={'unit': str})
    expected = actual[actual.region_id == FIRST]
    np.testing.assert_allclose(obs.value.to_numpy(), expected.value.to_numpy(), equal_nan=True)
    ndvi = obs[obs.variable == 'ndvi']
    if not ndvi.empty:
        assert len(ndvi) == 264
        assert ndvi.unit.eq('1').all()
        assert ndvi.source.eq('MOD13A3.061').all()
        assert ndvi.loc[ndvi.value.notna(), 'value'].between(-.2, 1).all()
        assert ndvi.loc[ndvi.quality_flag.isin(['pending_export', 'missing', 'no_valid_pixels']), 'value'].isna().all()
    paired = detail['paired_analysis']
    common = sorted(set(_complete_annual(obs, 'ndvi').index) & set(_complete_annual(obs, 'soil_water_0_100cm').index))
    if paired is None:
        assert detail['screening']['classification'] == 'pending'
        assert detail['screening']['category'] is None
    else:
        assert paired['observation_period']['years'] == common
        if len(common) < 8:
            assert detail['screening']['classification'] == 'insufficient'
            assert detail['screening']['category'] is None
        else:
            assert detail['screening']['classification'] in {'supported_signal', 'uncertain_signal', 'no_detected_divergence'}
            assert detail['screening']['category'] in {'Supported Signal', 'Uncertain Signal', 'No Detected Divergence'}
    expected_kind = 'available_indicator' if detail['available_indicator_analysis'] else 'paired'
    assert detail['scientific_display']['analysis_kind'] == expected_kind
    assert not detail['scientific_display']['qa_reviewed']
    assert not detail['scientific_display']['synthetic_demo']
    assert '0.25-degree' in detail['provenance']['resolution_notice']
    json.dumps(detail, allow_nan=False)


def test_actual_soil_fit_matches_independent_means_for_its_reported_annual_record():
    bundle = load_fine_region(FIRST)
    detail = build_region_detail(bundle)
    frame = bundle['observations'].query("variable == 'soil_water_0_100cm'")
    all_annual = _complete_annual(frame, 'soil_water_0_100cm')
    assert all_annual.index.tolist() == list(range(2003, 2025))
    assert frame.groupby(frame.date.dt.year).value.count().eq(12).all()
    display = detail['available_indicator_analysis'] or detail['paired_analysis']
    years = display['analysis']['soil_water_0_100cm']['data_quality']['analyzed_years']
    assert len(years) >= 8
    annual = all_annual.reindex(years)
    origin = years[0]
    # Independent least squares over exactly the stored analyzed years.
    slope, intercept = np.polyfit(annual.index.to_numpy() - origin, annual.to_numpy(), 1)
    fit = detail['annual_fits']['soil_water_0_100cm']
    assert fit['unit'] == 'kg m-2'
    assert fit['slope_unit'] == 'kg m-2/year'
    assert fit['slope_per_year'] == pytest.approx(slope, rel=1e-10, abs=1e-12)
    assert fit['intercept'] == pytest.approx(intercept, rel=1e-12)
    assert fit['time_origin'] == origin
    assert len(fit['points']) == len(years)
    assert [point['year'] for point in fit['points']] == years
    assert all(point['date'] == f"{point['year']}-01-01" for point in fit['points'])
    assert [point['value'] for point in fit['points']] == pytest.approx(intercept + slope * (np.asarray(years) - origin))


def test_native_map_keeps_frozen_pilot_family_as_actual_ndvi_arrives():
    payload = fine_map()
    report = json.loads((FINE / 'screening.json').read_text())
    frame = pd.read_csv(FINE / 'monthly_timeseries.csv', dtype={'unit': str})
    assert payload['type'] == 'FeatureCollection'
    assert len(payload['features']) == 16
    assert len({feature['id'] for feature in payload['features']}) == 16
    family = payload['multiple_testing']
    assert family['catalog_regions'] == 16
    independent_eligible = 0
    for _, group in frame.groupby('region_id'):
        common = set(_complete_annual(group, 'ndvi').index) & set(_complete_annual(group, 'soil_water_0_100cm').index)
        independent_eligible += len(common) >= 8
    assert family['eligible_regions'] == independent_eligible
    assert family['family_size'] == 2 * independent_eligible
    assert 'pilot' in family['scope'].lower()
    assert family['scope'] == report['multiple_testing']['scope']
    assert family['provisional']
    records = {record['region_id']: record for record in report['regions']}
    for name, key in [('monthly_timeseries.csv', 'source_csv_sha256'), ('catalog.json', 'source_catalog_sha256')]:
        assert payload[key] == hashlib.sha256((FINE / name).read_bytes()).hexdigest()
    for feature in payload['features']:
        p = feature['properties']
        record = records[feature['id']]
        paired = record['analysis']
        available = record['available_indicator_analysis']
        assert p['bbox'] == cell_bbox(*parse_cell_id(feature['id']))
        assert p['native_resolution_degrees'] == .25
        assert p['classification'] == record['screening']['classification']
        assert p['category'] == record['screening']['category']
        assert p['paired_year_count'] == len((paired or {}).get('observation_period', {}).get('years', []))
        assert p['available_year_count'] == len((available or {}).get('observation_period', {}).get('years', []))
        assert not p['qa_reviewed']
        assert not p['synthetic_demo']
        for variable, indicator in p['indicators'].items():
            if record['status'] == 'eligible':
                q = record['screening']['adjusted_p_values'][variable]
                assert 0 <= q <= 1
                assert indicator['worldwide_adjusted_p_value'] == q
                assert indicator['worldwide_significant'] == (q < report['settings']['alpha'])
            else:
                assert indicator['worldwide_significant'] is None
                assert indicator['worldwide_adjusted_p_value'] is None


@pytest.mark.parametrize('changed', ['monthly_timeseries.csv', 'catalog.json'])
def test_fresh_source_or_boundary_change_withholds_old_science(copied_release, changed):
    first = load_fine_region(FIRST, directory=copied_release)
    assert first['screening_status'] == 'current'
    assert len(fine_map(directory=copied_release)['features']) == 16
    path = copied_release / changed
    if changed.endswith('.csv'):
        # A source-byte revision must invalidate the old release even if values match.
        path.write_bytes(path.read_bytes() + b'\n')
    else:
        catalog = json.loads(path.read_text())
        catalog['features'][0]['properties']['bbox'][0] += .01
        path.write_text(json.dumps(catalog))
    second = load_fine_region(FIRST, directory=copied_release)
    assert second['screening_status'] == 'stale_rebuild_required'
    assert second['screening'] is None
    assert second['research_context']['dataset_version'] != first['research_context']['dataset_version']
    detail = build_region_detail(second)
    assert detail['paired_analysis'] is None
    assert detail['available_indicator_analysis'] is None
    assert detail['annual_fits'] == {}
    assert detail['screening'] is None
    with pytest.raises(ValueError, match='rebuild'):
        fine_map(directory=copied_release)


def test_native_lookup_rejects_coarse_invalid_and_unavailable_ids():
    for region_id in ('grid_r12_c08', 'gldas025_r600_c0000', 'gldas025_r000_c0000'):
        with pytest.raises(ValueError):
            load_fine_region(region_id)


def test_native_loader_returns_independent_observations_and_provenance():
    first = load_fine_region(FIRST)
    original_value = first['observations'].value.iloc[0]
    first['observations'].iloc[0, first['observations'].columns.get_loc('value')] = -9999
    first['provenance']['resolution_notice'] = 'modified by caller'
    first['feature']['properties']['bbox'][0] = -999
    second = load_fine_region(FIRST)
    assert second['observations'].value.iloc[0] == original_value
    assert second['provenance']['resolution_notice'] != 'modified by caller'
    assert second['feature']['properties']['bbox'][0] == -98
