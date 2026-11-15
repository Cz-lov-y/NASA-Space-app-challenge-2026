"""Six-tile joint-family regressions with explicitly synthetic temporary inputs."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.fine_collection import audit_collection, prepare_collection
from src.fine_grid import build_tile_catalog

BBOXES = [(-98,37,-97,38), (-106,54,-105,55), (-5,38,-4,39), (2,13,3,14), (145,-36,146,-35), (-60,-4,-59,-3)]


def write_tile(root, tile, *, ndvi=False, constant=False):
    directory = root/tile['directory']; directory.mkdir(parents=True, exist_ok=True)
    catalog = build_tile_catalog(tile['bbox'])
    dates = pd.date_range('2003-01-01', '2024-12-01', freq='MS')
    rows = []
    for feature in catalog['features']:
        p = feature['properties']
        p.update(tile_id=tile['id'], variables=['soil_water_0_10cm','soil_water_0_100cm']+(['ndvi'] if ndvi else []),
                 data_status='partial_ndvi' if ndvi else 'pending_ndvi')
        for variable, unit in [('soil_water_0_10cm','kg m-2'),('soil_water_0_100cm','kg m-2')]+([('ndvi','1')] if ndvi else []):
            for date in dates:
                year = date.year-2003
                pending = variable == 'ndvi' and year >= 8
                value = (0.4 if constant else .2+.01*year) if variable == 'ndvi' else 100-2*year
                rows.append({'date':date.strftime('%Y-%m-%d'), 'value':np.nan if pending else value,
                    'unit':unit,'variable':variable,'source':'SYNTHETIC_TEST_ONLY','region_id':p['region_id'],
                    'valid_area_fraction':np.nan if pending else 1.,'valid_area_m2':np.nan if pending else p['region_area_m2'],
                    'region_area_m2':p['region_area_m2'],'quality_flag':'pending_export' if pending else 'coverage_review_required',
                    'area_method':'modis_sinusoidal_sphere_native_pixel_v2' if variable == 'ndvi' and not pending else None})
    frame = pd.DataFrame(rows).sort_values(['region_id','variable','date'])
    frame.to_csv(directory/'monthly_timeseries.csv', index=False)
    frame[frame.variable != 'ndvi'].to_csv(directory/'gldas_monthly_timeseries.csv', index=False)
    (directory/'catalog.json').write_text(json.dumps(catalog))
    (directory/'metadata.json').write_text(json.dumps({'data_kind':'SYNTHETIC_TEST_ONLY'}))
    manifest = []
    for date in dates:
        path = root/'raw'/date.strftime('%Y-%m.txt'); path.parent.mkdir(exist_ok=True)
        data = ('SYNTHETIC_TEST_ONLY '+date.strftime('%Y-%m')).encode(); path.write_bytes(data)
        manifest.append({'file':str(path.relative_to(root)), 'date':date.strftime('%Y-%m-%d'), 'sha256':hashlib.sha256(data).hexdigest()})
    (directory/'source_manifest.json').write_text(json.dumps(manifest))


@pytest.fixture
def collection_inputs(tmp_path):
    index = {'schema_version':'fine-tiles-1', 'period':['2003-01-01','2024-12-31'],
        'collection_directory':'collection', 'selection_basis':'SYNTHETIC_TEST_ONLY frozen six tiles',
        'tiles':[{'id':f'tile_{i}', 'name':f'Test tile{i}', 'bbox':list(bbox), 'directory':f'tiles/{i}'} for i,bbox in enumerate(BBOXES)]}
    for i,tile in enumerate(index['tiles']):
        write_tile(tmp_path, tile, ndvi=i==0)
    path = tmp_path/'tiles.json'; path.write_text(json.dumps(index))
    return tmp_path, path, index


def test_one_joint_collection_preserves_all_source_values_and_frozen96cells(collection_inputs):
    root,index_path,index = collection_inputs
    before = {str(path):path.read_bytes() for path in (root/'tiles').rglob('*') if path.is_file()}
    result = prepare_collection(index_path, root=root)
    assert result['integrity_passed'] and result['errors'] == []
    assert result['native_cells'] == 96 and result['tiles'] == 6
    assert result['gldas_source_files'] == 264
    assert result['paired_eligible_cells'] == 16 and result['family_size'] == 32
    report = json.loads((root/'collection/screening.json').read_text())
    assert len(report['regions']) == report['multiple_testing']['catalog_regions'] == 96
    assert report['multiple_testing']['declared_tiles'] == [tile['id'] for tile in index['tiles']]
    assert 'six frozen' in report['multiple_testing']['scope']
    assert all(r['screening']['qa_reviewed'] is False for r in report['regions'])
    metadata = json.loads((root/'collection/metadata.json').read_text())
    assert metadata['data_kind'] == 'synthetic test inputs'
    assert before == {str(path):path.read_bytes() for path in (root/'tiles').rglob('*') if path.is_file()}


def test_more_actual_paired_tests_change_joint_q_but_not_frozen_family_identity(collection_inputs):
    root,index_path,index = collection_inputs
    first = prepare_collection(index_path, root=root)
    before = json.loads((root/'collection/screening.json').read_text())
    write_tile(root,index['tiles'][1],ndvi=True,constant=True)
    second = prepare_collection(index_path,root=root)
    after = json.loads((root/'collection/screening.json').read_text())
    assert first['family_id'] == second['family_id']
    assert first['family_size'] == 32 and second['family_size'] == 64
    rid = next(r['region_id'] for r in before['regions'] if r['status'] == 'eligible')
    old = next(r for r in before['regions'] if r['region_id'] == rid)
    new = next(r for r in after['regions'] if r['region_id'] == rid)
    assert new['screening']['adjusted_p_values']['ndvi'] > old['screening']['adjusted_p_values']['ndvi']
    assert new['analysis'] == old['analysis']  # Original per-region response is untouched.


def test_audit_detects_q_value_tampering_even_when_map_and_report_match(collection_inputs):
    root,index_path,_ = collection_inputs
    prepare_collection(index_path,root=root)
    directory = root/'collection'
    report = json.loads((directory/'screening.json').read_text())
    eligible = next(r for r in report['regions'] if r['status']=='eligible')
    eligible['screening']['adjusted_p_values']['ndvi'] = .9
    (directory/'screening.json').write_text(json.dumps(report))
    mapping = json.loads((directory/'map_screening.geojson').read_text())
    mapped = next(f for f in mapping['features'] if f['id']==eligible['region_id'])
    mapped['properties']['indicators']['ndvi']['worldwide_adjusted_p_value'] = .9
    mapped['properties']['indicators']['ndvi']['worldwide_significant'] = False
    (directory/'map_screening.geojson').write_text(json.dumps(mapping))
    result = audit_collection(directory,root=root)
    assert not result['integrity_passed']
    assert 'Stored q-value does not use the joint family' in result['errors']


def test_registry_overlap_and_changed_source_during_fit_are_rejected(collection_inputs,monkeypatch):
    import src.fine_collection as module
    root,index_path,index = collection_inputs
    overlap = deepcopy(index); overlap['tiles'][1]['directory'] = overlap['tiles'][0]['directory']
    index_path.write_text(json.dumps(overlap))
    with pytest.raises(ValueError, match='Duplicate tile directory'):
        prepare_collection(index_path,root=root)
    index_path.write_text(json.dumps(index))
    original = module.build_regional_screening
    def changing(frame,catalog,**kwargs):
        result = original(frame,catalog,**kwargs)
        path = root/index['tiles'][0]['directory']/'monthly_timeseries.csv'
        path.write_bytes(path.read_bytes()+b'\n')
        return result
    monkeypatch.setattr(module,'build_regional_screening',changing)
    with pytest.raises(ValueError,match='changed during'):
        prepare_collection(index_path,root=root)
    assert not (root/'collection/screening.json').exists()


def test_collection_refuses_mixed_or_legacy_area_method_before_publishing(collection_inputs):
    root,index_path,index = collection_inputs
    path = root/index['tiles'][0]['directory']/'monthly_timeseries.csv'
    frame = pd.read_csv(path,dtype={'unit':str},float_precision='round_trip')
    received = (frame.variable == 'ndvi') & (frame.quality_flag != 'pending_export')
    frame.loc[received, 'area_method'] = 'legacy_ellipsoidal_pixel_area_v1'
    frame.to_csv(path,index=False)
    with pytest.raises(ValueError,match='area_methodv2'):
        prepare_collection(index_path,root=root)
    assert not (root/'collection/screening.json').exists()


def test_failed_staged_audit_cannot_publish_or_replace_a_release(collection_inputs,monkeypatch):
    import src.fine_collection as module
    root,index_path,_ = collection_inputs
    output = root/'collection'
    output.mkdir()
    (output/'screening.json').write_bytes(b'EXISTING_RELEASE_SENTINEL')
    (output/'map_screening.geojson').write_bytes(b'EXISTING_MAP_SENTINEL')
    def reject(directory,**kwargs):
        assert Path(directory) != output
        assert (Path(directory)/'screening.json').is_file()
        assert (output/'screening.json').read_bytes() == b'EXISTING_RELEASE_SENTINEL'
        return {'integrity_passed':False,'errors':['Deliberate synthetic staging rejection']}
    monkeypatch.setattr(module,'audit_collection',reject)
    with pytest.raises(ValueError,match='staging rejection'):
        prepare_collection(index_path,root=root)
    assert (output/'screening.json').read_bytes() == b'EXISTING_RELEASE_SENTINEL'
    assert (output/'map_screening.geojson').read_bytes() == b'EXISTING_MAP_SENTINEL'
    assert not (output/'release_audit.json').exists()
