"""Browser/Python numerical parity using actual inputs and marked synthetic cases.

Requires installed frontend development dependencies and Node. No browser/server,
network calls, or generated NASA data are used by these checks.
"""
import json
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.regional_statistics import build_regional_screening

ROOT=Path(__file__).resolve().parents[1]


def node_binary():
    executable=shutil.which('node')
    if executable:return executable
    candidates=sorted((ROOT/'.cache/node-runtime').glob('*/bin/node'))
    if candidates:return str(candidates[-1])
    pytest.skip('Node is required for the frontend/Python numerical parity check')


def run_live(cases):
    if not (ROOT/'frontend/node_modules/esbuild').exists():
        pytest.skip('Install locked frontend development dependencies for browser parity tests')
    script="""
import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(process.cwd()+'/frontend/package.json');
const esbuild=require('esbuild');
const mod={exports:{}};
const source=esbuild.buildSync({entryPoints:['frontend/src/services/liveScreening.ts'],bundle:true,write:false,format:'cjs',platform:'node',target:'es2020'}).outputFiles[0].text;
new Function('module','exports','require',source)(mod,mod.exports,require);
const cases=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(cases.map(c=>mod.exports.computeLiveScreening(c.raw,c.options))));
"""
    completed=subprocess.run([node_binary(),'--input-type=module','-e',script],input=json.dumps(cases,allow_nan=False),
        text=True,capture_output=True,cwd=ROOT,timeout=30,check=True)
    return json.loads(completed.stdout)


def synthetic(seed=3,years=22,mode='random'):
    rng=np.random.default_rng(seed)
    dates=pd.date_range('2003-01-01',periods=years*12,freq='MS')
    frames=[]
    for variable in ('ndvi','soil_water_0_100cm'):
        annual=.3+np.arange(years)*.004+rng.normal(0,.008,years) if variable=='ndvi' else 150-np.arange(years)*.7+rng.normal(0,2,years)
        if mode=='line':annual=.3+np.arange(years)*.01 if variable=='ndvi' else 150-np.arange(years)*2.
        if mode=='constant':annual=np.full(years,.3 if variable=='ndvi' else 150.)
        if mode=='ties':annual=np.round(annual,1 if variable=='ndvi' else 0)
        values=np.repeat(annual,12)
        frames.append(pd.DataFrame({'date':dates.strftime('%Y-%m-%d'),'value':values,'unit':'1' if variable=='ndvi' else 'kg m-2',
            'variable':variable,'source':'SYNTHETIC_TEST_ONLY','region_id':'test','quality_flag':'coverage_review_required'}))
    return pd.concat(frames,ignore_index=True)


def payload(frame,start=2003,end=2024):
    observations=json.loads(frame.to_json(orient='records',date_format='iso',double_precision=15))
    return {'raw':{'region_id':str(frame.region_id.iloc[0]),'feature':{'type':'Feature','geometry':None,'properties':{}},
        'dataset_version':'TEST_SOURCE_VERSION','observations':observations,'provenance':{'status':'TEST_PARITY_ONLY'}},
        'options':{'startYear':start,'endYear':end,'estimateMissing':False}}


def assert_numerics_match(live,expected):
    if expected['analysis']:
        actual=live['paired_analysis']
        reference=expected['analysis']
        assert actual['observation_period']==reference['observation_period']
        for variable in reference['variables']:
            a,b=actual['analysis'][variable],reference['analysis'][variable]
            assert a['status']==b['status']
            assert a['reliable']==b['reliable']
            assert a['data_quality']['analyzed_years']==b['data_quality']['analyzed_years']
            assert a['data_quality']['missing_fraction']==b['data_quality']['missing_fraction']
            for method,keys in [('linear_regression',['slope','intercept','p_value','standard_error','confidence_interval']),
                ('theil_sen',['slope','intercept','confidence_interval']),('mann_kendall',['s','variance','z','p_value','tau_a'])]:
                if b[method] is None:
                    assert a[method] is None
                    continue
                for key in keys:
                    np.testing.assert_allclose(a[method][key],b[method][key],rtol=2e-6,atol=1e-11,err_msg=f'{variable}/{method}/{key}')
    assert live['screening']['classification']==expected['screening']['classification']
    assert live['screening']['category']==expected['screening']['category']
    assert live['screening']['probability'] is None
    assert not live['screening']['multiple_testing']['globally_adjusted']
    assert live['provenance']['live_analysis']['engine']=='browser-typescript-v1'


def test_browser_matches_python_synthetic_and_actual_monthly_cases():
    cases=[synthetic(mode=mode) for mode in ('random','line','constant','ties')]
    missing=synthetic(seed=8);missing.loc[[0,40,200],'value']=np.nan;cases.append(missing)
    short=synthetic(years=7);cases.append(short)
    gapped=synthetic();gapped.loc[pd.to_datetime(gapped.date).dt.year.between(2007,2020),'value']=np.nan;cases.append(gapped)
    actual=pd.read_csv(ROOT/'data/processed/fine/collection/monthly_timeseries.csv',dtype={'unit':str},float_precision='round_trip')
    ids=actual.region_id.drop_duplicates().tolist()
    for index in (0,20,40,60,80):
        cases.append(actual[actual.region_id==ids[index]].copy())
    outputs=run_live([payload(frame) for frame in cases])
    for frame,live in zip(cases,outputs):
        # Recreate the JSON transport precision used in the browser input.
        transported=pd.DataFrame(payload(frame)['raw']['observations'])
        expected=build_regional_screening(transported)['regions'][0]
        assert_numerics_match(live,expected)


def test_time_window_changes_actual_fit_and_does_not_reuse_precomputed_statistics():
    frame=synthetic(seed=9)
    cases=[payload(frame),payload(frame,2010,2024),payload(frame,2020,2024)]
    outputs=run_live(cases)
    for item,live in zip(cases,outputs):
        selected=pd.DataFrame(item['raw']['observations'])
        years=pd.to_datetime(selected.date).dt.year
        selected=selected[years.between(item['options']['startYear'],item['options']['endYear'])]
        expected=build_regional_screening(selected)['regions'][0]
        assert_numerics_match(live,expected)
    assert outputs[0]['paired_analysis']['trend_slopes']['ndvi']!=outputs[1]['paired_analysis']['trend_slopes']['ndvi']
    assert outputs[2]['screening']['classification']=='insufficient'


def test_live_preserves_source_qa_missing_values_and_synthetic_flag():
    frame=synthetic(seed=11)
    frame.loc[0,'quality_flag']='low_coverage'
    frame.loc[1,'value']=np.nan
    soil_only=frame[frame.variable=='soil_water_0_100cm'].copy()
    unsupported=soil_only.copy();unsupported['value']=np.nan;unsupported['quality_flag']='no_valid_pixels'
    outputs=run_live([payload(frame),payload(soil_only),payload(unsupported)])
    assert_numerics_match(outputs[0],build_regional_screening(pd.DataFrame(payload(frame)['raw']['observations']))['regions'][0])
    assert 2003 not in outputs[0]['paired_analysis']['observation_period']['years']
    assert outputs[0]['observations'][0]['value']==payload(frame)['raw']['observations'][0]['value']
    assert outputs[0]['observations'][0]['quality_flag']=='low_coverage'
    assert outputs[0]['observations'][1]['value'] is None
    assert outputs[0]['paired_analysis']['data_quality']['synthetic_demo']
    assert outputs[1]['paired_analysis'] is None
    assert outputs[1]['screening']['classification']=='pending'
    assert outputs[1]['available_indicator_analysis']['observation_period']['years']==list(range(2003,2025))
    assert outputs[2]['screening']['classification']=='unsupported'
    assert outputs[2]['screening']['category'] is None
    assert outputs[2]['annual_fits']=={}


def test_canadian_seasonal_estimates_enable_screening_without_changing_source_observations():
    frame=pd.read_csv(ROOT/'data/processed/fine/canada/monthly_timeseries.csv')
    region=frame.region_id.iloc[0]
    frame=frame.loc[frame.region_id==region].copy()
    case=payload(frame)
    observed_only=run_live([case])[0]
    case['options']['estimateMissing']=True
    estimated=run_live([case])[0]
    assert observed_only['screening']['classification']=='insufficient'
    assert estimated['screening']['classification']!='insufficient'
    assert estimated['provenance']['live_analysis']['ndvi_estimated_months']>0
    quality=estimated['paired_analysis']['analysis']['ndvi']['data_quality']
    assert quality['n_years']>=8 and quality['model_estimated_observations']>0
    assert quality['raw_missing_fraction']>0 and quality['raw_incomplete_retained_years']
    assert estimated['observations']==case['raw']['observations']
