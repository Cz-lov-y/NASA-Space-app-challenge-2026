"""Synthetic MODIS protocol fixtures only; no invented data enter repo artifacts."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
import pytest
from scripts.merge_fine_modis import validate,validate_frame,ingest
from scripts.export_fine_modis_earth_engine import load_request,CALCULATION_VERSION
ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture
def fine_release(tmp_path):
    source=ROOT/'data/processed/fine/central_us';out=tmp_path/'SYNTHETIC_MODIS_PROTOCOL_TEST';out.mkdir()
    for name in ['gldas_monthly_timeseries.csv','source_manifest.json','metadata.json']:
        shutil.copyfile(source/name,out/name)
    shutil.copyfile(out/'gldas_monthly_timeseries.csv',out/'monthly_timeseries.csv')
    catalog=json.loads((source/'catalog.json').read_text())
    for f in catalog['features']:
        p=f['properties'];p.update(variables=['soil_water_0_10cm','soil_water_0_100cm'],data_status='pending_ndvi',ndvi_status='pending_export')
        p.pop('ndvi_valid_months',None);p.pop('ndvi_exported_months',None)
    (out/'catalog.json').write_text(json.dumps(catalog))
    metadata=json.loads((out/'metadata.json').read_text());metadata['data_kind']='SYNTHETIC_MODIS_TEST_ONLY; copied real GLDAS for interface validation'
    (out/'metadata.json').write_text(json.dumps(metadata))
    return out,catalog


def fake_rows(catalog,dates):
    """Invented NDVI with declared source protocol metadata, in temp files only."""
    transform=pd.read_csv(ROOT/'data/raw/modis_earth_engine/mod13a3_whole_earth_pilot_2003_01.csv').source_transform.iloc[0]
    return pd.DataFrame([{'date':date,'region_id':f['properties']['region_id'],'variable':'ndvi','value':.3,
        'unit':'1','source':'MOD13A3.061','valid_area_fraction':.6,
        'valid_area_m2':f['properties']['region_area_m2']*.6,'region_area_m2':f['properties']['region_area_m2'],
        'quality_flag':'coverage_review_required','source_image_count':1,
        'source_asset_id':'MODIS/061/MOD13A3/'+date.replace('-','_'),'source_time_start':date,
        'source_crs':'SR-ORG:6974','source_transform':transform,
        'qa_rule':'raw NDVI [-2000,10000]; (DetailedQA & 3)==0; SummaryQA==0','configured_at_utc':'2026-11-15T00:00:00Z',
        'tile_id':f['properties']['tile_id'],'target_resolution_degrees':.25,'area_method':CALCULATION_VERSION}
        for date in dates for f in catalog['features']])


def test_validation_is_readonly_and_checks_native_geometry_and_complete_cells(fine_release,tmp_path):
    out,catalog=fine_release;path=tmp_path/'SYNTHETIC_JAN.csv';rows=fake_rows(catalog,['2003-01-01']);rows.to_csv(path,index=False)
    before={p.name:p.read_bytes() for p in out.iterdir()}
    assert len(validate(path,catalog,expected_month='2003-01-01'))==16
    assert before=={p.name:p.read_bytes() for p in out.iterdir()}
    with pytest.raises(ValueError,match='expected month'):validate(path,catalog,expected_month='2003-02-01')
    with pytest.raises(ValueError,match='every requested'):validate_frame(rows.iloc[:-1],catalog)
    for changes in [{'area_method':'legacy_ellipsoid_pixelarea'},{'target_resolution_degrees':.01},{'tile_id':'wrong_tile'},{'unit':'m3 m-3'},
                    {'source_asset_id':'MODIS/061/MOD13A3/2003_02_01'},{'valid_area_m2':-1}]:
        bad=rows.copy()
        for key,value in changes.items():bad[key]=value
        with pytest.raises(ValueError):validate_frame(bad,catalog)
    changed=deepcopy(catalog);changed['features'][0]['properties']['bbox'][0]+=.01
    with pytest.raises(ValueError,match='geometry'):validate_frame(rows,changed)


def test_incremental_archives_conflicts_and_immutable_glDas(fine_release,tmp_path):
    out,catalog=fine_release
    original_glDas=(out/'gldas_monthly_timeseries.csv').read_bytes();manifest_before=(out/'source_manifest.json').read_bytes()
    geometry_before=[(f['geometry'],f['properties']['bbox']) for f in catalog['features']]
    jan=tmp_path/'SYNTHETIC_JAN.csv';feb=tmp_path/'SYNTHETIC_FEB.csv'
    fake_rows(catalog,['2003-01-01']).to_csv(jan,index=False);fake_rows(catalog,['2003-02-01']).to_csv(feb,index=False)
    report=ingest([jan],out)
    assert report['accepted_ndvi_rows']==16 and report['pending_export_rows']==4208
    frame=pd.read_csv(out/'monthly_timeseries.csv',dtype={'unit':str},float_precision='round_trip')
    ndvi=frame.loc[frame.variable=='ndvi'];pending=ndvi.quality_flag.eq('pending_export')
    assert len(frame)==12672 and len(ndvi)==4224 and ndvi.grid_row.notna().all() and ndvi.grid_col.notna().all()
    assert ndvi.loc[pending,'value'].isna().all() and ndvi.loc[pending,'valid_area_m2'].isna().all()
    assert ndvi.region_area_m2.notna().all()
    ingest([feb],out)
    fingerprint=json.loads((out/'metadata.json').read_text())['dataset_fingerprint']
    accepted=(out/'accepted_modis_observations.csv').read_bytes()
    ingest([jan],out)
    assert fingerprint==json.loads((out/'metadata.json').read_text())['dataset_fingerprint']
    assert accepted==(out/'accepted_modis_observations.csv').read_bytes()
    changed=fake_rows(catalog,['2003-01-01']);changed['configured_at_utc']='2026-11-15T01:00:00Z'
    conflict=tmp_path/'SYNTHETIC_CHANGED.csv';changed.to_csv(conflict,index=False)
    before={p.name:p.read_bytes() for p in out.iterdir() if p.is_file()}
    with pytest.raises(ValueError,match='Conflicting'):ingest([conflict],out)
    assert before=={p.name:p.read_bytes() for p in out.iterdir() if p.is_file()}
    report=ingest([conflict],out,replace=True)
    assert report['accepted_ndvi_rows']==32 and report['archived_source_files']==3
    assert (out/'gldas_monthly_timeseries.csv').read_bytes()==original_glDas
    assert (out/'source_manifest.json').read_bytes()==manifest_before
    updated=json.loads((out/'catalog.json').read_text())
    assert [(f['geometry'],f['properties']['bbox']) for f in updated['features']]==geometry_before
    sources=json.loads((out/'modis_source_manifest.json').read_text())
    for source in sources:
        path=Path(source['file']);assert path.name==source['sha256']+'.csv'
        assert hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256']
    ledger=pd.read_csv(out/'accepted_modis_observations.csv')
    assert set(ledger.source_file_sha256).issubset({s['sha256'] for s in sources})
    # Annual imports change availability, but the target export identity is stable.
    request=tmp_path/'fine_request.json';request.write_text(json.dumps({'tile_id':'central_us_1deg','catalog':str(out/'catalog.json')}))
    _,_,after_hash=load_request(request)
    (out/'catalog.json').write_text(json.dumps(catalog));_,_,before_hash=load_request(request)
    assert after_hash==before_hash


def test_full_month_index_and_exported_missing_values_stay_distinct(fine_release,tmp_path):
    out,catalog=fine_release
    dates=pd.date_range('2003-01-01','2024-12-01',freq='MS').strftime('%Y-%m-%d')
    rows=fake_rows(catalog,dates)
    rows.loc[len(rows)-1,['value','valid_area_m2','valid_area_fraction','quality_flag']]=[np.nan,0,0,'no_valid_pixels']
    source=tmp_path/'SYNTHETIC_COMPLETE_PROTOCOL.csv';rows.to_csv(source,index=False)
    report=ingest([source],out)
    assert report['accepted_ndvi_rows']==4224 and report['valid_ndvi_values']==4223 and report['pending_export_rows']==0
    updated=json.loads((out/'catalog.json').read_text())
    last=updated['features'][-1]['properties']
    assert last['ndvi_exported_months']==264 and last['ndvi_valid_months']==263
    assert last['ndvi_status']=='complete_with_missing' and last['data_status']=='incomplete_ndvi'
    assert all(f['properties']['ndvi_valid_months']==264 for f in updated['features'][:-1])
    quality=pd.read_csv(out/'quality_report.csv')
    assert quality.loc[quality.variable=='ndvi','missing_months'].sum()==1


def test_processing_method_upgrade_requires_complete_legacy_replacement(fine_release,tmp_path):
    out,catalog=fine_release
    jan=tmp_path/'SYNTHETIC_V2_JAN.csv';feb=tmp_path/'SYNTHETIC_V2_FEB.csv'
    fake_rows(catalog,['2003-01-01']).to_csv(jan,index=False)
    fake_rows(catalog,['2003-02-01']).to_csv(feb,index=False)
    ingest([jan,feb],out)
    ledger_path=out/'accepted_modis_observations.csv'
    old=pd.read_csv(ledger_path,dtype={'unit':str},float_precision='round_trip')
    old['area_method']='SYNTHETIC_LEGACY_ELLIPSOID_METHOD';old.to_csv(ledger_path,index=False)
    before=ledger_path.read_bytes()
    with pytest.raises(ValueError,match='Legacy fine area method'):
        ingest([jan,feb],out)
    with pytest.raises(ValueError,match='every previously accepted legacy'):
        ingest([jan],out,replace=True)
    assert ledger_path.read_bytes()==before
    report=ingest([jan,feb],out,replace=True)
    assert report['accepted_ndvi_rows']==32 and report['archived_source_files']==2
    updated=pd.read_csv(ledger_path)
    assert updated.area_method.eq(CALCULATION_VERSION).all()
    metadata=json.loads((out/'metadata.json').read_text())
    assert metadata['modis_calculation_version']==CALCULATION_VERSION
    assert metadata['ndvi']['area_method']==CALCULATION_VERSION


def test_range_boundary_accepts_single_float_rounding_step_only(fine_release):
    _,catalog=fine_release
    rows=fake_rows(catalog,['2003-01-01'])
    rows.loc[rows.index[0],'value']=np.nextafter(-.2,-np.inf)
    rows.loc[rows.index[1],'value']=np.nextafter(1.,np.inf)
    result=validate_frame(rows,catalog)
    assert result.loc[0,'value']==rows.loc[0,'value']
    bad=rows.copy();bad.loc[0,'value']=-.200001
    with pytest.raises(ValueError,match='scale/range mismatch'):validate_frame(bad,catalog)
