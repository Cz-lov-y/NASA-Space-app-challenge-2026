"""No-account tests reuse genuine archived NASA rows with mocked cloud transport."""
from copy import deepcopy
import hashlib
import json
from threading import Event
import time

import pandas as pd
import pytest

import src.global_cell_modis as modis
from src.fine_workflow import FINE,load_fine_region

RID='gldas025_r388_c0328'


@pytest.fixture
def native():
    base=load_fine_region(RID)
    soil=base['observations'].loc[base['observations'].variable!='ndvi'].copy()
    actual=pd.read_csv(FINE/'accepted_modis_observations.csv',dtype={'unit':str},float_precision='round_trip')
    actual=actual.loc[actual.region_id==RID].copy()
    actual['tile_id']=RID
    base['observations']=soil
    return base,actual


def test_one_cell_yearly_transport_progress_and_verified_persistent_cache(native,tmp_path,monkeypatch):
    base,actual=native
    calls=[];progress=[]
    def fetch(ee,project,request,catalog,target_sha,plan,cache,deadline_seconds):
        assert len(catalog['features'])==1 and deadline_seconds==30
        item=plan[0];calls.append(item['label'])
        frame=actual.loc[actual.date.str.startswith(item['start'][:4])]
        path=tmp_path/(item['label']+'.csv');frame.to_csv(path,index=False)
        return {'files':[{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]}
    monkeypatch.setattr(modis,'fetch',fetch)
    result=modis.retrieve_native_modis(base,cache_directory=tmp_path,ee_module=object(),progress=lambda **p:progress.append(p))
    assert len(calls)==22 and progress[-1]['completed_years']==22
    assert len(result['observations'])==792
    assert result['observations'].query("variable=='ndvi'").shape[0]==264
    pd.testing.assert_frame_equal(result['observations'].query("variable!='ndvi'").reset_index(drop=True).reindex(columns=base['observations'].columns),
        base['observations'].sort_values(['variable','date']).reset_index(drop=True),check_dtype=False)
    monkeypatch.setattr(modis,'fetch',lambda *a,**k:pytest.fail('Completed cache must not call Earth Engine'))
    cached=modis.retrieve_native_modis(base,cache_directory=tmp_path,ee_module=object())
    assert cached['availability']['ndvi_received_months']==264
    assert cached['provenance']['native_ndvi']['qa_reviewed'] is False
    directory=modis._directory(base,tmp_path)
    (directory/'monthly_ndvi.csv').write_bytes(b'CORRUPTED TEST BYTES')
    with pytest.raises(ValueError,match='checksum'):
        modis.cached_native_modis(base,cache_directory=tmp_path)


def test_native_data_job_dedup_progress_queue_and_selection_guard(tmp_path,monkeypatch):
    import src.global_screening as screening
    started,release=Event(),Event();calls=[]
    def runner(bundle,**kwargs):
        calls.append(bundle['region_id']);started.set()
        kwargs['progress'](completed_years=3,total_years=22,current_year=2006)
        assert release.wait(2)
        return bundle
    monkeypatch.setattr(screening,'screen_global_cell',lambda data:data)
    monkeypatch.setattr(modis,'save_screened_summary',lambda *a,**k:None)
    jobs=modis.NativeModisJobs(cache_directory=tmp_path,runner=runner)
    def base(rid):return {'region_id':rid,'research_context':{'dataset_version':'source-v1'}}
    try:
        first=jobs.submit(base('cell-one'));assert started.wait(1)
        duplicate=jobs.submit(base('cell-one'))
        assert duplicate['request_id']==first['request_id']
        second=jobs.submit(base('cell-two'))
        assert second['state']=='queued'
        assert jobs.submit(base('cell-three'))['state']=='busy'
        assert jobs.poll(first['request_id'],region_id='wrong',context_key=first['context_key'])['state']=='stale'
        state=jobs.poll(first['request_id'],region_id='cell-one',context_key=first['context_key'])
        assert state['completed_years']==3
        release.set()
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            state=jobs.poll(first['request_id'],region_id='cell-one',context_key=first['context_key'])
            if state['state']=='complete':break
            time.sleep(.005)
        assert state['state']=='complete' and calls.count('cell-one')==1
    finally:
        release.set();jobs.close()


def test_batch_map_shards_are_paged_without_cloud_calls(tmp_path,monkeypatch):
    import src.fine_workflow as workflow
    from src.fine_grid import cell_feature
    fake_root=tmp_path/'repository'
    directory=fake_root/'data/processed/fine/global/global_r100_c200'
    directory.mkdir(parents=True)
    index=directory.parent/'index.json'
    tile={'ready':True,'calculation_version':modis.CALCULATION_VERSION,
          'directory':str(directory),'bbox':[20,40,21,41]}
    index.write_text(json.dumps({'schema_version':'global-native-tile-index-1',
        'calculation_version':modis.CALCULATION_VERSION,'tiles':{'global_r100_c200':tile}}))
    features=[cell_feature(row,col) for row in range(400,404) for col in range(800,804)]
    calls=[]
    def map_source(**kwargs):
        calls.append(kwargs['directory'])
        return {'features':deepcopy(features),'multiple_testing':{'family_size':32}}
    monkeypatch.setattr(modis,'ROOT',fake_root)
    monkeypatch.setattr(workflow,'fine_map',map_source)
    page=modis.all_screened_summaries(cache_directory=tmp_path/'cache',index_path=index,limit=3,offset=5)
    assert page['total']==16 and page['has_more'] and len(page['features'])==3
    assert [f['id'] for f in page['features']]==[f['id'] for f in features[5:8]]
    assert all(f['properties']['family_scope']=='single-tile exploratory; not worldwide adjusted' for f in page['features'])
    assert all(f['properties']['probability'] is None and not f['properties']['globally_adjusted'] for f in page['features'])
    assert modis.batch_tile_directory(features[0]['id'],index_path=index)==directory
    assert len(calls)==2


def test_failed_native_data_job_is_honest_and_retry_requires_explicit_action(tmp_path):
    calls=[]
    def fail(bundle,**kwargs):
        calls.append(bundle['region_id'])
        raise ValueError('private account response must not appear')
    jobs=modis.NativeModisJobs(cache_directory=tmp_path,runner=fail)
    data={'region_id':RID,'research_context':{'dataset_version':'test-version'}}
    try:
        request=jobs.submit(data)
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            state=jobs.poll(request['request_id'],region_id=RID,context_key=request['context_key'])
            if state['state']=='failed':break
            time.sleep(.005)
        assert state['state']=='failed' and state['retryable']
        assert 'private account' not in str(state)
        assert jobs.submit(data)['request_id']==request['request_id']
        assert calls==[RID]
        assert jobs.submit(data,retry=True)['request_id']!=request['request_id']
    finally:jobs.close()


def test_failed_progress_survives_restart_and_new_selection_resumes(native,tmp_path):
    base,_=native
    def fail(bundle,**kwargs):
        kwargs['progress'](completed_years=5,total_years=22,current_year=2008)
        raise ValueError('private remote error')
    first=modis.NativeModisJobs(cache_directory=tmp_path,runner=fail)
    request=first.submit(base)
    try:
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            state=first.poll(request['request_id'],region_id=RID,context_key=request['context_key'])
            if state['state']=='failed':break
            time.sleep(.005)
        saved=json.loads((modis._directory(base,tmp_path)/'progress.json').read_text())
        assert saved['state']=='failed' and saved['completed_years']==5
        assert 'private' not in str(saved)
    finally:first.close()
    started,release=Event(),Event()
    def resume(bundle,**kwargs):
        started.set();assert release.wait(2)
        raise ValueError('test termination')
    second=modis.NativeModisJobs(cache_directory=tmp_path,runner=resume)
    try:
        new=second.submit(base)
        assert new['request_id']!=request['request_id']
        assert new['completed_years']==5 and started.wait(1)
    finally:release.set();second.close()


def test_corrupt_solo_snapshot_does_not_duplicate_batch_cells_across_pages(tmp_path,monkeypatch):
    import src.fine_workflow as workflow
    from src.fine_grid import cell_feature
    root=tmp_path/'root';root.mkdir()
    monkeypatch.setattr(modis,'ROOT',root)
    solo=tmp_path/'cache/gldas025_r388_c0328'/modis.CALCULATION_VERSION/'screening_summary.json'
    solo.parent.mkdir(parents=True);solo.write_text('invalid JSON TEST ONLY')
    directory=root/'data/processed/fine/global/global_r100_c200';directory.mkdir(parents=True)
    index=directory.parent/'index.json'
    index.write_text(json.dumps({'schema_version':'global-native-tile-index-1','calculation_version':modis.CALCULATION_VERSION,
        'tiles':{'global_r100_c200':{'ready':True,'calculation_version':modis.CALCULATION_VERSION,
                                   'directory':str(directory),'bbox':[20,40,21,41]}}}))
    features=[cell_feature(r,c) for r in range(400,404) for c in range(800,804)]
    monkeypatch.setattr(workflow,'fine_map',lambda **kwargs:{'features':deepcopy(features)})
    first=modis.all_screened_summaries(cache_directory=tmp_path/'cache',index_path=index,limit=3,offset=0)
    second=modis.all_screened_summaries(cache_directory=tmp_path/'cache',index_path=index,limit=3,offset=3)
    assert [f['id'] for f in first['features']]==[f['id'] for f in features[:2]]
    assert [f['id'] for f in second['features']]==[f['id'] for f in features[2:5]]
    assert not {f['id'] for f in first['features']} & {f['id'] for f in second['features']}


def test_raw_and_statistically_annotated_selection_share_native_data_job_key():
    raw={'region_id':RID,'research_context':{'dataset_version':'actual-source-fingerprint'}}
    legacy={'region_id':RID,'research_context':{'dataset_version':'statistical-adapter-version',
        'raw_dataset_version':'actual-source-fingerprint'}}
    assert modis.NativeModisJobs._key(raw)==modis.NativeModisJobs._key(legacy)
