"""Bounded orchestration tests with synthetic protocol files and fake services."""
from pathlib import Path
import json
import hashlib
import pandas as pd
import pytest
import scripts.acquire_fine_tiles as mod
from src.fine_grid import build_tile_catalog


def registry(tmp_path,monkeypatch,tiles=None):
    monkeypatch.setattr(mod,'ROOT',tmp_path)
    tiles=tiles or [{'id':'test_1deg','name':'Synthetic test location','bbox':[-98,37,-97,38],
        'directory':'data/processed/fine/test'}]
    path=tmp_path/'tiles.json';path.write_text(json.dumps({'schema_version':'fine-tiles-1','tiles':tiles}))
    return path


def write_native(root,tile):
    directory=tile['directory'];directory.mkdir(parents=True,exist_ok=True)
    catalog=build_tile_catalog(tile['bbox'])
    for f in catalog['features']:f['properties'].update(tile_id=tile['id'],variables=['soil_water_0_10cm','soil_water_0_100cm'])
    (directory/'catalog.json').write_text(json.dumps(catalog))
    dates=pd.date_range('2003-01-01','2024-12-01',freq='MS').strftime('%Y-%m-%d')
    data=pd.DataFrame([{'date':date,'region_id':f['id'],'variable':v,'value':10.,'quality_flag':'coverage_review_required',
        'unit':'kg m-2','source':'GLDAS_NOAH025_M.2.1'} for f in catalog['features'] for date in dates
        for v in ['soil_water_0_10cm','soil_water_0_100cm']])
    data.to_csv(directory/'gldas_monthly_timeseries.csv',index=False);data.to_csv(directory/'monthly_timeseries.csv',index=False)
    (directory/'metadata.json').write_text('{"data_kind":"SYNTHETIC_PROTOCOL_TEST_ONLY"}')
    (directory/'source_manifest.json').write_text('[]')
    return catalog


def complete_release(directory):
    catalog=json.loads((directory/'catalog.json').read_text());dates=pd.date_range('2003-01-01','2024-12-01',freq='MS').strftime('%Y-%m-%d')
    ndvi=pd.DataFrame([{'date':date,'region_id':f['id'],'variable':'ndvi','value':.3,'quality_flag':'coverage_review_required',
        'unit':'1','source':'MOD13A3.061','area_method':mod.CALCULATION_VERSION} for f in catalog['features'] for date in dates])
    # Retained source QA gaps must not force another cloud download.
    ndvi.loc[0,['value','quality_flag']]=[float('nan'),'no_valid_pixels']
    gl=pd.read_csv(directory/'gldas_monthly_timeseries.csv',dtype={'unit':str})
    pd.concat([gl,ndvi],ignore_index=True).to_csv(directory/'monthly_timeseries.csv',index=False)
    hashes={'source_csv_sha256':hashlib.sha256((directory/'monthly_timeseries.csv').read_bytes()).hexdigest(),
        'source_catalog_sha256':hashlib.sha256((directory/'catalog.json').read_bytes()).hexdigest()}
    for name in ['screening.json','map_screening.geojson']:(directory/name).write_text(json.dumps(hashes))


def test_dryplan_never_processes_or_calls_cloud_and_validates_registry(tmp_path,monkeypatch):
    path=registry(tmp_path,monkeypatch)
    for name in ['process_native','fetch_sources','ingest','prepare']:
        monkeypatch.setattr(mod,name,lambda *a,**kw:pytest.fail('dry plan must have no side effects'))
    before={p for p in tmp_path.rglob('*')}
    result=mod.acquire(path,'SYNTHETIC_PROJECT')
    assert result['mode']=='dry_plan' and result['requires_fetch_tiles']==1
    assert result['tiles'][0]['native_cells']==16 and result['tiles'][0]['pilot_requests']==1
    assert {p for p in tmp_path.rglob('*')}==before
    with pytest.raises(ValueError,match='Unknown selected'):mod.load_tiles(path,['missing'])
    unsafe=registry(tmp_path,monkeypatch,[{'id':'escape','directory':'../escape','bbox':[-98,37,-97,38]}])
    with pytest.raises(ValueError,match='under data'):mod.load_tiles(unsafe)


def test_complete_release_is_reused_including_actual_QA_gaps(tmp_path,monkeypatch):
    path=registry(tmp_path,monkeypatch);tile=mod.load_tiles(path)[0]
    write_native(tmp_path,tile);complete_release(tile['directory'])
    monkeypatch.setattr(mod,'fetch_sources',lambda *a,**kw:pytest.fail('complete received release must not fetch again'))
    monkeypatch.setattr(mod,'process_native',lambda *a,**kw:pytest.fail('complete native input must not be overwritten'))
    monkeypatch.setattr(mod,'audit',lambda directory:{'integrity_passed':True,'passed_checks':99})
    result=mod.acquire(path,'SYNTHETIC_PROJECT',fetch_requested=True,ee_client=object())
    assert result['ready_tiles']==1 and result['tiles'][0]['action']=='reused_complete_release'
    assert result['tiles'][0]['stage']=='ready_with_source_QA_gaps' and result['tiles'][0]['ndvi_qa_gaps']==1


def test_pilot_precedes_annuals_zero_valid_winter_allowed_then_annual_only_import(tmp_path,monkeypatch):
    path=registry(tmp_path,monkeypatch);tile=mod.load_tiles(path)[0];catalog=write_native(tmp_path,tile)
    calls=[]
    monkeypatch.setattr(mod,'process_native',lambda *a,**kw:pytest.fail('reuse initializedGLDAS'))
    monkeypatch.setattr(mod,'load_request',lambda path:({'tile_id':tile['id']},catalog,'SYNTHETIC_TARGET'))
    def fetch(ee,project,request,catalog,digest,plan,cache):
        calls.append(('fetch',len(plan)))
        return {'files':[{'path':str(tmp_path/('pilot.csv' if len(plan)==1 else str(i)+'.csv')),
                          'rows':16 if len(plan)==1 else 192,'finite_values':0 if len(plan)==1 else 192} for i in range(len(plan))]}
    monkeypatch.setattr(mod,'fetch_sources',fetch)
    monkeypatch.setattr(mod,'validate',lambda path,catalog,expected_month:calls.append(('pilot_validate',expected_month)))
    def ingest(paths,directory,replace=False):
        calls.append(('ingest',len(paths)));assert all('pilot' not in Path(p).name for p in paths)
        complete_release(directory);return {'source_files':len(paths)}
    monkeypatch.setattr(mod,'ingest',ingest)
    monkeypatch.setattr(mod,'prepare',lambda directory:calls.append(('prepare',)) or {'cells':16})
    monkeypatch.setattr(mod,'audit',lambda directory:{'integrity_passed':True})
    result=mod.acquire(path,'SYNTHETIC_PROJECT',fetch_requested=True,ee_client=object())
    assert calls==[('fetch',1),('pilot_validate','2003-01-01'),('fetch',22),('ingest',22),('prepare',)]
    assert result['ready_tiles']==1 and result['tiles'][0]['pilot_finite_rows']==0
    assert (tile['directory']/'release_audit.json').exists()


def test_partial_native_release_requires_explicit_repair(tmp_path,monkeypatch):
    path=registry(tmp_path,monkeypatch);tile=mod.load_tiles(path)[0]
    tile['directory'].mkdir(parents=True);(tile['directory']/'catalog.json').write_text('{}')
    monkeypatch.setattr(mod,'process_native',lambda *a,**kw:pytest.fail('neveroverwritepartialrelease'))
    with pytest.raises(ValueError,match='explicit repair'):
        mod.acquire(path,'SYNTHETIC_PROJECT',fetch_requested=True,ee_client=object())



def test_reprocessing_requires_explicit_replace_and_ready_reuse_requires_integrity(tmp_path,monkeypatch):
    path=registry(tmp_path,monkeypatch);tile=mod.load_tiles(path)[0]
    write_native(tmp_path,tile);complete_release(tile['directory'])
    with pytest.raises(ValueError,match='explicit --replace'):
        mod.acquire(path,'SYNTHETIC_PROJECT',fetch_requested=True,reprocess=True)
    monkeypatch.setattr(mod,'audit',lambda directory:{'integrity_passed':False,'errors':['SYNTHETIC_CORRUPTION']})
    monkeypatch.setattr(mod,'fetch_sources',lambda *a,**kw:pytest.fail('corruption must not trigger cloud replacement'))
    with pytest.raises(ValueError,match='failed integrity audit'):
        mod.acquire(path,'SYNTHETIC_PROJECT',fetch_requested=True,ee_client=object())
    frame=pd.read_csv(tile['directory']/'monthly_timeseries.csv')
    frame=frame.drop(columns='area_method');frame.to_csv(tile['directory']/'monthly_timeseries.csv',index=False)
    assert mod.readiness(tile)['needs_processing_correction']
    with pytest.raises(ValueError,match='--reprocess --replace'):
        mod.acquire(path,'SYNTHETIC_PROJECT',fetch_requested=True,ee_client=object())


def test_explicit_audit_deferral_never_claims_pass_or_performs_heavy_audit(tmp_path,monkeypatch):
    path=registry(tmp_path,monkeypatch);tile=mod.load_tiles(path)[0]
    write_native(tmp_path,tile);complete_release(tile['directory'])
    monkeypatch.setattr(mod,'audit',lambda directory:pytest.fail('audit was explicitly deferred'))
    result=mod.acquire(path,'SYNTHETIC_PROJECT',fetch_requested=True,ee_client=object(),audit_required=False)
    assert result['tiles'][0]['release_audit_status']=='deferred_for_demo'
    assert result['tiles'][0]['audit_passed_checks'] is None
    assert not (tile['directory']/'release_audit.json').exists()
