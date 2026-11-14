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
    assert ndvi.quality_flag.eq('pending_export').sum()==263
    assert json.loads((out/'catalog.json').read_text())['features'][0]['properties']['ndvi_status']=='partial'
    saved=(out/'monthly_timeseries.csv').read_bytes()
    with pytest.raises(ValueError,match='discard previously imported'):
        mod.main([second],out)
    assert (out/'monthly_timeseries.csv').read_bytes()==saved
    mod.main([first,second],out)
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
    full.to_csv(complete,index=False);mod.main([complete],out)
    p=json.loads((out/'catalog.json').read_text())['features'][0]['properties']
    assert p['ndvi_status']=='no_valid_observations' and p['data_status']=='unavailable_ndvi'
    # An explicit replacement is allowed and makes omitted dates pending again.
    mod.main([first],out,replace=True)
    assert pd.read_csv(out/'monthly_timeseries.csv').query("variable=='ndvi'").value.notna().sum()==1


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
