#!/usr/bin/env python3
"""Compute real monthly 10-degree GLDAS storage; preserve missing observations."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.regions import RADIUS_M, make_grid, add_jurisdictions

LAYERS = ('SoilMoi0_10cm_inst', 'SoilMoi10_40cm_inst', 'SoilMoi40_100cm_inst')
VARIABLES = ('soil_water_0_10cm', 'soil_water_0_100cm')


def regional_sums(values, lat):
    """Exact sphere cell area; source grid aligns with every 10-degree edge."""
    if values.shape != (600,1440):
        raise ValueError('Expected the 600 by 1440 GLDAS grid')
    weights = RADIUS_M**2 * np.deg2rad(.25) * (np.sin(np.deg2rad(lat + .125)) - np.sin(np.deg2rad(lat - .125)))
    valid = np.isfinite(values)
    def blocks(a):
        return a.reshape(15,40,36,40).sum(axis=(1,3))
    numerator = blocks(np.where(valid, values, 0) * weights[:,None])
    denominator = blocks(valid * weights[:,None])
    negative = blocks((valid & (values < 0)).astype(int)) > 0
    means = np.divide(numerator, denominator, out=np.full_like(numerator,np.nan), where=denominator>0)
    # First three latitude bands are below GLDAS's -60-degree limit.
    return (np.pad(means, ((3,0),(0,0)), constant_values=np.nan).ravel(),
            np.pad(denominator, ((3,0),(0,0))).ravel(),
            np.pad(negative, ((3,0),(0,0))).ravel())


def main(raw, out):
    out.mkdir(parents=True,exist_ok=True)
    grid = make_grid()
    boundaries = out/'naturalearth_countries.geojson'
    if boundaries.exists():
        grid = add_jurisdictions(grid,json.loads(boundaries.read_text()))
    (ROOT/'data/regions/grid_10deg.geojson').write_text(json.dumps(grid,indent=2)+'\n')
    dates = pd.date_range('2003-01-01','2024-12-01',freq='MS')
    means = np.full((len(dates),2,648),np.nan)
    areas = np.zeros_like(means)
    negatives = np.zeros(means.shape,dtype=bool)
    manifest=[]
    for i, date in enumerate(dates):
        paths = list(raw.glob(f'*A{date:%Y%m}.*.nc4'))
        if len(paths)>1: raise ValueError(f'Duplicate month {date}')
        if not paths: continue
        path=paths[0]
        with xr.open_dataset(path,mask_and_scale=True) as ds:
            if ds.sizes.get('time')!=1 or pd.Timestamp(ds.time.values[0])!=date:
                raise ValueError(f'Wrong time in {path}')
            lat,lon=np.asarray(ds.lat.values,dtype=float),np.asarray(ds.lon.values,dtype=float)
            if lat.shape!=(600,) or lon.shape!=(1440,) or not np.allclose(lat,np.arange(600)*.25-59.875,atol=1e-5) or not np.allclose(lon,np.arange(1440)*.25-179.875,atol=1e-5):
                raise ValueError('Unexpected grid coordinates')
            layers=[]
            for layer in LAYERS:
                var=ds[layer]
                if var.attrs.get('units')!='kg m-2' or var.attrs.get('cell_methods')!='time: mean': raise ValueError('Unexpected GLDAS metadata')
                if var.encoding.get('scale_factor',1)!=1 or var.encoding.get('add_offset',0)!=0: raise ValueError('Unexpected scaling')
                layers.append(np.asarray(var.isel(time=0).transpose('lat','lon').values,dtype=float))
            for v,values in enumerate((layers[0],layers[0]+layers[1]+layers[2])):
                means[i,v],areas[i,v],negatives[i,v]=regional_sums(values,lat)
        manifest.append({'file':str(path.relative_to(ROOT)), 'date':date.strftime('%Y-%m-%d'),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    supported=np.isfinite(means).any(axis=(0,1))
    rows=[]
    for j,feature in enumerate(grid['features']):
        p=feature['properties']
        p['data_status']='pending_ndvi' if supported[j] else 'unsupported_gldas'
        p['variables']=list(VARIABLES) if supported[j] else []
        p['gldas_valid_months']={name:int(np.isfinite(means[:,v,j]).sum()) for v,name in enumerate(VARIABLES)}
        p['ndvi_status']='pending_export'
        if not supported[j]: continue
        for i,date in enumerate(dates):
            for v,name in enumerate(VARIABLES):
                value=means[i,v,j]
                flag='negative_value' if negatives[i,v,j] else 'coverage_review_required' if np.isfinite(value) else 'no_valid_pixels' if any(m['date']==date.strftime('%Y-%m-%d') for m in manifest) else 'missing'
                rows.append({'date':date.strftime('%Y-%m-%d'),'value':value,'unit':'kg m-2','variable':name,'source':'GLDAS_NOAH025_M.2.1','region_id':p['region_id'],'valid_area_fraction':areas[i,v,j]/p['region_area_m2'],'valid_area_m2':areas[i,v,j],'region_area_m2':p['region_area_m2'],'quality_flag':flag})
    frame=pd.DataFrame(rows)
    frame.to_csv(out/'gldas_monthly_timeseries.csv',index=False)
    frame.to_csv(out/'monthly_timeseries.csv',index=False)
    (out/'catalog.json').write_text(json.dumps(grid,indent=2)+'\n')
    (out/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    metadata={'dataset_version':'GLDAS_NOAH025_M.2.1','status':'real NASA-derived regional aggregates; independent scientific review pending','period':['2003-01-01','2024-12-01'],'crs':'EPSG:4326','native_resolution_degrees':.25,'soil_layers':{'soil_water_0_10cm':['0-10cm'],'soil_water_0_100cm':['0-10cm','10-40cm','40-100cm']},'unit':'kg m-2','scale_applied':'CF decoding; identity scale and zero offset checked','aggregation':'monthly source time: mean; exact spherical cell-area weighted means; native .25-degree cells align with region boundaries','radius_m':RADIUS_M,'fill_values':'CF fill/missing decoded to NaN; blanks in CSV; no imputation','quality_rules':'0-100cm requires all three layers finite in the same cell. Negative source cells flagged, not silently discarded. Coverage denominator is entire 10-degree cell including oceans. No universal 0.8 threshold; coverage_review_required remains provisional. Low coverage months require explicit footprint review before statistical interpretation.','footprints':'MODIS and GLDAS geographic supports are not confirmed identical. Co-occurrence is only provisional regional screening.','unsupported_cells':'Kept in catalog; no fabricated series for cells with no valid GLDAS anywhere in required period.','jurisdictions':{'status':'geographic country candidates from coarse Natural Earth intersections' if boundaries.exists() else 'not_resolved','source_url':'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson','license':'public domain','sha256':hashlib.sha256(boundaries.read_bytes()).hexdigest() if boundaries.exists() else None,'limitations':'centroid is not proof of legal authority; disputed boundaries and official policies require source review'},'reproduction':'python scripts/process_regional_gldas.py; source_manifest.json records input hashes'}
    (out/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    report=frame.groupby(['region_id','variable']).agg(expected_months=('value','size'),valid_months=('value','count'),min_coverage=('valid_area_fraction','min'),max_coverage=('valid_area_fraction','max'))
    report['missing_months']=report.expected_months-report.valid_months
    report.to_csv(out/'quality_report.csv')
    print(f'{len(manifest)} inputs; {supported.sum()} supported cells; {len(frame)} real GLDAS rows. NDVI pending.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw',type=Path,default=ROOT/'data/raw/gldas');p.add_argument('--out',type=Path,default=ROOT/'data/processed/regional');a=p.parse_args();main(a.raw,a.out)
