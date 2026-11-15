"""Real native-cell handoff checks; fixtures copy data only into temporary storage.

No screening refit or network request is needed. Independent annual OLS below
uses 22 actual GLDAS annual means to check the stored fit's aggregation/units.
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


def test_real_native_cell_detail_preserves_528_rows_units_and_pending_pair():
    bundle = load_fine_region(FIRST)
    detail = build_region_detail(bundle)
    assert detail['screening_status'] == 'current'
    assert detail['screening']['classification'] == 'pending'
    assert detail['screening']['category'] is None
    assert detail['paired_analysis'] is None
    assert len(detail['observations']) == 528
    obs = pd.DataFrame(detail['observations'])
    assert set(obs.variable) == {'soil_water_0_10cm', 'soil_water_0_100cm'}
    assert obs.unit.eq('kg m-2').all()
    assert obs.source.eq('GLDAS_NOAH025_M.2.1').all()
    assert obs.quality_flag.eq('coverage_review_required').all()
    assert obs.value.notna().all()
    assert set(obs.region_id) == {FIRST}
    months = pd.date_range('2003-01-01', '2024-12-01', freq='MS')
    for _, group in obs.groupby('variable'):
        dates = pd.to_datetime(group.date, utc=True)
        assert dates.dt.strftime('%Y-%m-%d').tolist() == months.strftime('%Y-%m-%d').tolist()
    actual = pd.read_csv(FINE / 'monthly_timeseries.csv', dtype={'unit': str})
    expected = actual[actual.region_id == FIRST]
    assert obs.value.tolist() == pytest.approx(expected.value.tolist())
    assert detail['scientific_display']['analysis_kind'] == 'available_indicator'
    assert not detail['scientific_display']['qa_reviewed']
    assert not detail['scientific_display']['synthetic_demo']
    assert '0.25-degree' in detail['provenance']['resolution_notice']
    json.dumps(detail, allow_nan=False)


def test_actual_22_year_soil_fit_matches_independent_annual_means():
    bundle = load_fine_region(FIRST)
    detail = build_region_detail(bundle)
    frame = bundle['observations'].query("variable == 'soil_water_0_100cm'")
    annual = frame.groupby(frame.date.dt.year).value.mean()
    assert annual.index.tolist() == list(range(2003, 2025))
    assert frame.groupby(frame.date.dt.year).value.count().eq(12).all()
    # Independent degree-one least-squares calculation; source values stay untouched.
    slope, intercept = np.polyfit(annual.index.to_numpy() - 2003, annual.to_numpy(), 1)
    fit = detail['annual_fits']['soil_water_0_100cm']
    assert fit['unit'] == 'kg m-2'
    assert fit['slope_unit'] == 'kg m-2/year'
    assert fit['slope_per_year'] == pytest.approx(slope, rel=1e-10, abs=1e-12)
    assert fit['intercept'] == pytest.approx(intercept, rel=1e-12)
    assert fit['time_origin'] == 2003
    assert len(fit['points']) == 22
    assert [point['year'] for point in fit['points']] == list(range(2003, 2025))
    assert all(point['date'] == f"{point['year']}-01-01" for point in fit['points'])
    assert [point['value'] for point in fit['points']] == pytest.approx(intercept + slope * np.arange(22))


def test_native_map_is_the_frozen_16_cell_pilot_without_paired_significance():
    payload = fine_map()
    report = json.loads((FINE / 'screening.json').read_text())
    assert payload['type'] == 'FeatureCollection'
    assert len(payload['features']) == 16
    assert len({feature['id'] for feature in payload['features']}) == 16
    family = payload['multiple_testing']
    assert family['catalog_regions'] == 16
    assert family['family_size'] == family['eligible_regions'] == 0
    assert 'pilot' in family['scope'].lower()
    assert family['scope'] == report['multiple_testing']['scope']
    assert family['provisional']
    for name, key in [('monthly_timeseries.csv', 'source_csv_sha256'), ('catalog.json', 'source_catalog_sha256')]:
        assert payload[key] == hashlib.sha256((FINE / name).read_bytes()).hexdigest()
    for feature in payload['features']:
        p = feature['properties']
        assert p['bbox'] == cell_bbox(*parse_cell_id(feature['id']))
        assert p['native_resolution_degrees'] == .25
        assert p['classification'] == 'pending'
        assert p['category'] is None
        assert p['paired_year_count'] == 0 and p['available_year_count'] == 22
        assert not p['qa_reviewed']
        assert not p['synthetic_demo']
        assert p['indicators']['soil_water_0_100cm']['worldwide_significant'] is None
        assert p['indicators']['soil_water_0_100cm']['worldwide_adjusted_p_value'] is None


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
