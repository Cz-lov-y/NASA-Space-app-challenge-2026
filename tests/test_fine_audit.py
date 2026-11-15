"""Read-only audit regressions using temporary copies of genuine native data."""
import hashlib
import json
from pathlib import Path
import shutil

import pandas as pd
import pytest

from scripts.audit_fine_release import audit
from src.fine_workflow import FINE


def soil_only_copy(source, destination):
    """Create a deterministic soil-only view in temporary test storage.

    The checked-in release may have no, partial or complete real NDVI. Tests
    exercise each ingestion state independently using its genuine unchanged soil
    table. Source archives/manifests in the repository are never modified.
    """
    from scripts.prepare_fine_backend import prepare
    destination=Path(destination)
    if destination.resolve()==Path(source).resolve():
        raise ValueError('Test destination must differ from the real release')
    shutil.copytree(source,destination)
    soil=pd.read_csv(destination/'gldas_monthly_timeseries.csv',dtype={'unit':str},float_precision='round_trip')
    soil.to_csv(destination/'monthly_timeseries.csv',index=False)
    catalog_path=destination/'catalog.json'
    catalog=json.loads(catalog_path.read_text())
    for feature in catalog['features']:
        props=feature['properties']
        props['variables']=['soil_water_0_10cm','soil_water_0_100cm']
        props['ndvi_status']='pending_export'
        props.pop('ndvi_valid_months',None)
        props.pop('ndvi_exported_months',None)
        if props.get('data_status')!='unsupported_gldas':
            props['data_status']='pending_ndvi'
    catalog_path.write_text(json.dumps(catalog,indent=2)+'\n')
    metadata_path=destination/'metadata.json'
    metadata=json.loads(metadata_path.read_text())
    metadata['ndvi']='Pending native MODIS aggregation; soil-only temporary test view'
    for key in ('dataset_versions','dataset_fingerprint','modis'):
        metadata.pop(key,None)
    metadata_path.write_text(json.dumps(metadata,indent=2)+'\n')
    # Remove accepted NDVI only in the copied test directory. The genuine source
    # manifests and archived bytes referenced outside this copy remain intact.
    for name in ('accepted_modis_observations.csv','modis_source_manifest.json',
                 'modis_pilot_audit.json','modis_pixel_validation.json','release_audit.json'):
        (destination/name).unlink(missing_ok=True)
    quality=soil.groupby(['region_id','variable']).agg(expected_months=('value','size'),
        valid_months=('value','count'),min_coverage=('valid_area_fraction','min'),
        max_coverage=('valid_area_fraction','max'))
    quality['missing_months']=quality.expected_months-quality.valid_months
    quality.to_csv(destination/'quality_report.csv')
    prepare(destination)
    return destination


@pytest.fixture
def copied_release(tmp_path):
    return soil_only_copy(FINE,tmp_path/'fine')


def test_genuine_fine_audit_distinguishes_integrity_from_ndvi_completeness(copied_release):
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in copied_release.iterdir() if p.is_file()}
    result=audit(copied_release)
    assert result['integrity_passed'] and result['errors']==[]
    assert result['native_cells']==16 and result['gldas_rows']==8448 and result['source_months']==264
    assert result['required_ndvi_rows']==4224
    assert 'provisional' in result['scientific_review_status']
    assert 'pilot only' in result['scope']
    after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in copied_release.iterdir() if p.is_file()}
    assert before==after


def test_changed_soil_units_and_values_cannot_pass_as_original_data(copied_release):
    path=copied_release/'monthly_timeseries.csv'
    data=pd.read_csv(path,dtype={'unit':str},float_precision='round_trip')
    index=data.index[data.variable=='soil_water_0_100cm'][0]
    data.loc[index,'unit']='m3 m-3'
    data.loc[index,'value']+=1
    data.to_csv(path,index=False)
    result=audit(copied_release)
    assert not result['integrity_passed']
    assert 'soil storage units/product remain canonical' in result['errors']
    assert 'combined soil observations exactly preserve original native GLDAS table' in result['errors']
    assert 'screening: current source fingerprints' in result['errors']


def test_grid_shift_and_invented_statistical_year_are_detected(copied_release):
    path=copied_release/'catalog.json'
    catalog=json.loads(path.read_text())
    catalog['features'][0]['geometry']['coordinates'][0][0][0]+=.01
    path.write_text(json.dumps(catalog))
    path=copied_release/'screening.json'
    screening=json.loads(path.read_text())
    diagnostic=screening['regions'][0]['available_indicator_analysis']
    diagnostic['analysis']['soil_water_0_100cm']['data_quality']['analyzed_years'].append(1999)
    path.write_text(json.dumps(screening))
    result=audit(copied_release)
    assert not result['integrity_passed']
    assert any('native canonical geometry' in e for e in result['errors'])
    assert any('analyzed years have12independent valid months' in e for e in result['errors'])


def test_source_hash_mismatch_and_wrong_test_family_are_detected(copied_release,tmp_path):
    fake=tmp_path/'deliberately_altered_test_source.nc4'
    fake.write_bytes(b'TEST ONLY deliberately altered source bytes')
    path=copied_release/'source_manifest.json'
    manifest=json.loads(path.read_text())
    manifest[0]['file']=str(fake)
    path.write_text(json.dumps(manifest))
    path=copied_release/'map_screening.geojson'
    mapping=json.loads(path.read_text())
    mapping['multiple_testing']['scope']='Worldwide fine-resolution significant hotspots'
    mapping['features'][0]['properties']['qa_reviewed']=True
    path.write_text(json.dumps(mapping))
    result=audit(copied_release)
    assert not result['integrity_passed']
    assert any('source hash matches (deliberately_altered_test_source.nc4)' in e for e in result['errors'])
    assert 'map: testing family explicitly bounded to fine pilot' in result['errors']
    assert any('map retains provisional real labels' in e for e in result['errors'])


def test_removed_month_and_misreported_quality_are_detected(copied_release):
    path=copied_release/'monthly_timeseries.csv'
    data=pd.read_csv(path,dtype={'unit':str},float_precision='round_trip')
    data.iloc[1:].to_csv(path,index=False)
    path=copied_release/'quality_report.csv'
    quality=pd.read_csv(path)
    quality.loc[0,'valid_months']=999
    quality.to_csv(path,index=False)
    result=audit(copied_release)
    assert not result['integrity_passed']
    assert any('preserved complete264-month index' in e for e in result['errors'])
    assert 'quality report counts reconcile independently' in result['errors']


def synthetic_modis_fixture(catalog):
    """Synthetic exported values only for tests; never saved in shipped data."""
    from scripts.merge_regional_timeseries import NATIVE_AFFINE
    transform='PARAM_MT["Affine",'+','.join(f'PARAMETER["{k}",{v}]' for k,v in NATIVE_AFFINE.items())+']'
    return pd.DataFrame([{
        'date':'2003-01-01','region_id':p['region_id'],'variable':'ndvi','value':.4,
        'unit':'1','source':'MOD13A3.061','valid_area_fraction':.8,
        'valid_area_m2':p['region_area_m2']*.8,'region_area_m2':p['region_area_m2'],
        'quality_flag':'coverage_review_required','source_image_count':1,
        'source_asset_id':'MODIS/061/MOD13A3/2003_01_01','source_time_start':'2003-01-01',
        'source_crs':'SR-ORG:6974','source_transform':transform,
        'qa_rule':'raw NDVI [-2000,10000]; (DetailedQA & 3)==0; SummaryQA==0',
        'configured_at_utc':'2026-11-15T12:00:00Z','tile_id':p['tile_id'],
        'target_resolution_degrees':.25,'test_fixture':'SYNTHETIC_UNIT_TEST_VALUES_ONLY',
    } for p in (f['properties'] for f in catalog['features'])])


def test_partial_import_passes_integrity_keeps_placeholders_and_detects_archive_ledger_tamper(copied_release,tmp_path):
    from scripts.merge_fine_modis import ingest
    from scripts.prepare_fine_backend import prepare
    catalog=json.loads((copied_release/'catalog.json').read_text())
    path=tmp_path/'SYNTHETIC_TEST_EXPORT.csv'
    synthetic_modis_fixture(catalog).to_csv(path,index=False)
    ingest([path],copied_release)
    prepare(copied_release)
    result=audit(copied_release)
    assert result['integrity_passed'],result['errors']
    assert not result['full_required_period_complete']
    assert result['ndvi_rows']==4224 and result['ndvi_exported_rows']==16
    assert result['ndvi_valid_rows']==16 and result['paired_eligible_cells']==0
    # Tamper both accepted ledger and combined values equally: merely comparing
    # them would miss the change; archival bytes must catch it independently.
    path=copied_release/'accepted_modis_observations.csv'
    ledger=pd.read_csv(path,dtype={'unit':str},float_precision='round_trip')
    ledger.loc[0,'value']=.5
    ledger.to_csv(path,index=False)
    path=copied_release/'monthly_timeseries.csv'
    combined=pd.read_csv(path,dtype={'unit':str},float_precision='round_trip')
    combined.loc[(combined.variable=='ndvi') & (combined.region_id==ledger.region_id.iloc[0]) & (combined.date=='2003-01-01'),'value']=.5
    combined.to_csv(path,index=False)
    result=audit(copied_release)
    assert not result['integrity_passed']
    assert 'ledger authoritative values/provenance equal original archived bytes' in result['errors']


def test_full_import_integrity_is_separate_from_scientific_review(copied_release,tmp_path):
    """All NDVI here is synthetic test input; only the copied soil is real data."""
    from scripts.merge_fine_modis import ingest
    from scripts.prepare_fine_backend import prepare
    catalog=json.loads((copied_release/'catalog.json').read_text())
    one=synthetic_modis_fixture(catalog)
    months=[]
    for date in pd.date_range('2003-01-01','2024-12-01',freq='MS'):
        frame=one.copy()
        frame['date']=date.strftime('%Y-%m-%d')
        frame['source_time_start']=date.strftime('%Y-%m-%d')
        frame['source_asset_id']='MODIS/061/MOD13A3/'+date.strftime('%Y_%m_%d')
        months.append(frame)
    path=tmp_path/'SYNTHETIC_FULL_INDEX_TEST_EXPORT.csv'
    pd.concat(months,ignore_index=True).to_csv(path,index=False)
    ingest([path],copied_release)
    prepare(copied_release)
    result=audit(copied_release)
    assert result['integrity_passed'],result['errors']
    assert result['full_required_period_complete']
    assert result['ndvi_valid_rows']==4224 and result['paired_eligible_cells']==16
    assert 'pending' in result['scientific_review_status']
    assert 'no worldwide inference' in result['scope']
    # The fixture reset must also work after a complete paired release exists,
    # preserving the original real soil values and removing accepted NDVI only
    # from the new temporary copy.
    reset=soil_only_copy(copied_release,tmp_path/'reset_from_complete')
    reset_result=audit(reset)
    assert reset_result['integrity_passed'],reset_result['errors']
    assert reset_result['ndvi_rows']==0 and reset_result['paired_eligible_cells']==0
    assert not reset_result['full_required_period_complete']
    pd.testing.assert_frame_equal(
        pd.read_csv(reset/'gldas_monthly_timeseries.csv',float_precision='round_trip'),
        pd.read_csv(copied_release/'gldas_monthly_timeseries.csv',float_precision='round_trip'))


def test_pending_cell_cannot_be_recolored_as_supported_by_mutating_both_artifacts(copied_release):
    path=copied_release/'screening.json'
    report=json.loads(path.read_text())
    decision=report['regions'][0]['screening']
    decision['classification']='supported_signal'
    decision['category']='Supported Signal'
    path.write_text(json.dumps(report))
    path=copied_release/'map_screening.geojson'
    mapping=json.loads(path.read_text())
    mapping['features'][0]['properties']['classification']='supported_signal'
    mapping['features'][0]['properties']['category']='Supported Signal'
    path.write_text(json.dumps(mapping))
    result=audit(copied_release)
    assert not result['integrity_passed']
    assert any('noneligible status cannot become a detected signal' in error for error in result['errors'])
