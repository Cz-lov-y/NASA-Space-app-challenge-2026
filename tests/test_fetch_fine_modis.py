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
