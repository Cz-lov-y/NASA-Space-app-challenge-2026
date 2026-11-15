"""Real native GLDAS cell reads anywhere in its envelope; per-cell disk cache.

Geometry is not availability. Oceans/fill-only cells remain unsupported and no
NDVI is fabricated or borrowed from a coarse regional average. No account calls.
"""
from pathlib import Path
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import io
import json
import re
import numpy as np
import pandas as pd
import xarray as xr
from src.fine_grid import cell_feature,index_for_coordinate,parse_cell_id
from src.regions import add_jurisdictions
from scripts.process_fine_gldas import extract_layers

ROOT=Path(__file__).resolve().parents[1]
METHOD='gldas025_native_on_demand_v1'
DATES=pd.date_range('2003-01-01','2024-12-01',freq='MS')
VARIABLES=('soil_water_0_10cm','soil_water_0_100cm')


def locate_cell(lon,lat):
    """Resolve native geometry without claiming source/land data are available."""
    if isinstance(lon,bool) or isinstance(lat,bool) or not np.isfinite(float(lon)) or not np.isfinite(float(lat)):
        raise ValueError('Longitude and latitude must be finite numbers')
    lon,lat=float(lon),float(lat)
    if not -180<=lon<=180 or not -90<=lat<=90:raise ValueError('Coordinates outside geographic bounds')
    if lat < -60:
        return {'region_id':None,'bbox':None,'centroid':[lon,lat],'status':'outside_gldas_extent',
            'native_resolution_degrees':.25,'crs':'EPSG:4326','native_envelope':[-180,-60,180,90]}
    row,col=index_for_coordinate(lon,lat);feature=cell_feature(row,col);p=feature['properties']
    return {'region_id':p['region_id'],'bbox':p['bbox'],'centroid':p['centroid'],
        'status':'native_cell_available_on_request','native_resolution_degrees':.25,'crs':'EPSG:4326',
        'native_envelope':[-180,-60,180,90]}


def _atomic(path,content):
    path.parent.mkdir(parents=True,exist_ok=True)
    import tempfile
    with tempfile.NamedTemporaryFile(dir=path.parent,prefix=path.name+'.',delete=False) as handle:
        temporary=Path(handle.name);handle.write(content)
    temporary.replace(path)


def _source_release(raw,cache,refresh):
    if not raw.is_dir():raise FileNotFoundError('Local raw GLDAS source directory is unavailable')
    by_month={}
    for path in sorted(raw.glob('*.nc4')):
        match=re.search(r'\.A(\d{6})\.',path.name)
        if not match:continue
        date=pd.to_datetime(match.group(1),format='%Y%m')
        if not DATES[0]<=date<=DATES[-1]:continue
        key=date.strftime('%Y-%m-%d')
        if key in by_month:raise ValueError('Duplicate GLDAS native source month')
        by_month[key]=path
    if not by_month:raise FileNotFoundError('No local GLDAS monthly files are available for2003-2024')
    inventory=[]
    for date,path in sorted(by_month.items()):
        stat=path.stat();inventory.append({'date':date,'file':str(path.resolve()),'size':stat.st_size,'mtime_ns':stat.st_mtime_ns})
    inventory_key=hashlib.sha256(json.dumps(inventory,sort_keys=True).encode()).hexdigest()
    path=cache/'_source_release.json'
    if path.exists() and not refresh:
        previous=json.loads(path.read_text())
        if previous.get('inventory_sha256')==inventory_key:return by_month,previous
    sources=[{**item,'sha256':hashlib.sha256(Path(item['file']).read_bytes()).hexdigest()} for item in inventory]
    source_sha=hashlib.sha256(json.dumps([{k:r[k] for k in ['date','sha256']} for r in sources],sort_keys=True).encode()).hexdigest()
    release={'inventory_sha256':inventory_key,'source_sha256':source_sha,'sources':sources,'method':METHOD}
    _atomic(path,(json.dumps(release,indent=2)+'\n').encode())
    return by_month,release


def _geography(feature,boundary):
    if not boundary.exists():return feature,None
    content=boundary.read_bytes();catalog={'type':'FeatureCollection','features':[feature]}
    add_jurisdictions(catalog,json.loads(content))
    return catalog['features'][0],hashlib.sha256(content).hexdigest()


def load_global_cell(region_id,*,raw_directory=ROOT/'data/raw/gldas',cache_directory=ROOT/'.cache/global_cells',refresh=False):
    """Return an existing-workflow-compatible bundle containing528native rows.

    First access hashes the264source inputs once and reads this cell from each
    available month. Further cells reuse release hashes; repeat clicks reuse
    verified cached observations. Missing source files/values remain missing.
    """
    row,col=parse_cell_id(region_id);raw=Path(raw_directory);cache=Path(cache_directory)
    by_month,release=_source_release(raw,cache,refresh)
    feature=cell_feature(row,col)
    feature,boundary_sha=_geography(feature,ROOT/'data/processed/regional/naturalearth_countries.geojson')
    p=feature['properties'];area=p['region_area_m2'];directory=cache/region_id
    fingerprint=hashlib.sha256((METHOD+region_id+release['source_sha256']+str(boundary_sha)).encode()).hexdigest()
    manifest_path=directory/'cache_manifest.json';csv_path=directory/'monthly_timeseries.csv';meta_path=directory/'metadata.json'
    cache_hit=False
    if manifest_path.exists() and csv_path.exists() and meta_path.exists() and not refresh:
        manifest=json.loads(manifest_path.read_text())
        if manifest.get('dataset_version')==fingerprint:
            csv_content=csv_path.read_bytes();meta_content=meta_path.read_bytes()
            if hashlib.sha256(csv_content).hexdigest()!=manifest['csv_sha256'] or hashlib.sha256(meta_content).hexdigest()!=manifest['metadata_sha256']:
                raise ValueError('Global native cell cache integrity failure; explicitly refresh after inspection')
            frame=pd.read_csv(io.BytesIO(csv_content),dtype={'unit':str},float_precision='round_trip')
            metadata=json.loads(meta_content);cache_hit=True
    if not cache_hit:
        records=[]
        for date in DATES:
            key=date.strftime('%Y-%m-%d');path=by_month.get(key)
            values=[np.nan,np.nan]
            if path is not None:
                with xr.open_dataset(path,mask_and_scale=True) as ds:
                    surface,total=extract_layers(ds,[row],[col],date);values=[float(surface[0]),float(total[0])]
            for variable,value in zip(VARIABLES,values):
                finite=bool(np.isfinite(value))
                flag=('negative_value' if value<0 else 'coverage_review_required') if finite else 'no_valid_pixels' if path else 'missing'
                records.append({'date':key,'value':value,'unit':'kg m-2','variable':variable,'source':'GLDAS_NOAH025_M.2.1',
                    'region_id':region_id,'quality_flag':flag,'valid_area_fraction':float(finite) if path else np.nan,
                    'valid_area_m2':area*float(finite) if path else np.nan,'region_area_m2':area,'grid_row':row,'grid_col':col})
        frame=pd.DataFrame(records)
        generated=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
        metadata={'dataset_version':fingerprint,'product':'GLDAS_NOAH025_M.2.1','processing_version':METHOD,
            'data_kind':'Real NASA-derived native GLDAS model cells; no synthetic values or spatial interpolation',
            'spatial_coverage':{'bbox':p['bbox'],'crs':'EPSG:4326','native_resolution_degrees':.25,'grid_row':row,'grid_col':col},
            'time_range':{'start':'2003-01-01','end':'2024-12-01'},'temporal_resolution':'monthly source time: mean; no extra temporal aggregation',
            'unit':'kg m-2','quality_control':{'status':'provisional','qa_reviewed':False,'fill':'CF fill values becomeNaN/blank CSV; no imputation',
                'rules':'Native source coordinates/time/units/identity scaling checked;0-100cm sums3finite same-cell layers',
                'coverage':'1meansvalid native modeled cell, not independent observed land coverage'},
            'source_release_sha256':release['source_sha256'],'source_months_available':len(by_month),'source_manifest':'source_manifest.json',
            'local_processed_at_utc':generated,'ndvi_status':'pending_native_aggregation','geography_boundary_sha256':boundary_sha,
            'limitations':['Native GLDAS envelope is not a land availability mask.','No native-cell NDVI has been acquired by this lookup; paired divergence is unavailable.',
                'A soil-only trend is not paired greening/drying evidence or validated ecological risk.','Country intersections are coarse geographic candidates, not legal authority.']}
        csv_content=frame.to_csv(index=False).encode();meta_content=(json.dumps(metadata,indent=2)+'\n').encode()
        _atomic(csv_path,csv_content);_atomic(meta_path,meta_content)
        _atomic(directory/'source_manifest.json',(json.dumps(release['sources'],indent=2)+'\n').encode())
        manifest={'dataset_version':fingerprint,'csv_sha256':hashlib.sha256(csv_content).hexdigest(),'metadata_sha256':hashlib.sha256(meta_content).hexdigest()}
        _atomic(manifest_path,(json.dumps(manifest,indent=2)+'\n').encode())
    counts={v:int(frame.loc[frame.variable==v,'value'].notna().sum()) for v in VARIABLES}
    any_valid=any(counts.values());status='soil_only_pending_ndvi' if any_valid else 'unsupported_gldas'
    p.update(data_status=status,variables=list(VARIABLES),gldas_valid_months=counts,ndvi_status='pending_native_aggregation')
    frame['date']=pd.to_datetime(frame.date);frame.attrs['metadata']=deepcopy(metadata)
    availability={'status':status,'valid_months':counts,'expected_months':264,'ndvi_status':'pending_native_aggregation',
        'source_months_available':metadata['source_months_available'],'qa_reviewed':False}
    return {'region_id':region_id,'feature':feature,'observations':frame,'provenance':metadata,
        'screening':None,'screening_status':'pending_ndvi','status':status,'availability':availability,'cache_hit':cache_hit,
        'research_context':{'region_id':region_id,'bbox':p['bbox'],'jurisdictions':deepcopy(p.get('jurisdictions',[])),
            'dataset_version':fingerprint,'period':['2003-01-01','2024-12-31']}}
