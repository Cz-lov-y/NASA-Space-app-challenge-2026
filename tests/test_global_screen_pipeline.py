"""Small orchestration checks only; no account calls or synthetic repo outputs."""
import json
from pathlib import Path
import numpy as np
import scripts.global_screen_earth_engine as mod


def fake_support():
    mask=np.zeros((150,360),dtype=bool);mask[97,82]=True;mask[98,83]=True
    return mask,{'source_release_sha256':'SYNTHETIC_SOURCE_RELEASE','source_months_available':264,
        'supported_1deg_tiles':2,'geometric_1deg_tiles':54000}


def test_global_partition_is_native_and_default_plan_does_not_acquire(tmp_path,monkeypatch):
    monkeypatch.setattr(mod,'ROOT',tmp_path)
    monkeypatch.setattr(mod,'supported_tiles',lambda *a:fake_support())
    monkeypatch.setattr(mod,'acquire',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('dry plan must not acquire')))
    tile=mod.tile_for_cell('gldas025_r388_c0328')
    assert tile['id']=='global_r097_c082' and tile['bbox']==[-98,37,-97,38]
    report=mod.run(cache_directory=tmp_path/'cache')
    assert report['selected_supported_tiles']==2 and report['annual_requests_before_cache']==44
    assert not report['worldwide_paired_complete'] and not report['worldwide_testing_family_complete']
    assert not list(tmp_path.rglob('current_tile.json'))


def test_bounded_global_run_resumes_next_tile_and_defers_rigorous_audit(tmp_path,monkeypatch):
    monkeypatch.setattr(mod,'ROOT',tmp_path);monkeypatch.setattr(mod,'supported_tiles',lambda *a:fake_support())
    done=set();calls=[]
    def load(path):return json.loads(Path(path).read_text())['tiles']
    monkeypatch.setattr(mod,'load_tiles',load)
    monkeypatch.setattr(mod,'readiness',lambda tile:{'ready':tile['id'] in done})
    def acquire(path,project,**kwargs):
        tile=load(path)[0];done.add(tile['id']);calls.append(kwargs)
        return {'tiles':[{'directory':tile['directory'],'ready':True,'ndvi_valid_rows':4224,'ndvi_required_rows':4224}]}
    monkeypatch.setattr(mod,'acquire',acquire)
    first=mod.run(fetch=True,max_tiles=1,cache_directory=tmp_path/'cache')
    assert len(calls)==1 and calls[0]['audit_required'] is False
    assert first['completed_tiles'][0]['release_audit_status']=='deferred_for_demo'
    assert not first['worldwide_paired_complete']
    second=mod.run(fetch=True,max_tiles=1,cache_directory=tmp_path/'cache')
    assert len(calls)==2 and second['reused_index_tiles']==1 and second['worldwide_paired_complete']
    assert not second['worldwide_testing_family_complete']
    assert first['completed_tiles'][0]['id']!=second['completed_tiles'][0]['id']


def test_low_disk_space_checkpoints_before_any_tile_acquisition(tmp_path,monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(mod,'ROOT',tmp_path);monkeypatch.setattr(mod,'supported_tiles',lambda *a:fake_support())
    monkeypatch.setattr(mod,'load_tiles',lambda path:json.loads(Path(path).read_text())['tiles'])
    monkeypatch.setattr(mod,'readiness',lambda tile:{'ready':False})
    monkeypatch.setattr(mod.shutil,'disk_usage',lambda path:SimpleNamespace(free=19*1024**3))
    monkeypatch.setattr(mod,'acquire',lambda *a,**kw:(_ for _ in ()).throw(AssertionError('low disk must stop before acquisition')))
    result=mod.run(fetch=True,cache_directory=tmp_path/'cache')
    assert result['stop_reason']=='low_disk_space' and not result['worldwide_paired_complete']
    index=json.loads((tmp_path/result['index']).read_text())
    assert index['last_stop_reason']=='low_disk_space' and index['tiles']=={}


def test_tile_failure_continues_then_retry_clears_checkpoint_without_refetching_success(tmp_path,monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(mod,'ROOT',tmp_path);monkeypatch.setattr(mod,'supported_tiles',lambda *a:fake_support())
    monkeypatch.setattr(mod.shutil,'disk_usage',lambda path:SimpleNamespace(free=100*1024**3))
    def load(path):return json.loads(Path(path).read_text())['tiles']
    monkeypatch.setattr(mod,'load_tiles',load)
    done=set();calls=[];fail=True
    monkeypatch.setattr(mod,'readiness',lambda tile:{'ready':tile['id'] in done})
    def acquire(path,project,**kwargs):
        tile=load(path)[0];calls.append(tile['id'])
        if fail and tile['id']=='global_r097_c082':raise ValueError('SYNTHETIC polar geometry bounds failure')
        done.add(tile['id'])
        return {'tiles':[{'directory':tile['directory'],'ready':True,'ndvi_valid_rows':4224,'ndvi_required_rows':4224}]}
    monkeypatch.setattr(mod,'acquire',acquire)
    first=mod.run(fetch=True,cache_directory=tmp_path/'cache')
    assert len(first['failed_tiles'])==1 and len(first['completed_tiles'])==1 and not first['worldwide_paired_complete']
    fail=False
    second=mod.run(fetch=True,cache_directory=tmp_path/'cache')
    assert second['worldwide_paired_complete'] and second['reused_index_tiles']==1
    index=json.loads((tmp_path/second['index']).read_text())
    assert index['failed_tiles']=={} and calls.count('global_r098_c083')==1


def test_service_quota_failure_stops_without_attempting_remaining_tiles(tmp_path,monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(mod,'ROOT',tmp_path);monkeypatch.setattr(mod,'supported_tiles',lambda *a:fake_support())
    monkeypatch.setattr(mod.shutil,'disk_usage',lambda path:SimpleNamespace(free=100*1024**3))
    monkeypatch.setattr(mod,'load_tiles',lambda path:json.loads(Path(path).read_text())['tiles'])
    monkeypatch.setattr(mod,'readiness',lambda tile:{'ready':False})
    calls=[]
    def acquire(*a,**kw):calls.append(1);raise RuntimeError('Quota exceeded429')
    monkeypatch.setattr(mod,'acquire',acquire)
    result=mod.run(fetch=True,cache_directory=tmp_path/'cache')
    assert len(calls)==1 and result['stop_reason']=='source_or_service_blocked'
    assert not result['worldwide_paired_complete']


def test_country_priority_orders_actual_country_intersections_first(tmp_path):
    from shapely.geometry import box, mapping
    path=tmp_path/'countries.json'
    path.write_text(json.dumps({'type':'FeatureCollection','features':[
        {'type':'Feature','properties':{'ISO_A3':code},'geometry':mapping(box(x,0,x+1,1))}
        for code,x in [('CAN',-100),('USA',-90),('PRI',-60)]
    ]}))
    jobs=[{'id':'other','bbox':[10,10,11,11]},
          {'id':'us','bbox':[-90,0,-89,1]},
          {'id':'canada','bbox':[-100,0,-99,1]}]
    ordered,count=mod.prioritize_north_america(jobs,path)
    assert [j['id'] for j in ordered]==['us','canada','other']
    assert count==2


def test_southern_alberta_is_first_and_other_priorities_preserve_order(tmp_path):
    from shapely.geometry import box, mapping
    path=tmp_path/'geography.json'
    path.write_text(json.dumps({'regions':[{'name':'Alberta','country':'Canada',
        'geometry':mapping(box(-120,49,-110,60))}]}))
    jobs=[{'id':'us','bbox':[-100,35,-99,36]},
          {'id':'central_alberta','bbox':[-114,53,-113,54]},
          {'id':'south_alberta','bbox':[-114,50,-113,51]},
          {'id':'outside','bbox':[-109,50,-108,51]}]
    ordered,count=mod.prioritize_southern_alberta(jobs,path)
    assert [j['id'] for j in ordered]==['south_alberta','us','central_alberta','outside']
    assert count==1


def test_southern_prairies_then_canada_then_other_locations(tmp_path):
    from shapely.geometry import box, mapping
    path=tmp_path/'geography.json'
    path.write_text(json.dumps({
        'countries':[{'name':'Canada','geometry':mapping(box(-130,49,-80,70))}],
        'regions':[{'name':name,'country':'Canada','geometry':mapping(box(west,49,west+5,60))}
                   for name,west in [('Alberta',-120),('Saskatchewan',-115),('Manitoba',-110)]]}))
    jobs=[{'id':'world','bbox':[-100,35,-99,36]},
          {'id':'northern_canada','bbox':[-100,58,-99,59]},
          {'id':'southern_saskatchewan','bbox':[-114,50,-113,51]},
          {'id':'southern_manitoba','bbox':[-109,51,-108,52]}]
    ordered,prairies,canada=mod.prioritize_canada_prairies(jobs,path)
    assert [j['id'] for j in ordered]==['southern_saskatchewan','southern_manitoba','northern_canada','world']
    assert prairies==2 and canada==3
