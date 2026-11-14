#!/usr/bin/env python3
"""Read-only integrity and completeness audit of the regional data release."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.regions import make_grid, RADIUS_M


def audit(directory, *, root=ROOT, expected_grid=648, expected_supported=301):
    directory=Path(directory);root=Path(root)
    errors=[];checks=[]
    def check(condition,message):
        (checks if bool(condition) else errors).append(message)
    def read(name):
        return json.loads((directory/name).read_text())
    catalog=read('catalog.json');features=catalog['features']
    ids=[f['properties']['region_id'] for f in features]
    check(len(ids)==expected_grid and len(set(ids))==len(ids),'catalog has the expected unique regional cells')
    supported={f['properties']['region_id'] for f in features if f['properties']['data_status']!='unsupported_gldas'}
    check(len(supported)==expected_supported,'supported GLDAS cell count matches release expectation')
    if expected_grid==648:
        canonical={f['id']:f for f in make_grid()['features']}
        check(set(ids)==set(canonical),'catalog contains every canonical grid ID')
        for feature in features:
            rid=feature['properties']['region_id'];reference=canonical.get(rid)
            if reference:
                check(feature['geometry']==reference['geometry'] and feature['properties']['bbox']==reference['properties']['bbox'],f'{rid}: canonical geometry and bbox')
    frame=pd.read_csv(directory/'monthly_timeseries.csv',dtype={'unit':str},float_precision='round_trip')
    gldas=pd.read_csv(directory/'gldas_monthly_timeseries.csv',dtype={'unit':str},float_precision='round_trip')
    required={'date','value','unit','variable','source','region_id','quality_flag','valid_area_m2','valid_area_fraction','region_area_m2'}
    if not required.issubset(frame.columns):
        return {'integrity_passed':False,'full_required_period_complete':False,'errors':['monthly observations are missing required columns']}
    check(not frame.duplicated(['region_id','variable','date']).any(),'one observation per region/variable/month')
    check(set(frame.region_id).issubset(supported),'observations belong to supported catalog regions')
    check(set(frame.variable).issubset({'ndvi','soil_water_0_10cm','soil_water_0_100cm'}),'only canonical variables are present')
    dates=pd.to_datetime(frame.date,errors='raise')
    check(((dates==dates.dt.normalize()) & (dates.dt.day==1) & dates.dt.year.between(2003,2024)).all(),'observations use monthly dates in2003-2024')
    months=set(pd.date_range('2003-01-01','2024-12-01',freq='MS').strftime('%Y-%m-%d'))
    for (rid,var),rows in frame.groupby(['region_id','variable']):
        check(len(rows)==264 and set(rows.date)==months,f'{rid}/{var}: complete264-month index')
    numeric={c:pd.to_numeric(frame[c],errors='raise') for c in ['value','valid_area_m2','valid_area_fraction','region_area_m2']}
    check(all(not np.isinf(v).any() for v in numeric.values()),'numeric data contain no infinities')
    check(numeric['valid_area_m2'].dropna().ge(0).all(),'valid areas are nonnegative')
    check(numeric['region_area_m2'].notna().all() and numeric['region_area_m2'].gt(0).all(),'regional area denominators are positive')
    check(numeric['valid_area_fraction'].dropna().between(0,1.001).all(),'area fractions have physically plausible bounds')
    check(np.allclose(numeric['valid_area_fraction'],numeric['valid_area_m2']/numeric['region_area_m2'],rtol=1e-6,atol=1e-9,equal_nan=True),'coverage fraction matches recorded areas')
    allowed_flags={'coverage_review_required','negative_value','no_valid_pixels','missing','pending_export'}
    check(frame.quality_flag.isin(allowed_flags).all(),'all quality flags are known')
    finite=frame.value.notna()
    check(frame.loc[finite,'quality_flag'].isin({'coverage_review_required','negative_value'}).all(),'finite values retain provisional quality flags')
    check(frame.loc[~finite,'quality_flag'].isin({'no_valid_pixels','missing','pending_export'}).all(),'missing values have explicit missing-data flags')
    soil=frame.loc[frame.variable!='ndvi'].sort_values(['region_id','variable','date']).reset_index(drop=True)
    original=gldas.sort_values(['region_id','variable','date']).reset_index(drop=True)
    check(soil[list(gldas.columns)].equals(original),'combined observations preserve GLDAS input table exactly')
    check(soil.unit.eq('kg m-2').all() and soil.source.eq('GLDAS_NOAH025_M.2.1').all(),'GLDAS units and source remain canonical')
    check(len(soil)==expected_supported*264*2,'GLDAS has264months and2depths per supported cell')
    ndvi=frame.loc[frame.variable=='ndvi']
    check(ndvi.unit.eq('1').all() and ndvi.source.eq('MOD13A3.061').all(),'NDVI units and source remain canonical')
    if not ndvi.empty:
        check(ndvi.loc[ndvi.value.notna(),'value'].between(-.2,1).all(),'NDVI retains scaled physical range')
    for feature in features:
        p=feature['properties'];rid=p['region_id'];rows=ndvi.loc[ndvi.region_id==rid]
        check(p.get('ndvi_valid_months',0)==int(rows.value.notna().sum()),f'{rid}: catalog NDVI valid-month count')
        check(p.get('ndvi_exported_months',0)==int(rows.quality_flag.ne('pending_export').sum()),f'{rid}: catalog NDVI exported-month count')
        recorded=set(p.get('variables',[]));actual=set(frame.loc[frame.region_id==rid,'variable'])
        check(recorded==actual,f'{rid}: catalog variable availability agrees with observations')
        for var,n in p.get('gldas_valid_months',{}).items():
            check(n==int(frame.loc[(frame.region_id==rid)&(frame.variable==var),'value'].notna().sum()),f'{rid}/{var}: GLDAS count matches catalog')
    manifest_count=0;archival_hashes=set()
    for name in ['source_manifest.json','modis_source_manifest.json']:
        path=directory/name
        if not path.exists(): continue
        records=read(name)
        if name=='source_manifest.json':
            manifest_count=len(records);check(manifest_count==264,'GLDAS manifest contains264source months')
            check(len({r['file'] for r in records})==len(records),'GLDAS manifest source files are unique')
            check({r.get('date') for r in records}==months,'GLDAS manifest dates cover the required264months')
        for record in records:
            target=Path(record['file']);target=target if target.is_absolute() else root/target
            check(target.is_file(),f'{name}: source file exists ({target.name})')
            if target.is_file(): check(hashlib.sha256(target.read_bytes()).hexdigest()==record['sha256'],f'{name}: source hash matches ({target.name})')
            if name=='modis_source_manifest.json': archival_hashes.add(record['sha256'])
    ledger_path=directory/'accepted_modis_observations.csv'
    if ledger_path.exists():
        # Import validation performs native projection/QA/asset consistency checks.
        from scripts.merge_regional_timeseries import validate_modis
        ledger=validate_modis(pd.read_csv(ledger_path,dtype={'unit':str},float_precision='round_trip'))
        check('source_file_sha256' in ledger and ledger.source_file_sha256.isin(archival_hashes).all(),'accepted MODIS rows link to archived input hashes')
        accepted=ledger.loc[ledger.region_id.isin(supported)].set_index(['region_id','date'])
        actual=ndvi.loc[ndvi.quality_flag.ne('pending_export')].set_index(['region_id','date'])
        check(set(accepted.index)==set(actual.index),'all accepted supported MODIS rows reach the combined release')
        common=accepted.index.intersection(actual.index)
        check(np.allclose(accepted.loc[common,'value'],actual.loc[common,'value'],equal_nan=True,rtol=0,atol=0),'combined NDVI values equal the accepted ledger')
    else:
        check(ndvi.empty or ndvi.quality_flag.eq('pending_export').all(),'observed NDVI requires an accepted archival ledger')
    global_path=root/'data/processed/global_gldas/monthly_timeseries.csv'
    max_error=None
    if global_path.exists():
        global_frame=pd.read_csv(global_path)
        diffs=[]
        for (date,var),rows in soil.groupby(['date','variable']):
            reference=global_frame.loc[(global_frame.date==date)&(global_frame.variable==var)]
            if reference.empty: errors.append(f'Global comparison missing {date}/{var}');continue
            mean=(rows.value*rows.valid_area_m2).sum()/rows.valid_area_m2.sum()
            diffs.append(abs(float(mean)-float(reference.value.iloc[0])))
            expected_area=float(reference.valid_area_fraction.iloc[0])*4*np.pi*RADIUS_M**2
            check(np.isclose(rows.valid_area_m2.sum(),expected_area,rtol=1e-12),f'{date}/{var}: GLDAS area sums reconcile globally')
        max_error=max(diffs,default=None)
        check(max_error is not None and max_error<1e-9,'regional GLDAS weighted means reconcile globally within1e-9kgm-2')
    metadata=read('metadata.json');country=metadata.get('jurisdictions',{})
    if isinstance(country,dict) and country.get('sha256'):
        boundary=directory/'naturalearth_countries.geojson'
        check(boundary.is_file() and hashlib.sha256(boundary.read_bytes()).hexdigest()==country['sha256'],'Natural Earth retained boundary hash matches metadata')
    quality=pd.read_csv(directory/'quality_report.csv')
    expected=frame.groupby(['region_id','variable']).value.agg(['size','count'])
    reported=quality.set_index(['region_id','variable'])
    check(set(reported.index)==set(expected.index),'quality report covers exactly the released regional series')
    common=expected.index.intersection(reported.index)
    check((reported.loc[common,'expected_months']==expected.loc[common,'size']).all() and (reported.loc[common,'valid_months']==expected.loc[common,'count']).all(),'quality report counts match observations')
    complete=not ndvi.empty and ndvi.value.notna().sum()==expected_supported*264
    preview_eligible=None
    screening_path=directory/'screening.json'
    screening_status='not_built'
    if screening_path.exists():
        screening=read('screening.json')
        if (screening.get('source_csv_sha256')==hashlib.sha256((directory/'monthly_timeseries.csv').read_bytes()).hexdigest()
                and screening.get('source_catalog_sha256')==hashlib.sha256((directory/'catalog.json').read_bytes()).hexdigest()):
            screening_status='current'
            preview_eligible=sum(r.get('status')=='eligible' for r in screening.get('regions',[]))
        else: screening_status='stale_rebuild_required'
    return {'integrity_passed':not errors,'full_required_period_complete':bool(complete),
        'paired_preview_eligible_regions':preview_eligible,'screening_status':screening_status,
        'scientific_review_status':'provisional; independent MODIS pixel and footprint review pending',
        'grid_cells':len(ids),'supported_gldas_cells':len(supported),'gldas_rows':len(soil),
        'ndvi_valid_rows':int(ndvi.value.notna().sum()),'ndvi_required_rows':expected_supported*264,
        'source_months':manifest_count,'passed_checks':len(checks),'errors':errors,
        'max_regional_global_mean_error_kg_m2':max_error,
        'external_next_action':None if complete else 'Run authenticated regional MODIS pilot, audit it, then retrieve and incrementally import annual exports.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--directory',type=Path,default=ROOT/'data/processed/regional')
    args=parser.parse_args()
    try: report=audit(args.directory)
    except (ValueError,KeyError,OSError,TypeError) as exc:
        report={'integrity_passed':False,'full_required_period_complete':False,'errors':[str(exc)]}
    print(json.dumps(report,indent=2,allow_nan=False))
    raise SystemExit(0 if report['integrity_passed'] else 1)
