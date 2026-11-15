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


def test_bounded_gap_only_and_pending_are_never_invented():
    rows = [dict(date=f'2020-{m:02d}-01', value=value, quality_flag=flag) for m, value, flag in [
        (1,.2,'ok'),(2,None,'no_valid_pixels'),(3,None,'no_valid_pixels'),(4,.5,'ok'),
        (5,None,'pending_export'),(6,.6,'ok'),(7,None,'no_valid_pixels')]]
    original = json.dumps(rows)
    result = run_estimates(rows)
    assert result[0] == {'value': .2, 'estimated': False}
    assert abs(result[1]['value'] - .3) < 1e-10 and result[1]['estimated']
    assert abs(result[2]['value'] - .4) < 1e-10 and result[2]['estimated']
    assert result[3] == {'value': .5, 'estimated': False}
    assert result[4:] == [None, None, None]
    assert json.dumps(rows) == original


def test_real_canada_winter_gaps_are_estimated_without_extrapolating():
    frame = pd.read_csv(ROOT/'data/processed/fine/canada/monthly_timeseries.csv')
    ndvi = frame.loc[(frame.variable=='ndvi') & (frame.region_id==frame.region_id.iloc[0])].sort_values('date')
    rows = json.loads(ndvi.to_json(orient='records'))
    estimates = run_estimates(rows)
    assert any(x and x['estimated'] for x in estimates)
    assert all(not x or not x['estimated'] or (row['value'] is None and row['quality_flag']=='no_valid_pixels')
               for row, x in zip(rows, estimates))
