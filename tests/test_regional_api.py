"""Offline route and localhost HTTP boundary checks; provider calls are mocked."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from threading import Thread
import time

import pandas as pd
import pytest
import requests

import src.regional_api as module
from src.regional_api import RegionalAPI,make_server
from src.regional_research import research_context_key

ID='grid_r14_c07'
SETTINGS={key:'secret-value-'+key for key in module.SETTINGS}


def bundle():
    return {'region_id':ID,'screening_status':'current','feature':{'type':'Feature','geometry':None,
        'properties':{'region_id':ID}},'observations':pd.DataFrame(), 'provenance':{},'screening':None,
        'research_context':{'region_id':ID,'bbox':[-110,50,-100,60],'dataset_version':'release',
        'period':['2003-01-01','2024-12-31'],'jurisdictions':[{'name':'Canada','land_area_fraction':1}]}}


class Jobs:
    def __init__(self):
        self.calls=[]
    def submit(self,data,**kwargs):
        self.calls.append((deepcopy(data),kwargs))
        return {'request_id':'a'*32,'region_id':ID,'context_key':research_context_key(data['research_context']),
                'state':'queued','report':None,'error_code':None}
    def poll(self,request_id,**kwargs):
        return {'request_id':request_id,'state':'loading','report':None}
    def close(self,**kwargs):
        pass


@pytest.fixture
def api(monkeypatch,tmp_path):
    monkeypatch.setattr(module,'load_region',lambda *a,**k:bundle())
    monkeypatch.setattr(module,'build_region_detail',lambda data:{'region_id':data['region_id'],'paired_analysis':None,
        'available_indicator_analysis':{'variables':['soil_water_0_100cm']},'annual_fits':{'soil_water_0_100cm':{}}})
    service=RegionalAPI(directory=tmp_path,cache_dir=tmp_path/'cache',report_dir=tmp_path/'reports',
                        settings=SETTINGS,live_enabled=True,jobs=Jobs(),fine_directory=tmp_path/"fine")
    yield service
    service.close()


def test_reads_are_offline_and_detail_uses_science_transport(api):
    status,health=api.handle('GET','/health')
    assert status==200 and all(health['configured'].values())
    assert not any(value in str(health) for value in SETTINGS.values())
    status,detail=api.handle('GET',f'/api/v1/regions/{ID}')
    assert status==200 and detail['paired_analysis'] is None
    assert detail['available_indicator_analysis']['variables']==['soil_water_0_100cm']
    assert 'annual_fits' in detail
    assert detail['research']['can_start_live']
    assert detail['research']['jurisdictions'][0]['official_domains']==['canada.ca','gc.ca']
    assert api.jobs.calls==[]
    assert api.handle('GET','/api/v1/regions/grid_r99_c00')[0]==404
    assert api.handle('GET','/api/v1/regions/demo-region')[0]==404


def test_live_post_accepts_only_empty_json_and_keeps_settings_server_side(api):
    route=f'/api/v1/regions/{ID}/research'
    for body in (None,[],{'MODEL_API_KEY':'client-key'},{'provider_url':'https://attacker.example'}):
        assert api.handle('POST',route,body)[0]==400
    status,request=api.handle('POST',route,{})
    assert status==202 and len(api.jobs.calls)==1
    assert 'poll_url' in request
    assert not any(value in str(request) for value in SETTINGS.values())
    assert api.jobs.calls[0][1]['environ']==SETTINGS
    assert api.handle('GET',request['poll_url'])[0]==200
    assert api.handle('GET',request['poll_url'].replace(request['context_key'],'stale'))[0]==409
    assert api.handle('GET','/api/v1/jobs/'+'a'*32)[0]==400


def test_live_disabled_unconfigured_or_full_queue(api,monkeypatch):
    route=f'/api/v1/regions/{ID}/research'
    api.live_enabled=False
    assert api.handle('POST',route,{})[0]==403
    api.live_enabled=True
    api._settings={}
    assert api.handle('POST',route,{})[0]==503
    api._settings=SETTINGS
    def full(*a,**kwargs):
        raise RuntimeError('private-provider-message')
    monkeypatch.setattr(api.jobs,'submit',full)
    status,result=api.handle('POST',route,{})
    assert status==429 and 'private-provider' not in str(result)


def test_cached_read_uses_current_numerical_payload_without_network(api,monkeypatch):
    calls=[]
    def load(path,analysis,context,**kwargs):
        calls.append((path,analysis,context))
        return {'status':'cached','verification_status':'machine_generated_unreviewed','limitations':[]}
    monkeypatch.setattr(module,'load_cached_report',load)
    status,report=api.handle('GET',f'/api/v1/regions/{ID}/research/cached')
    assert status==200 and report['status']=='cached'
    assert len(calls)==1 and calls[0][1]['region']==ID
    assert report['limitations']
    assert api.jobs.calls==[]
    monkeypatch.setattr(module,'load_cached_report',lambda *a,**k:(_ for _ in ()).throw(ValueError('privatepath')))
    status,result=api.handle('GET',f'/api/v1/regions/{ID}/research/cached')
    assert status==404 and 'privatepath' not in str(result)


def test_stale_release_and_map_source_hashes(api,monkeypatch):
    data=bundle()
    data['screening_status']='stale_rebuild_required'
    monkeypatch.setattr(module,'load_region',lambda *a,**k:deepcopy(data))
    assert api.handle('GET',f'/api/v1/regions/{ID}')[0]==409
    data['screening_status']='current'
    for name in ('monthly_timeseries.csv','catalog.json'):
        (api.directory/name).write_text('actual-source')
    h=hashlib.sha256(b'actual-source').hexdigest()
    payload={'type':'FeatureCollection','features':[],'source_csv_sha256':h,'source_catalog_sha256':h}
    path=api.directory/'map_screening.geojson'
    path.write_text(json.dumps(payload))
    assert api.handle('GET','/api/v1/regions')[0]==200
    (api.directory/'monthly_timeseries.csv').write_text('new-source')
    assert api.handle('GET','/api/v1/regions')[0]==409


def test_exact_cors_host_json_and_preflight_over_real_local_http(api):
    server=make_server(api,port=0)
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        result=requests.get(base+'/health',headers={'Origin':'http://localhost:3000'},timeout=2)
        assert result.status_code==200
        assert result.headers['Access-Control-Allow-Origin']=='http://localhost:3000'
        for origin in ('https://localhost:3000','http://evil.example','http://localhost:3000.evil.example'):
            result=requests.get(base+'/health',headers={'Origin':origin},timeout=2)
            assert result.status_code==403 and 'Access-Control-Allow-Origin' not in result.headers
        assert requests.get(base+'/health',headers={'Host':'evil.example'},timeout=2).status_code==403
        preflight=requests.options(base+'/api/v1/regions',headers={'Origin':'http://127.0.0.1:3000'},timeout=2)
        assert preflight.status_code==200
        assert preflight.headers['Access-Control-Allow-Methods']=='GET, POST, OPTIONS'
        form=requests.post(base+f'/api/v1/regions/{ID}/research',data='{}',timeout=2)
        assert form.status_code==400 and api.jobs.calls==[]
        post=requests.post(base+f'/api/v1/regions/{ID}/research',json={},
                           headers={'Origin':'http://127.0.0.1:3000'},timeout=2)
        assert post.status_code==202 and len(api.jobs.calls)==1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_non_loopback_bind_rejected():
    with pytest.raises(ValueError):
        make_server(host='0.0.0.0')


def test_cached_numeric_refresh_keeps_long_diagnostic_when_pair_is_insufficient(api,monkeypatch):
    data=bundle()
    data['screening']={
        'analysis':{'region':ID,'variables':['ndvi','soil_water_0_100cm'],'data_quality':{'common_years':[]}},
        'available_indicator_analysis':{'region':ID,'variables':['soil_water_0_100cm'],
                                        'observation_period':{'start':'2003-01-01','end':'2024-12-31'}}}
    monkeypatch.setattr(module,'load_region',lambda *a,**k:deepcopy(data))
    def cached(path,analysis,context,**kwargs):
        assert analysis['variables']==['soil_water_0_100cm']
        assert analysis['observation_period']['start']=='2003-01-01'
        return {'status':'cached','quantitative_analysis':analysis,'limitations':[]}
    monkeypatch.setattr(module,'load_cached_report',cached)
    status,report=api.handle('GET',f'/api/v1/regions/{ID}/research/cached')
    assert status==200
    assert report['quantitative_analysis']['variables']==['soil_water_0_100cm']


def test_api_cache_permits_only_numeric_revision_reuse(api,monkeypatch):
    calls=[]
    def cached(path,analysis,context,**kwargs):
        calls.append(kwargs)
        return {'status':'cached','qualitative_reused_across_data_revision':True,'limitations':[]}
    monkeypatch.setattr(module,'load_cached_report',cached)
    status,report=api.handle('GET',f'/api/v1/regions/{ID}/research/cached')
    assert status==200 and calls[0]=={'allow_data_revision':True}
    assert report['qualitative_reused_across_data_revision']


def test_fine_catalog_and_detail_dispatch_are_offline(api,monkeypatch):
    import src.fine_workflow as fine
    native_id='gldas025_r400_c400'
    data=bundle()
    data['region_id']=native_id
    data['research_context']['region_id']=native_id
    data['feature']['properties']['region_id']=native_id
    calls=[]
    def load(region_id,**kwargs):
        calls.append((region_id,kwargs))
        return deepcopy(data)
    monkeypatch.setattr(fine,'load_fine_region',load)
    monkeypatch.setattr(fine,'fine_map',lambda **kwargs:{'type':'FeatureCollection','features':[data['feature']]})
    status,catalog=api.handle('GET','/api/v1/fine-regions')
    assert status==200 and catalog['features'][0]['properties']['region_id']==native_id
    status,detail=api.handle('GET',f'/api/v1/regions/{native_id}')
    assert status==200 and detail['region_id']==native_id
    assert calls[0][1]['directory']==api.fine_directory
    assert api.jobs.calls==[]


def test_registry_routes_allow_only_one_known_tile_id(api,monkeypatch,tmp_path):
    import src.fine_workflow as workflow
    api._registered_fine=True
    api.tile_index=tmp_path/'tiles.json';api.tile_index.write_text('{}')
    registry={'schema_version':'fine-tiles-1','tiles':[{'id':'central_us_1deg','name':'US','bbox':[-98,37,-97,38]}]}
    monkeypatch.setattr(workflow,'load_tile_index',lambda **kwargs:deepcopy(registry))
    monkeypatch.setattr(workflow,'fine_tiles',lambda **kwargs:deepcopy(registry))
    calls=[]
    def selected(tile_id,**kwargs):
        calls.append(tile_id)
        return {'type':'FeatureCollection','features':[],'viewport':{'tile_id':tile_id}}
    monkeypatch.setattr(workflow,'registered_fine_map',selected)
    assert api.handle('GET','/api/v1/fine-tiles')[0]==200
    assert api.handle('GET','/api/v1/fine-regions?tile_id=central_us_1deg')[0]==200
    assert calls==['central_us_1deg']
    assert api.handle('GET','/api/v1/fine-regions?tile_id=canada_1deg')[0]==404
    assert api.handle('GET','/api/v1/fine-regions?tile_id=central_us_1deg&tile_id=central_us_1deg')[0]==400
    assert api.handle('GET','/api/v1/fine-regions?directory=/etc')[0]==400
    assert api.handle('GET','/api/v1/fine-tiles?tile_id=central_us_1deg')[0]==400
    assert api.jobs.calls==[]


def test_registered_detail_stale_source_manifest_returns_rebuild_conflict(api,monkeypatch,tmp_path):
    import src.fine_workflow as workflow
    api._registered_fine=True
    api.tile_index=tmp_path/'tiles.json';api.tile_index.write_text('{}')
    def stale(*a,**kwargs):
        raise workflow.FineCollectionStale('private input path must not leak')
    monkeypatch.setattr(workflow,'load_registered_fine_region',stale)
    monkeypatch.setattr(api,'_registered_native',lambda region_id:True)
    status,payload=api.handle('GET','/api/v1/regions/gldas025_r388_c0328')
    assert status==409
    assert payload['error']['code']=='fine_collection_rebuild_required'
    assert 'private' not in str(payload)


def test_global_native_fallback_and_ocean_status_never_start_research(api,monkeypatch):
    api._registered_fine=True
    monkeypatch.setattr(api,'_registered_native',lambda region_id:False)
    rid='gldas025_r300_c1000'
    data=bundle();data['region_id']=rid;data['research_context']['region_id']=rid
    data['observations']=pd.DataFrame({'value':[float('nan')]})
    data['status']='unsupported_gldas';data['availability']={'status':'unsupported_gldas','ndvi_status':'pending_native_aggregation'}
    calls=[]
    def loaded(region_id):
        calls.append(region_id)
        return deepcopy(data)
    monkeypatch.setattr(api,'_global_native',loaded)
    status,result=api.handle('GET',f'/api/v1/regions/{rid}')
    assert status==200 and not result['hasData']
    assert result['status']=='unsupported_gldas'
    assert result['availability']['ndvi_status']=='pending_native_aggregation'
    assert calls==[rid] and api.jobs.calls==[]


def test_coordinate_lookup_bounds_and_antimeridian_are_geometry_only(api):
    for query in ('lon=0&lat=-70','lon=180&lat=0','lon=-180&lat=0'):
        status,result=api.handle('GET','/api/v1/cell?'+query)
        assert status==200
        if query=='lon=0&lat=-70':
            assert result['region_id'] is None and result['status']=='outside_gldas_extent'
        else:
            assert result['region_id']=='gldas025_r240_c0000'
    for query in ('lon=NaN&lat=0','lon=0&lat=91','lon=181&lat=0','lon=0&lat=0&lat=1','lon=0','lon=0&lat=0&url=x'):
        assert api.handle('GET','/api/v1/cell?'+query)[0]==400
    assert api.jobs.calls==[]


def test_global_scan_is_serialized_deduplicated_and_cache_bounded(api,monkeypatch):
    from threading import Event,Thread
    import src.global_cell_data as source
    import src.global_cell_analysis as stats
    started,release=Event(),Event()
    calls=[]
    def loaded(region_id,**kwargs):
        calls.append(region_id)
        started.set()
        assert release.wait(2)
        return {'region_id':region_id}
    monkeypatch.setattr(source,'load_global_cell',loaded)
    monkeypatch.setattr(stats,'analyze_global_cell',lambda data:deepcopy(data))
    monkeypatch.setattr(api,'_global_source_signature',lambda:('version-one',))
    results=[]
    thread=Thread(target=lambda:results.append(api._global_native('one')))
    thread.start();assert started.wait(1)
    try:
        with pytest.raises(module.APIError) as exc:
            api._global_native('different-cell')
        assert exc.value.status==429
        release.set();thread.join(timeout=2)
        assert api._global_native('one')=={'region_id':'one'} and calls==['one']
        for i in range(20):api._global_native(str(i))
        assert len(api._global_memory)==16
    finally:
        release.set();thread.join(timeout=2)


def test_registered_cell_never_falls_back_when_joint_collection_is_stale(api,monkeypatch):
    import src.fine_workflow as workflow
    api._registered_fine=True
    api.tile_index=api.cache_dir.parent/'test_registry.json';api.tile_index.write_text('{}')
    monkeypatch.setattr(api,'_registered_native',lambda region_id:True)
    monkeypatch.setattr(api,'_global_native',lambda region_id:pytest.fail('Global fallback would bypass joint-family guard'))
    def stale(*a,**kwargs):raise workflow.FineCollectionStale('changed')
    monkeypatch.setattr(workflow,'load_registered_fine_region',stale)
    assert api.handle('GET','/api/v1/regions/gldas025_r388_c0328')[0]==409


@pytest.mark.parametrize('failure',[False,True])
def test_duplicate_cell_requests_share_one_scan_and_propagate_result(api,monkeypatch,failure):
    from threading import Event,Thread
    import src.global_cell_data as source
    import src.global_cell_analysis as stats
    started,release=Event(),Event()
    calls=[];results=[]
    def loaded(region_id,**kwargs):
        calls.append(region_id);started.set()
        assert release.wait(2)
        if failure:raise ValueError('private source failure')
        return {'region_id':region_id}
    monkeypatch.setattr(source,'load_global_cell',loaded)
    monkeypatch.setattr(stats,'analyze_global_cell',lambda data:deepcopy(data))
    monkeypatch.setattr(api,'_global_source_signature',lambda:('stable-version',))
    def request():
        try:results.append((200,api._global_native('same-cell')))
        except module.APIError as exc:results.append((exc.status,exc.code))
    first=Thread(target=request);first.start();assert started.wait(1)
    second=Thread(target=request);second.start()
    try:
        time.sleep(.02)
        assert second.is_alive()
        release.set();first.join(timeout=2);second.join(timeout=2)
        assert len(calls)==1 and len(results)==2
        if failure:
            assert results==[(503,'global_cell_unavailable')]*2
            assert 'private' not in str(results)
        else:
            assert all(status==200 and data['region_id']=='same-cell' for status,data in results)
    finally:
        release.set();first.join(timeout=2);second.join(timeout=2)


def test_duplicate_wait_is_bounded_without_cancelling_owner_scan(api,monkeypatch):
    from threading import Event,Thread
    import src.global_cell_data as source
    import src.global_cell_analysis as stats
    started,release=Event(),Event()
    def loaded(region_id,**kwargs):
        started.set();assert release.wait(2)
        return {'region_id':region_id}
    monkeypatch.setattr(source,'load_global_cell',loaded)
    monkeypatch.setattr(stats,'analyze_global_cell',lambda data:deepcopy(data))
    monkeypatch.setattr(api,'_global_source_signature',lambda:('stable-version',))
    api._global_wait_seconds=.02
    results=[]
    first=Thread(target=lambda:results.append(api._global_native('same-cell')))
    first.start();assert started.wait(1)
    try:
        with pytest.raises(module.APIError) as exc:api._global_native('same-cell')
        assert exc.value.status==503 and exc.value.code=='global_cell_wait_timeout'
        release.set();first.join(timeout=2)
        assert api._global_native('same-cell')=={'region_id':'same-cell'}
    finally:
        release.set();first.join(timeout=2)
