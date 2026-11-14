# GLDAS integration sample

This is real NASA-derived model output, not synthetic data. It is an integration sample, not the project's whole-Earth study region.

- Region ID: `central_us_sample`; rectangle longitude −100 to −90, latitude 35 to 45, WGS84 (EPSG:4326). The bounds align with the 0.25° grid, so no partial cells occur.
- Source: NASA GLDAS Noah `GLDAS_NOAH025_M.2.1`, monthly 0.25° model output, surface layer `SoilMoi0_10cm_inst`, exported as `soil_water_0_10cm`. This is model-estimated soil water, not a direct satellite observation or total root-zone storage.
- Unit: `kg m-2`; no unit conversion or additional scaling. The processor checks for non-identity scale/offset and uses xarray CF decoding. The files describe `cell_methods: time: mean`; their monthly values are spatially averaged, with no additional temporal averaging.
- Period: 2003-01 through 2024-12, inclusive, one row for every month. Source time coordinates and file uniqueness are checked. Extra 2025–2026 data are outside this sample.
- Source fill/missing value is −9999 (verified in the January 2003 source); xarray decodes declared per-file missing values to NaN. Missing CSV values are empty fields, never zero or interpolated. The script checks units, monthly time method, grid spacing, and source time. Finite values are retained; any negative values flag the month rather than being deleted. This is basic validation, not a comprehensive scientific quality assessment.
- The mean uses cosine-of-latitude weights, equivalent to spherical cell-area weights on this regular grid. `valid_area_fraction` is the valid weighted cell area divided by the entire rectangle area. Flag `low_coverage` when this fraction is below 0.8; this is a provisional project choice, not a NASA threshold. If any occur, exclude them from a primary statistical analysis or run a sensitivity analysis with and without them, and report the choice. `missing` is excluded; investigate `negative_value` before use. A `good` flag only reflects these checks.
- For this run, all 264 months have data, coverage is 1.0 for each month, and all are flagged `good`. This should not be generalized to other regions or periods. Filename version is consistent with the requested product; independent verification of every upstream archive granule and broader physical plausibility has not been performed.

## Reproduce

From repository root, install `requirements-data.txt`, retain the original files in `data/raw/gldas`, and run `python scripts/export_gldas_integration.py`. The script reads the monthly subsetted NetCDF files, masks declared fill values, validates units and coordinates, computes the weighted means and coverage, and writes both CSVs. `source_manifest.json` lists every source file and its SHA-256 checksum. `quality_report.csv` reports counts, date list of missing months, coverage range/mean, flag counts and value range; per-month coverage and flags are in `monthly_timeseries.csv`.
