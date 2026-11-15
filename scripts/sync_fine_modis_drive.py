#!/usr/bin/env python3
"""Download and validate native-cell MODIS exports; cloud submission is separate."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.sync_regional_modis_drive import list_files,download_file
from scripts.export_fine_modis_earth_engine import load_request


def discover(session,tile_id):
    # Legacy exports used a different area model and are historical evidence.
    # Only the explicitly versioned spherical-area exports may enter this route.
    pattern=re.compile(r'^mod13a3_gldas025_sphere_v2_'+re.escape(tile_id)+r'_(pilot_2003_01|200[3-9]|201[0-9]|202[0-4]|retry_\d{8})\.csv$')
    folders=list_files(session,"trashed = false and mimeType = 'application/vnd.google-apps.folder' and name = 'NASA_member_B_fine'")
    found={}
    for folder in folders:
        fid=folder['id'].replace('\\','\\\\').replace("'","\\'")
        for item in list_files(session,f"trashed = false and '{fid}' in parents"):
            match=pattern.fullmatch(item.get('name',''))
            if not match:continue
            label=match.group(1)
            year=2003 if label.startswith('pilot') else int(label[6:10]) if label.startswith('retry_') else int(label)
            found[item['id']]={**item,'year':year,'label':label}
    return sorted(found.values(),key=lambda i:(i['label'],i['id']))


def sync(session,request_path,cache,*,directory=None,ingest=False,include_pilot=False,file_ids=None):
    from scripts.merge_fine_modis import validate,ingest as import_files
    import pandas as pd
    request,catalog,digest=load_request(request_path)
    cache=Path(cache);cache.mkdir(parents=True,exist_ok=True)
    manifest_path=cache/'manifest.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {'files':{}}
    items=discover(session,request['tile_id'])
    if file_ids:
        if set(file_ids)-{i['id'] for i in items}:raise ValueError('Unknown fine export file IDs')
        items=[i for i in items if i['id'] in file_ids]
    files=[];accepted=[];annual_versions={}
    for item in items:
        record,downloaded=download_file(session,item,cache,manifest['files'].get(item['id']))
        manifest['files'][item['id']]=record
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
        frame=validate(Path(record['path']),catalog)
        label=item['label']
        months=[f'{item["year"]}-{m:02d}-01' for m in range(1,13)] if label.isdigit() else ['2003-01-01'] if label.startswith('pilot') else [pd.Timestamp(label[6:]).strftime('%Y-%m-%d')]
        expected={(f['properties']['region_id'],m) for f in catalog['features'] for m in months}
        if set(zip(frame.region_id,frame.date))!=expected or len(frame)!=len(expected):
            raise ValueError('Incomplete or wrong-month fine export')
        pilot=label.startswith('pilot')
        if pilot:
            content=Path(record['path']).read_bytes()
            if hashlib.sha256(content).hexdigest()!=record['sha256']:
                raise ValueError('Downloaded pilot changed before archival')
            target=ROOT/'data/raw/modis_earth_engine/fine_validation'/(record['sha256']+'.csv')
            target.parent.mkdir(parents=True,exist_ok=True)
            if target.exists() and target.read_bytes()!=content:
                raise ValueError('Immutable pilot archive was modified')
            if not target.exists():target.write_bytes(content)
        if label.isdigit():annual_versions.setdefault(label,set()).add(record['sha256'])
        entry={'drive_id':item['id'],'name':item['name'],'label':label,'path':record['path'],
               'sha256':record['sha256'],'downloaded':downloaded,'rows':len(frame),
               'finite_values':int(frame.value.notna().sum()),'status':'structural_and_provenance_checks_passed',
               'independent_pixel_review':'pending','pilot_validation_only':pilot and not include_pilot}
        files.append(entry)
        if not pilot or include_pilot:accepted.append(Path(record['path']))
    if ingest and any(len(v)>1 for v in annual_versions.values()):
        raise ValueError('Ambiguous annual versions; select accepted --file-id values')
    result={'tile_id':request['tile_id'],'catalog_sha256':digest,'files':files,'ingested':False,
            'note':'Pilot validation is read-only by default. Independent source-pixel checks and scientific review remain separate.'}
    if ingest and accepted:
        if directory is None:directory=(ROOT/request['catalog']).parent
        result['import']=import_files(accepted,Path(directory));result['ingested']=True
        from scripts.prepare_fine_backend import prepare
        result['backend']=prepare(Path(directory))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request',type=Path,default=ROOT/'data/requests/fine_central_us_1deg.json')
    parser.add_argument('--cache',type=Path,default=ROOT/'.cache/fine_modis_drive')
    parser.add_argument('--directory',type=Path)
    parser.add_argument('--ingest',action='store_true')
    parser.add_argument('--include-pilot',action='store_true',help='Deliberately import pilot rows; future annual overlap may require explicit replacement')
    parser.add_argument('--file-id',action='append')
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    import ee
    from google.auth.transport.requests import AuthorizedSession
    session=AuthorizedSession(ee.data.get_persistent_credentials())
    result=sync(session,args.request,args.cache,directory=args.directory,ingest=args.ingest,include_pilot=args.include_pilot,file_ids=args.file_id)
    if args.report:
        args.report.parent.mkdir(parents=True,exist_ok=True)
        args.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
