#!/usr/bin/env python3
"""Ingest regional GEE exports without accepting duplicate or invented observations."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.regions import make_grid


NATIVE_AFFINE = {'elt_0_0':926.625433055833, 'elt_0_2':-20015109.354,
                 'elt_1_1':-926.6254330558334, 'elt_1_2':10007554.677003}


def native_transform_matches(text):
    """Accept native1km MODIS lattice, including cropped1200-pixel tile origins.

    Monthly mosaics can omit empty northern/western tiles. Their original origin
    then shifts by complete MODIS tiles; scale, shear and lattice are unchanged.
    """
    parameters = dict(re.findall(r'PARAMETER\["(elt_\d_\d)",\s*([-+0-9.eE]+)\s*\]',str(text)))
    if not all(key in parameters for key in NATIVE_AFFINE):return False
    if not all(np.isclose(float(parameters[key]),NATIVE_AFFINE[key],rtol=0,atol=1e-6) for key in ('elt_0_0','elt_1_1')):return False
    if not all(key not in parameters or float(parameters[key])==0 for key in ('elt_0_1','elt_1_0')):return False
    for origin,scale,max_tile in [('elt_0_2','elt_0_0',35),('elt_1_2','elt_1_1',17)]:
        tiles=(float(parameters[origin])-NATIVE_AFFINE[origin])/(NATIVE_AFFINE[scale]*1200)
        tile=round(tiles)
        if not 0<=tile<=max_tile or not np.isclose(tiles,tile,rtol=0,atol=1e-9):return False
    return True


def validate_modis(frame, region_areas=None):
    required={'date','region_id','variable','value','unit','source','valid_area_fraction','valid_area_m2','region_area_m2','quality_flag','source_image_count','source_asset_id','source_time_start','source_crs','source_transform','qa_rule','configured_at_utc'}
    if not required.issubset(frame.columns): raise ValueError(f'Missing columns: {sorted(required-set(frame.columns))}')
    if frame.empty: raise ValueError('Export contains no regional rows')
    frame=frame.copy(); dates=pd.to_datetime(frame.date,errors='raise')
    if not ((dates.dt.day==1)&(dates==dates.dt.normalize())&(dates.dt.year>=2003)&(dates.dt.year<=2024)).all(): raise ValueError('Dates must be month starts in2003-2024')
    frame['date']=dates.dt.strftime('%Y-%m-%d')
    valid_ids=({f['id']:f['properties']['region_area_m2'] for f in make_grid()['features']}
               if region_areas is None else dict(region_areas))
    if not frame.region_id.isin(valid_ids).all(): raise ValueError('Unknown region')
    if frame.duplicated(['region_id','date']).any(): raise ValueError('Duplicate regional month')
    if not ((frame.variable=='ndvi')&(frame.unit.astype(str)=='1')&(frame.source=='MOD13A3.061')).all(): raise ValueError('Wrong MODIS variable,unit,source')
    for column in ['value','valid_area_fraction','valid_area_m2','region_area_m2','source_image_count']:
        frame[column]=pd.to_numeric(frame[column],errors='raise')
        if np.isinf(frame[column]).any(): raise ValueError('Infinite numeric values')
    finite=frame.value.notna()
    count=frame.source_image_count
    if count.isna().any() or not count.isin([0,1]).all(): raise ValueError('Source image count must be zero or one')
    present=count.eq(1)
    if frame.region_area_m2.isna().any() or not frame.region_area_m2.gt(0).all(): raise ValueError('Invalid region area')
    if not frame.valid_area_m2.dropna().ge(0).all(): raise ValueError('Negative valid area')
    if frame.loc[present,['valid_area_m2','valid_area_fraction']].isna().any().any(): raise ValueError('Present imagery requires area coverage')
    if not frame.loc[~present,'quality_flag'].eq('missing').all() or frame.loc[~present,['value','valid_area_m2','valid_area_fraction']].notna().any().any(): raise ValueError('Missing-image rows must have missing values and areas')
    for column in ['source_asset_id','source_time_start','source_crs','source_transform']:
        if frame.loc[~present,column].notna().any(): raise ValueError('Missing-image rows cannot claim source imagery')
    if not frame.loc[present & ~finite,'quality_flag'].eq('no_valid_pixels').all() or not frame.loc[present & ~finite,'valid_area_m2'].eq(0).all(): raise ValueError('Empty image rows require zero valid area')
    configured=frame.configured_at_utc.astype(str)
    if not configured.str.contains(r'(?:Z|[+-]\d{2}:\d{2})$',regex=True).all(): raise ValueError('Configured time requires timezone')
    pd.to_datetime(configured,utc=True,errors='raise')
    # Native weighted means can land one floating-point step beyond a bound.
    # Keep the original value and reject anything farther outside the product range.
    if not frame.loc[finite,'value'].between(np.nextafter(-.2,-np.inf),np.nextafter(1.,np.inf)).all(): raise ValueError('NDVI scale/range mismatch')
    if not frame.valid_area_fraction.dropna().between(0,1.001).all(): raise ValueError('Invalid coverage')
    expected=frame.region_id.map(valid_ids)
    if not np.allclose(frame.region_area_m2,expected,rtol=1e-8): raise ValueError('Region area mismatch')
    if not np.allclose(frame.valid_area_fraction,frame.valid_area_m2/frame.region_area_m2,rtol=1e-6,atol=1e-9,equal_nan=True): raise ValueError('Coverage area mismatch')
    if not (frame.loc[finite,'source_image_count']==1).all(): raise ValueError('Finite NDVI requires one source image')
    if not (frame.loc[finite,'valid_area_m2']>0).all(): raise ValueError('Finite NDVI requires valid area')
    for col in ['source_asset_id','source_time_start','source_crs','source_transform','qa_rule']:
        if frame.loc[present,col].isna().any() or frame.loc[present,col].astype(str).str.strip().eq('').any(): raise ValueError(f'Missing source provenance {col}')
    if not (pd.to_datetime(frame.loc[present,'source_time_start']).dt.strftime('%Y-%m-%d').values==frame.loc[present,'date'].values).all(): raise ValueError('Source time mismatch')
    expected_assets='MODIS/061/MOD13A3/'+frame.loc[present,'date'].str.replace('-','_',regex=False)
    if not frame.loc[present,'source_asset_id'].eq(expected_assets).all(): raise ValueError('Wrong source asset or asset month')
    if not frame.loc[present,'source_crs'].eq('SR-ORG:6974').all() or not frame.loc[present,'source_transform'].map(native_transform_matches).all(): raise ValueError('Unexpected native MODIS projection/transform')
    if not frame['qa_rule'].eq('raw NDVI [-2000,10000]; (DetailedQA & 3)==0; SummaryQA==0').all(): raise ValueError('Unexpected QA rule')
    if not frame.loc[finite,'quality_flag'].eq('coverage_review_required').all(): raise ValueError('Unexpected finite-value QA flag')
    if frame.quality_flag.eq('duplicate_month').any(): raise ValueError('Duplicate source imagery flagged')
    return frame


def combine_records(frames, replace=False):
    """Union monthly observations; conflicting measurements/provenance need opt-in.

    Input-file hash identifies archival origin, not scientific equality: one
    identical row may appear in both a pilot and an annual source CSV.
    """
    accepted = {}
    columns = sorted(set().union(*(set(f.columns) for f in frames)))
    compare = [c for c in columns if c != 'source_file_sha256']
    for frame in frames:
        for row in frame.reindex(columns=columns).to_dict('records'):
            key = (row['region_id'], row['date'])
            if key in accepted:
                old = accepted[key]
                equal = all((pd.isna(row[c]) and pd.isna(old[c])) or row[c] == old[c] for c in compare)
                if equal:
                    continue
                if not replace:
                    raise ValueError(f'Conflicting regional observation {key}; use --replace to accept changed values/provenance')
            accepted[key] = row
    return pd.DataFrame(accepted.values(), columns=columns).sort_values(['region_id','date']).reset_index(drop=True)


def read_exports(paths, replace=False):
    manifests=[];parts=[]
    for path in paths:
        path=Path(path)
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        frame=validate_modis(pd.read_csv(path,dtype={'unit':str},float_precision='round_trip'))
        frame['source_file_sha256']=digest
        parts.append(frame)
        manifests.append({'file':str(path.resolve().relative_to(ROOT)) if path.resolve().is_relative_to(ROOT) else str(path.resolve()),
                          'original_name':path.name,'sha256':digest})
    if not parts: raise ValueError('Provide regional exports; old whole-Earth exports cannot locate spots')
    return combine_records(parts,replace=replace),manifests


def archive_exports(paths, manifests, directory):
    """Retain exact source bytes under content hashes; never overwrite a hash."""
    directory=Path(directory)
    archived=[]
    for path,record in zip(paths,manifests):
        content=Path(path).read_bytes()
        if hashlib.sha256(content).hexdigest()!=record['sha256']:
            raise ValueError('Source changed during import')
        target=directory/(record['sha256']+'.csv')
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=record['sha256']:
            raise ValueError('Existing source archive hash mismatch')
        directory.mkdir(parents=True,exist_ok=True)
        if not target.exists(): target.write_bytes(content)
        archived.append({'file':str(target.resolve().relative_to(ROOT)) if target.resolve().is_relative_to(ROOT) else str(target.resolve()),
                         'original_name':record['original_name'],'sha256':record['sha256']})
    return archived


def audit_exports(paths):
    """Read and validate only: never alter the accepted dataset or create files."""
    modis,manifests=read_exports(paths)
    by_month=[]
    for date, rows in modis.groupby('date'):
        by_month.append({'date':date,'region_rows':len(rows),'expected_grid_regions':648,
            'missing_grid_regions':648-len(rows),'valid_values':int(rows.value.notna().sum()),
            'quality_flags':{str(k):int(v) for k,v in rows.quality_flag.value_counts().items()},
            'partition_valid_area_m2':float(rows.valid_area_m2.sum()),
            'partition_weighted_ndvi':float((rows.value*rows.valid_area_m2).sum()/rows.valid_area_m2.sum()) if rows.valid_area_m2.sum()>0 else None})
    return {'status':'structural_and_provenance_checks_passed; independent pixel validation pending',
        'files':manifests,'rows':len(modis),'regions':int(modis.region_id.nunique()),
        'months':by_month,'all_exported_months_cover_full_grid':all(m['region_rows']==648 for m in by_month)}


def main(paths,out,replace=False,archive=None):
    out=Path(out)
    modis,new_manifests=read_exports(paths,replace=replace)
    gldas=pd.read_csv(out/'gldas_monthly_timeseries.csv',dtype={'unit':str},float_precision='round_trip')
    catalog=json.loads((out/'catalog.json').read_text())
    ledger_path=out/'accepted_modis_observations.csv'
    if ledger_path.exists():
        previous=validate_modis(pd.read_csv(ledger_path,dtype={'unit':str},float_precision='round_trip'))
        modis=combine_records([previous,modis],replace=replace)
    elif (out/'monthly_timeseries.csv').exists():
        # Migrate earlier releases without silently discarding their observations.
        previous=pd.read_csv(out/'monthly_timeseries.csv',dtype={'unit':str},float_precision='round_trip')
        previous=previous.loc[(previous.variable=='ndvi') & previous.quality_flag.ne('pending_export')]
        if not previous.empty:
            modis=combine_records([validate_modis(previous),modis],replace=replace)
    # Validate complete union before archiving or changing any accepted outputs.
    modis=validate_modis(modis)
    if archive is None:
        archive=(ROOT/'data/raw/modis_earth_engine/regional' if out.resolve()==(ROOT/'data/processed/regional').resolve() else out/'source_archive')
    archived=archive_exports(paths,new_manifests,archive)
    manifest_path=out/'modis_source_manifest.json'
    old_manifests=json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    manifests=list({item['sha256']:item for item in old_manifests+archived}.values())
    modis.to_csv(ledger_path,index=False)
    ids={f['id'] for f in catalog['features'] if f['properties']['data_status']!='unsupported_gldas'}
    # Explicit empty rows for every unexported month in eligible cells.
    dates=pd.date_range('2003-01-01','2024-12-01',freq='MS').strftime('%Y-%m-%d')
    index=pd.MultiIndex.from_product([sorted(ids),dates],names=['region_id','date'])
    modis=modis.set_index(['region_id','date']).reindex(index).reset_index()
    modis['variable']='ndvi';modis['unit']='1';modis['source']='MOD13A3.061'
    modis['quality_flag']=modis.quality_flag.fillna('pending_export')
    region_areas={f['id']:f['properties']['region_area_m2'] for f in catalog['features']}
    modis['region_area_m2']=modis.region_area_m2.fillna(modis.region_id.map(region_areas))
    for feature in catalog['features']:
        p=feature['properties']; rows=modis.loc[modis.region_id==p['region_id']]
        if rows.empty: continue
        n=int(rows.value.notna().sum()); exported=int(rows.quality_flag.ne('pending_export').sum());p['ndvi_valid_months']=n;p['ndvi_exported_months']=exported
        p['variables']=list(dict.fromkeys(p['variables']+['ndvi']))
        p['ndvi_status']='complete' if n==264 else 'complete_with_missing' if exported==264 and n else 'no_valid_observations' if exported==264 else 'partial' if n else 'partial_no_valid_observations' if exported else 'pending_export'
        p['data_status']='available' if n==264 else 'incomplete_ndvi' if exported==264 and n else 'unavailable_ndvi' if exported==264 else 'partial_ndvi' if n else 'pending_ndvi'
    combined=pd.concat([gldas,modis],ignore_index=True).sort_values(['region_id','variable','date'])
    combined.to_csv(out/'monthly_timeseries.csv',index=False)
    quality=combined.groupby(['region_id','variable']).agg(expected_months=('value','size'),valid_months=('value','count'),min_coverage=('valid_area_fraction','min'),max_coverage=('valid_area_fraction','max'))
    quality['missing_months']=quality.expected_months-quality.valid_months
    quality.to_csv(out/'quality_report.csv')
    (out/'catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
    (out/'modis_source_manifest.json').write_text(json.dumps(manifests,indent=2)+'\n')
    meta=json.loads((out/'metadata.json').read_text());meta['dataset_versions']=['GLDAS_NOAH025_M.2.1','MOD13A3.061'];meta['modis']={'dataset_version':'MOD13A3.061','native_grid':'approximately1km sinusoidal','qa':'raw NDVI [-2000,10000]; (DetailedQA &3)==0; SummaryQA==0; source masks; scale .0001 once','unit':'1','aggregation':'native-projection pixelArea-weighted mean per10deg cell; geometry boundary rasterization may differ from alignedGLDAS; scientific validation pending','missing':'blank CSV; pending_export explicit; no inventedvalues','reproduction':'scripts/export_regional_modis_earth_engine.js; scripts/merge_regional_timeseries.py; modis_source_manifest.json'}
    meta['dataset_fingerprint']=hashlib.sha256((hashlib.sha256((out/'source_manifest.json').read_bytes()).hexdigest()+json.dumps(manifests,sort_keys=True)).encode()).hexdigest()
    (out/'metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
    print(f'Merged {len(manifests)} exports; {modis.value.notna().sum()} imported regional NDVI values; unexported months retained.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('exports',type=Path,nargs='+');p.add_argument('--out',type=Path,default=ROOT/'data/processed/regional')
    p.add_argument('--validate-only',action='store_true',help='Print a read-only pilot/export audit without merging')
    p.add_argument('--replace',action='store_true',help='Accept changed rows for overlapping region/months; all unrelated accepted rows remain')
    p.add_argument('--archive',type=Path,help='Override the raw source archive directory')
    a=p.parse_args()
    if a.validate_only: print(json.dumps(audit_exports(a.exports),indent=2))
    else: main(a.exports,a.out,replace=a.replace,archive=a.archive)
