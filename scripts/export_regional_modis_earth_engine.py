#!/usr/bin/env python3
"""Plan or submit native-grid regional MOD13A3 exports using existing EE auth.

Without --submit this command uses no Earth Engine client or network services.
Known live limitation: the worldwide pilot currently fails on polar raster bounds;
see docs/member_b_regional_steps.md before any retry or annual submission.
"""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.regions import make_grid

COLLECTION='MODIS/061/MOD13A3'
QA_RULE='raw NDVI [-2000,10000]; (DetailedQA & 3)==0; SummaryQA==0'
COLUMNS=['date','region_id','variable','value','unit','source','valid_area_fraction',
    'valid_area_m2','region_area_m2','quality_flag','source_image_count','source_asset_id',
    'source_time_start','source_crs','source_transform','qa_rule','configured_at_utc']


def export_plan(mode='pilot', first_year=2003, last_year=2024, month='2003-01-01'):
    if not 2003<=first_year<=last_year<=2024: raise ValueError('Year bounds must lie in2003-2024')
    if mode=='pilot': return [{'start':'2003-01-01','end':'2003-02-01','label':'pilot_2003_01'}]
    if mode=='years': return [{'start':f'{y}-01-01','end':f'{y+1}-01-01','label':str(y)} for y in range(first_year,last_year+1)]
    if mode!='month': raise ValueError('Mode must be pilot, years or month')
    date=datetime.strptime(month,'%Y-%m-%d')
    if date.strftime('%Y-%m-%d')!=month or date.day!=1 or not 2003<=date.year<=2024:
        raise ValueError('Month must be a first-of-month date in2003-2024')
    end=datetime(date.year+(date.month==12),date.month%12+1,1).strftime('%Y-%m-%d')
    return [{'start':month,'end':end,'label':'retry_'+month.replace('-','')}]


def export_grid(nonpolar=False):
    features=make_grid()['features']
    return [f for f in features if not nonpolar or (f['properties']['bbox'][1]>-90 and f['properties']['bbox'][3]<90)]


def build_collection(ee, start, end, configured_at, nonpolar=False):
    """Construct the graph only; task submission remains a separate explicit step."""
    features=[]
    for feature in export_grid(nonpolar):
        p=feature['properties']
        geometry=ee.Geometry.Rectangle(p['bbox'],None,False)
        features.append(ee.Feature(geometry,{'region_id':p['region_id'],'region_area_m2':p['region_area_m2']}))
    grid=ee.FeatureCollection(features)
    collection=ee.ImageCollection(COLLECTION)

    def monthly(date):
        date=ee.Date(date)
        images=collection.filterDate(date,date.advance(1,'month'))
        count=images.size()
        def absent(f):
            return f.set({'value':None,'valid_area_m2':None,'valid_area_fraction':None,
                'quality_flag':ee.Algorithms.If(count.eq(0),'missing','duplicate_month'),
                'source_asset_id':None,'source_time_start':None,'source_crs':None,'source_transform':None})
        image=ee.Image(images.first())
        raw=image.select('NDVI');detailed=image.select('DetailedQA');summary=image.select('SummaryQA')
        projection=raw.projection()
        valid=(raw.mask().And(detailed.mask()).And(summary.mask())
               .And(raw.gte(-2000)).And(raw.lte(10000))
               .And(detailed.bitwiseAnd(3).eq(0)).And(summary.eq(0)).unmask(0))
        area=ee.Image.pixelArea().updateMask(valid).rename('valid_area_m2')
        weighted=raw.multiply(.0001).multiply(area).rename('weighted_ndvi')
        reduced=weighted.addBands(area).unmask(0,False).reduceRegions(
            collection=grid,reducer=ee.Reducer.sum(),crs=projection,tileScale=4)
        def summarize(f):
            covered=ee.Number(f.get('valid_area_m2'))
            return f.set({'value':ee.Algorithms.If(covered.gt(0),ee.Number(f.get('weighted_ndvi')).divide(covered.max(1)),None),
                'valid_area_fraction':covered.divide(ee.Number(f.get('region_area_m2'))),
                'quality_flag':ee.Algorithms.If(covered.gt(0),'coverage_review_required','no_valid_pixels'),
                'source_asset_id':ee.String(COLLECTION+'/').cat(image.get('system:index')),
                'source_time_start':image.date().format('YYYY-MM-dd'),
                'source_crs':projection.crs(),'source_transform':projection.transform()})
        result=ee.FeatureCollection(ee.Algorithms.If(count.eq(1),reduced.map(summarize),grid.map(absent)))
        return result.map(lambda f:f.set({'date':date.format('YYYY-MM-dd'),'variable':'ndvi','unit':'1',
            'source':'MOD13A3.061','source_image_count':count,'qa_rule':QA_RULE,'configured_at_utc':configured_at}))

    start=ee.Date(start);end=ee.Date(end)
    count=(ee.Number(end.get('year')).subtract(start.get('year')).multiply(12)
           .add(ee.Number(end.get('month')).subtract(start.get('month'))))
    return ee.FeatureCollection(ee.List.sequence(0,count.subtract(1)).map(
        lambda i:monthly(start.advance(i,'month')))).flatten()


def submit_plan(ee, project, plan, manifest_path, force=False, nonpolar=False):
    """Initialize using pre-existing credentials and explicitly submit listed tasks."""
    manifest_path=Path(manifest_path)
    records=json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    scope='nonpolar' if nonpolar else 'full'
    if not force:
        for item in plan:
            duplicate=next((r for r in records if r.get('project')==project and r.get('start')==item['start']
                and r.get('end_exclusive')==item['end'] and r.get('scope','full')==scope and r.get('status') not in {'FAILED','CANCELLED'}),None)
            if duplicate:
                raise ValueError(f"Task already recorded for {item['start']} to {item['end']}: {duplicate['task_id']}. Poll --status; use --force only for intentional resubmission.")
    ee.Initialize(project=project)
    configured=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    new=[]
    for item in plan:
        description='mod13a3_grid10_'+item['label']+('_nonpolar' if nonpolar else '')
        task=ee.batch.Export.table.toDrive(collection=build_collection(ee,item['start'],item['end'],configured,nonpolar),
            description=description,folder='NASA_member_B_regional',fileNamePrefix=description,
            fileFormat='CSV',selectors=COLUMNS)
        task.start()
        record={'task_id':task.id,'description':description,'project':project,'start':item['start'],
                'end_exclusive':item['end'],'scope':scope,'region_count':len(export_grid(nonpolar)),
                'submitted_at_utc':configured,'status':'SUBMITTED'}
        records.append(record);new.append(record)
        manifest_path.parent.mkdir(parents=True,exist_ok=True)
        manifest_path.write_text(json.dumps(records,indent=2)+'\n')
    return new


def poll_status(ee, project, manifest_path):
    """Poll only recorded task IDs for this project; never create export tasks."""
    manifest_path=Path(manifest_path)
    records=json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    selected=[r for r in records if r.get('project')==project]
    if not selected: return []
    ee.Initialize(project=project)
    status={}
    for start in range(0,len(selected),100):
        for result in ee.data.getTaskStatus([r['task_id'] for r in selected[start:start+100]]):
            status[result['id']]=result
    updated=datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    for record in selected:
        result=status.get(record['task_id'],{})
        record['status']=result.get('state','UNKNOWN')
        record['status_checked_at_utc']=updated
        if result.get('error_message'): record['error_message']=result['error_message']
    manifest_path.write_text(json.dumps(records,indent=2)+'\n')
    return selected


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',required=True,help='Earth Engine enabled Google Cloud project ID')
    p.add_argument('--mode',choices=['pilot','years','month'],default='pilot')
    p.add_argument('--first-year',type=int,default=2003);p.add_argument('--last-year',type=int,default=2024)
    p.add_argument('--month',default='2003-01-01')
    p.add_argument('--nonpolar',action='store_true',help='Explicit partial export:576 unchanged cells excluding the two bands touching the poles')
    actions=p.add_mutually_exclusive_group();actions.add_argument('--submit',action='store_true');actions.add_argument('--status',action='store_true')
    p.add_argument('--force',action='store_true',help='Intentionally submit a duplicate recorded date range')
    p.add_argument('--task-manifest',type=Path,default=ROOT/'.cache/regional_modis_tasks.json')
    args=p.parse_args(argv)
    plan=export_plan(args.mode,args.first_year,args.last_year,args.month)
    if not args.project.strip(): p.error('--project must be nonempty')
    if args.force and not args.submit: p.error('--force requires --submit')
    if not args.submit and not args.status:
        result={'mode':'dry_plan','project':args.project,'task_count':len(plan),'tasks':plan,
                'region_count':len(export_grid(args.nonpolar)),'scope':'nonpolar' if args.nonpolar else 'full','catalog_region_count':648,'source':COLLECTION,'native_projection':True,'qa_rule':QA_RULE,
                'cloud_validation_status':'nonpolar_pilot_structurally_validated_source_pixel_review_pending' if args.nonpolar else 'failed_polar_bounds',
                'note':'No cloud calls. Nonpolar pilot CSV passed structural/provenance checks; source-pixel validation pending. Full-world mode still fails polar raster bounds.'}
    else:
        try: import ee
        except ImportError as exc: raise SystemExit('Install requirements-earthengine.txt in the existing environment first.') from exc
        if args.status:
            result={'mode':'status','tasks':poll_status(ee,args.project,args.task_manifest)}
        else:
            result={'mode':'submitted','tasks':submit_plan(ee,args.project,plan,args.task_manifest,force=args.force,nonpolar=args.nonpolar),
                    'local_task_manifest':str(args.task_manifest)}
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
