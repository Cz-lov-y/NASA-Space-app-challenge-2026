"""Bounded fake-client tests; no account calls or invented repo observations."""
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json
import pytest
from scripts.fetch_fine_modis import fetch,main
from tests.test_merge_fine_modis import fine_release,fake_rows


def test_direct_fetch_is_bounded_raw_archived_resumable_and_dry_by_default(fine_release,tmp_path,monkeypatch,capsys):
    import scripts.fetch_fine_modis as mod
    _,catalog=fine_release;request={'tile_id':'central_us_1deg','bbox':[-98,37,-97,38]}
    rows=fake_rows(catalog,['2003-01-01']);payload={'type':'FeatureCollection','features':[{'properties':r} for r in rows.to_dict('records')]}
    calls=[]
    fake=SimpleNamespace(Initialize=lambda **kw:calls.append(('initialize',kw)),data=SimpleNamespace(
        setDeadline=lambda ms:calls.append(('deadline',ms)),setMaxRetries=lambda n:calls.append(('retries',n))))
    class Collection:
        def getInfo(self):calls.append(('getInfo',));return payload
    monkeypatch.setattr(mod,'build_collection',lambda *args:Collection())
    monkeypatch.setattr(mod,'load_request',lambda *args:(request,catalog,'SYNTHETIC_TARGET_HASH'))
    mod.main(['--project','SYNTHETIC_TEST_PROJECT'])
    assert json.loads(capsys.readouterr().out)['mode']=='dry_plan' and not calls
    plan=[{'start':'2003-01-01','end':'2003-02-01','label':'pilot_2003_01'}]
    cache=tmp_path/'cache'
    report=fetch(fake,'SYNTHETIC_TEST_PROJECT',request,catalog,'SYNTHETIC_TARGET_HASH',plan,cache)
    record=report['files'][0]
    assert not record['reused'] and report['export_tasks_submitted']==0
    assert ('deadline',30000) in calls and ('retries',0) in calls and calls.count(('getInfo',))==1
    for filename,digest in [(record['path'],record['sha256']),(record['raw_response_path'],record['raw_response_sha256'])]:
        assert hashlib.sha256(Path(filename).read_bytes()).hexdigest()==digest
    again=fetch(fake,'SYNTHETIC_TEST_PROJECT',request,catalog,'SYNTHETIC_TARGET_HASH',plan,cache)
    assert again['files'][0]['reused'] and calls.count(('getInfo',))==1
    Path(record['path']).write_text('SYNTHETIC_TAMPERING')
    with pytest.raises(ValueError,match='immutable.*hash mismatch'):
        fetch(fake,'SYNTHETIC_TEST_PROJECT',request,catalog,'SYNTHETIC_TARGET_HASH',plan,cache)
    assert calls.count(('getInfo',))==1


def test_failed_validation_retains_raw_response_without_completed_receipt(fine_release,tmp_path,monkeypatch):
    import scripts.fetch_fine_modis as mod
    _,catalog=fine_release;request={'tile_id':'central_us_1deg'}
    payload={'type':'FeatureCollection','features':[{'properties':r} for r in fake_rows(catalog,['2003-01-01']).iloc[:-1].to_dict('records')]}
    fake=SimpleNamespace(Initialize=lambda **kw:None,data=SimpleNamespace(setDeadline=lambda ms:None,setMaxRetries=lambda n:None))
    monkeypatch.setattr(mod,'build_collection',lambda *args:SimpleNamespace(getInfo=lambda:payload))
    plan=[{'start':'2003-01-01','end':'2003-02-01','label':'pilot_2003_01'}];cache=tmp_path/'failed'
    with pytest.raises(ValueError,match='raw service response retained'):
        fetch(fake,'SYNTHETIC_TEST_PROJECT',request,catalog,'SHA',plan,cache)
    assert len(list(cache.glob('raw_*.json')))==1
    assert not list(cache.glob('*.csv')) and not (cache/'receipt.json').exists()
    too_many={'features':catalog['features']+[catalog['features'][0]]}
    with pytest.raises(ValueError,match='at most16'):
        fetch(fake,'SYNTHETIC_TEST_PROJECT',request,too_many,'SHA',plan,cache)
    with pytest.raises(ValueError,match='1to30'):
        fetch(fake,'SYNTHETIC_TEST_PROJECT',request,catalog,'SHA',plan,cache,deadline_seconds=31)



def test_getinfo_omitted_null_properties_preserve_winter_and_absent_image_semantics(fine_release):
    from scripts.fetch_fine_modis import checked_result
    _,catalog=fine_release
    source=fake_rows(catalog,['2003-01-01'])
    winter=[]
    for row in source.to_dict('records'):
        row.pop('value');row.update(valid_area_m2=0,valid_area_fraction=0,quality_flag='no_valid_pixels')
        winter.append({'properties':row})
    item={'start':'2003-01-01','end':'2003-02-01','label':'pilot'}
    result=checked_result({'features':winter},catalog,item)
    assert len(result)==16 and result.value.isna().all() and result.quality_flag.eq('no_valid_pixels').all()
    absent=[]
    for feature in winter:
        row=feature['properties'].copy()
        for col in ['value','valid_area_m2','valid_area_fraction','source_asset_id','source_time_start','source_crs','source_transform']:
            row.pop(col,None)
        row.update(source_image_count=0,quality_flag='missing');absent.append({'properties':row})
    result=checked_result({'features':absent},catalog,item)
    assert result.value.isna().all() and result.valid_area_m2.isna().all() and result.quality_flag.eq('missing').all()
    # Required metadata is never invented when the service response omits it.
    for column in ['source_image_count','configured_at_utc','region_area_m2','tile_id']:
        malformed=[{'properties':{k:v for k,v in feature['properties'].items() if k!=column}} for feature in winter]
        with pytest.raises(ValueError):checked_result({'features':malformed},catalog,item)
    missing_present_crs=[{'properties':{k:v for k,v in feature['properties'].items() if k!='source_crs'}} for feature in winter]
    with pytest.raises(ValueError,match='source provenance'):
        checked_result({'features':missing_present_crs},catalog,item)


def test_calculation_version_change_cannot_reuse_legacy_cache_key(fine_release,tmp_path,monkeypatch):
    import scripts.fetch_fine_modis as mod
    _,catalog=fine_release;request={'tile_id':'central_us_1deg'}
    payload={'features':[{'properties':row} for row in fake_rows(catalog,['2003-01-01']).to_dict('records')]}
    calls=[]
    fake=SimpleNamespace(Initialize=lambda **kw:None,data=SimpleNamespace(setDeadline=lambda ms:None,setMaxRetries=lambda n:None))
    monkeypatch.setattr(mod,'build_collection',lambda *a:SimpleNamespace(getInfo=lambda:calls.append('fetch') or payload))
    plan=[{'start':'2003-01-01','end':'2003-02-01','label':'pilot'}];cache=tmp_path/'version_cache'
    first=fetch(fake,'SYNTHETIC_PROJECT',request,catalog,'SYNTHETIC_TARGET',plan,cache)
    assert first['files'][0]['calculation_version']==mod.CALCULATION_VERSION
    receipt_path=cache/'receipt.json';receipt=json.loads(receipt_path.read_text())
    old=receipt['requests'].pop(next(iter(receipt['requests'])))
    old['calculation_version']='SYNTHETIC_PREVIOUS_METHOD'
    receipt['requests']['SYNTHETIC_OLD_VERSION_KEY']=old
    receipt_path.write_text(json.dumps(receipt))
    second=fetch(fake,'SYNTHETIC_PROJECT',request,catalog,'SYNTHETIC_TARGET',plan,cache)
    assert not second['files'][0]['reused'] and calls==['fetch','fetch']
