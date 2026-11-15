#!/usr/bin/env python3
"""Read-only integrity audit for a bounded native GLDAS/MODIS tile.

Integrity and temporal completeness are distinct. Passing does not certify source
pixel QA, common footprints, causal interpretation or policy applicability.
"""
from pathlib import Path
import argparse
import hashlib
import json
import sys

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from src.fine_grid import build_tile_catalog,cell_feature,parse_cell_id

MONTHS=set(pd.date_range('2003-01-01','2024-12-01',freq='MS').strftime('%Y-%m-%d'))
SOIL={'soil_water_0_10cm','soil_water_0_100cm'}
REJECTED={'low_coverage','missing','invalid','qa_rejected','no_valid_data','no_valid_pixels','negative_value','pending_export'}
FLAGS={'coverage_review_required','negative_value','no_valid_pixels','missing','pending_export'}


def audit(directory, *, root=ROOT):
    """Audit files and independent calendar/geometry relationships; no refitting."""
    directory,root=Path(directory),Path(root)
    errors=[];passed=[]
    def check(condition,message):
        (passed if bool(condition) else errors).append(message)
    def read(name):
        return json.loads((directory/name).read_text())
    def table(name):
        return pd.read_csv(directory/name,dtype={'unit':str},float_precision='round_trip')
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    def manifest(name):
        path=directory/name
        if not path.exists(): return []
        records=read(name)
        check(isinstance(records,list),f'{name}: manifest is a list')
        if not isinstance(records,list): return []
        check(len({r['file'] for r in records})==len(records),f'{name}: unique archived file paths')
        for record in records:
            file=Path(record['file']);file=file if file.is_absolute() else root/file
            check(file.is_file(),f'{name}: source exists ({file.name})')
            if file.is_file():
                check(digest(file)==record['sha256'],f'{name}: source hash matches ({file.name})')
        return records
    metadata=read('metadata.json');catalog=read('catalog.json')
    features=catalog['features'];ids=[f['properties']['region_id'] for f in features]
    check(1<=len(ids)<=4096 and len(set(ids))==len(ids),'bounded catalog contains unique cells')
    bbox=metadata['bbox'];canonical_tile=build_tile_catalog(bbox)
    check(set(ids)=={f['id'] for f in canonical_tile['features']},'tile covers exactly its documented native cell envelope')
    check(catalog.get('requested_bbox')==bbox,'requested bbox agrees with metadata')
    check(metadata.get('period')==['2003-01-01','2024-12-01'],'documented required monthly period is2003-2024')
    check(metadata.get('crs')=='EPSG:4326' and metadata.get('native_resolution_degrees')==.25,'metadata uses native .25-degree EPSG4326 coordinates')
    check('synthetic' not in str(metadata.get('data_kind','')).lower().replace('no synthetic observations',''),'release does not identify synthetic observations as NASA data')
    by_id={f['properties']['region_id']:f for f in features}
    for feature in features:
        p=feature['properties'];rid=p['region_id'];row,col=parse_cell_id(rid)
        reference=cell_feature(row,col)
        check(feature.get('id')==rid and feature['geometry']==reference['geometry'],f'{rid}: native canonical geometry and ID')
        check(p.get('bbox')==reference['properties']['bbox'] and p.get('centroid')==reference['properties']['centroid'],f'{rid}: native bbox and centroid')
        check(p.get('grid_row')==row and p.get('grid_col')==col,f'{rid}: native row/column identity')
        check(p.get('tile_id')==metadata.get('tile_id'),f'{rid}: consistent tile identity')
        check(np.isclose(p['region_area_m2'],reference['properties']['region_area_m2'],rtol=1e-12),f'{rid}: exact spherical cell area')
        check(p.get('native_resolution_degrees')==.25 and p.get('crs')=='EPSG:4326',f'{rid}: native spatial resolution')
    frame=table('monthly_timeseries.csv');original=table('gldas_monthly_timeseries.csv')
    required={'date','value','unit','variable','source','region_id','valid_area_fraction','valid_area_m2','region_area_m2','quality_flag','grid_row','grid_col'}
    if not required.issubset(frame) or not required.issubset(original):
        raise ValueError('Fine observations are missing required columns')
    check(not frame.duplicated(['region_id','variable','date']).any(),'unique region/variable/month rows')
    check(set(frame.region_id)==set(ids),'observations cover exactly the catalog cells')
    check(set(frame.variable).issubset(SOIL|{'ndvi'}),'canonical indicator names only')
    parsed=pd.to_datetime(frame.date,errors='raise')
    check(parsed.dt.strftime('%Y-%m-%d').eq(frame.date).all() and parsed.dt.day.eq(1).all() and set(frame.date).issubset(MONTHS),'canonical monthly dates within2003-2024')
    for (rid,var),rows in frame.groupby(['region_id','variable']):
        check(len(rows)==264 and set(rows.date)==MONTHS,f'{rid}/{var}: preserved complete264-month index')
    for column in ('value','valid_area_fraction','valid_area_m2','region_area_m2'):
        frame[column]=pd.to_numeric(frame[column],errors='raise')
        check(not np.isinf(frame[column]).any(),f'{column}: no infinite values')
    check(frame.region_area_m2.notna().all() and frame.region_area_m2.gt(0).all(),'positive area denominators')
    check(frame.valid_area_m2.dropna().ge(0).all() and frame.valid_area_fraction.dropna().between(0,1.001).all(),'valid-area coverage has plausible bounds')
    check(np.allclose(frame.valid_area_fraction,frame.valid_area_m2/frame.region_area_m2,equal_nan=True,rtol=1e-6,atol=1e-9),'coverage fraction agrees with areas')
    for rid,rows in frame.groupby('region_id'):
        row,col=parse_cell_id(rid)
        check(rows.grid_row.eq(row).all() and rows.grid_col.eq(col).all(),f'{rid}: table retains original grid indices')
        check(np.allclose(rows.region_area_m2,by_id[rid]['properties']['region_area_m2'],rtol=1e-12),f'{rid}: table area agrees with geometry')
    finite=frame.value.notna()
    check(frame.quality_flag.isin(FLAGS).all(),'known provisional/missing quality flags')
    check(frame.loc[finite,'quality_flag'].isin({'coverage_review_required','negative_value'}).all(),'finite values retain provisional source QA')
    check(frame.loc[~finite,'quality_flag'].isin({'missing','pending_export','no_valid_pixels'}).all(),'missing values retain explicit missing flags')
    soil=frame[frame.variable.isin(SOIL)].sort_values(['region_id','variable','date']).reset_index(drop=True)
    original=original.sort_values(['region_id','variable','date']).reset_index(drop=True)
    check(set(soil.variable)==SOIL and len(soil)==len(ids)*264*2,'two full monthly soil-depth indexes per cell')
    check(set(soil.unit)=={'kg m-2'} and set(soil.source)=={'GLDAS_NOAH025_M.2.1'},'soil storage units/product remain canonical')
    check(set(original.columns).issubset(soil.columns) and soil[list(original.columns)].equals(original),'combined soil observations exactly preserve original native GLDAS table')
    check(soil.loc[soil.value.notna(),'valid_area_fraction'].eq(1).all(),'finite GLDAS values retain original one-cell support')
    check(soil.loc[soil.value.notna(),'quality_flag'].eq('negative_value').equals(soil.loc[soil.value.notna(),'value'].lt(0)),'negative soil values are explicitly and accurately flagged')
    for feature in features:
        p=feature['properties'];rid=p['region_id'];rows=frame[frame.region_id==rid]
        for var in SOIL:
            n=int(rows.loc[rows.variable==var,'value'].notna().sum())
            check(p.get('gldas_valid_months',{}).get(var)==n,f'{rid}/{var}: catalog valid-month count')
        check(set(p.get('variables',[]))==set(rows.variable),f'{rid}: catalog variable availability')
    glmanifest=manifest('source_manifest.json')
    check(len(glmanifest)==264 and {r.get('date') for r in glmanifest}==MONTHS,'GLDAS source manifest covers264required months')
    ndvi=frame[frame.variable=='ndvi']
    check(ndvi.unit.eq('1').all() and ndvi.source.eq('MOD13A3.061').all(),'NDVI remains scaled dimensionless MOD13A3.061')
    check(ndvi.loc[ndvi.value.notna(),'value'].between(-.2,1).all(),'NDVI retains scaled physical range')
    if not ndvi.empty:
        check(len(ndvi)==len(ids)*264,'NDVI import preserves264-month placeholders per cell')
    modis_manifest=manifest('modis_source_manifest.json')
    archive_hashes={r['sha256'] for r in modis_manifest}
    ledger_path=directory/'accepted_modis_observations.csv'
    if ledger_path.exists():
        from scripts.merge_fine_modis import validate_frame
        ledger=validate_frame(table('accepted_modis_observations.csv'),catalog)
        check('source_file_sha256' in ledger and ledger.source_file_sha256.isin(archive_hashes).all(),'accepted MODIS rows link to immutable archived input hashes')
        keys=['region_id','date']
        check(not ledger.duplicated(keys).any(),'accepted MODIS ledger has unique regional months')
        accepted=ledger.set_index(keys).sort_index()
        active_hashes=set(ledger.source_file_sha256)
        for source in modis_manifest:
            path=Path(source['file']);path=path if path.is_absolute() else root/path
            check(path.name==source['sha256']+'.csv','fine MODIS source archive uses content-addressed filenames')
            # Every historical file was hash-checked above. Superseded legacy
            # exports remain immutable provenance, not active v2 observations.
            # Only ledger-referenced archives must pass today's strict method.
            if not path.is_file() or source['sha256'] not in active_hashes: continue
            try:
                archived=validate_frame(pd.read_csv(path,dtype={'unit':str},float_precision='round_trip'),catalog).set_index(keys).sort_index()
            except ValueError:
                check(False,'active MODIS archive passes current native-area/provenance validation')
                continue
            authoritative=accepted[accepted.source_file_sha256==source['sha256']]
            check(set(authoritative.index).issubset(archived.index),'ledger authoritative rows exist in their recorded source archive')
            common_source=authoritative.index.intersection(archived.index)
            columns=[c for c in archived.columns if c!='source_file_sha256']
            check(set(columns).issubset(authoritative.columns) and authoritative.loc[common_source,columns].equals(archived.loc[common_source,columns]),'ledger authoritative values/provenance equal original archived bytes')
        actual=ndvi[ndvi.quality_flag!='pending_export'].set_index(keys).sort_index()
        check(set(actual.index)==set(accepted.index),'all accepted fine MODIS rows reach release exactly once')
        common=accepted.index.intersection(actual.index)
        for column in ('value','valid_area_fraction','valid_area_m2','region_area_m2'):
            check(np.allclose(accepted.loc[common,column],actual.loc[common,column],rtol=0,atol=0,equal_nan=True),f'accepted MODIS {column} preserved exactly')
        check(accepted.loc[common,'quality_flag'].equals(actual.loc[common,'quality_flag']),'accepted MODIS quality flags preserved')
    else:
        check(ndvi.empty or ndvi.quality_flag.eq('pending_export').all(),'observed NDVI requires an accepted archival ledger')
    for feature in features:
        p=feature['properties'];rows=ndvi[ndvi.region_id==p['region_id']]
        check(p.get('ndvi_valid_months',0)==int(rows.value.notna().sum()),f'{p["region_id"]}: NDVI valid-month count')
        check(p.get('ndvi_exported_months',0)==int(rows.quality_flag.ne('pending_export').sum()),f'{p["region_id"]}: NDVI accepted-month count')
    quality=table('quality_report.csv').set_index(['region_id','variable'])
    actual=frame.groupby(['region_id','variable']).value.agg(['size','count'])
    check(quality.index.is_unique and set(quality.index)==set(actual.index),'quality report covers exactly the released series')
    common=actual.index.intersection(quality.index)
    check((quality.loc[common,'expected_months']==actual.loc[common,'size']).all() and (quality.loc[common,'valid_months']==actual.loc[common,'count']).all() and (quality.loc[common,'missing_months']==actual.loc[common,'size']-actual.loc[common,'count']).all(),'quality report counts reconcile independently')
    coverage=frame.groupby(['region_id','variable']).valid_area_fraction.agg(['min','max'])
    check(np.allclose(quality.loc[common,'min_coverage'],coverage.loc[common,'min'],equal_nan=True) and np.allclose(quality.loc[common,'max_coverage'],coverage.loc[common,'max'],equal_nan=True),'quality report coverage extrema match observations')
    if 'pending_export_months' in quality:
        pending=frame.groupby(['region_id','variable']).quality_flag.apply(lambda flags:int(flags.eq('pending_export').sum()))
        check(quality.loc[common,'pending_export_months'].eq(pending.loc[common]).all(),'quality report pending export counts match observations')
    boundary=metadata.get('country_boundary_source')
    if boundary:
        source=Path(boundary['file']);source=source if source.is_absolute() else root/source
        check(source.is_file() and digest(source)==boundary['sha256'],'country-boundary source matches recorded hash')
    screening=read('screening.json');mapping=read('map_screening.geojson')
    for name,payload in [('screening',screening),('map',mapping)]:
        check(payload.get('source_csv_sha256')==digest(directory/'monthly_timeseries.csv') and payload.get('source_catalog_sha256')==digest(directory/'catalog.json'),f'{name}: current source fingerprints')
        family=payload['multiple_testing']
        check('Only this frozen fine pilot catalog' in family.get('scope',''),f'{name}: testing family explicitly bounded to fine pilot')
        check(family.get('catalog_regions')==len(ids) and family.get('provisional') is True,f'{name}: provisional family size matches tile')
    records=screening['regions'];mapped=mapping['features']
    check(len(records)==len(ids) and {r['region_id'] for r in records}==set(ids),'statistical records exactly cover tile')
    check(len(mapped)==len(ids) and {r['id'] for r in mapped}==set(ids),'map features exactly cover tile')
    usable=frame[frame.value.notna() & ~frame.quality_flag.isin(REJECTED)].copy()
    usable['year']=pd.to_datetime(usable.date).dt.year
    counts=usable.groupby(['region_id','variable','year']).size()
    years={}
    for (rid,var,year),n in counts.items():
        if n==12: years.setdefault((rid,var),set()).add(year)
    family_count=0;eligible_count=0
    for record in records:
        rid=record['region_id'];decision=record['screening'];paired=record.get('analysis')
        check(record['geometry']==by_id[rid]['geometry'] and record['bbox']==by_id[rid]['properties']['bbox'],f'{rid}: statistical geometry matches native cell')
        check(decision.get('qa_reviewed') is False and decision.get('provisional') is True,f'{rid}: screening never promotes source QA')
        if record['status']=='eligible':
            eligible_count+=1;family_count+=2
            common_years=years.get((rid,'ndvi'),set()) & years.get((rid,'soil_water_0_100cm'),set())
            check(len(common_years)>=screening['settings']['min_years'],f'{rid}: paired eligibility has independent complete-month support')
            check(set(decision['adjusted_p_values'])=={'ndvi','soil_water_0_100cm'} and all(0<=v<=1 for v in decision['adjusted_p_values'].values()),f'{rid}: paired adjusted tests are bounded')
        else:
            check(not decision.get('adjusted_p_values'),f'{rid}: noneligible record has no paired significance')
            check(decision.get('classification')==record['status'] and decision.get('category') is None,f'{rid}: noneligible status cannot become a detected signal')
        for analysis in (paired,record.get('available_indicator_analysis')):
            if not analysis: continue
            check(not analysis.get('data_quality',{}).get('qa_reviewed') and not analysis.get('data_quality',{}).get('synthetic_demo'),f'{rid}: analysis remains real provisional data')
            for var,result in analysis['analysis'].items():
                reported=set(result.get('data_quality',{}).get('analyzed_years',[]))
                check(reported.issubset(years.get((rid,var),set())),f'{rid}/{var}: analyzed years have12independent valid months')
    for feature in mapped:
        p=feature['properties'];rid=p['region_id']
        check(feature['geometry']==by_id[rid]['geometry'] and p.get('native_resolution_degrees')==.25,f'{rid}: map retains native geometry')
        check(p.get('qa_reviewed') is False and not p.get('synthetic_demo'),f'{rid}: map retains provisional real labels')
        record=next(r for r in records if r['region_id']==rid)
        check(p['classification']==record['screening']['classification'],f'{rid}: map classification matches stored screening')
        if record['status']!='eligible':
            check(all(i.get('worldwide_adjusted_p_value') is None and i.get('worldwide_significant') is None for i in p.get('indicators',{}).values()),f'{rid}: diagnostics cannot imply map-wide significance')
    check(mapping['multiple_testing']==screening['multiple_testing'],'map and detailed screening declare the identical fine testing family')
    check(screening['multiple_testing']['family_size']==family_count and screening['multiple_testing']['eligible_regions']==eligible_count,'paired testing family counts match eligible records')
    complete=len(ndvi)==len(ids)*264 and ndvi.value.notna().all() and soil.value.notna().all()
    pending=int(ndvi.quality_flag.eq('pending_export').sum()) if not ndvi.empty else len(ids)*264
    received=len(ndvi)==len(ids)*264 and pending==0
    return {'integrity_passed':not errors,'full_required_period_complete':bool(complete),'native_cells':len(ids),
        'gldas_rows':len(soil),'ndvi_rows':len(ndvi),'ndvi_valid_rows':int(ndvi.value.notna().sum()),
        'ndvi_exported_rows':int(ndvi.quality_flag.ne('pending_export').sum()),'required_ndvi_rows':len(ids)*264,
        'ndvi_pending_rows':pending,'full_export_index_received':bool(received),
        'paired_eligible_cells':eligible_count,'source_months':len(glmanifest),'passed_checks':len(passed),'errors':errors,
        'scientific_review_status':'provisional; independent MODIS pixel/common-footprint review remains pending',
        'scope':'bounded native GLDAS fine pilot only; no worldwide inference',
        'external_next_action':None if complete else 'Review exported missing/QA-rejected months; retain gaps without invented values.' if received else 'Retrieve authenticated fine MODIS exports and ingest without filling missing months.'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=ROOT/'data/processed/fine/central_us')
    parser.add_argument('--output',type=Path,help='Optional explicit audit JSON; source observations remain unchanged')
    args=parser.parse_args(argv)
    try:
        report=audit(args.directory)
    except (ValueError,KeyError,OSError,TypeError,IndexError) as exc:
        report={'integrity_passed':False,'full_required_period_complete':False,
                'errors':[f'Fine audit could not complete ({type(exc).__name__}); inspect release structure.']}
    if args.output:
        args.output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(report,indent=2,allow_nan=False))
    return 0 if report['integrity_passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
