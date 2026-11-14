// Paste into https://code.earthengine.google.com/ after registering a project.
// Read docs/modis_download_options.md first. Cloud execution is not yet validated.
// Start with one month. Change MODE to 'years' only after checking the pilot CSV.
var MODE = 'pilot';
var FIRST_YEAR = 2003;
var LAST_YEAR = 2026;
var END_EXCLUSIVE = '2026-12-01'; // Request through November; availability may lag.

var COLLECTION_ID = 'MODIS/061/MOD13A3';
var collection = ee.ImageCollection(COLLECTION_ID);
var world = ee.Geometry.Rectangle([-180, -90, 180, 90], null, false);
// MODIS sinusoidal sphere; use this convention for both datasets in comparisons.
var EARTH_AREA_M2 = 4 * Math.PI * Math.pow(6371007.181, 2);
var configuredAt = new Date().toISOString();
var columns = [
  'date', 'region_id', 'variable', 'value', 'unit', 'source',
  'valid_area_fraction', 'quality_flag', 'valid_area_m2', 'region_area_m2',
  'source_image_count', 'source_asset_id', 'source_time_start',
  'source_crs', 'source_transform', 'qa_rule', 'configured_at_utc'
];

print('Latest available image date (check before requesting recent months)',
  ee.Date(collection.aggregate_max('system:time_start')));
print('Pilot bands', collection.first().bandNames());
print('Pilot NDVI projection', collection.first().select('NDVI').projection());

function summarize(image) {
  var raw = image.select('NDVI');
  var detailed = image.select('DetailedQA');
  var reliability = image.select('SummaryQA');
  var projection = raw.projection();
  // Keep source masks, reject fill/out-of-range values, apply QA before averaging.
  var valid = raw.gte(-2000).and(raw.lte(10000))
    .and(detailed.bitwiseAnd(3).eq(0)).and(reliability.eq(0));
  var area = ee.Image.pixelArea().updateMask(valid).rename('valid_area_m2');
  var weighted = raw.multiply(0.0001).multiply(area).rename('weighted_ndvi');
  var sums = weighted.addBands(area).unmask(0, false).reduceRegion({
    reducer: ee.Reducer.sum(),
    geometry: world,
    // A Projection object carries both the CRS and its native affine transform.
    // projection.transform() is WKT text, not the numeric list crsTransform expects.
    crs: projection,
    maxPixels: 1e10,
    tileScale: 4,
    bestEffort: false // Never silently substitute a coarser grid.
  });
  var covered = ee.Number(sums.get('valid_area_m2'));
  return ee.Dictionary({
    value: ee.Algorithms.If(covered.gt(0),
      ee.Number(sums.get('weighted_ndvi')).divide(covered.max(1)), null),
    valid_area_fraction: covered.divide(EARTH_AREA_M2),
    valid_area_m2: covered,
    // A global land-based sufficiency threshold has not been agreed yet.
    quality_flag: ee.Algorithms.If(covered.gt(0), 'coverage_review_required',
      'no_valid_pixels'),
    source_asset_id: ee.String(COLLECTION_ID).cat('/').cat(image.get('system:index')),
    source_time_start: image.date().format('YYYY-MM-dd'),
    source_crs: projection.crs(),
    source_transform: projection.transform()
  });
}

function monthlyRows(start, end) {
  start = ee.Date(start);
  end = ee.Date(end);
  var offsets = ee.List.sequence(0, end.difference(start, 'month').subtract(1));
  return ee.FeatureCollection(offsets.map(function(offset) {
    var date = start.advance(offset, 'month');
    var month = collection.filterDate(date, date.advance(1, 'month'));
    var count = month.size();
    var base = ee.Dictionary({
      date: date.format('YYYY-MM-dd'), region_id: 'whole_earth', variable: 'ndvi',
      unit: '1', source: 'MOD13A3.061', region_area_m2: EARTH_AREA_M2,
      source_image_count: count,
      qa_rule: 'raw NDVI [-2000,10000]; (DetailedQA & 3)==0; SummaryQA==0',
      configured_at_utc: configuredAt
    });
    // Preserve absent months as blank values. Never select an arbitrary duplicate.
    var absent = ee.Dictionary({
      value: null, valid_area_fraction: null, valid_area_m2: null,
      quality_flag: ee.Algorithms.If(count.eq(0), 'missing', 'duplicate_month'),
      source_asset_id: null, source_time_start: null,
      source_crs: null, source_transform: null
    });
    var result = ee.Dictionary(ee.Algorithms.If(count.eq(1),
      summarize(ee.Image(month.first())), absent));
    return ee.Feature(null, base.combine(result));
  }));
}

function exportMonths(start, end, label) {
  Export.table.toDrive({
    collection: monthlyRows(start, end),
    description: 'mod13a3_whole_earth_' + label,
    folder: 'NASA_member_B', fileNamePrefix: 'mod13a3_whole_earth_' + label,
    fileFormat: 'CSV', selectors: columns
  });
}

if (MODE === 'pilot') {
  exportMonths('2003-01-01', '2003-02-01', 'pilot_2003_01');
} else if (MODE === 'years') {
  for (var year = FIRST_YEAR; year <= LAST_YEAR; year++) {
    var end = year === LAST_YEAR ? END_EXCLUSIVE : (year + 1) + '-01-01';
    exportMonths(year + '-01-01', end, String(year));
  }
} else {
  throw new Error("MODE must be 'pilot' or 'years'");
}
