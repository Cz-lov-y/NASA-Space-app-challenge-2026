#!/usr/bin/env python3
"""Extract original native0.25-degree GLDAS cells for one bounded pilot tile."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np
import pandas as pd
import xarray as xr
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.regions import add_jurisdictions

LAYERS=('SoilMoi0_10cm_inst','SoilMoi10_40cm_inst','SoilMoi40_100cm_inst')
VARIABLES=('soil_water_0_10cm','soil_water_0_100cm')
BBOX=[-98,37,-97,38]


def extract_layers(ds,rows,cols,month):
    """Read native cells only, after verifying source coordinate orientation."""
    lat=np.asarray(ds.lat.values,dtype=float);lon=np.asarray(ds.lon.values,dtype=float)
    if ds.sizes.get('time')!=1 or pd.Timestamp(ds.time.values[0])!=pd.Timestamp(month):
        raise ValueError('Source month/time mismatch')
    if lat.shape!=(600,) or lon.shape!=(1440,) or not np.allclose(lat,np.arange(600)*.25-59.875,atol=1e-5) or not np.allclose(lon,np.arange(1440)*.25-179.875,atol=1e-5):
        raise ValueError('Unexpected GLDAS coordinates or orientation')
    arrays=[]
    # Paired advanced indices avoid reading or averaging an entire coarse region.
    for layer in LAYERS:
        var=ds[layer]
        if var.attrs.get('units')!='kg m-2' or var.attrs.get('cell_methods')!='time: mean':
            raise ValueError('Unexpected source units or time method')
        if var.encoding.get('scale_factor',1)!=1 or var.encoding.get('add_offset',0)!=0:
            raise ValueError('Unexpected source scaling')
        selected=var.isel(time=0,lat=xr.DataArray(rows,dims='cell'),lon=xr.DataArray(cols,dims='cell'))
        arrays.append(np.asarray(selected.values,dtype=float))
    return arrays[0],arrays[0]+arrays[1]+arrays[2]


def main(raw,out,bbox=BBOX,tile_id='central_us_1deg'):
    if (Path(out)/'accepted_modis_observations.csv').exists():
        raise ValueError('This fine release contains accepted MODIS data. Rebuild GLDAS into a separate --out directory and reimport archived MODIS sources before replacing the release.')
    from src.fine_grid import build_tile_catalog,parse_cell_id
    catalog=build_tile_catalog(bbox)
    if not 1<=len(catalog['features'])<=4096: raise ValueError('Process a bounded tile of at most4096native cells')
    features=catalog['features'];indices=[parse_cell_id(f['properties']['region_id']) for f in features]
    rows=[i[0] for i in indices];cols=[i[1] for i in indices]
    dates=pd.date_range('2003-01-01','2024-12-01',freq='MS')
    values=np.full((264,2,len(features)),np.nan);present=np.zeros(264,dtype=bool);manifest=[]
    for i,date in enumerate(dates):
        paths=list(Path(raw).glob(f'*A{date:%Y%m}.*.nc4'))
        if len(paths)>1: raise ValueError(f'Duplicate source month{date}')
        if not paths: continue
        path=paths[0]
        with xr.open_dataset(path,mask_and_scale=True) as ds:
            surface,total=extract_layers(ds,rows,cols,date)
            values[i,0]=surface;values[i,1]=total;present[i]=True
        manifest.append({'file':str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path.resolve()),
                         'date':date.strftime('%Y-%m-%d'),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    boundaries=ROOT/'data/processed/regional/naturalearth_countries.geojson'
    if boundaries.exists():catalog=add_jurisdictions(catalog,json.loads(boundaries.read_text()))
    records=[]
    for j,f in enumerate(features):
        p=f['properties'];rid=p['region_id'];p['grid_row'],p['grid_col']=indices[j]
        p.update(tile_id=tile_id,native_resolution_degrees=.25,ndvi_status='pending_export',
            data_status='pending_ndvi' if np.isfinite(values[:,:,j]).any() else 'unsupported_gldas',
            variables=list(VARIABLES),gldas_valid_months={v:int(np.isfinite(values[:,k,j]).sum()) for k,v in enumerate(VARIABLES)})
        p.setdefault('bbox',f['bbox'] if 'bbox' in f else None)
        if p.get('region_area_m2') is None:
            import math
            w,s,e,n=p['bbox'];p['region_area_m2']=6371007.181**2*math.radians(e-w)*(math.sin(math.radians(n))-math.sin(math.radians(s)))
        for i,date in enumerate(dates):
            for k,v in enumerate(VARIABLES):
                value=values[i,k,j];finite=bool(np.isfinite(value))
                flag=('negative_value' if value<0 else 'coverage_review_required') if finite else 'no_valid_pixels' if present[i] else 'missing'
                records.append({'date':date.strftime('%Y-%m-%d'),'value':value,'unit':'kg m-2','variable':v,
                    'source':'GLDAS_NOAH025_M.2.1','region_id':rid,'valid_area_fraction':float(finite) if present[i] else np.nan,
                    'valid_area_m2':p['region_area_m2']*float(finite) if present[i] else np.nan,'region_area_m2':p['region_area_m2'],
                    'quality_flag':flag,'grid_row':rows[j],'grid_col':cols[j]})
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    frame=pd.DataFrame(records)
    frame.to_csv(out/'gldas_monthly_timeseries.csv',index=False)
    frame.to_csv(out/'monthly_timeseries.csv',index=False)
    (out/'catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
    (out/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    quality=frame.groupby(['region_id','variable']).agg(expected_months=('value','size'),valid_months=('value','count'),min_coverage=('valid_area_fraction','min'),max_coverage=('valid_area_fraction','max'))
    quality['missing_months']=quality.expected_months-quality.valid_months;quality.to_csv(out/'quality_report.csv')
    metadata={'tile_id':tile_id,'bbox':bbox,'crs':'EPSG:4326','native_resolution_degrees':.25,
        'data_kind':'real NASA-derived native model grid cells; no synthetic observations',
        'dataset_version':'GLDAS_NOAH025_M.2.1','unit':'kg m-2','period':['2003-01-01','2024-12-01'],
        'cell_identity':'gldas025_r{row:03d}_c{col:04d}; row0south=-60; col0west=-180;600rows1440columns',
        'horizontal_method':'Read original GLDAS cell values by verified native indices; no spatial interpolation or splitting of10-degree means',
        'temporal_method':'Monthly source time: mean, retained without further temporal aggregation or filling',
        'soil_water_0_10cm':'Original SoilMoi0_10cm_inst cell',
        'soil_water_0_100cm':'Sum SoilMoi0_10cm_inst+SoilMoi10_40cm_inst+SoilMoi40_100cm_inst at same native cell; all three must be finite',
        'scaling':'CF missing values decoded; identity scale and zero offset verified; kgm-2 retained',
        'fill_missing':'CF source fills becomeNaN/blank CSV; no imputation; missing source months retained',
        'coverage':'For one native GLDAS cell valid area fraction is1or0; this is model support, not independent within-cell measurement coverage',
        'quality_rules':'Finite values remain coverage_review_required; negative values flagged; never automatically certify scientificQA',
        'ndvi':'Pending native MODIS pixel-area weighted aggregation into exact0.25-degree GLDAS footprints; no upsampling of soil data',
        'limitations':['Native model resolution is not a guarantee of independent observations between adjacent cells.',
            'Fine-tile findings cannot establish global hotspot coverage.','Common GLDAS/MODIS support and independent source-pixel checks remain pending.'],
        'reproduce':'python scripts/process_fine_gldas.py; source_manifest.json identifies exact original inputs'}
    if boundaries.exists():metadata['country_boundary_source']={'file':str(boundaries.relative_to(ROOT)),'sha256':hashlib.sha256(boundaries.read_bytes()).hexdigest(),'status':'coarse geographic candidates only'}
    (out/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    definition={'grid_id':'gldas025','crs':'EPSG:4326','resolution_degrees':.25,'rows':600,'columns':1440,
        'native_envelope':[-180,-60,180,90],'cell_count_in_envelope':864000,'cell_id':'gldas025_r{row:03d}_c{col:04d}',
        'orientation':'row0south=-60;rowincreasesnorth;col0west=-180;colincreaseseast',
        'support':'Envelope is not land availability; source valid masks determine actual support. Outside envelope is unsupported by GLDAS.',
        'storage':'Bounded tile catalogs and source reads; no eager864000-feature global JSON.',
        'pilot':{'tile_id':tile_id,'bbox':bbox,'catalog':str((out/'catalog.json').relative_to(ROOT)) if (out/'catalog.json').is_relative_to(ROOT) else str(out/'catalog.json')}}
    (out.parent/'grid_definition.json').write_text(json.dumps(definition,indent=2)+'\n')
    request={'tile_id':tile_id,'bbox':bbox,'catalog':str((out/'catalog.json').relative_to(ROOT)) if (out/'catalog.json').is_relative_to(ROOT) else str(out/'catalog.json'),
        'source':'MODIS/061/MOD13A3','target_grid':'GLDAS native0.25degree','first_year':2003,'last_year':2024,
        'pilot_month':'2003-01-01','qa_rule':'raw NDVI [-2000,10000]; (DetailedQA & 3)==0; SummaryQA==0',
        'native_projection_required':True,'soil_resampling':'none'}
    (ROOT/'data/requests'/f'fine_{tile_id}.json').write_text(json.dumps(request,indent=2)+'\n')
    print(f'{len(manifest)}realmonthlysourcefiles;{len(features)}nativecells;{len(frame)}rows;{frame.value.notna().sum()}finite;NDVIpending')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--raw',type=Path,default=ROOT/'data/raw/gldas')
    parser.add_argument('--out',type=Path,default=ROOT/'data/processed/fine/central_us')
    parser.add_argument('--bbox',type=float,nargs=4,default=BBOX);parser.add_argument('--tile-id',default='central_us_1deg')
    args=parser.parse_args();main(args.raw,args.out,args.bbox,args.tile_id)
