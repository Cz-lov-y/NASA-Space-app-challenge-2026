#!/usr/bin/env python3
"""Bounded interactive retrieval of MODIS aggregates for <=16 native GLDAS cells.

Default is a local dry plan. --fetch explicitly uses the already authorized
Earth Engine account/project. Each request is one month or calendar year and
has a30second deadline; server quota errors stop the run without new accounts,
projects or alternate data. No export tasks are submitted.
"""
from pathlib import Path
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import io
import json
import sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.export_fine_modis_earth_engine import load_request,build_collection,CALCULATION_VERSION
from scripts.export_regional_modis_earth_engine import COLUMNS,export_plan,QA_RULE
from scripts.merge_fine_modis import validate_frame,validate


def checked_result(payload,catalog,item):
    features=payload.get('features',[])
    frame=pd.DataFrame([feature['properties'] for feature in features])
    # Earth Engine omits null-valued dictionary keys from JSON. Restore only
    # scientifically nullable source fields; required identity/QA metadata must
    # still be present and passes the existing source-image-count consistency.
    nullable=['value','valid_area_m2','valid_area_fraction','source_asset_id',
              'source_time_start','source_crs','source_transform']
    for column in nullable:
        if column not in frame.columns:frame[column]=float('nan')
    frame=validate_frame(frame,catalog)
    dates=pd.date_range(pd.Timestamp(item['start']),pd.Timestamp(item['end']),freq='MS',inclusive='left').strftime('%Y-%m-%d')
    ids={f['properties']['region_id'] for f in catalog['features']}
    expected={(rid,date) for rid in ids for date in dates}
    if len(frame)!=len(expected) or set(zip(frame.region_id,frame.date))!=expected:
        raise ValueError('Interactive response does not cover every requested native cell/month')
    return frame.sort_values(['region_id','date'])


def fetch(ee,project,request,catalog,target_sha,plan,cache,deadline_seconds=30,refresh=False):
    """Retrieve one bounded request at a time, recording only verified completions."""
    if not 1<=len(catalog['features'])<=16:raise ValueError('Interactive fine retrieval is restricted to at most16native cells')
    if not 1<=deadline_seconds<=30:raise ValueError('Interactive deadline must be1to30seconds')
    cache=Path(cache);receipt_path=cache/'receipt.json'
    receipt=json.loads(receipt_path.read_text()) if receipt_path.exists() else {'requests':{},'history':[]}
    ee_initialized=False;results=[]
    for item in plan:
        identity={'project':project,'target_geometry_sha256':target_sha,'tile_id':request['tile_id'],
            'start':item['start'],'end_exclusive':item['end'],'source':'MODIS/061/MOD13A3','qa_rule':QA_RULE,
            'calculation_version':CALCULATION_VERSION}
        key=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
        previous=receipt['requests'].get(key)
        if previous and not refresh:
            path=Path(previous['path'])
            if path.exists():
                if hashlib.sha256(path.read_bytes()).hexdigest()!=previous['sha256']:
                    raise ValueError('Existing immutable interactive CSV hash mismatch; inspect it before an explicit --refresh')
                # Validate cached source and full requested month set before reuse.
                existing=validate(path,catalog)
                checked_result({'features':[{'properties':r} for r in existing.to_dict('records')]},catalog,item)
                results.append({**previous,'reused':True});continue
        if not ee_initialized:
            ee.Initialize(project=project);ee.data.setDeadline(deadline_seconds*1000);ee.data.setMaxRetries(0);ee_initialized=True
        configured=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
        # This is the unchanged native-projection/QA graph used by cloud exports.
        payload=build_collection(ee,catalog,item['start'],item['end'],configured,request['tile_id']).getInfo()
        # Retain the exact successful service response before scientific checks;
        # failed validation must be replayable without another cloud request.
        raw=json.dumps(payload,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
        raw_digest=hashlib.sha256(raw).hexdigest();cache.mkdir(parents=True,exist_ok=True)
        raw_path=cache/('raw_mod13a3_'+request['tile_id']+'_'+item['label']+'_'+raw_digest+'.json')
        if raw_path.exists() and hashlib.sha256(raw_path.read_bytes()).hexdigest()!=raw_digest:
            raise ValueError('Immutable raw response hash mismatch')
        if not raw_path.exists():raw_path.write_bytes(raw)
        try:frame=checked_result(payload,catalog,item)
        except (ValueError,KeyError,TypeError) as exc:
            raise ValueError(f'{exc}; raw service response retained at {raw_path}') from exc
        buffer=io.StringIO(newline='')
        columns=COLUMNS+['tile_id','target_resolution_degrees','area_method']
        writer=csv.DictWriter(buffer,fieldnames=columns,extrasaction='ignore',lineterminator='\n')
        writer.writeheader()
        # DataFrame missing values must remain blank rather than literal nan text.
        writer.writerows(frame.astype(object).where(pd.notna(frame),None).to_dict('records'))
        content=buffer.getvalue().encode();digest=hashlib.sha256(content).hexdigest()
        filename='mod13a3_gldas025_'+request['tile_id']+'_'+item['label']+'_'+digest+'.csv'
        path=cache/filename;cache.mkdir(parents=True,exist_ok=True)
        if path.exists():
            if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Immutable target cache hash mismatch')
        else:
            temp=path.with_suffix('.csv.part');temp.write_bytes(content);temp.replace(path)
        record={**identity,'label':item['label'],'path':str(path.resolve()),'sha256':digest,
            'rows':len(frame),'finite_values':int(frame.value.notna().sum()),'configured_at_utc':configured,
            'raw_response_path':str(raw_path.resolve()),'raw_response_sha256':raw_digest,
            'deadline_seconds':deadline_seconds,'transport':'Earth Engine FeatureCollection.getInfo; existing authorized project',
            'scientific_review':'source metadata/QA/native-grid checks passed; independent pixel validation pending'}
        receipt['requests'][key]=record
        if not any(r['sha256']==digest and r['path']==record['path'] for r in receipt['history']):receipt['history'].append(record)
        receipt_path.write_text(json.dumps(receipt,indent=2)+'\n')
        results.append({**record,'reused':False})
    return {'mode':'fetched','tile_id':request['tile_id'],'native_cells':len(catalog['features']),
        'files':results,'receipt':str(receipt_path),'export_tasks_submitted':0,
        'ingested':False,'next_step':'Validate retained source files and explicitly ingest with scripts/merge_fine_modis.py; rebuild statistics/bundle afterward.'}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',required=True);p.add_argument('--request',type=Path,default=ROOT/'data/requests/fine_central_us_1deg.json')
    p.add_argument('--mode',choices=['pilot','years','month'],default='pilot');p.add_argument('--month',default='2003-01-01')
    p.add_argument('--first-year',type=int);p.add_argument('--last-year',type=int)
    p.add_argument('--fetch',action='store_true');p.add_argument('--refresh',action='store_true')
    p.add_argument('--deadline-seconds',type=int,default=30);p.add_argument('--cache',type=Path,default=ROOT/'.cache/fine_modis_direct')
    args=p.parse_args(argv)
    if not args.project.strip():p.error('--project must be nonempty')
    if args.refresh and not args.fetch:p.error('--refresh requires --fetch')
    if not 1<=args.deadline_seconds<=30:p.error('--deadline-seconds must be1to30')
    request,catalog,digest=load_request(args.request)
    if len(catalog['features'])>16:p.error('Interactive fine retrieval is restricted to at most16native cells')
    first=args.first_year if args.first_year is not None else request.get('first_year',2003)
    last=args.last_year if args.last_year is not None else request.get('last_year',2024)
    plan=export_plan(args.mode,first,last,args.month)
    if args.fetch:
        import ee
        result=fetch(ee,args.project,request,catalog,digest,plan,args.cache,args.deadline_seconds,args.refresh)
    else:result={'mode':'dry_plan','tile_id':request['tile_id'],'native_cells':len(catalog['features']),
        'target_resolution_degrees':.25,'target_geometry_sha256':digest,'calculation_version':CALCULATION_VERSION,'request_count':len(plan),'requests':plan,
        'deadline_seconds':args.deadline_seconds,'export_tasks_submitted':0,'network_calls':0}
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
