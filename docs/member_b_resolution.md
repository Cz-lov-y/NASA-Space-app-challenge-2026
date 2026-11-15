# Member B: finest defensible shared grid

The finest shared analysis cells supported by the current inputs are the **native GLDAS 0.25° cells**. MOD13A3 NDVI is approximately 1 km, but GLDAS soil water is provided at 0.25°. The paired analysis therefore aggregates the original MODIS pixels into exact GLDAS cell footprints. It does not divide 10° means into smaller cells, interpolate soil water onto a 1 km grid, or imply that adjacent model cells are independent observations.

At the Central-US pilot latitude, 0.25° is approximately 22 km east–west by 28 km north–south. Geographic cell sizes vary with latitude. Native model resolution identifies the source support; it does not establish validated ecological risk at that scale.

## Native grid and stable identity

- CRS: EPSG:4326.
- Native GLDAS envelope: `[-180, -60, 180, 90]`, 600 latitude rows × 1,440 longitude columns.
- Row 0 begins at 60°S and rows increase northward. Column 0 begins at 180°W and columns increase eastward. Native centers are `lat = -59.875 + row × 0.25` and `lon = -179.875 + col × 0.25`.
- IDs: `gldas025_r{row:03d}_c{col:04d}`. Geographic support and valid land-model availability are separate: a geometrically defined cell may have no valid source values. Outside the envelope, GLDAS is unsupported.
- The envelope contains 864,000 possible cells. Global metadata define this grid lazily; the repository does not eagerly generate a global 864,000-feature GeoJSON or label every geometric cell as land.

The first tile is `central_us_1deg`, bounding box `[-98, 37, -97, 38]`. It consists of 16 complete native cells: rows 388–391 and columns 328–331. The tile is a bounded pilot for a scalable native-grid pipeline. It is not evidence of global fine-cell coverage.

## GLDAS extraction

`scripts/process_fine_gldas.py` verifies the full source coordinate arrays, increasing latitude/longitude orientation, monthly time coordinate, units, temporal method and identity scaling before indexing the native cells. It reads each selected cell directly from the existing original monthly NetCDF source files.

`soil_water_0_10cm` retains the original `SoilMoi0_10cm_inst` cell. `soil_water_0_100cm` sums the 0–10, 10–40 and 40–100 cm layer values at the same cell, requiring all three to be finite. Both remain `kg m-2`. The source reports `time: mean` despite the `_inst` variable suffix; the output retains those monthly means. Missing/fill values remain NaN/blank CSV, and no observations are fabricated.

For a single native GLDAS cell, valid-area fraction is 1 when the required native value/layers are valid and 0 when invalid. This represents valid model support, not independent within-cell measurements. Missing source months have missing area/coverage. Finite values remain `coverage_review_required`; negative source values are flagged and preserved.

Run locally:

```sh
.venv/bin/python scripts/process_fine_gldas.py
```

Outputs are separate from the existing 10° data:

| File | Purpose |
| --- | --- |
| `data/processed/fine/grid_definition.json` | Lazy native global-grid envelope and indexing definition |
| `data/processed/fine/central_us/catalog.json` | Sixteen exact native cell boundaries, indices, availability and geographic country candidates |
| `data/processed/fine/central_us/monthly_timeseries.csv` | Actual native GLDAS monthly observations; NDVI remains pending |
| `data/processed/fine/central_us/gldas_monthly_timeseries.csv` | Reusable native GLDAS source extraction |
| `data/processed/fine/central_us/source_manifest.json` | Original monthly input paths and SHA-256 hashes |
| `data/processed/fine/central_us/metadata.json` | Product/version, layer semantics, scaling, missing rules and limitations |
| `data/processed/fine/central_us/quality_report.csv` | Per-cell/variable temporal coverage and valid support |
| `data/requests/fine_central_us_1deg.json` | Bounded MODIS target request and frozen 2003–2024 period |

## Actual pilot verification

The native extraction has completed: **264 real monthly source files, 16 cells, 8,448 output rows, all finite**. Every cell has 264 months for each soil depth. Native centers are latitudes 37.125, 37.375, 37.625 and 37.875°N and longitudes −97.875, −97.625, −97.375 and −97.125°E.

A separate netCDF4 scalar-index check compared three source months, four tile corners and both depths against the xarray vector-indexed CSV output: 24 checks, maximum absolute difference **0.0 kg m-2**. `validation_report.json` records this evidence. This verifies indexing, layer sums and preserved source values; it does not establish independent scientific validation of the model or MODIS. All fine-cell NDVI remains pending until an actual export is checked and integrated.

## Native MODIS aggregation into those exact cells

`scripts/export_fine_modis_earth_engine.py` reads the checked-in tile request/catalog. It validates the native cell IDs and exact 0.25° bounds, then reduces the original MOD13A3.061 pixels in the source sinusoidal projection. It intersects NDVI, DetailedQA and SummaryQA masks, applies raw NDVI range [-2000, 10000], DetailedQA bits 0–1 equal to 0, SummaryQA equal to 0, and scales NDVI by 0.0001 once. It computes pixel-area weighted means into each unchanged GLDAS footprint. No alternate/coarser source scale or `bestEffort` substitution is used.

The pilot requests January 2003 only: 16 rows. After checking its actual CSV, the full required period is 264 months per cell, or 4,224 NDVI rows. Yearly exports contain 192 rows each. These aggregate tables avoid downloading global MODIS rasters. Coverage is valid MODIS area divided by the whole native GLDAS footprint; source support can still differ between indicators and must be reviewed.

Preview without cloud calls:

```sh
.venv/bin/python scripts/export_fine_modis_earth_engine.py --project earthrisk-greenmirage --mode pilot
```

The controller can explicitly submit one pilot using the already authorized OAuth account/project:

```sh
.venv/bin/python scripts/export_fine_modis_earth_engine.py --project earthrisk-greenmirage --mode pilot --submit
```

The controller submitted the fine pilot as `DDCABQK6DQS4LU2TMPYCBK4S`; last recorded state READY. See `data/requests/fine_earth_engine_tasks.json`. No fine annual batch has been submitted. Account authorization alone does not verify the new fine-cell output. Task IDs are stored in ignored `.cache/fine_modis_tasks.json`; duplicate tile/catalog/date submissions are guarded. Inspect status with `--status`. Only after pilot review, the controller can use `--mode years --submit` for the 22 annual tasks or `--mode month --month YYYY-MM-01 --submit` for a single retry. Outputs go to Drive folder `NASA_member_B_fine`, with prefix `mod13a3_gldas025_central_us_1deg_`.

The existing 10° importer does not accept fine-grid IDs. Fine exports need fine-grid source validation and integration before they can join the soil series. Whole-Earth and 10° NDVI means cannot be reused as fine-cell NDVI. Existing coarse processed artifacts are retained independently.

## Expansion after the pilot

Use bounded, native-aligned tiles and viewport/catalog paging. A 1° tile contains 16 source cells; tile jobs can read existing monthly GLDAS files by native indices, request only the corresponding MODIS aggregates, and store per-tile provenance/completeness. Dataset-level statistics must disclose their actual tested region family; a one-tile preview must not be presented as global multiple-testing validation.

The GLDAS envelope includes the north pole. The prior full-world MODIS reduction has a documented polar-bounds failure. This midlatitude pilot does not resolve that issue, and no polar cell is clipped or silently reclassified. Global native-grid delivery needs explicit handling and validation of every supported tile, including those touching the pole, plus independent MODIS source-pixel and footprint review.
