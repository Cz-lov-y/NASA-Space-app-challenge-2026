"""Fine-grid data checks; generated arrays are explicitly synthetic fixtures."""
from pathlib import Path
import importlib.util
import json
import numpy as np
import pandas as pd
import pytest
import xarray as xr
ROOT=Path(__file__).resolve().parents[1]


def load(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def synthetic_native_dataset():
    surface=np.arange(600,dtype=float)[:,None]+np.arange(1440,dtype=float)[None,:]/100
    dims=('time','lat','lon')
    ds=xr.Dataset({name:(dims,values[None,:,:]) for name,values in zip(
        ('SoilMoi0_10cm_inst','SoilMoi10_40cm_inst','SoilMoi40_100cm_inst'),
        (surface,np.full_like(surface,20),np.full_like(surface,30)))},coords={
        'time':[pd.Timestamp('2003-01-01')],'lat':np.arange(600)*.25-59.875,'lon':np.arange(1440)*.25-179.875})
    for var in ds.data_vars:ds[var].attrs.update(units='kg m-2',cell_methods='time: mean')
    return ds


def test_native_extraction_keeps_cell_values_and_shared_layer_missing_mask():
    mod=load('process_fine_gldas');ds=synthetic_native_dataset()
    rows=[388,388,391];cols=[328,331,331]
    surface,total=mod.extract_layers(ds,rows,cols,'2003-01-01')
    assert np.array_equal(surface,np.array(rows)+np.array(cols)/100)
    assert np.array_equal(total,surface+50)
    ds['SoilMoi10_40cm_inst'].values[0,388,328]=np.nan
    surface,total=mod.extract_layers(ds,rows,cols,'2003-01-01')
    assert np.isfinite(surface[0]) and np.isnan(total[0])
    assert np.isfinite(total[1:]).all()
    with pytest.raises(ValueError,match='orientation'):
        mod.extract_layers(ds.isel(lat=slice(None,None,-1)),rows,cols,'2003-01-01')
    with pytest.raises(ValueError,match='month/time'):
        mod.extract_layers(ds,rows,cols,'2003-02-01')
    ds['SoilMoi0_10cm_inst'].attrs['units']='m3 m-3'
    with pytest.raises(ValueError,match='units'):
        mod.extract_layers(ds,rows,cols,'2003-01-01')


def test_fine_export_submission_is_explicit_and_targets_exact_catalog(tmp_path,monkeypatch,capsys):
    from types import SimpleNamespace
    mod=load('export_fine_modis_earth_engine')
    request={'tile_id':'SYNTHETIC_TEST_TILE','bbox':[-98,37,-97,38]}
    catalog={'features':[{'properties':{'region_id':'gldas025_r388_c0328'}}]}
    monkeypatch.setattr(mod,'load_request',lambda path:(request,catalog,'SYNTHETIC_SHA'))
    monkeypatch.setattr(mod,'submit',lambda *a:pytest.fail('dry plan must not submit'))
    mod.main(['--project','SYNTHETIC_PROJECT'])
    result=json.loads(capsys.readouterr().out)
    assert result['mode']=='dry_plan' and result['target_resolution_degrees']==.25 and result['region_count']==1
    mod=load('export_fine_modis_earth_engine');calls=[]
    class Task:
        id='SYNTHETIC_TASK'
        def start(self):calls.append('start')
    def export(**kwargs):calls.append(kwargs);return Task()
    fake=SimpleNamespace(Initialize=lambda **kw:calls.append(kw),batch=SimpleNamespace(Export=SimpleNamespace(table=SimpleNamespace(toDrive=export))))
    monkeypatch.setattr(mod,'build_collection',lambda ee,cat,*args:('SYNTHETIC_GRAPH',cat))
    manifest=tmp_path/'tasks.json'
    plan=[{'start':'2003-01-01','end':'2003-02-01','label':'pilot_2003_01'}]
    result=mod.submit(fake,'SYNTHETIC_PROJECT',request,catalog,'SYNTHETIC_SHA',plan,manifest)
    assert calls[1]['collection']==('SYNTHETIC_GRAPH',catalog)
    assert calls[1]['folder']=='NASA_member_B_fine' and calls[1]['fileFormat']=='CSV'
    assert calls[1]['selectors'][-2:]==['tile_id','target_resolution_degrees']
    assert result[0]['scope']=='native_gldas025_tile' and result[0]['region_count']==1
    with pytest.raises(ValueError,match='already recorded'):
        mod.submit(fake,'SYNTHETIC_PROJECT',request,catalog,'SYNTHETIC_SHA',plan,manifest)



def test_checked_in_fine_pilot_is_real_native_complete_and_export_request_matches():
    from src.fine_grid import parse_cell_id,cell_bbox
    out=ROOT/'data/processed/fine/central_us'
    frame=pd.read_csv(out/'gldas_monthly_timeseries.csv',dtype={'unit':str},float_precision='round_trip')
    catalog=json.loads((out/'catalog.json').read_text())
    assert len(catalog['features'])==16 and len(frame)==8448 and frame.value.notna().all()
    assert frame.groupby(['region_id','variable']).size().eq(264).all()
    assert set(frame.unit)=={'kg m-2'} and set(frame.source)=={'GLDAS_NOAH025_M.2.1'}
    assert frame.valid_area_fraction.eq(1).all() and set(frame.variable)=={'soil_water_0_10cm','soil_water_0_100cm'}
    for feature in catalog['features']:
        p=feature['properties'];row,col=parse_cell_id(p['region_id'])
        assert p['bbox']==cell_bbox(row,col) and 388<=row<=391 and 328<=col<=331
        assert p['gldas_valid_months']=={'soil_water_0_10cm':264,'soil_water_0_100cm':264}
        assert p['jurisdictions'] and p['jurisdictions'][0]['country_code']=='US'
    exporter=load('export_fine_modis_earth_engine')
    request,target,_=exporter.load_request(ROOT/'data/requests/fine_central_us_1deg.json')
    assert request['bbox']==[-98,37,-97,38] and len(target['features'])==16
    report=json.loads((out/'validation_report.json').read_text())
    assert report['independent_read_checks']==24 and report['max_absolute_difference_kg_m2']==0
