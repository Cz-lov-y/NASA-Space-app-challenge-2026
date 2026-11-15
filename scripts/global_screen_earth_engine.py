#!/usr/bin/env python3
"""Automatic worldwide native-grid alignment using bounded exact-source jobs.

Enumerates all 1-degree tiles of the GLDAS native envelope automatically. Local
source masks avoid requests for fill-only tiles. Each supported tile follows the
existing exact MODIS native-pixel sphere-area method: pilot,22annual requests,
immutable source archive, monthly merge, statistics and map shard. No source
interpolation, 3-hourly soil substitution, probability invention or export tasks.
Default is a local plan; --fetch explicitly permits sequential authenticated work.
"""
from pathlib import Path
import argparse
from datetime import datetime,timezone
import io
import json
import shutil
import sys
import numpy as np
import xarray as xr
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.global_cell_data import _source_release,_atomic
from src.fine_grid import parse_cell_id
from scripts.acquire_fine_tiles import acquire,readiness,load_tiles
from scripts.export_fine_modis_earth_engine import CALCULATION_VERSION
from scripts.fetch_fine_modis import grouped_year_plan


def tile_for_cell(region_id):
    row,col=parse_cell_id(region_id);r,c=row//4,col//4
    return {'id':f'global_r{r:03d}_c{c:03d}','bbox':[-180+c,-60+r,-179+c,-59+r]}


def supported_tiles(raw_directory,cache_directory):
    """Union actual native model support across all available required months."""
    raw=Path(raw_directory);cache=Path(cache_directory)
    by_month,release=_source_release(raw,cache,False)
    path=cache/('native_support_'+release['source_sha256']+'.npz')
    if path.exists():
        with np.load(path,allow_pickle=False) as stored:mask=stored['support']
        if mask.shape!=(600,1440):raise ValueError('Unexpected cached native support shape')
    else:
        mask=np.zeros((600,1440),dtype=bool)
        for source in by_month.values():
            with xr.open_dataset(source,mask_and_scale=True) as ds:
                if ds.sizes.get('lat')!=600 or ds.sizes.get('lon')!=1440:raise ValueError('Unexpected native GLDAS dimensions')
                if not np.allclose(ds.lat.values,np.arange(600)*.25-59.875) or not np.allclose(ds.lon.values,np.arange(1440)*.25-179.875):
                    raise ValueError('Unexpected native GLDAS orientation')
                arrays=[np.asarray(ds[name].isel(time=0).transpose('lat','lon').values) for name in
                    ['SoilMoi0_10cm_inst','SoilMoi10_40cm_inst','SoilMoi40_100cm_inst']]
                mask |= np.isfinite(arrays[0]) | (np.isfinite(arrays[0]) & np.isfinite(arrays[1]) & np.isfinite(arrays[2]))
        buffer=io.BytesIO();np.savez_compressed(buffer,support=mask);_atomic(path,buffer.getvalue())
    tiled=mask.reshape(150,4,360,4).any(axis=(1,3))
    return tiled,{'source_release_sha256':release['source_sha256'],'source_months_available':len(by_month),
        'source_native_cells_with_any_soil_data':int(mask.sum()),'supported_1deg_tiles':int(tiled.sum()),
        'geometric_1deg_tiles':54000,'support_method':'Union of finite original0-10cm or finite three-layer0-100cm native cells over available2003-2024inputs'}


def iter_tiles(supported,bbox=None):
    """Lazy bounded partition; never expands a million-feature world GeoJSON."""
    for r,c in zip(*np.where(supported)):
        south,west=-60+int(r),-180+int(c);bounds=[west,south,west+1,south+1]
        if bbox is not None:
            w,s,e,n=bbox
            if not (bounds[0]<e and bounds[2]>w and bounds[1]<n and bounds[3]>s):continue
        yield {'id':f'global_r{r:03d}_c{c:03d}','name':f'Native GLDAS tile{west},{south}',
            'bbox':bounds,'directory':f'data/processed/fine/global/global_r{r:03d}_c{c:03d}'}



def prioritize_north_america(jobs, boundary_path):
    """Visit tiles intersecting Canada or the US before all remaining tiles."""
    from shapely.geometry import shape, box
    from shapely.ops import unary_union
    from shapely.prepared import prep
    collection=json.loads(Path(boundary_path).read_text())
    features=[shape(f['geometry']) for f in collection['features']
              if f.get('properties',{}).get('ISO_A3') in {'CAN','USA','PRI'}]
    if len(features)!=3:
        raise ValueError('Canada, US, or Puerto Rico boundary is missing')
    boundary=prep(unary_union(features))
    priority=[];remaining=[]
    for job in jobs:
        (priority if boundary.intersects(box(*job['bbox'])) else remaining).append(job)
    return priority+remaining, len(priority)


def prioritize_southern_alberta(jobs, boundary_path):
    """Move Alberta tiles south of 52.5 N first; preserve remaining order."""
    from shapely.geometry import shape, box
    collection=json.loads(Path(boundary_path).read_text())
    matches=[feature for feature in collection['regions']
             if feature.get('name')=='Alberta' and feature.get('country')=='Canada']
    if len(matches)!=1:raise ValueError('Alberta boundary is unavailable or ambiguous')
    south=shape(matches[0]['geometry']).intersection(box(-180,49,180,52.5))
    if south.is_empty:raise ValueError('Southern Alberta boundary is empty')
    priority=[];remaining=[]
    for job in jobs:
        (priority if south.intersection(box(*job['bbox'])).area>0 else remaining).append(job)
    return priority+remaining,len(priority)

def existing_tiles(registry):
    path=Path(registry)
    if not path.exists():return {}
    return {tuple(t['bbox']):t for t in json.loads(path.read_text()).get('tiles',[])}


def run(*,project='tactical-attic-456217-t0',raw_directory=ROOT/'data/raw/gldas',
        cache_directory=ROOT/'.cache/global_screen',fetch=False,bbox=None,max_tiles=None,
        reprocess=False,replace=False,min_free_gib=20,years_per_request=1,priority_north_america=False,priority_southern_alberta=False,request_workers=1):
    if isinstance(request_workers,bool) or not isinstance(request_workers,int) or not 1<=request_workers<=16:raise ValueError('--request-workers must be1to16')
    if not np.isfinite(min_free_gib) or min_free_gib<0:raise ValueError('--min-free-gib must be finite and nonnegative')
    if max_tiles is not None and max_tiles<1:raise ValueError('--max-tiles must be positive')
    if reprocess and not (fetch and replace):raise ValueError('--reprocess requires --fetch --replace')
    request_count=len(grouped_year_plan(years_per_request=years_per_request))
    supported,support=supported_tiles(raw_directory,cache_directory)
    existing=existing_tiles(ROOT/'data/processed/fine/tiles.json')
    jobs=list(iter_tiles(supported,bbox))
    priority_count=0
    if priority_north_america or priority_southern_alberta:
        jobs,priority_count=prioritize_north_america(jobs,ROOT/'data/processed/regional/naturalearth_countries.geojson')
    alberta_count=0
    if priority_southern_alberta:
        jobs,alberta_count=prioritize_southern_alberta(jobs,ROOT/'frontend/public/data/geography.json')
    report={'mode':'acquire' if fetch else 'dry_plan','project':project,'calculation_version':CALCULATION_VERSION,
        'grid':'Native GLDAS0.25degrees; exact16cell1degree jobs','native_envelope':[-180,-60,180,90],
        'support':support,'selected_supported_tiles':len(jobs),'annual_requests_before_cache':len(jobs)*request_count,'years_per_request':years_per_request,
        'pilot_requests_before_cache':len(jobs),'max_tiles_this_run':max_tiles,'export_tasks_submitted':0,
        'priority':'Southern Alberta, then Canada, US and Puerto Rico' if priority_southern_alberta else 'Canada, US and Puerto Rico first' if priority_north_america else 'native grid order',
        'southern_alberta_tiles':alberta_count,
        'priority_tiles':priority_count,'request_workers':request_workers,
        'worldwide_paired_complete':False,'worldwide_testing_family_complete':False,
        'statistical_scope':'Per-tile provisional screening; no worldwide BH claim or risk probability',
        'completed_tiles':[],'failed_tiles':[],'stop_reason':None,'minimum_free_gib':min_free_gib,'release_audit_status':'deferred_for_demo','reused_index_tiles':0}
    if not fetch:
        report['next_step']='Run with --fetch --max-tiles1 for a bounded pilot, or --fetch to iterate all supported tiles. Full acquisition is substantial under the existing quota.'
        report['example_tiles']=jobs[:3];return report
    root_output=ROOT/'data/processed/fine/global';root_output.mkdir(parents=True,exist_ok=True)
    index_path=root_output/'index.json';index=json.loads(index_path.read_text()) if index_path.exists() else {'schema_version':'global-native-tile-index-1','tiles':{}}
    fingerprint_changed=index.get('source_release_sha256') not in {None,support['source_release_sha256']}
    if fingerprint_changed:raise ValueError('Local source release changed; explicit global index migration required')
    index.setdefault('failed_tiles',{})
    index.update(source_release_sha256=support['source_release_sha256'],calculation_version=CALCULATION_VERSION,
        native_resolution_degrees=.25,supported_tiles_expected=int(supported.sum()),worldwide_testing_family_complete=False,
        statistical_scope=report['statistical_scope'])
    cache=Path(cache_directory);cache.mkdir(parents=True,exist_ok=True)
    index['completed_supported_tiles']=sum(t.get('ready') and t.get('calculation_version')==CALCULATION_VERSION for t in index['tiles'].values())
    index['worldwide_paired_complete']=index['completed_supported_tiles']==int(supported.sum()) and not index['failed_tiles']
    processed=0
    for job in jobs:
        if max_tiles is not None and processed>=max_tiles:break
        alias=existing.get(tuple(job['bbox']))
        acquisition_job=alias if alias is not None else job
        # One compact registry is enough for the existing complete source pipeline.
        registry_path=cache/'current_tile.json'
        _atomic(registry_path,(json.dumps({'schema_version':'fine-tiles-1','tiles':[acquisition_job]},indent=2)+'\n').encode())
        try:
            selected=load_tiles(registry_path)[0];state=readiness(selected)
        except (ValueError,KeyError,TypeError,OSError):
            # Let the acquisition stage below record the tile-specific error.
            state={'ready':False}
        previous=index['tiles'].get(job['id'],{})
        if state['ready'] and not reprocess and previous.get('ready') and previous.get('calculation_version')==CALCULATION_VERSION:
            # Resume checkpoint plus current source/catalog hashes avoid spending
            # a bounded pilot budget on already completed tiles.
            report['reused_index_tiles']+=1
            continue
        free_gib=shutil.disk_usage(ROOT).free/(1024**3)
        if free_gib<min_free_gib:
            report['stop_reason']='low_disk_space';report['available_free_gib']=free_gib
            index['last_stop_reason']='low_disk_space';index['worldwide_paired_complete']=False
            _atomic(index_path,(json.dumps(index,indent=2)+'\n').encode())
            break
        try:
            result=acquire(registry_path,project,fetch_requested=True,cache=ROOT/'.cache/fine_modis_direct',
                reprocess=reprocess,replace=replace,audit_required=False,years_per_request=years_per_request,request_workers=request_workers)
        except Exception as exc:
            message=str(exc)
            failure={'id':job['id'],'bbox':job['bbox'],'error_type':type(exc).__name__,
                'message':message[:500],'attempts':index['failed_tiles'].get(job['id'],{}).get('attempts',0)+1,
                'updated_at_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z')}
            index['failed_tiles'][job['id']]=failure;report['failed_tiles'].append(failure);processed+=1
            # Keep a previously completed tile from counting as current after a
            # failed explicit reprocessing attempt.
            if job['id'] in index['tiles']:index['tiles'][job['id']]['ready']=False
            lower=message.lower()
            systemic=isinstance(exc,(FileNotFoundError,OSError)) or any(word in lower for word in
                ['quota','429','too many concurrent aggregations','permission','credential','authenticate','unexpected gldas','unexpected source units','unexpected source scaling','source month/time'])
            if systemic:report['stop_reason']='source_or_service_blocked';index['last_stop_reason']=report['stop_reason']
            index['worldwide_paired_complete']=False
            _atomic(index_path,(json.dumps(index,indent=2)+'\n').encode())
            if systemic:break
            continue
        tile=result['tiles'][0]
        directory=tile['directory']
        index['failed_tiles'].pop(job['id'],None)
        index['tiles'][job['id']]={'id':job['id'],'source_tile_id':acquisition_job['id'],'bbox':job['bbox'],
            'directory':directory,'ready':tile['ready'],'calculation_version':CALCULATION_VERSION,
            'map':str(Path(directory)/'map_screening.geojson'),'statistics':str(Path(directory)/'screening.json'),
            'release_audit_status':'deferred_for_demo','ndvi_valid_rows':tile['ndvi_valid_rows'],'ndvi_required_rows':tile['ndvi_required_rows'],
            'updated_at_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z')}
        index['completed_supported_tiles']=sum(t.get('ready') and t.get('calculation_version')==CALCULATION_VERSION for t in index['tiles'].values())
        index['worldwide_paired_complete']=index['completed_supported_tiles']==int(supported.sum()) and not index['failed_tiles']
        _atomic(index_path,(json.dumps(index,indent=2)+'\n').encode())
        report['completed_tiles'].append(index['tiles'][job['id']]);processed+=1
    report['index']=str(index_path.relative_to(ROOT));report['worldwide_paired_complete']=index.get('worldwide_paired_complete',False)
    report['global_resume']='Rerun the same command; verified existing tile releases and yearly request receipts are reused.'
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',default='tactical-attic-456217-t0')
    p.add_argument('--raw',type=Path,default=ROOT/'data/raw/gldas');p.add_argument('--cache',type=Path,default=ROOT/'.cache/global_screen')
    p.add_argument('--fetch',action='store_true');p.add_argument('--max-tiles',type=int);p.add_argument('--bbox',type=float,nargs=4)
    p.add_argument('--priority-north-america',action='store_true');p.add_argument('--priority-southern-alberta',action='store_true');p.add_argument('--request-workers',type=int,default=1);p.add_argument('--years-per-request',type=int,default=1);p.add_argument('--reprocess',action='store_true');p.add_argument('--replace',action='store_true');p.add_argument('--min-free-gib',type=float,default=20)
    a=p.parse_args(argv)
    if not a.project.strip():p.error('--project must be nonempty')
    if a.bbox is not None:
        w,s,e,n=a.bbox
        if not(-180<=w<e<=180 and -60<=s<n<=90):p.error('--bbox must be a positive rectangle inside the GLDAS native envelope')
    result=run(project=a.project,raw_directory=a.raw,cache_directory=a.cache,fetch=a.fetch,bbox=a.bbox,
        max_tiles=a.max_tiles,reprocess=a.reprocess,replace=a.replace,min_free_gib=a.min_free_gib,years_per_request=a.years_per_request,priority_north_america=a.priority_north_america,priority_southern_alberta=a.priority_southern_alberta,request_workers=a.request_workers)
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
