"""Resumable native MODIS retrieval for one selected GLDAS cell, without AI.

Only the existing authorized Earth Engine project is used. Each remote request
contains one cell and one calendar year, with a thirty-second service deadline.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
from threading import RLock
import uuid

import pandas as pd

from src.fine_grid import cell_feature,parse_cell_id
from src.regional_workflow import ROOT
from scripts.export_fine_modis_earth_engine import CALCULATION_VERSION
from scripts.export_regional_modis_earth_engine import export_plan
from scripts.fetch_fine_modis import fetch
from scripts.merge_fine_modis import validate_frame

PROJECT='earthrisk-greenmirage'
CACHE=ROOT/'.cache/global_modis'


def target(bundle):
    rid=bundle['region_id'];feature=cell_feature(*parse_cell_id(rid))
    if feature['geometry']!=bundle['feature']['geometry']:
        raise ValueError('MODIS target must retain exact native geometry')
    feature['properties']['tile_id']=rid
    catalog={'type':'FeatureCollection','features':[feature]}
    p=feature['properties']
    identity={'tile_id':rid,'source':'MODIS/061/MOD13A3','target_grid':'gldas025',
              'cells':[{'region_id':rid,'bbox':p['bbox'],'region_area_m2':p['region_area_m2'],'geometry':feature['geometry']}]}
    sha=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return catalog,sha


def _directory(bundle,cache_directory):
    return Path(cache_directory)/bundle['region_id']/CALCULATION_VERSION


def _atomic(path,payload):
    from tempfile import NamedTemporaryFile
    path.parent.mkdir(parents=True,exist_ok=True)
    with NamedTemporaryFile(dir=path.parent,delete=False) as stream:
        temporary=Path(stream.name);stream.write(payload)
    temporary.replace(path)


def cached_native_modis(bundle,*,cache_directory=CACHE):
    """Read only verified final source observations; None means not retrieved yet."""
    catalog,geometry_sha=target(bundle)
    directory=_directory(bundle,cache_directory);path=directory/'complete.json'
    if not path.exists():return None
    metadata=json.loads(path.read_text())
    if (metadata['region_id']!=bundle['region_id'] or metadata['target_geometry_sha256']!=geometry_sha
            or metadata['area_method']!=CALCULATION_VERSION or metadata['period']!=['2003-01-01','2024-12-01']):
        raise ValueError('Cached native MODIS identity mismatch')
    content=(directory/'monthly_ndvi.csv').read_bytes()
    if hashlib.sha256(content).hexdigest()!=metadata['csv_sha256']:
        raise ValueError('Cached native MODIS data checksum mismatch')
    for source in metadata['sources']:
        original=Path(source['path']).read_bytes()
        if hashlib.sha256(original).hexdigest()!=source['sha256']:
            raise ValueError('Cached annual MODIS source checksum mismatch')
    ndvi=validate_frame(pd.read_csv(io.BytesIO(content),dtype={'unit':str},float_precision='round_trip'),catalog)
    archived=[]
    for source in metadata['sources']:
        archived.append(validate_frame(pd.read_csv(source['path'],dtype={'unit':str},float_precision='round_trip'),catalog))
    if len(archived)!=22:
        raise ValueError('Cached native MODIS must retain22annual source records')
    original=pd.concat(archived,ignore_index=True).sort_values(['region_id','date']).reset_index(drop=True)
    retained=ndvi.sort_values(['region_id','date']).reset_index(drop=True)
    if set(original.columns)!=set(retained.columns) or not original.equals(retained.reindex(columns=original.columns)):
        raise ValueError('Cached native MODIS does not match archived annual source observations')
    months=set(pd.date_range('2003-01-01','2024-12-01',freq='MS').strftime('%Y-%m-%d'))
    if len(ndvi)!=264 or set(ndvi.date)!=months:
        raise ValueError('Cached MODIS must preserve264actual monthly slots')
    result=deepcopy(bundle)
    soil=result['observations'].loc[result['observations'].variable!='ndvi'].copy()
    ndvi['date']=pd.to_datetime(ndvi.date)
    row,col=parse_cell_id(bundle['region_id']);ndvi['grid_row']=row;ndvi['grid_col']=col
    result['observations']=pd.concat([soil,ndvi],ignore_index=True).sort_values(['variable','date']).reset_index(drop=True)
    result['provenance']['native_ndvi']=metadata
    result['provenance']['native_ndvi']['scientific_review']='Native-grid/sourceQA/area-method checks passed; independent cell pixel and footprint review pending'
    result['research_context']['dataset_version']=hashlib.sha256((result['research_context']['dataset_version']+metadata['csv_sha256']+CALCULATION_VERSION).encode()).hexdigest()
    valid=int(ndvi.value.notna().sum())
    result['availability']=deepcopy(result.get('availability',{}))
    result['availability'].update(ndvi_status='complete' if valid==264 else 'complete_with_missing',ndvi_valid_months=valid,
                                  ndvi_expected_months=264,ndvi_received_months=264)
    result['status']='native_indicators_available' if valid else 'native_ndvi_no_valid_pixels'
    result['feature']['properties']['variables']=['soil_water_0_10cm','soil_water_0_100cm','ndvi']
    result['feature']['properties']['ndvi_status']=result['availability']['ndvi_status']
    return result


def retrieve_native_modis(bundle,*,cache_directory=CACHE,project=PROJECT,progress=None,ee_module=None):
    """Fetch/resume22one-year requests, preserve receipts and never invent values."""
    if project!=PROJECT:raise ValueError('Use the existing authorized Earth Engine project only')
    ready=cached_native_modis(bundle,cache_directory=cache_directory)
    if ready is not None:return ready
    if not bundle['observations'].value.notna().any():
        raise ValueError('No valid native GLDAS data to pair')
    catalog,geometry_sha=target(bundle);rid=bundle['region_id']
    directory=_directory(bundle,cache_directory)
    if ee_module is None:
        import ee as ee_module
    sources=[]
    for i,item in enumerate(export_plan('years'),1):
        if progress:progress(completed_years=i-1,total_years=22,current_year=int(item['start'][:4]))
        result=fetch(ee_module,project,{'tile_id':rid},catalog,geometry_sha,[item],directory,deadline_seconds=30)
        sources.extend(result['files'])
        if progress:progress(completed_years=i,total_years=22,current_year=int(item['start'][:4]))
    frames=[pd.read_csv(record['path'],dtype={'unit':str},float_precision='round_trip') for record in sources]
    combined=validate_frame(pd.concat(frames,ignore_index=True),catalog)
    content=combined.to_csv(index=False).encode()
    metadata={'schema_version':'native-modis-cache-1','region_id':rid,'target_geometry_sha256':geometry_sha,
              'area_method':CALCULATION_VERSION,'period':['2003-01-01','2024-12-01'],
              'csv_sha256':hashlib.sha256(content).hexdigest(),'sources':sources,
              'retrieved_at':datetime.now(timezone.utc).isoformat(),'project':project,
              'missing_values':'Blank CSV/NaN; genuine missing/no_valid_pixels months retained; no interpolation',
              'unit':'1','dataset_version':'MOD13A3.061','qa_reviewed':False}
    _atomic(directory/'monthly_ndvi.csv',content)
    _atomic(directory/'complete.json',(json.dumps(metadata,indent=2,allow_nan=False)+'\n').encode())
    return cached_native_modis(bundle,cache_directory=cache_directory)


class NativeModisJobs:
    """One data worker, one queued cell, bounded history and per-selection dedupe."""
    def __init__(self,*,cache_directory=CACHE,runner=retrieve_native_modis):
        self.cache_directory=Path(cache_directory);self.runner=runner
        self.lock=RLock();self.executor=ThreadPoolExecutor(max_workers=1,thread_name_prefix='native-modis')
        self.jobs={};self.by_key={};self.closed=False
    @staticmethod
    def _key(bundle):
        context=bundle['research_context']
        version=context.get('raw_dataset_version',context['dataset_version'])
        return hashlib.sha256((bundle['region_id']+version).encode()).hexdigest()
    @staticmethod
    def _snapshot(job):
        return {k:deepcopy(job[k]) for k in ('request_id','region_id','context_key','state','completed_years','total_years','current_year','error_code','retryable')}
    def submit(self,bundle,*,retry=False):
        key=self._key(bundle)
        with self.lock:
            if self.closed:return {'state':'unavailable','error_code':'data_worker_closed','retryable':False}
            previous=self.by_key.get(key)
            if previous and (not retry or self.jobs[previous]['state'] not in ('failed',)):
                return self._snapshot(self.jobs[previous])
            if sum(not j['future'].done() for j in self.jobs.values())>=2:
                return {'state':'busy','error_code':'native_data_queue_busy','retryable':True}
            while len(self.jobs)>=32:
                old=next((rid for rid,j in self.jobs.items() if j['future'].done()),None)
                if old is None:break
                removed=self.jobs.pop(old)
                if self.by_key.get(removed['context_key'])==old:self.by_key.pop(removed['context_key'])
            rid=uuid.uuid4().hex
            job={'request_id':rid,'region_id':bundle['region_id'],'context_key':key,'state':'queued',
                 'completed_years':0,'total_years':22,'current_year':None,'error_code':None,'retryable':False}
            progress_path=_directory(bundle,self.cache_directory)/'progress.json'
            try:
                saved=json.loads(progress_path.read_text())
                if saved.get('region_id')==bundle['region_id'] and saved.get('context_key')==key:
                    completed=saved.get('completed_years',0)
                    if isinstance(completed,int) and 0<=completed<=22:job['completed_years']=completed
            except (OSError,ValueError,KeyError,TypeError):pass
            def persist():
                try:
                    payload=self._snapshot(job)
                    payload['updated_at']=datetime.now(timezone.utc).isoformat()
                    _atomic(progress_path,(json.dumps(payload,allow_nan=False)+'\n').encode())
                except OSError:pass  # Source receipts remain authoritative/replayable.
            def progress(**changes):
                with self.lock:
                    job.update(changes)
                    persist()
            def run():
                with self.lock:
                    job['state']='loading'
                    persist()
                try:
                    merged=self.runner(deepcopy(bundle),cache_directory=self.cache_directory,progress=progress)
                    from src.global_screening import screen_global_cell
                    save_screened_summary(screen_global_cell(merged),cache_directory=self.cache_directory)
                    with self.lock:
                        job.update(state='complete',completed_years=22,retryable=False)
                        persist()
                except Exception:
                    with self.lock:
                        job.update(state='failed',error_code='native_modis_unavailable',retryable=True)
                        persist()
            self.jobs[rid]=job;self.by_key[key]=rid
            persist()
            job['future']=self.executor.submit(run)
            return self._snapshot(job)
    def poll(self,request_id,*,region_id,context_key):
        with self.lock:
            job=self.jobs.get(request_id)
            if job is None:return {'state':'unknown','error_code':'unknown_data_job','retryable':True}
            if job['region_id']!=region_id or job['context_key']!=context_key:
                return {'state':'stale','error_code':'data_selection_changed','retryable':False}
            return self._snapshot(job)
    def close(self):
        with self.lock:self.closed=True
        self.executor.shutdown(wait=False,cancel_futures=True)


def save_screened_summary(bundle,*,cache_directory=CACHE):
    """Persist a compact single-cell screening snapshot; never a risk probability."""
    decision=(bundle.get('screening') or {}).get('screening') or {}
    props=bundle['feature']['properties']
    record={'type':'Feature','id':bundle['region_id'],'geometry':deepcopy(bundle['feature']['geometry']),
            'properties':{'region_id':bundle['region_id'],'bbox':props['bbox'],'centroid':props['centroid'],
            'classification':decision.get('classification','pending'),'category':decision.get('category'),
            'evidence_level':decision.get('evidence_level'),'confidence_label':decision.get('confidence_label'),
            'probability':None,'provisional':True,'qa_reviewed':False,'globally_adjusted':False,
            'family_scope':'single-cell exploratory; not adjusted across regions',
            'dataset_version':bundle['research_context']['dataset_version'],
            'saved_at':datetime.now(timezone.utc).isoformat()}}
    _atomic(_directory(bundle,cache_directory)/'screening_summary.json',(json.dumps(record,allow_nan=False)+'\n').encode())


def screened_summaries(*,cache_directory=CACHE,limit=1000,offset=0):
    """Read only compact persisted snapshots; never read source grids or run EE."""
    files=sorted(Path(cache_directory).glob('gldas025_*/'+CALCULATION_VERSION+'/screening_summary.json'))
    selected=[]
    for path in files[offset:offset+limit]:
        try:
            record=json.loads(path.read_text());rid=record['id']
            canonical=cell_feature(*parse_cell_id(rid))
            if record['geometry']!=canonical['geometry'] or record['properties'].get('probability') is not None:
                continue
            selected.append(record)
        except (OSError,ValueError,KeyError,TypeError):continue
    return {'type':'FeatureCollection','schema_version':'global-screened-cells-1','features':selected,
            'total':len(files),'offset':offset,'limit':limit,'has_more':offset+limit<len(files),
            'limitations':['Cached per-cell snapshots; current sources are checked when a cell is selected.',
                          'Single-cell exploratory classifications are not adjusted across regions; probability is not calibrated.']}


BATCH_INDEX=ROOT/'data/processed/fine/global/index.json'


def _batch_records(index_path=BATCH_INDEX):
    path=Path(index_path)
    if not path.is_file():return {}
    index=json.loads(path.read_text())
    if index.get('schema_version')!='global-native-tile-index-1' or index.get('calculation_version')!=CALCULATION_VERSION:
        return {}
    return {key:value for key,value in index.get('tiles',{}).items()
            if value.get('ready') and value.get('calculation_version')==CALCULATION_VERSION}


def _batch_id(region_id):
    row,col=parse_cell_id(region_id)
    return f'global_r{row//4:03d}_c{col//4:03d}'


def batch_tile_directory(region_id,*,index_path=BATCH_INDEX):
    """Find completed source shard metadata; no download or full-world expansion."""
    record=_batch_records(index_path).get(_batch_id(region_id))
    if record is None:return None
    candidate=Path(record['directory'])
    directory=(candidate if candidate.is_absolute() else ROOT/candidate).resolve()
    if not directory.is_relative_to((ROOT/'data/processed/fine').resolve()):
        raise ValueError('Unsafe global source tile directory')
    from src.fine_workflow import fine_map
    payload=fine_map(directory=directory)
    if region_id not in {f['id'] for f in payload['features']}:
        raise ValueError('Completed global tile does not contain requested native cell')
    return directory


def all_screened_summaries(*,cache_directory=CACHE,index_path=BATCH_INDEX,limit=1000,offset=0):
    """Page compact single-cell snapshots and completed batch map shards only."""
    from src.fine_workflow import fine_map
    batches=_batch_records(index_path)
    registry=ROOT/'data/processed/fine/tiles.json'
    reserved={tuple(t['bbox']) for t in json.loads(registry.read_text()).get('tiles',[])} if registry.is_file() else set()
    batches={key:value for key,value in batches.items() if tuple(value.get('bbox',[])) not in reserved}
    paths=sorted(Path(cache_directory).glob('gldas025_*/'+CALCULATION_VERSION+'/screening_summary.json'))
    paths=[p for p in paths if _batch_id(p.parent.parent.name) not in batches]
    # Fixed native 1-degree batch shards have16cells. Only shards intersecting
    # this bounded page are read; complete global geometry is never expanded.
    total=len(paths)+16*len(batches);features=[]
    for path in paths[offset:min(len(paths),offset+limit)]:
        try:
            record=json.loads(path.read_text());canonical=cell_feature(*parse_cell_id(record['id']))
            if record['geometry']==canonical['geometry'] and record['properties'].get('probability') is None:
                features.append(record)
        except (OSError,ValueError,KeyError,TypeError):continue
    batch_offset=max(0,offset-len(paths))
    batch_end=max(0,offset+limit-len(paths))
    for number,(key,record) in enumerate(sorted(batches.items())):
        start=number*16;end=start+16
        if end<=batch_offset:continue
        if start>=batch_end:break
        try:
            candidate=Path(record['directory']);directory=(candidate if candidate.is_absolute() else ROOT/candidate).resolve()
            if not directory.is_relative_to((ROOT/'data/processed/fine').resolve()):continue
            payload=fine_map(directory=directory)
            selected=payload['features'][max(0,batch_offset-start):min(16,batch_end-start)]
            for feature in selected:
                feature['properties'].update(probability=None,globally_adjusted=False,
                    family_scope='single-tile exploratory; not worldwide adjusted',provisional=True,qa_reviewed=False)
            features.extend(selected)
        except (OSError,ValueError,KeyError,TypeError):continue
    return {'type':'FeatureCollection','schema_version':'global-screened-cells-1','features':features,
            'total':total,'offset':offset,'limit':limit,'has_more':offset+limit<total,
            'limitations':['Cached per-cell/per-tile snapshots; current cell sources are checked on selection.',
                'Batch tile and individual-cell testing families are exploratory; no worldwide adjustment or calibrated harm probability.']}
