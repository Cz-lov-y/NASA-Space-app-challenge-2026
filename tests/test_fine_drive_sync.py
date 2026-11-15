"""Drive sync refuses partial annual exports and accidental pilot ingestion."""
import json
from pathlib import Path
import pandas as pd
import pytest
import scripts.sync_fine_modis_drive as module


def setup(monkeypatch,tmp_path,label,dates):
    monkeypatch.setattr(module,'ROOT',tmp_path)
    import scripts.prepare_fine_backend as backend
    monkeypatch.setattr(backend,'prepare',lambda directory:{'cells':1})
    catalog={'features':[{'properties':{'region_id':'gldas025_r388_c0328'}}]}
    monkeypatch.setattr(module,'load_request',lambda _:({'tile_id':'tile','catalog':'none/catalog.json'},catalog,'hash'))
    monkeypatch.setattr(module,'discover',lambda *a:[{'id':'id','year':2003,'label':label,'name':label+'.csv'}])
    path=tmp_path/'download.csv';path.write_text('source bytes')
    monkeypatch.setattr(module,'download_file',lambda *a:({'path':str(path),'sha256':__import__('hashlib').sha256(path.read_bytes()).hexdigest()},True))
    import scripts.merge_fine_modis as merge
    frame=pd.DataFrame({'region_id':['gldas025_r388_c0328']*len(dates),'date':dates,'value':[.4]*len(dates)})
    monkeypatch.setattr(merge,'validate',lambda *a:frame)
    calls=[]
    monkeypatch.setattr(merge,'ingest',lambda *a:(calls.append(a) or {'ok':True}))
    return calls


def test_pilot_is_validation_only_until_explicitly_included(monkeypatch,tmp_path):
    calls=setup(monkeypatch,tmp_path,'pilot_2003_01',['2003-01-01'])
    result=module.sync(None,'request',tmp_path/'cache',directory=tmp_path,ingest=True)
    assert not result['ingested'] and not calls
    assert result['files'][0]['pilot_validation_only']
    result=module.sync(None,'request',tmp_path/'cache',directory=tmp_path,ingest=True,include_pilot=True)
    assert result['ingested'] and len(calls)==1


def test_partial_annual_never_reaches_import(monkeypatch,tmp_path):
    calls=setup(monkeypatch,tmp_path,'2003',['2003-01-01'])
    with pytest.raises(ValueError,match='Incomplete'):
        module.sync(None,'request',tmp_path/'cache',directory=tmp_path,ingest=True)
    assert calls==[]


def test_complete_annual_reaches_import(monkeypatch,tmp_path):
    dates=[f'2003-{m:02d}-01' for m in range(1,13)]
    calls=setup(monkeypatch,tmp_path,'2003',dates)
    result=module.sync(None,'request',tmp_path/'cache',directory=tmp_path,ingest=True)
    assert result['ingested'] and len(calls)==1


def test_discovery_accepts_only_current_area_method_exports(monkeypatch):
    def files(session,query):
        if "name = 'NASA_member_B_fine'" in query:return [{'id':'folder'}]
        return [{'id':'old','name':'mod13a3_gldas025_tile_2003.csv'},
                {'id':'current','name':'mod13a3_gldas025_sphere_v2_tile_2003.csv'},
                {'id':'other','name':'mod13a3_gldas025_sphere_v2_other_2003.csv'}]
    monkeypatch.setattr(module,'list_files',files)
    result=module.discover(None,'tile')
    assert [r['id'] for r in result]==['current']
    assert result[0]['year']==2003
