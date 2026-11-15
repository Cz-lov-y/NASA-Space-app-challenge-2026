#!/usr/bin/env python3
"""Export native MODIS means into exact native GLDAS0.25-degree tile cells.

Default is a local dry plan. --submit explicitly starts cloud tasks; the
controller owns that action. No downscaled soil values or coarse-region means.
"""
from pathlib import Path
import argparse
from datetime import datetime,timezone
import hashlib
import json
import re
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts.export_regional_modis_earth_engine import COLUMNS,QA_RULE,export_plan,poll_status


def load_request(path):
    from src.fine_grid import cell_bbox,parse_cell_id
    path=Path(path);request=json.loads(path.read_text())
    tile=request['tile_id']
    if not re.fullmatch(r'[A-Za-z0-9_-]+',tile):raise ValueError('Invalid tile identifier')
    catalog_path=Path(request['catalog']);catalog_path=catalog_path if catalog_path.is_absolute() else ROOT/catalog_path
    catalog=json.loads(catalog_path.read_text());features=catalog['features']
    if not 1<=len(features)<=4096:raise ValueError('Use a bounded tile of at most4096native cells')
    ids=[]
    for feature in features:
        p=feature['properties'];row,col=parse_cell_id(p['region_id']);ids.append(p['region_id'])
        if list(p['bbox'])!=list(cell_bbox(row,col)):raise ValueError('Catalog cell boundary differs from native GLDAS grid')
        if p.get('native_resolution_degrees',.25)!=.25:raise ValueError('Target must be native0.25degree GLDAS')
    if len(set(ids))!=len(ids):raise ValueError('Duplicate fine cell IDs')
    target={'tile_id':tile,'source':'MODIS/061/MOD13A3','target_grid':'gldas025','cells':sorted(
        [{'region_id':f['properties']['region_id'],'bbox':f['properties']['bbox'],
          'region_area_m2':f['properties']['region_area_m2'],'geometry':f['geometry']} for f in features],key=lambda c:c['region_id'])}
    # Availability/provenance changes must not make a duplicate export look new.
    digest=hashlib.sha256(json.dumps(target,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return request,catalog,digest


def build_collection(ee,catalog,start,end,configured,tile_id):
    grid=ee.FeatureCollection([ee.Feature(ee.Geometry.Rectangle(f['properties']['bbox'],None,False),
        {'region_id':f['properties']['region_id'],'region_area_m2':f['properties']['region_area_m2']}) for f in catalog['features']])
    collection=ee.ImageCollection('MODIS/061/MOD13A3')
    def monthly(date):
        date=ee.Date(date);images=collection.filterDate(date,date.advance(1,'month'));count=images.size()
        def absent(f):return f.set({'value':None,'valid_area_m2':None,'valid_area_fraction':None,
            'quality_flag':ee.Algorithms.If(count.eq(0),'missing','duplicate_month'),
            'source_asset_id':None,'source_time_start':None,'source_crs':None,'source_transform':None})
        image=ee.Image(images.first());raw=image.select('NDVI')
        detailed=image.select('DetailedQA');summary=image.select('SummaryQA');projection=raw.projection()
        valid=(raw.mask().And(detailed.mask()).And(summary.mask()).And(raw.gte(-2000)).And(raw.lte(10000))
            .And(detailed.bitwiseAnd(3).eq(0)).And(summary.eq(0)).unmask(0))
        area=ee.Image.pixelArea().updateMask(valid).rename('valid_area_m2')
        weighted=raw.multiply(.0001).multiply(area).rename('weighted_ndvi')
        reduced=weighted.addBands(area).unmask(0,False).reduceRegions(collection=grid,
            reducer=ee.Reducer.sum(),crs=projection,tileScale=4)
        def summarize(f):
            covered=ee.Number(f.get('valid_area_m2'))
            return f.set({'value':ee.Algorithms.If(covered.gt(0),ee.Number(f.get('weighted_ndvi')).divide(covered.max(1)),None),
                'valid_area_fraction':covered.divide(ee.Number(f.get('region_area_m2'))),
                'quality_flag':ee.Algorithms.If(covered.gt(0),'coverage_review_required','no_valid_pixels'),
                'source_asset_id':ee.String('MODIS/061/MOD13A3/').cat(image.get('system:index')),
                'source_time_start':image.date().format('YYYY-MM-dd'),'source_crs':projection.crs(),
                'source_transform':projection.transform()})
        result=ee.FeatureCollection(ee.Algorithms.If(count.eq(1),reduced.map(summarize),grid.map(absent)))
        return result.map(lambda f:f.set({'date':date.format('YYYY-MM-dd'),'variable':'ndvi','unit':'1','source':'MOD13A3.061',
            'source_image_count':count,'qa_rule':QA_RULE,'configured_at_utc':configured,'tile_id':tile_id,'target_resolution_degrees':.25}))
    start=ee.Date(start);end=ee.Date(end)
    n=(ee.Number(end.get('year')).subtract(start.get('year')).multiply(12)
        .add(ee.Number(end.get('month')).subtract(start.get('month'))))
    return ee.FeatureCollection(ee.List.sequence(0,n.subtract(1)).map(lambda i:monthly(start.advance(i,'month')))).flatten()


def submit(ee,project,request,catalog,catalog_sha,plan,manifest_path,force=False):
    manifest_path=Path(manifest_path);records=json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    tile=request['tile_id']
    if not force:
        for item in plan:
            if any(r.get('project')==project and r.get('tile_id')==tile and
                r.get('start')==item['start'] and r.get('end_exclusive')==item['end'] and r.get('status') not in {'FAILED','CANCELLED'} for r in records):
                raise ValueError('Fine export already recorded; poll status or explicitly --force an intentional retry')
    ee.Initialize(project=project);configured=datetime.now(timezone.utc).isoformat().replace('+00:00','Z');new=[]
    for item in plan:
        name='mod13a3_gldas025_'+tile+'_'+item['label']
        task=ee.batch.Export.table.toDrive(collection=build_collection(ee,catalog,item['start'],item['end'],configured,tile),
            description=name,folder='NASA_member_B_fine',fileNamePrefix=name,fileFormat='CSV',
            selectors=COLUMNS+['tile_id','target_resolution_degrees'])
        task.start()
        record={'task_id':task.id,'description':name,'project':project,'tile_id':tile,'catalog_sha256':catalog_sha,'target_geometry_sha256':catalog_sha,
            'start':item['start'],'end_exclusive':item['end'],'region_count':len(catalog['features']),
            'scope':'native_gldas025_tile','status':'SUBMITTED','submitted_at_utc':configured}
        records.append(record);new.append(record);manifest_path.parent.mkdir(parents=True,exist_ok=True)
        manifest_path.write_text(json.dumps(records,indent=2)+'\n')
    return new


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',required=True)
    p.add_argument('--request',type=Path,default=ROOT/'data/requests/fine_central_us_1deg.json')
    p.add_argument('--mode',choices=['pilot','years','month'],default='pilot');p.add_argument('--month',default='2003-01-01')
    group=p.add_mutually_exclusive_group();group.add_argument('--submit',action='store_true');group.add_argument('--status',action='store_true')
    p.add_argument('--force',action='store_true');p.add_argument('--task-manifest',type=Path,default=ROOT/'.cache/fine_modis_tasks.json')
    args=p.parse_args(argv)
    if args.force and not args.submit:p.error('--force requires --submit')
    if not args.project.strip():p.error('--project must be nonempty')
    request,catalog,digest=load_request(args.request)
    plan=export_plan(args.mode,request.get('first_year',2003),request.get('last_year',2024),args.month)
    if not args.submit and not args.status:
        result={'mode':'dry_plan','tile_id':request['tile_id'],'bbox':request['bbox'],'region_count':len(catalog['features']),
            'target_resolution_degrees':.25,'source':'MODIS/061/MOD13A3','native_projection':True,'qa_rule':QA_RULE,
            'task_count':len(plan),'tasks':plan,'catalog_sha256':digest,
            'status':'fine tile source-pixel/cloud pilot validation pending; no cloud calls made'}
    else:
        import ee
        result={'mode':'status','tasks':poll_status(ee,args.project,args.task_manifest)} if args.status else {
            'mode':'submitted','tasks':submit(ee,args.project,request,catalog,digest,plan,args.task_manifest,args.force)}
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
