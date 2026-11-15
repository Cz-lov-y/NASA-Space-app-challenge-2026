#!/usr/bin/env python3
"""One-pass Drive sync of completed annual nonpolar MODIS CSV exports.

Uses existing Earth Engine OAuth, never starts tasks or opens a browser. Downloads
stay in ignored .cache until --ingest explicitly validates and archives them.
"""
from pathlib import Path
import argparse
import contextlib
import io
import hashlib
import json
import re
import sys
from urllib.parse import quote

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.export_regional_modis_earth_engine import export_grid
from scripts.merge_regional_timeseries import main as ingest_exports, validate_modis

DRIVE='https://www.googleapis.com/drive/v3/files'
FOLDER='NASA_member_B_regional'
ANNUAL=re.compile(r'^mod13a3_grid10_(200[3-9]|201[0-9]|202[0-4])_nonpolar\.csv$')


def list_files(session,query):
    token=None;seen=set();files=[]
    while True:
        params={'q':query,'pageSize':1000,
            'fields':'nextPageToken,files(id,name,mimeType,md5Checksum,size,modifiedTime,version,parents)'}
        if token: params['pageToken']=token
        response=session.get(DRIVE,params=params,timeout=60)
        response.raise_for_status();result=response.json();files.extend(result.get('files',[]))
        token=result.get('nextPageToken')
        if not token: return files
        if token in seen: raise ValueError('Repeated Drive pagination token')
        seen.add(token)


def discover_annuals(session,file_ids=None):
    """Read only folders with the exact export-folder name and their children."""
    folders=list_files(session,"trashed = false and mimeType = 'application/vnd.google-apps.folder' and name = 'NASA_member_B_regional'")
    found={}
    for folder in folders:
        fid=folder['id'].replace('\\','\\\\').replace("'","\\'")
        for item in list_files(session,f"trashed = false and '{fid}' in parents and mimeType != 'application/vnd.google-apps.folder'"):
            match=ANNUAL.fullmatch(item.get('name',''))
            if match:
                found[item['id']]={**item,'year':int(match.group(1))}
    if file_ids:
        unknown=set(file_ids)-set(found)
        if unknown: raise ValueError('Requested file IDs are not matching annual exports in the named folder')
        found={key:value for key,value in found.items() if key in file_ids}
    return sorted(found.values(),key=lambda f:(f['year'],f['id']))


def download_file(session,item,cache,previous=None):
    """Verify Drive MD5/size and retain immutable ID+SHA256 addressed bytes."""
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    version={key:str(item.get(key,'')) for key in ['id','version','modifiedTime','md5Checksum','size']}
    if previous and previous.get('remote_version')==version:
        path=Path(previous['path'])
        if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==previous['sha256']:
            return previous,False
    identity=hashlib.sha256(item['id'].encode()).hexdigest()[:24]
    partial=cache/(identity+'.part')
    md5=hashlib.md5();sha=hashlib.sha256();size=0
    try:
        response=session.get(DRIVE+'/'+quote(item['id'],safe=''),params={'alt':'media'},stream=True,timeout=(10,120))
        response.raise_for_status()
        with partial.open('wb') as handle:
            for chunk in response.iter_content(chunk_size=1024*1024):
                if not chunk: continue
                handle.write(chunk);md5.update(chunk);sha.update(chunk);size+=len(chunk)
        if item.get('size') is not None and size!=int(item['size']): raise ValueError('Drive download size mismatch')
        if item.get('md5Checksum') and md5.hexdigest()!=item['md5Checksum']: raise ValueError('Drive download MD5 mismatch')
        target=cache/(identity+'_'+sha.hexdigest()+'.csv')
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest()!=sha.hexdigest(): raise ValueError('Immutable local cache was modified')
            partial.unlink()
        else: partial.replace(target)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return {'drive_id':item['id'],'name':item['name'],'year':item['year'],'remote_version':version,
            'sha256':sha.hexdigest(),'md5':md5.hexdigest(),'size':size,'path':str(target.resolve())},True


def validate_annual(path,year):
    import pandas as pd
    frame=validate_modis(pd.read_csv(path,dtype={'unit':str},float_precision='round_trip'))
    regions={f['id'] for f in export_grid(nonpolar=True)}
    expected={(rid,f'{year}-{month:02d}-01') for rid in regions for month in range(1,13)}
    if set(zip(frame.region_id,frame.date))!=expected or len(frame)!=6912:
        raise ValueError(f'Annual{year} export must have576 requested cells ×12months; partial or wrong-year CSV rejected')
    return {'year':year,'rows':len(frame),'finite_values':int(frame.value.notna().sum()),
            'source_pixel_review':'pending'}


def sync(session,cache,*,ingest=False,out=None,file_ids=None,replace=False,list_only=False):
    cache=Path(cache);items=discover_annuals(session,file_ids)
    report={'folder':FOLDER,'matching_annual_files':len(items),'files':[],
            'ingested':False,'scope':'nonpolar','catalog_cells':648,'requested_cells':576}
    if list_only:
        report['files']=[{k:f.get(k) for k in ['id','name','year','size','md5Checksum','version']} for f in items]
        return report
    manifest_path=cache/'manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'files':{},'history':[]}
    paths=[];by_year={}
    for item in items:
        record,downloaded=download_file(session,item,cache,manifest['files'].get(item['id']))
        manifest['files'][item['id']]=record
        if not any(r['drive_id']==record['drive_id'] and r['sha256']==record['sha256'] for r in manifest['history']):
            manifest['history'].append(record)
        # Save each completed download so an interruption does not lose progress.
        cache.mkdir(parents=True,exist_ok=True)
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
        report['files'].append({'id':record['drive_id'],'name':record['name'],'sha256':record['sha256'],
                                'path':record['path'],'downloaded':downloaded})
        paths.append(Path(record['path']));by_year.setdefault(record['year'],set()).add(record['sha256'])
    ambiguous=[year for year,hashes in by_year.items() if len(hashes)>1]
    report['ambiguous_duplicate_years']=ambiguous
    if ingest and paths:
        if ambiguous: raise ValueError('Different Drive files exist for the same annual export; select accepted IDs with --file-id before ingestion')
        report['annual_validation']=[validate_annual(path,item['year']) for path,item in zip(paths,items)]
        progress=io.StringIO()
        with contextlib.redirect_stdout(progress):
            ingest_exports(paths,Path(out) if out else ROOT/'data/processed/regional',replace=replace)
        report['import_summary']=progress.getvalue().strip()
        report['ingested']=True
        report['next_step']='Rebuild regional statistics, screening and frontend bundle; this sync does not rewrite those artifacts.'
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache',type=Path,default=ROOT/'.cache/regional_modis_drive')
    p.add_argument('--out',type=Path,default=ROOT/'data/processed/regional')
    p.add_argument('--file-id',action='append',help='Select exact accepted Drive ID when duplicate names exist')
    p.add_argument('--list-only',action='store_true');p.add_argument('--ingest',action='store_true')
    p.add_argument('--replace',action='store_true',help='Explicitly accept changed existing source rows during ingestion')
    p.add_argument('--poll-tasks',action='store_true',help='Refresh recorded task states once; never submit or wait')
    p.add_argument('--project',default='earthrisk-greenmirage')
    p.add_argument('--task-manifest',type=Path,default=ROOT/'.cache/regional_modis_tasks.json')
    args=p.parse_args(argv)
    if args.list_only and args.ingest: p.error('--list-only and --ingest are mutually exclusive')
    if args.replace and not args.ingest: p.error('--replace requires --ingest')
    import ee
    from google.auth.transport.requests import AuthorizedSession
    # Reuse existing approved credentials; never authenticate/open a browser here.
    session=AuthorizedSession(ee.data.get_persistent_credentials())
    if args.poll_tasks:
        from scripts.export_regional_modis_earth_engine import poll_status
        task_states=poll_status(ee,args.project,args.task_manifest)
    else: task_states=None
    report=sync(session,args.cache,ingest=args.ingest,out=args.out,file_ids=args.file_id,
                replace=args.replace,list_only=args.list_only)
    if task_states is not None:
        report['tasks']=[{k:r.get(k) for k in ['task_id','description','scope','status']} for r in task_states]
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
