import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from src.regions import make_grid, RADIUS_M

ROOT=Path(__file__).resolve().parents[1]
# Known native-grid transform; synthetic observations below are still invented.
NATIVE_TRANSFORM = ('PARAM_MT["Affine", PARAMETER["elt_0_0", 926.625433055833], '
                    'PARAMETER["elt_0_2", -20015109.354], '
                    'PARAMETER["elt_1_1", -926.6254330558334], '
                    'PARAMETER["elt_1_2", 10007554.677003]]')
def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod


def test_grid_exhausts_sphere_with_unique_ids():
    grid=make_grid()['features']
    assert len(grid)==648 and len({f['id'] for f in grid})==648
    assert grid[0]['properties']['bbox']==[-180,-90,-170,-80]
    assert grid[-1]['properties']['bbox']==[170,80,180,90]
    assert sum(f['properties']['region_area_m2'] for f in grid)==pytest.approx(4*np.pi*RADIUS_M**2)
    # Adjacent bounds touch with no longitudinal or latitudinal overlap.
    for r in range(18):
        row=grid[r*36:(r+1)*36]
        assert all(a['properties']['bbox'][2]==b['properties']['bbox'][0] for a,b in zip(row,row[1:]))


def test_gldas_partition_reconciles_global_weighted_mean_and_masks():
    mod=load('process_regional_gldas')
    lat=np.arange(600)*.25-59.875
    values=np.broadcast_to(np.linspace(10,40,600)[:,None],(600,1440)).copy()
    values[200:240,400:440]=np.nan
    means,areas,negative=mod.regional_sums(values,lat)
    weights=RADIUS_M**2*np.deg2rad(.25)*(np.sin(np.deg2rad(lat+.125))-np.sin(np.deg2rad(lat-.125)))[:,None]
    valid=np.isfinite(values)
    expected=np.sum(np.where(valid,values,0)*weights)/np.sum(valid*weights)
    assert np.nansum(means*areas)/sum(areas)==pytest.approx(expected,rel=1e-13)
    assert np.isnan(means[:108]).all()
    assert np.isfinite(means).sum()==539
    assert not negative.any()
    values[0,0]=-1
    assert mod.regional_sums(values,lat)[2][108]


def test_modis_rejects_global_exports_and_duplicate_months():
    mod=load('merge_regional_timeseries')
    with pytest.raises(ValueError,match='Missing columns'):
        mod.validate_modis(pd.DataFrame({'region_id':['whole_earth']}))
    props=make_grid()['features'][300]['properties']
    row={'date':'2003-01-01','region_id':props['region_id'],'variable':'ndvi','value':.3,'unit':'1','source':'MOD13A3.061',
         'valid_area_fraction':.5,'valid_area_m2':props['region_area_m2']*.5,'region_area_m2':props['region_area_m2'],
         'quality_flag':'coverage_review_required','source_image_count':1,'source_asset_id':'MODIS/061/MOD13A3/2003_01_01',
         'source_time_start':'2003-01-01','source_crs':'SR-ORG:6974','source_transform':NATIVE_TRANSFORM,
         'qa_rule':'raw NDVI [-2000,10000]; (DetailedQA & 3)==0; SummaryQA==0','configured_at_utc':'2026-11-14T00:00:00Z'}
    assert mod.validate_modis(pd.DataFrame([row])).value.iloc[0]==.3
    with pytest.raises(ValueError,match='Duplicate'):
        mod.validate_modis(pd.DataFrame([row,row]))
    with pytest.raises(ValueError,match='scale/range'):
        mod.validate_modis(pd.DataFrame([{**row,'value':3000}]))
    with pytest.raises(ValueError,match='Source time'):
        mod.validate_modis(pd.DataFrame([{**row,'source_time_start':'2003-02-01'}]))

    for changes in ({'source_image_count':np.nan},{'configured_at_utc':'yesterday'},
                    {'date':'2003-01-01T01:00:00'},{'value':np.nan,'valid_area_m2':-1},
                    {'qa_rule':'QA omitted'},{'value':np.nan,'quality_flag':'missing'},
                    {'source_transform':NATIVE_TRANSFORM.replace('926.625433','1926.625433')},
                    {'source_asset_id':'MODIS/061/MOD13A3/2003_02_01'}):
        with pytest.raises(ValueError):
            mod.validate_modis(pd.DataFrame([{**row,**changes}]))


def synthetic_modis_rows(dates):
    """Synthetic protocol fixtures only; never written into repository NASA data."""
    p=make_grid()['features'][300]['properties']
    return pd.DataFrame([{'date':date,'region_id':p['region_id'],'variable':'ndvi','value':.3,
        'unit':'1','source':'MOD13A3.061','valid_area_fraction':.5,
        'valid_area_m2':p['region_area_m2']*.5,'region_area_m2':p['region_area_m2'],
        'quality_flag':'coverage_review_required','source_image_count':1,
        'source_asset_id':'MODIS/061/MOD13A3/'+date.replace('-','_'),
        'source_time_start':date,'source_crs':'SR-ORG:6974','source_transform':NATIVE_TRANSFORM,
        'qa_rule':'raw NDVI [-2000,10000]; (DetailedQA & 3)==0; SummaryQA==0',
        'configured_at_utc':'2026-11-14T00:00:00Z'} for date in dates])


def test_readonly_audit_and_import_roundtrip_preserve_months_and_status(tmp_path):
    """Entirely synthetic files under pytest temp storage; no NASA values implied."""
    import hashlib
    import json
    mod=load('merge_regional_timeseries')
    out=tmp_path/'SYNTHETIC_TEST_OUTPUT';out.mkdir()
    grid=make_grid();feature=grid['features'][300]
    feature['properties'].update(data_status='pending_ndvi',variables=['soil_water_0_10cm','soil_water_0_100cm'])
    grid['features']=[feature]
    (out/'catalog.json').write_text(json.dumps(grid))
    (out/'metadata.json').write_text(json.dumps({'status':'SYNTHETIC_TEST_FIXTURE_ONLY'}))
    (out/'source_manifest.json').write_text('[]')
    dates=pd.date_range('2003-01-01','2024-12-01',freq='MS').strftime('%Y-%m-%d')
    # Names/units exercise the protocol, but all measurements are invented fixture values.
    gldas=pd.DataFrame([{'date':date,'value':10.,'unit':'kg m-2','source':'SYNTHETIC_TEST',
        'variable':var,'region_id':feature['id'],'quality_flag':'coverage_review_required',
        'valid_area_fraction':.5,'valid_area_m2':feature['properties']['region_area_m2']*.5,
        'region_area_m2':feature['properties']['region_area_m2']}
        for date in dates for var in ('soil_water_0_10cm','soil_water_0_100cm')])
    gldas.to_csv(out/'gldas_monthly_timeseries.csv',index=False)
    original_gldas_bytes=(out/'gldas_monthly_timeseries.csv').read_bytes()
    gldas.to_csv(out/'monthly_timeseries.csv',index=False)
    first=tmp_path/'synthetic_jan.csv';second=tmp_path/'synthetic_feb.csv'
    synthetic_modis_rows(dates[:1]).to_csv(first,index=False)
    synthetic_modis_rows(dates[1:2]).to_csv(second,index=False)
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
    audit=mod.audit_exports([first])
    assert audit['rows']==1 and not audit['all_exported_months_cover_full_grid']
    assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
    mod.main([first],out)
    frame=pd.read_csv(out/'monthly_timeseries.csv')
    ndvi=frame.loc[frame.variable=='ndvi']
    assert len(ndvi)==264 and ndvi.value.notna().sum()==1
    assert ndvi.region_area_m2.notna().all() and ndvi.region_area_m2.gt(0).all()
    assert ndvi.loc[ndvi.quality_flag=='pending_export','valid_area_m2'].isna().all()
    assert ndvi.quality_flag.eq('pending_export').sum()==263
    assert json.loads((out/'catalog.json').read_text())['features'][0]['properties']['ndvi_status']=='partial'
    mod.main([second],out)
    saved=(out/'monthly_timeseries.csv').read_bytes()
    # Replaying either file is idempotent; a source-provenance change is explicit.
    mod.main([first,second],out)
    assert (out/'monthly_timeseries.csv').read_bytes()==saved
    changed=synthetic_modis_rows(dates[:1]);changed['value']=.4
    conflicting=tmp_path/'synthetic_changed.csv';changed.to_csv(conflicting,index=False)
    with pytest.raises(ValueError,match='Conflicting regional'):
        mod.main([conflicting],out)
    assert (out/'monthly_timeseries.csv').read_bytes()==saved
    changed['value']=.3;changed['configured_at_utc']='2026-11-14T01:00:00Z';changed.to_csv(conflicting,index=False)
    with pytest.raises(ValueError,match='Conflicting regional'):
        mod.main([conflicting],out)
    mod.main([conflicting],out,replace=True)
    assert pd.read_csv(out/'monthly_timeseries.csv').query("variable=='ndvi'").value.notna().sum()==2
    archived=json.loads((out/'modis_source_manifest.json').read_text())
    assert len(archived)==3
    for source in archived:
        path=Path(source['file'])
        assert path.name==source['sha256']+'.csv'
        assert hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256']
    # Restore original provenance before testing the complete annual union.
    mod.main([first],out,replace=True)
    assert pd.read_csv(out/'monthly_timeseries.csv').query("variable=='ndvi'").value.notna().sum()==2
    full=synthetic_modis_rows(dates)
    full.loc[263,['value','valid_area_m2','valid_area_fraction','quality_flag']]=[np.nan,0,0,'no_valid_pixels']
    complete=tmp_path/'synthetic_complete.csv';full.to_csv(complete,index=False)
    mod.main([complete],out)
    p=json.loads((out/'catalog.json').read_text())['features'][0]['properties']
    assert p['ndvi_exported_months']==264 and p['ndvi_valid_months']==263
    assert p['ndvi_status']=='complete_with_missing' and p['data_status']=='incomplete_ndvi'
    report=pd.read_csv(out/'quality_report.csv').query("variable=='ndvi'").iloc[0]
    assert report.valid_months==263 and report.missing_months==1
    full.loc[:,['value','valid_area_m2','valid_area_fraction','quality_flag']]=[np.nan,0,0,'no_valid_pixels']
    full.to_csv(complete,index=False);mod.main([complete],out,replace=True)
    p=json.loads((out/'catalog.json').read_text())['features'][0]['properties']
    assert p['ndvi_status']=='no_valid_observations' and p['data_status']=='unavailable_ndvi'
    # Explicit replacement changes matching rows and preserves unrelated accepted dates.
    mod.main([first],out,replace=True)
    frame=pd.read_csv(out/'monthly_timeseries.csv').query("variable=='ndvi'")
    assert frame.value.notna().sum()==1 and frame.quality_flag.eq('pending_export').sum()==0
    assert (out/'gldas_monthly_timeseries.csv').read_bytes()==original_gldas_bytes
    first_archive=next(r for r in json.loads((out/'modis_source_manifest.json').read_text()) if r['sha256']==hashlib.sha256(first.read_bytes()).hexdigest())
    Path(first_archive['file']).write_bytes(b'SYNTHETIC_CORRUPTION')
    accepted_before=(out/'accepted_modis_observations.csv').read_bytes()
    with pytest.raises(ValueError,match='archive hash mismatch'):
        mod.main([first],out)
    assert (out/'accepted_modis_observations.csv').read_bytes()==accepted_before


def test_missing_image_cannot_claim_coverage_or_source_provenance():
    mod=load('merge_regional_timeseries')
    row=synthetic_modis_rows(['2003-01-01'])
    for column in ['value','valid_area_m2','valid_area_fraction','source_asset_id',
                   'source_time_start','source_crs','source_transform']:
        row[column]=np.nan
    row['source_image_count']=0;row['quality_flag']='missing'
    assert len(mod.validate_modis(row))==1
    corrupt=row.copy();corrupt['valid_area_m2']=0;corrupt['valid_area_fraction']=0
    with pytest.raises(ValueError,match='missing values and areas'):
        mod.validate_modis(corrupt)
    corrupt=row.copy();corrupt['source_asset_id']='MODIS/061/MOD13A3/2003_01_01'
    with pytest.raises(ValueError,match='cannot claim source'):
        mod.validate_modis(corrupt)



def test_crossfile_identical_rows_are_idempotent_but_changed_overlap_is_explicit(tmp_path):
    mod=load('merge_regional_timeseries')
    a=tmp_path/'synthetic_pilot.csv';b=tmp_path/'synthetic_annual_overlap.csv'
    rows=synthetic_modis_rows(['2003-01-01']);rows.to_csv(a,index=False);rows.to_csv(b,index=False)
    combined,_=mod.read_exports([a,b])
    assert len(combined)==1
    rows['configured_at_utc']='2026-11-15T00:00:00Z';rows.to_csv(b,index=False)
    with pytest.raises(ValueError,match='Conflicting'):
        mod.read_exports([a,b])
    combined,_=mod.read_exports([a,b],replace=True)
    assert combined.configured_at_utc.iloc[0]=='2026-11-15T00:00:00Z'


def test_python_exporter_dryplan_has_no_cloud_side_effects_and_submits_explicit_plan(tmp_path,monkeypatch,capsys):
    import json
    from types import SimpleNamespace
    mod=load('export_regional_modis_earth_engine')
    assert len(mod.export_plan('years'))==22
    assert len(mod.export_grid())==648 and len(mod.export_grid(nonpolar=True))==576
    assert all(f['properties']['bbox'][1]>-90 and f['properties']['bbox'][3]<90 for f in mod.export_grid(True))
    assert mod.export_plan('month',month='2024-12-01')[0]['end']=='2025-01-01'
    for invalid in ['2003-01-02','2002-12-01','2024-2-01']:
        with pytest.raises(ValueError): mod.export_plan('month',month=invalid)
    monkeypatch.setattr(mod,'submit_plan',lambda *a:pytest.fail('dry plan must not submit'))
    mod.main(['--project','SYNTHETIC_TEST_PROJECT','--mode','pilot'])
    assert json.loads(capsys.readouterr().out)['mode']=='dry_plan'
    # Reload to restore submit_plan, then use a bounded in-memory fake EE client.
    mod=load('export_regional_modis_earth_engine')
    calls=[]
    class Task:
        id='SYNTHETIC_TEST_TASK_ID'
        def start(self): calls.append('start')
    def export(**kwargs):
        calls.append(kwargs)
        return Task()
    fake=SimpleNamespace(Initialize=lambda **kw:calls.append(kw),batch=SimpleNamespace(
        Export=SimpleNamespace(table=SimpleNamespace(toDrive=export))))
    monkeypatch.setattr(mod,'build_collection',lambda *args:'SYNTHETIC_TEST_GRAPH')
    path=tmp_path/'tasks.json'
    result=mod.submit_plan(fake,'SYNTHETIC_TEST_PROJECT',mod.export_plan(),path)
    assert calls[0]=={'project':'SYNTHETIC_TEST_PROJECT'}
    assert calls[1]['selectors']==mod.COLUMNS and calls[1]['fileFormat']=='CSV'
    assert calls[1]['collection']=='SYNTHETIC_TEST_GRAPH' and calls[2]=='start'
    assert result[0]['task_id']=='SYNTHETIC_TEST_TASK_ID'
    assert json.loads(path.read_text())==result
    with pytest.raises(ValueError,match='already recorded'):
        mod.submit_plan(fake,'SYNTHETIC_TEST_PROJECT',mod.export_plan(),path)
    fake.data=SimpleNamespace(getTaskStatus=lambda ids:[{'id':i,'state':'COMPLETED'} for i in ids])
    previous_starts=calls.count('start')
    assert mod.poll_status(fake,'SYNTHETIC_TEST_PROJECT',path)[0]['status']=='COMPLETED'
    assert calls.count('start')==previous_starts
    with pytest.raises(ValueError,match='already recorded'):
        mod.submit_plan(fake,'SYNTHETIC_TEST_PROJECT',mod.export_plan(),path)
    mod.submit_plan(fake,'SYNTHETIC_TEST_PROJECT',mod.export_plan(),path,force=True)
    assert calls.count('start')==previous_starts+1



def test_release_audit_is_readonly_and_detects_source_and_unit_tampering(tmp_path):
    """Tiny synthetic release exercises integrity checks without NASA source claims."""
    import hashlib
    import json
    mod=load('audit_regional_release')
    out=tmp_path/'synthetic_release';out.mkdir()
    feature=make_grid()['features'][300];rid=feature['id'];p=feature['properties']
    p.update(data_status='pending_ndvi',variables=['soil_water_0_10cm','soil_water_0_100cm'],
        gldas_valid_months={'soil_water_0_10cm':264,'soil_water_0_100cm':264})
    (out/'catalog.json').write_text(json.dumps({'type':'FeatureCollection','features':[feature]}))
    (out/'metadata.json').write_text(json.dumps({'status':'SYNTHETIC_TEST_ONLY'}))
    dates=pd.date_range('2003-01-01','2024-12-01',freq='MS').strftime('%Y-%m-%d')
    rows=pd.DataFrame([{'date':date,'value':10.,'unit':'kg m-2','variable':var,'source':'GLDAS_NOAH025_M.2.1',
        'region_id':rid,'quality_flag':'coverage_review_required','region_area_m2':p['region_area_m2'],
        'valid_area_m2':p['region_area_m2']*.5,'valid_area_fraction':.5}
        for date in dates for var in p['variables']])
    rows.to_csv(out/'gldas_monthly_timeseries.csv',index=False);rows.to_csv(out/'monthly_timeseries.csv',index=False)
    quality=rows.groupby(['region_id','variable']).value.agg(expected_months='size',valid_months='count')
    quality['missing_months']=0;quality.to_csv(out/'quality_report.csv')
    sources=[]
    for i,date in enumerate(dates):
        path=out/f'synthetic_source_{i}.txt';path.write_text('SYNTHETIC_TEST_NOT_NETCDF')
        sources.append({'file':str(path),'date':date,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (out/'source_manifest.json').write_text(json.dumps(sources))
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
    report=mod.audit(out,root=tmp_path,expected_grid=1,expected_supported=1)
    assert report['integrity_passed'] and not report['full_required_period_complete']
    assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
    Path(sources[0]['file']).write_text('SYNTHETIC_TAMPERING')
    assert not mod.audit(out,root=tmp_path,expected_grid=1,expected_supported=1)['integrity_passed']
    rows['unit']='m3 m-3';rows.to_csv(out/'monthly_timeseries.csv',index=False)
    report=mod.audit(out,root=tmp_path,expected_grid=1,expected_supported=1)
    assert any('units and source' in e for e in report['errors'])



def test_drive_sync_pagination_names_checksums_idempotency_and_immutable_versions(tmp_path,monkeypatch):
    import hashlib
    import json
    mod=load('sync_regional_modis_drive')
    contents={'id_a':b'SYNTHETIC_CSV_A','id_b':b'SYNTHETIC_CSV_B'}
    downloads=[]
    class Response:
        def __init__(self,data=None,content=None):self.data=data;self.content=content
        def raise_for_status(self):pass
        def json(self):return self.data
        def iter_content(self,chunk_size):yield self.content[:3];yield b'';yield self.content[3:]
    def item(fid,year):
        content=contents[fid]
        return {'id':fid,'name':f'mod13a3_grid10_{year}_nonpolar.csv','size':str(len(content)),
            'md5Checksum':hashlib.md5(content).hexdigest(),'version':'1','modifiedTime':'2026-11-15T00:00:00Z'}
    class Session:
        def get(self,url,params,**kwargs):
            if params.get('alt')=='media':
                fid=url.rsplit('/',1)[-1];downloads.append(fid);return Response(content=contents[fid])
            query=params['q']
            if "name = 'NASA_member_B_regional'" in query:
                if not params.get('pageToken'):return Response({'files':[{'id':'folder_a'}],'nextPageToken':'folder_page2'})
                assert params['pageToken']=='folder_page2';return Response({'files':[{'id':'folder_b'}]})
            if "'folder_a' in parents" in query:
                if not params.get('pageToken'):
                    return Response({'files':[item('id_a',2003),{'id':'pilot','name':'mod13a3_grid10_pilot_2003_01_nonpolar.csv'}],'nextPageToken':'file_page2'})
                return Response({'files':[{'id':'global','name':'mod13a3_whole_earth_2004.csv'},{'id':'old','name':'mod13a3_grid10_2002_nonpolar.csv'}]})
            assert "'folder_b' in parents" in query
            return Response({'files':[item('id_a',2003),item('id_b',2004)]})
    cache=tmp_path/'cache';session=Session()
    listed=mod.sync(session,cache,list_only=True)
    assert listed['matching_annual_files']==2 and not cache.exists() and not downloads
    first=mod.sync(session,cache)
    assert downloads==['id_a','id_b'] and all(f['downloaded'] for f in first['files'])
    old_paths=[Path(f['path']) for f in first['files']]
    repeated=mod.sync(session,cache)
    assert downloads==['id_a','id_b'] and not any(f['downloaded'] for f in repeated['files'])
    contents['id_a']=b'SYNTHETIC_CHANGED_CONTENT'
    changed=mod.sync(session,cache)
    assert downloads==['id_a','id_b','id_a'] and changed['files'][0]['path']!=str(old_paths[0])
    assert old_paths[0].read_bytes()==b'SYNTHETIC_CSV_A'
    history=json.loads((cache/'manifest.json').read_text())['history']
    assert len(history)==3 and all(Path(r['path']).is_file() for r in history)
    # A valid download does not bypass explicit source validation and import scope.
    called=[]
    monkeypatch.setattr(mod,'validate_annual',lambda path,year:called.append(('validate',year)) or {'year':year})
    monkeypatch.setattr(mod,'ingest_exports',lambda paths,out,replace:called.append(('ingest',len(paths),replace)))
    ingested=mod.sync(session,cache,ingest=True,out=tmp_path/'release')
    assert ingested['ingested'] and called==[('validate',2003),('validate',2004),('ingest',2,False)]


def test_drive_download_hash_failure_and_duplicate_names_need_explicit_ids(tmp_path,monkeypatch):
    import hashlib
    mod=load('sync_regional_modis_drive')
    class Response:
        def raise_for_status(self):pass
        def iter_content(self,chunk_size):yield b'SYNTHETIC_BYTES'
    class Session:
        def get(self,*a,**kw):return Response()
    item={'id':'a','name':'mod13a3_grid10_2003_nonpolar.csv','year':2003,'size':15,'md5Checksum':'bad'}
    with pytest.raises(ValueError,match='size mismatch|MD5 mismatch'):
        mod.download_file(Session(),item,tmp_path/'bad_cache')
    assert not list((tmp_path/'bad_cache').glob('*.csv')) and not list((tmp_path/'bad_cache').glob('*.part'))
    candidates=[{**item,'id':fid} for fid in ['a','b']]
    monkeypatch.setattr(mod,'discover_annuals',lambda session,file_ids=None:candidates)
    def fake_download(session,item,cache,previous):
        path=Path(cache)/(item['id']+'.csv');path.parent.mkdir(parents=True,exist_ok=True);path.write_text('SYNTHETIC_'+item['id'])
        return {'drive_id':item['id'],'name':item['name'],'year':2003,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'path':str(path)},True
    monkeypatch.setattr(mod,'download_file',fake_download)
    monkeypatch.setattr(mod,'ingest_exports',lambda *a,**kw:pytest.fail('ambiguous files must not import'))
    with pytest.raises(ValueError,match='Different Drive files'):
        mod.sync(Session(),tmp_path/'duplicates',ingest=True)
