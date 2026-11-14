# NASA data: Member B

## Status and study area

**The authentic-data milestone is not yet complete.** There are 318 downloaded GLDAS files in `data/raw/gldas` (January 2000–June 2026 by filename); a complete content/quality audit and global processing remain outstanding. The user reports six AppEEARS requests with the first processing slowly and the others pending. `data/sample/demo_timeseries.csv` is synthetic. The requested region is the whole Earth, including oceans; its WGS84 boundary is `data/regions/whole_earth.geojson` (longitude −180 to 180, latitude −90 to 90). A global result is a single aggregate, not an analysis of regional variation.

See [MODIS download alternatives and pilot instructions](modis_download_options.md) for a way to export monthly statistics from NASA MOD13A3 data in Google Earth Engine, and the smaller official NASA MOD13C2 alternative. Neither alternative has been adopted or validated yet. The latter changes the product and introduces historical-climatology considerations; the former changes local raw-raster preservation to cloud provenance unless originals are separately archived. Existing AppEEARS request files remain unchanged.

Global processing requires additional work: `scripts/process_nasa_data.py` currently handles only non-antimeridian regional rasters and explicitly rejects the global polygon. It expects one aligned GeoTIFF per MODIS layer and month and cannot yet merge global tiles. Do not use it to report a global result. Global MODIS volume, tiling, reprojected cell areas, polar handling, and incomplete product coverage must be addressed and checked against real files. No observed monthly availability or coverage has been established. Keep raw files, request metadata, retrieval dates, product versions and any processing settings for reproducibility.

## Interpretation of whole-Earth coverage

The chosen boundary includes oceans, while GLDAS soil moisture is a land-model estimate and MODIS vegetation observations also have their own land, cloud, ice, and other quality limitations. Consequently, neither series represents an observation over every part of the Earth, and the valid geographical footprint can differ between datasets and from month to month. `valid_area_fraction` uses the whole Earth, including oceans, as its denominator; low percentages are expected and do not by themselves mean that the available land observations are poor quality. The prototype's 0.8 threshold is unsuitable for this global denominator and must be reviewed before producing global flags. A pair of global averages can summarize different geographic footprints and cannot establish that greening and drying occurred in the same places. Report both coverage fractions and their differences, and discuss any substantial mismatch with the team before interpreting results or changing the boundary. No global coverage has yet been measured.

## Sources and variables

- [MOD13A3 Collection 6.1 user guide](https://modis-land.gsfc.nasa.gov/pdf/MOD13_User_Guide_V61.pdf), accessed through [AppEEARS](https://appeears.earthdatacloud.nasa.gov/): monthly 1 km NDVI, VI Quality and Pixel Reliability. Raw NDVI has scale 0.0001 and fill −3000; confirm whether the downloaded representation is raw or already scaled. Never apply scaling twice.
- [GLDAS dataset documentation](https://ldas.gsfc.nasa.gov/gldas/dataset) and [data access](https://ldas.gsfc.nasa.gov/gldas/gldas-get-data): GLDAS_NOAH025_M.2.1, monthly 0.25-degree Noah model outputs `SoilMoi0_10cm_inst`, `SoilMoi10_40cm_inst`, and `SoilMoi40_100cm_inst`, in kg m-2. Despite `_inst`, select the monthly product. GLDAS soil moisture is **model-estimated**, not a direct satellite measurement. Sum the three layers on cells where all three exist for 0–100 cm soil water storage; retain the 0–10 cm layer. Storage is not universally root-zone moisture. See [LDAS FAQ](https://ldas.gsfc.nasa.gov/index.php/faq/all) for unit interpretation.

## Regional prototype (not global-ready)

Install using `python -m pip install -r requirements-data.txt`. Download gridded, non-aggregated files with the same boundary, and create a manifest CSV with header `date,ndvi,vi_quality,pixel_reliability,scale`. Each row references three aligned single-band GeoTIFF files relative to the manifest; `scale` must be `raw` or `scaled` as verified in the downloaded product metadata. Supply the original gridded NetCDF files with all three GLDAS layers, 0.25-degree lat/lon axes, units and time coordinates. The prototype does not identify source versions automatically: verify product identities, versions, monthly dates, and scaling from NASA's download metadata before running.

```
python scripts/process_nasa_data.py --region path/to/region.geojson --region-id region_001 \
  --modis-manifest path/to/manifest.csv --gldas path/to/file1.nc path/to/file2.nc
```

MODIS rules: retain pixels only when quality bits 0–1 are `00`, pixel reliability is 0, the bands are not masked/fill, and the scaled NDVI is within the documented −0.2 to 1.0 range. The script weights raster cells by approximate intersection area in a locally centered equal-area projection; valid-area fraction uses the whole region area as denominator. For GLDAS, the total is computed per cell using a common valid mask before averaging; surface and total can have different coverage. Coverage below 0.8 is flagged `low_coverage` (configurable); this is a provisional screening threshold, not a NASA recommendation. Missing months remain empty; the 264-month index is retained. Negative soil values are flagged in the quality report rather than deleted. A missing raster month has unknown coverage, while a present raster with no valid pixels has zero coverage.

The regional prototype writes `monthly_timeseries.csv`, `quality_report.csv`, and two time-series PNGs. It is tested with synthetic fixtures, not actual NASA downloads. Regional projection approximates curved cell edges as straight segments; evaluate errors for the chosen grid and region. No interpolation is performed. For whole Earth, ocean and ice/unobserved areas contribute to the area denominator, making the 0.8 threshold unsuitable and likely to flag most or all months. MODIS and GLDAS differ greatly in native resolution and valid spatial footprint; report both coverage fractions and notify the team if they differ substantially. Do not silently redefine the boundary.

## Next steps for the global request

1. Create or sign in to an [Earthdata Login](https://urs.earthdata.nasa.gov/), accept any requested data-access agreements, and use that account for the services. Do not put passwords or tokens in this repository.
2. Adapt the processor for chunked, tiled global data, antimeridian and polar geometry, duplicate/overlapping tiles, and mathematically sound global area weighting. Verify it against actual service output and retain versioned raw input.
3. Request the MODIS layers and GLDAS layers for January 2003 through December 2024. A world-scale MODIS extraction may require partitioned requests and substantial storage; check actual service constraints. Preserve download metadata. Do not use Giovanni area-averaged time series as if they were gridded inputs or assume they use the same valid footprint.
4. Generate the 792-row, three-variable output, coverage statistics, quality report and plots only after real data are available and validation passes. Coordinate with the team about the global denominator and coverage mismatch before changing the region.
