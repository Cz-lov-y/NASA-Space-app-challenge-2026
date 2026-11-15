#!/usr/bin/env python3
"""Strict fine-cell MODIS validation and incremental, source-archived ingestion."""
from pathlib import Path
import argparse
from copy import deepcopy
import hashlib
import io
import json
import sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.fine_grid import cell_bbox,cell_feature,parse_cell_id
from scripts.export_fine_modis_earth_engine import CALCULATION_VERSION
from scripts.merge_regional_timeseries import validate_modis,combine_records,archive_exports


def checked_catalog(catalog):
    catalog=deepcopy(catalog) if isinstance(catalog,dict) else json.loads(Path(catalog).read_text())
    features=catalog['features']
    if not 1<=len(features)<=4096:raise ValueError('Fine catalog must be a bounded tile of1to4096cells')
    areas={}
    for feature in features:
        p=feature['properties'];rid=p['region_id'];row,col=parse_cell_id(rid);canonical=cell_feature(row,col)
        if rid in areas:raise ValueError('Duplicate fine catalog cell')
        if p['bbox']!=cell_bbox(row,col) or feature['geometry']!=canonical['geometry']:
            raise ValueError('Fine target geometry differs from native GLDAS cell')
        if not np.isclose(p['region_area_m2'],canonical['properties']['region_area_m2'],rtol=1e-12,atol=1e-6):
            raise ValueError('Fine cell area differs from native GLDAS geometry')
        if p.get('native_resolution_degrees',.25)!=.25:raise ValueError('Fine catalog must retain native0.25degree resolution')
        areas[rid]=p['region_area_m2']
    return catalog,areas


def validate_frame(frame,catalog,expected_month=None):
    """Validate fine identity plus shared source-mask/QA/grid/coverage semantics."""
    catalog,areas=checked_catalog(catalog)
    required={'tile_id','target_resolution_degrees','area_method'}
    if not required.issubset(frame.columns):raise ValueError('Fine export requires tile_id, target_resolution_degrees and area_method')
    if not frame.area_method.eq(CALCULATION_VERSION).all():raise ValueError('Fine MODIS area method is outdated; reprocess using the declared native sinusoidal sphere calculation version')
    frame=validate_modis(frame,region_areas=areas)
    resolutions=pd.to_numeric(frame.target_resolution_degrees,errors='raise')
    if not resolutions.eq(.25).all():raise ValueError('Fine export must target native0.25degree GLDAS cells')
    tiles={f['properties'].get('tile_id') for f in catalog['features']}
    if None in tiles or len(tiles)!=1 or not frame.tile_id.isin(tiles).all():raise ValueError('Fine export tile_id does not match catalog')
    for date,rows in frame.groupby('date'):
        if len(rows)!=len(areas) or set(rows.region_id)!=set(areas):
            raise ValueError(f'Fine export month{date} does not contain every requested tile cell')
    if expected_month is not None:
        month=pd.Timestamp(expected_month)
        if month.day!=1 or month!=month.normalize():raise ValueError('Expected month must be a month start')
        if set(frame.date)!={month.strftime('%Y-%m-%d')}:
            raise ValueError('Fine pilot export month differs from expected month')
    return frame


def validate(path,catalog,expected_month=None):
    """Read-only source validation; never imports or rewrites the pilot dataset."""
    content=Path(path).read_bytes()
    frame=pd.read_csv(io.BytesIO(content),dtype={'unit':str},float_precision='round_trip')
    return validate_frame(frame,catalog,expected_month)


def ingest(paths,directory,replace=False):
    """Accept new complete-cell monthly exports while preserving earlier months.

    Exact repeats are idempotent. Any changed existing value or provenance field
    needs replace=True. Unrelated accepted observations are always preserved.
    """
    directory=Path(directory);catalog_path=directory/'catalog.json'
    catalog,areas=checked_catalog(catalog_path)
    metadata=json.loads((directory/'metadata.json').read_text())
    gldas_path=directory/'gldas_monthly_timeseries.csv'
    gldas=pd.read_csv(gldas_path,dtype={'unit':str},float_precision='round_trip')
    months=pd.date_range('2003-01-01','2024-12-01',freq='MS').strftime('%Y-%m-%d')
    expected={(rid,var,date) for rid in areas for var in ('soil_water_0_10cm','soil_water_0_100cm') for date in months}
    if gldas.duplicated(['region_id','variable','date']).any() or set(zip(gldas.region_id,gldas.variable,gldas.date))!=expected:
        raise ValueError('Native GLDAS source extraction must preserve full264-month indexes for both layers')
    if not gldas.unit.eq('kg m-2').all() or not gldas.source.eq('GLDAS_NOAH025_M.2.1').all():
        raise ValueError('GLDAS source units/product must be preserved')
    parts=[];sources=[];paths=[Path(path) for path in paths]
    for path in paths:
        content=path.read_bytes()
        frame=validate_frame(pd.read_csv(io.BytesIO(content),dtype={'unit':str},float_precision='round_trip'),catalog)
        digest=hashlib.sha256(content).hexdigest();frame['source_file_sha256']=digest;parts.append(frame)
        sources.append({'file':str(path),'original_name':path.name,'sha256':digest})
    if not parts:raise ValueError('Supply at least one actual fine MODIS source export')
    ledger_path=directory/'accepted_modis_observations.csv'
    if ledger_path.exists():
        previous_raw=pd.read_csv(ledger_path,dtype={'unit':str},float_precision='round_trip')
        current_method=(previous_raw.area_method.eq(CALCULATION_VERSION) if 'area_method' in previous_raw else pd.Series(False,index=previous_raw.index))
        legacy=previous_raw.loc[~current_method]
        if not legacy.empty:
            new_keys=set().union(*(set(zip(f.region_id,f.date)) for f in parts))
            legacy_keys=set(zip(legacy.region_id,legacy.date))
            if not replace or not legacy_keys.issubset(new_keys):
                raise ValueError('Legacy fine area method requires explicit --replace and corrected inputs covering every previously accepted legacy region/month; no mixed-method release is allowed')
        previous=previous_raw.loc[current_method]
        if not previous.empty:
            previous=validate_frame(previous,catalog)
            if 'source_file_sha256' not in previous or previous.source_file_sha256.isna().any():
                raise ValueError('Existing fine ledger lacks source archive links')
            parts.insert(0,previous)
    elif (directory/'monthly_timeseries.csv').exists():
        previous=pd.read_csv(directory/'monthly_timeseries.csv',dtype={'unit':str},float_precision='round_trip')
        previous=previous.loc[(previous.variable=='ndvi') & previous.quality_flag.ne('pending_export')]
        if not previous.empty:raise ValueError('Existing fine observations lack an archival ledger; reimport their actual source files first')
    accepted=validate_frame(combine_records(parts,replace=replace),catalog)
    index=pd.MultiIndex.from_product([sorted(areas),months],names=['region_id','date'])
    ndvi=accepted.set_index(['region_id','date']).reindex(index).reset_index()
    ndvi['variable']='ndvi';ndvi['unit']='1';ndvi['source']='MOD13A3.061'
    ndvi['quality_flag']=ndvi.quality_flag.fillna('pending_export')
    ndvi['region_area_m2']=ndvi.region_area_m2.fillna(ndvi.region_id.map(areas))
    tile=next(iter({f['properties']['tile_id'] for f in catalog['features']}))
    ndvi['tile_id']=ndvi.tile_id.fillna(tile);ndvi['target_resolution_degrees']=.25
    native_indices={rid:parse_cell_id(rid) for rid in areas}
    ndvi['grid_row']=ndvi.region_id.map(lambda rid:native_indices[rid][0])
    ndvi['grid_col']=ndvi.region_id.map(lambda rid:native_indices[rid][1])
    for feature in catalog['features']:
        p=feature['properties'];rows=ndvi.loc[ndvi.region_id==p['region_id']]
        n=int(rows.value.notna().sum());exported=int(rows.quality_flag.ne('pending_export').sum())
        p.update(ndvi_valid_months=n,ndvi_exported_months=exported,
            variables=list(dict.fromkeys(p.get('variables',[])+['ndvi'])),
            ndvi_status='complete' if n==264 else 'complete_with_missing' if exported==264 and n else
                'no_valid_observations' if exported==264 else 'partial' if n else
                'partial_no_valid_observations' if exported else 'pending_export')
        # Data availability is separate from native geometry and land support.
        if p.get('data_status')!='unsupported_gldas':
            p['data_status']='available' if n==264 else 'incomplete_ndvi' if exported==264 and n else 'unavailable_ndvi' if exported==264 else 'partial_ndvi' if n else 'pending_ndvi'
    combined=pd.concat([gldas,ndvi],ignore_index=True).sort_values(['region_id','variable','date'])
    quality=combined.groupby(['region_id','variable']).agg(expected_months=('value','size'),valid_months=('value','count'),min_coverage=('valid_area_fraction','min'),max_coverage=('valid_area_fraction','max'))
    quality['missing_months']=quality.expected_months-quality.valid_months
    quality['pending_export_months']=combined.groupby(['region_id','variable']).quality_flag.apply(lambda flags:int(flags.eq('pending_export').sum()))
    # All parsing, source/cell consistency and conflicts are checked before writes.
    manifest_path=directory/'modis_source_manifest.json'
    previous_manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    archive=(ROOT/'data/raw/modis_earth_engine/fine' if directory.resolve().is_relative_to((ROOT/'data/processed/fine').resolve()) else directory/'source_archive')
    archived=archive_exports(paths,sources,archive)
    manifests=sorted({r['sha256']:r for r in previous_manifest+archived}.values(),key=lambda r:r['sha256'])
    metadata['dataset_versions']=['GLDAS_NOAH025_M.2.1','MOD13A3.061']
    metadata['modis_calculation_version']=CALCULATION_VERSION
    metadata['ndvi']={'dataset_version':'MOD13A3.061','unit':'1','target_resolution_degrees':.25,
        'area_method':CALCULATION_VERSION,
        'method':'Constant native MODIS sinusoidal-sphere pixel area; original native sinusoidal MODIS pixel-area weighted means into unchanged native GLDAS cell footprints; scale0.0001once',
        'qa':'Intersect source NDVI/DetailedQA/SummaryQA masks; raw NDVI[-2000,10000]; (DetailedQA&3)==0;SummaryQA==0',
        'missing':'Unexported264-month slots remainNaN with pending_export; exported no_valid_pixels/missing retained without imputation',
        'scientific_validation':'Source metadata/QA/projection/index checks passed; independent source-pixel and common-footprint scientific review pending',
        'valid_imported_observations':int(ndvi.value.notna().sum()),'expected_observations':len(areas)*264,
        'source_archive':'modis_source_manifest.json; accepted_modis_observations.csv retains per-row file hashes',
        'reproduce':'python scripts/merge_fine_modis.py --ingest <source CSVs>; use per-row source_file_sha256 in accepted_modis_observations.csv to select authoritative rows from archived bytes'}
    accepted_bytes=accepted.to_csv(index=False).encode()
    metadata['dataset_fingerprint']=hashlib.sha256((hashlib.sha256((directory/'source_manifest.json').read_bytes()).hexdigest()+
        json.dumps(manifests,sort_keys=True)+hashlib.sha256(accepted_bytes).hexdigest()).encode()).hexdigest()
    ledger_path.write_bytes(accepted_bytes)
    combined.to_csv(directory/'monthly_timeseries.csv',index=False)
    quality.to_csv(directory/'quality_report.csv')
    catalog_path.write_text(json.dumps(catalog,indent=2)+'\n')
    manifest_path.write_text(json.dumps(manifests,indent=2)+'\n')
    (directory/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return {'imported_source_files':len(paths),'archived_source_files':len(manifests),'accepted_ndvi_rows':len(accepted),
        'valid_ndvi_values':int(ndvi.value.notna().sum()),'pending_export_rows':int(ndvi.quality_flag.eq('pending_export').sum()),
        'native_cells':len(areas),'expected_months_per_cell':264,'status':'provisional_native_cell_data; rebuild_statistics_and_frontend_bundle',
        'gldas_source_file_modified':False}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('exports',type=Path,nargs='+')
    p.add_argument('--directory',type=Path,default=ROOT/'data/processed/fine/central_us')
    p.add_argument('--expected-month',help='For read-only pilot validation, require this one month')
    p.add_argument('--ingest',action='store_true');p.add_argument('--replace',action='store_true')
    args=p.parse_args(argv)
    if args.replace and not args.ingest:p.error('--replace requires --ingest')
    if args.expected_month and args.ingest:p.error('--expected-month is a pilot validation option; omit it for ingestion')
    if args.ingest:result=ingest(args.exports,args.directory,replace=args.replace)
    else:
        catalog=json.loads((args.directory/'catalog.json').read_text())
        frames=[validate(path,catalog,args.expected_month) for path in args.exports]
        result={'status':'structural_and_provenance_checks_passed; source_pixel_review_pending','files':len(frames),
            'rows':sum(len(f) for f in frames),'valid_values':sum(int(f.value.notna().sum()) for f in frames),'ingested':False}
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
