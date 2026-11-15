#!/usr/bin/env python3
"""Acquire preselected native0.25degree tiles; default is a read-only local plan.

--fetch explicitly permits existing-account interactive requests and local source
processing/import. No project/tier changes, source resampling or task submission.
Acquisition follows the frozen registry; exploratory selection history is disclosed
in its documentation. The workflow never chooses replacements by classification.
"""
from pathlib import Path
import argparse
import contextlib
import hashlib
import io
import json
import re
import sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.fine_grid import build_tile_catalog
from scripts.process_fine_gldas import main as process_native
from scripts.export_fine_modis_earth_engine import load_request,CALCULATION_VERSION
from scripts.export_regional_modis_earth_engine import export_plan
from scripts.fetch_fine_modis import fetch as fetch_sources
from scripts.merge_fine_modis import checked_catalog,validate,ingest
from scripts.prepare_fine_backend import prepare
from scripts.audit_fine_release import audit


def load_tiles(registry_path,selected=None):
    registry=json.loads(Path(registry_path).read_text())
    tiles=registry['tiles'];ids=set();normalized=[]
    for tile in tiles:
        tile=tile.copy();tile_id=tile.get('id',tile.get('tile_id'))
        if not isinstance(tile_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]+',tile_id) or tile_id in ids:
            raise ValueError('Registry must contain unique safe tile IDs')
        ids.add(tile_id)
        directory=Path(tile['directory']);directory=directory if directory.is_absolute() else ROOT/directory
        if not directory.resolve().is_relative_to((ROOT/'data/processed/fine').resolve()):
            raise ValueError('Tile directory must remain under data/processed/fine')
        geometry=build_tile_catalog(tile['bbox'])
        if not 1<=len(geometry['features'])<=16:raise ValueError('Each acquisition tile must contain at most16complete native cells')
        tile.update(id=tile_id,directory=directory,expected_ids={f['id'] for f in geometry['features']})
        normalized.append(tile)
    unknown=set(selected or [])-ids
    if unknown:raise ValueError('Unknown selected tile IDs: '+','.join(sorted(unknown)))
    return [tile for tile in normalized if not selected or tile['id'] in selected]


def readiness(tile):
    directory=tile['directory'];required=['catalog.json','gldas_monthly_timeseries.csv','metadata.json','source_manifest.json','monthly_timeseries.csv']
    present=[name for name in required if (directory/name).exists()]
    state={'tile_id':tile['id'],'directory':str(directory.relative_to(ROOT)),
        'bbox':tile['bbox'],'native_cells':len(tile['expected_ids']),'native_ready':False,
        'full_export_index_received':False,'screening_current':False,'ready':False,
        'stage':'not_started','ndvi_valid_rows':0,'ndvi_required_rows':len(tile['expected_ids'])*264}
    if not present:return state
    if len(present)!=len(required):
        state.update(stage='incomplete_local_release',missing_files=sorted(set(required)-set(present)));return state
    catalog,areas=checked_catalog(directory/'catalog.json')
    if set(areas)!=tile['expected_ids'] or any(f['properties'].get('tile_id')!=tile['id'] for f in catalog['features']):
        raise ValueError('Existing tile catalog disagrees with frozen registry geometry/identity')
    state['native_ready']=True
    csv_bytes=(directory/'monthly_timeseries.csv').read_bytes();catalog_bytes=(directory/'catalog.json').read_bytes()
    frame=pd.read_csv(io.BytesIO(csv_bytes),dtype={'unit':str});ndvi=frame.loc[frame.variable=='ndvi']
    dates=pd.date_range('2003-01-01','2024-12-01',freq='MS').strftime('%Y-%m-%d')
    expected={(rid,date) for rid in areas for date in dates}
    state['ndvi_valid_rows']=int(ndvi.value.notna().sum())
    received=(len(ndvi)==len(expected) and not ndvi.duplicated(['region_id','date']).any()
        and set(zip(ndvi.region_id,ndvi.date))==expected and not ndvi.quality_flag.eq('pending_export').any())
    state['full_export_index_received']=bool(received)
    observed=not ndvi.empty and ndvi.quality_flag.ne('pending_export').any()
    state['calculation_version']=CALCULATION_VERSION
    state['processing_version_current']=bool('area_method' in ndvi and ndvi.loc[ndvi.quality_flag.ne('pending_export'),'area_method'].eq(CALCULATION_VERSION).all()) if observed else None
    state['needs_processing_correction']=bool(observed and not state['processing_version_current'])
    state['ndvi_qa_gaps']=int(ndvi.value.isna().sum()) if received else None
    if (directory/'screening.json').exists() and (directory/'map_screening.geojson').exists():
        screening=json.loads((directory/'screening.json').read_text());mapping=json.loads((directory/'map_screening.geojson').read_text())
        hashes={'source_csv_sha256':hashlib.sha256(csv_bytes).hexdigest(),'source_catalog_sha256':hashlib.sha256(catalog_bytes).hexdigest()}
        state['screening_current']=all(screening.get(k)==v and mapping.get(k)==v for k,v in hashes.items())
    state['ready']=bool(received and state['screening_current'] and not state['needs_processing_correction'])
    state['stage']='needs_explicit_processing_correction' if state['needs_processing_correction'] else 'ready_with_source_QA_gaps' if state['ready'] and state['ndvi_qa_gaps'] else 'ready' if state['ready'] else 'needs_statistics' if received else 'needs_MODIS'
    return state


def acquire(registry_path,project,*,fetch_requested=False,selected=None,cache=None,ee_client=None,reprocess=False,replace=False):
    if reprocess and not fetch_requested:raise ValueError('Explicit reprocessing requires --fetch')
    if reprocess and not replace:raise ValueError('Reprocessing existing source observations requires explicit --replace')
    tiles=load_tiles(registry_path,selected)
    cache=Path(cache) if cache else ROOT/'.cache/fine_modis_direct'
    report={'mode':'acquire' if fetch_requested else 'dry_plan','project':project,'registry':str(registry_path),
        'source_grid_degrees':.25,'selection':'Fixed registry; exploratory selection history disclosed separately. Acquisition never chooses replacements using classifications.','tiles':[],
        'export_tasks_submitted':0,'account_or_project_changes':False,'calculation_version':CALCULATION_VERSION,
        'reprocess_requested':reprocess,'replacement_authorized':replace}
    for tile in tiles:
        state=readiness(tile)
        if not fetch_requested:
            report['tiles'].append({**state,'pilot_requests':0 if state['full_export_index_received'] else 1,
                'annual_requests':0 if state['full_export_index_received'] else 22});continue
        directory=tile['directory']
        if state['stage']=='incomplete_local_release':raise ValueError('Partial local release requires explicit repair; native extraction will not overwrite it')
        if state.get('needs_processing_correction') and not (reprocess and replace):
            raise ValueError('Existing tile uses an outdated area calculation; require --fetch --reprocess --replace to correct it explicitly')
        if state['ready'] and not reprocess:
            audit_report=audit(directory)
            (directory/'release_audit.json').write_text(json.dumps(audit_report,indent=2,allow_nan=False)+'\n')
            if not audit_report['integrity_passed']:raise ValueError('Existing complete tile failed integrity audit; inspect '+str(directory/'release_audit.json'))
            report['tiles'].append({**state,'action':'reused_complete_release','audit_passed_checks':audit_report.get('passed_checks')});continue
        if not state['native_ready']:
            log=io.StringIO()
            with contextlib.redirect_stdout(log):process_native(ROOT/'data/raw/gldas',directory,tile['bbox'],tile['id'])
            state=readiness(tile)
            if not state['native_ready']:raise ValueError('Native GLDAS processing did not produce a complete local tile')
        request_path=ROOT/'data/requests'/('fine_'+tile['id']+'.json')
        if not request_path.exists():
            request_path.parent.mkdir(parents=True,exist_ok=True)
            request_path.write_text(json.dumps({'tile_id':tile['id'],'bbox':tile['bbox'],
                'catalog':str((directory/'catalog.json').relative_to(ROOT)),'source':'MODIS/061/MOD13A3',
                'first_year':2003,'last_year':2024,'pilot_month':'2003-01-01'},indent=2)+'\n')
        request,catalog,digest=load_request(request_path)
        acquisition={}
        if not state['full_export_index_received'] or reprocess:
            if ee_client is None:
                import ee
                ee_client=ee
            pilot=fetch_sources(ee_client,project,request,catalog,digest,export_plan('pilot'),cache)
            for source in pilot['files']:validate(source['path'],catalog,expected_month='2003-01-01')
            acquisition['pilot_rows']=sum(source['rows'] for source in pilot['files'])
            acquisition['pilot_finite_rows']=sum(source['finite_values'] for source in pilot['files'])
            # A valid winter pilot can have no valid pixels. Never choose a new
            # month or a new tile based on finding a desired statistical signal.
            annual=fetch_sources(ee_client,project,request,catalog,digest,export_plan('years'),cache)
            acquisition['annual_source_files']=len(annual['files'])
            acquisition['ingestion']=ingest([source['path'] for source in annual['files']],directory,replace=replace)
        acquisition['statistics']=prepare(directory)
        audit_report=audit(directory)
        (directory/'release_audit.json').write_text(json.dumps(audit_report,indent=2,allow_nan=False)+'\n')
        if not audit_report['integrity_passed']:raise ValueError('Tile release audit failed; inspect '+str(directory/'release_audit.json'))
        report['tiles'].append({**readiness(tile),'action':'acquired_and_prepared',**acquisition})
    report['ready_tiles']=sum(t['ready'] for t in report['tiles'])
    report['requires_fetch_tiles']=sum(not t['full_export_index_received'] for t in report['tiles'])
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--registry',type=Path,default=ROOT/'data/processed/fine/tiles.json')
    p.add_argument('--project',default='earthrisk-greenmirage');p.add_argument('--tile',action='append')
    p.add_argument('--fetch',action='store_true');p.add_argument('--reprocess',action='store_true');p.add_argument('--replace',action='store_true');p.add_argument('--cache',type=Path,default=ROOT/'.cache/fine_modis_direct')
    args=p.parse_args(argv)
    if not args.project.strip():p.error('--project must be nonempty')
    if args.reprocess and not (args.fetch and args.replace):p.error('--reprocess requires --fetch --replace')
    if args.replace and not args.fetch:p.error('--replace requires --fetch')
    print(json.dumps(acquire(args.registry,args.project,fetch_requested=args.fetch,selected=args.tile,cache=args.cache,reprocess=args.reprocess,replace=args.replace),indent=2))

if __name__=='__main__':main()
