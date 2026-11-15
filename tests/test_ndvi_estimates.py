"""Display-only NDVI estimates; synthetic unit cases and real Canada inputs."""
import json
from pathlib import Path
import subprocess
import shutil

import pytest

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def node_binary():
    binary = shutil.which('node')
    candidates = sorted((ROOT/'.cache/node-runtime').glob('*/bin/node'))
    if binary: return binary
    if candidates: return str(candidates[-1])
    pytest.skip('Node is required')


def run_estimates(rows):
    script = r'''
import fs from 'node:fs';
import {createRequire} from 'node:module';
const require=createRequire(process.cwd()+'/frontend/package.json');
const code=require('esbuild').transformSync(fs.readFileSync('frontend/src/utils/ndviEstimates.ts','utf8'),{loader:'ts',format:'cjs'}).code;
const mod={exports:{}};new Function('module','exports','require',code)(mod,mod.exports,require);
const rows=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(mod.exports.ndviGapEstimates(rows.map(r=>r.date),rows)));
'''
    result = subprocess.run([node_binary(), '--input-type=module', '-e', script], input=json.dumps(rows),
        text=True, capture_output=True, cwd=ROOT, check=True, timeout=20)
    return json.loads(result.stdout)


def test_seasonal_curve_gap_and_pending_are_never_invented():
    import math
    rows = []
    for year in range(2018, 2023):
        for month in range(1, 13):
            value = .4 + .2 * math.cos(2 * math.pi * (month - 7) / 12)
            rows.append(dict(date=f'{year}-{month:02d}-01', value=value, quality_flag='ok'))
    for row in rows:
        if row['date'] in ('2020-01-01', '2020-02-01', '2020-03-01'):
            row.update(value=None, quality_flag='no_valid_pixels')
        if row['date'] == '2021-01-01':
            row.update(value=None, quality_flag='pending_export')
    original = json.dumps(rows)
    result = run_estimates(rows)
    gap = [result[i] for i, row in enumerate(rows) if row['date'].startswith('2020-0') and row['date'][5:7] in ('01','02','03')]
    assert all(point and point['estimated'] for point in gap)
    assert abs(gap[0]['value'] - 2*gap[1]['value'] + gap[2]['value']) > .001
    assert result[next(i for i,r in enumerate(rows) if r['date']=='2021-01-01')] is None
    assert json.dumps(rows) == original


def test_not_enough_history_does_not_generate_a_curve():
    rows = [dict(date=f'2020-{m:02d}-01', value=value, quality_flag=flag) for m,value,flag in [
        (1,.2,'ok'),(2,None,'no_valid_pixels'),(3,.5,'ok')]]
    assert run_estimates(rows) == [None, None, None]


def test_real_canada_winter_gaps_are_estimated_without_extrapolating():
    frame = pd.read_csv(ROOT/'data/processed/fine/canada/monthly_timeseries.csv')
    ndvi = frame.loc[(frame.variable=='ndvi') & (frame.region_id==frame.region_id.iloc[0])].sort_values('date')
    rows = json.loads(ndvi.to_json(orient='records'))
    estimates = run_estimates(rows)
    assert any(x and x['estimated'] for x in estimates)
    assert all(not x or not x['estimated'] or (row['value'] is None and row['quality_flag']=='no_valid_pixels')
               for row, x in zip(rows, estimates))


def test_long_missing_interval_is_not_predicted():
    rows = [dict(date=f'{year}-{month:02d}-01', value=.3 + .01 * month, quality_flag='ok')
            for year in range(2018, 2023) for month in range(1, 13)]
    for row in rows:
        if row['date'].startswith('2020-') and 1 <= int(row['date'][5:7]) <= 7:
            row.update(value=None, quality_flag='no_valid_pixels')
    result=run_estimates(rows)
    gap=[result[i] for i,row in enumerate(rows) if row['date'].startswith('2020-') and int(row['date'][5:7]) <= 7]
    assert gap == [None] * 7
