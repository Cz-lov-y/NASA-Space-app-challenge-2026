// Paste into Earth Engine CODE EDITOR (code.earthengine.google.com), not Cloud Shell.
// Native MOD13A3.061 QA/scaling retained. Start with MODE='pilot'.
var MODE = 'pilot'; // 'years' creates 22 annual tasks; 'month' retries one month.
var FIRST_YEAR = 2003;
var LAST_YEAR = 2024;
var RETRY_MONTH = '2003-01-01';
var collection = ee.ImageCollection('MODIS/061/MOD13A3');
var configuredAt = new Date().toISOString();
var features = [];
for (var r = 0; r < 18; r++) {
  for (var c = 0; c < 36; c++) {
    var west = -180 + c * 10, south = -90 + r * 10;
    var rid = 'grid_r' + ('0' + r).slice(-2) + '_c' + ('0' + c).slice(-2);
    var area = Math.pow(6371007.181, 2) * Math.PI / 18 *
      (Math.sin((south + 10) * Math.PI / 180) - Math.sin(south * Math.PI / 180));
    features.push(ee.Feature(ee.Geometry.Rectangle([west,south,west+10,south+10],null,false),
      {region_id:rid,region_area_m2:area}));
  }
}
var grid = ee.FeatureCollection(features);
var columns = ['date','region_id','variable','value','unit','source','valid_area_fraction',
  'valid_area_m2','region_area_m2','quality_flag','source_image_count','source_asset_id',
  'source_time_start','source_crs','source_transform','qa_rule','configured_at_utc'];
function oneMonth(date) {
  date = ee.Date(date);
  var month = collection.filterDate(date,date.advance(1,'month'));
  var count = month.size();
  var absent = grid.map(function(f) {return f.set({value:null, valid_area_m2:null,
    valid_area_fraction:null,quality_flag:ee.Algorithms.If(count.eq(0),'missing','duplicate_month'),
    source_asset_id:null,source_time_start:null,source_crs:null,source_transform:null});});
  // The empty branch avoids selecting a nonexistent image for absent months.
  var summarized = ee.Algorithms.If(count.eq(1), (function() {
    var image = ee.Image(month.first()), raw = image.select('NDVI');
    var projection = raw.projection();
    var detailed = image.select('DetailedQA'), summary = image.select('SummaryQA');
    // Explicitly intersect all source masks, and make masked QA pixels invalid
    // in both numerator and denominator before filling reduction gaps with zero.
    var valid = raw.mask().and(detailed.mask()).and(summary.mask())
      .and(raw.gte(-2000)).and(raw.lte(10000))
      .and(detailed.bitwiseAnd(3).eq(0)).and(summary.eq(0)).unmask(0);
    var area = ee.Image.pixelArea().updateMask(valid).rename('valid_area_m2');
    var weighted = raw.multiply(.0001).multiply(area).rename('weighted_ndvi');
    return weighted.addBands(area).unmask(0,false).reduceRegions({
      collection:grid,reducer:ee.Reducer.sum(),crs:projection,tileScale:4
    }).map(function(f) {
      var covered = ee.Number(f.get('valid_area_m2'));
      return f.set({value:ee.Algorithms.If(covered.gt(0),ee.Number(f.get('weighted_ndvi')).divide(covered.max(1)),null),
        valid_area_fraction:covered.divide(ee.Number(f.get('region_area_m2'))),
        quality_flag:ee.Algorithms.If(covered.gt(0),'coverage_review_required','no_valid_pixels'),
        source_asset_id:ee.String('MODIS/061/MOD13A3/').cat(image.get('system:index')),
        source_time_start:image.date().format('YYYY-MM-dd'),source_crs:projection.crs(),
        source_transform:projection.transform()});
    });
  })(), absent);
  return ee.FeatureCollection(summarized).map(function(f) {return f.set({
    date:date.format('YYYY-MM-dd'),variable:'ndvi',unit:'1',source:'MOD13A3.061',
    source_image_count:count,qa_rule:'raw NDVI [-2000,10000]; (DetailedQA & 3)==0; SummaryQA==0',
    configured_at_utc:configuredAt});});
}
function exportMonths(start,end,label) {
  start=ee.Date(start);end=ee.Date(end);
  var count=ee.Number(end.get('year')).subtract(start.get('year')).multiply(12)
    .add(ee.Number(end.get('month')).subtract(start.get('month')));
  var rows=ee.FeatureCollection(ee.List.sequence(0,count.subtract(1)).map(function(i) {
    return oneMonth(start.advance(i,'month'));
  })).flatten();
  Export.table.toDrive({collection:rows,description:'mod13a3_grid10_'+label,
    folder:'NASA_member_B_regional',fileNamePrefix:'mod13a3_grid10_'+label,
    fileFormat:'CSV',selectors:columns});
}
if (MODE==='pilot') exportMonths('2003-01-01','2003-02-01','pilot_2003_01');
else if (MODE==='years') {
  for (var year=FIRST_YEAR;year<=LAST_YEAR;year++)
    exportMonths(year+'-01-01',(year+1)+'-01-01',String(year));
} else if (MODE==='month') exportMonths(RETRY_MONTH,ee.Date(RETRY_MONTH).advance(1,'month'),'retry_'+RETRY_MONTH.replace(/-/g,''));
else throw new Error("MODE must be pilot, years or month");
print('Region count',grid.size());
print('Native MODIS projection',collection.first().select('NDVI').projection());
