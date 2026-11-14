"""Real stored B→A→C integration, without network calls or synthetic NASA data."""
import json
import hashlib

import pytest

from src.nasa_data import get_timeseries
from src.regional_workflow import REGIONAL, export_region, load_region, research_selected_region


def test_real_regional_loader_and_unconfigured_research():
    catalog = json.loads((REGIONAL / 'catalog.json').read_text())
    feature = next(f for f in catalog['features']
                   if f['properties']['variables'] and f['properties']['jurisdictions'])
    region = feature['properties']['region_id']
    bundle = load_region(region)
    frame = get_timeseries(region, 'soil_water_0_100cm')
    assert len(frame) == 264
    assert frame.unit.eq('kg m-2').all()
    assert frame.source.eq('GLDAS_NOAH025_M.2.1').all()
    assert frame.value.notna().all()
    assert frame.attrs['metadata']['dataset_version'] == 'GLDAS_NOAH025_M.2.1'
    report = research_selected_region(bundle, environ={})
    assert report['status'] == 'unavailable'
    assert report['qualitative'] is None
    assert report['quantitative_analysis']['region'] == region
    assert report['candidate_sources'] == []


def test_unknown_regional_id_fails():
    with pytest.raises(ValueError, match='Unknown regional ID'):
        load_region('grid_r99_c99')


def test_cached_snapshots_are_isolated_and_detail_export_keeps_real_numbers():
    first = load_region('grid_r14_c07')
    original = first['observations'].value.iloc[0]
    detail = export_region(first)
    assert detail['observations'][0]['value'] == pytest.approx(original)
    assert detail['paired_analysis'] is None
    assert detail['available_indicator_analysis']['variables'] == ['soil_water_0_100cm']
    json.dumps(detail, allow_nan=False)
    first['observations'].iloc[0, first['observations'].columns.get_loc('value')] = -123
    first['feature']['properties']['bbox'][0] = -999
    first['screening']['status'] = 'invented'
    second = load_region('grid_r14_c07')
    assert second['observations'].value.iloc[0] == original
    assert second['feature']['properties']['bbox'][0] != -999
    assert second['screening']['status'] == 'pending'
    missing = second['observations'].copy()
    missing.loc[missing.index[0], 'value'] = float('nan')
    second['observations'] = missing
    assert export_region(second)['observations'][0]['value'] is None


def test_changed_data_or_boundary_withholds_screening_and_changes_cache_identity(tmp_path):
    """Prevent fresh numbers from being paired with a previous release's result."""
    catalog = {'type': 'FeatureCollection', 'features': [{
        'type': 'Feature', 'geometry': None,
        'properties': {'region_id': 'cell', 'bbox': [0, 0, 10, 10],
                       'jurisdictions': [{'name': 'Country'}]}}]}
    catalog_path = tmp_path / 'catalog.json'
    catalog_path.write_text(json.dumps(catalog))
    csv = tmp_path / 'monthly_timeseries.csv'
    csv.write_text('date,value,unit,variable,source,region_id\n2003-01-01,20,kg m-2,soil_water_0_100cm,GLDAS_NOAH025_M.2.1,cell\n')
    (tmp_path / 'metadata.json').write_text('{}')
    record = {'region_id': 'cell', 'analysis': None,
              'available_indicator_analysis': {'region': 'cell', 'trend_slopes': {'soil_water_0_100cm': -1}}}
    report = {'source_csv_sha256': hashlib.sha256(csv.read_bytes()).hexdigest(),
              'source_catalog_sha256': hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
              'regions': [record]}
    (tmp_path / 'screening.json').write_text(json.dumps(report))
    first = load_region('cell', directory=tmp_path)
    assert first['screening_status'] == 'current'
    research = research_selected_region(first, environ={})
    assert research['quantitative_analysis']['trend_slopes']['soil_water_0_100cm'] == -1
    assert any('paired analysis is unavailable' in x for x in research['limitations'])
    csv.write_text(csv.read_text().replace(',20,', ',21,'))
    changed = load_region('cell', directory=tmp_path)
    assert changed['screening_status'] == 'stale_rebuild_required'
    assert changed['screening'] is None
    assert changed['research_context']['dataset_version'] != first['research_context']['dataset_version']
    csv.write_text(csv.read_text().replace(',21,', ',20,'))
    catalog['features'][0]['properties']['bbox'] = [0, 0, 5, 5]
    catalog_path.write_text(json.dumps(catalog))
    changed_boundary = load_region('cell', directory=tmp_path)
    assert changed_boundary['screening'] is None
    assert changed_boundary['research_context']['dataset_version'] != first['research_context']['dataset_version']
