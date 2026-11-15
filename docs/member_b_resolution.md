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
| `data/processed/fine/central_us/monthly_timeseries.csv` | Combined actual native GLDAS and fine-cell NDVI observations after explicit import |
| `data/processed/fine/central_us/gldas_monthly_timeseries.csv` | Reusable native GLDAS source extraction |
| `data/processed/fine/central_us/source_manifest.json` | Original monthly input paths and SHA-256 hashes |
| `data/processed/fine/central_us/metadata.json` | Product/version, layer semantics, scaling, missing rules and limitations |
| `data/processed/fine/central_us/quality_report.csv` | Per-cell/variable temporal coverage and valid support |
| `data/requests/fine_central_us_1deg.json` | Bounded MODIS target request and frozen 2003–2024 period |

## Actual pilot verification

The native extraction has completed: **264 real monthly source files, 16 cells, 8,448 output rows, all finite**. Every cell has 264 months for each soil depth. Native centers are latitudes 37.125, 37.375, 37.625 and 37.875°N and longitudes −97.875, −97.625, −97.375 and −97.125°E.

A separate netCDF4 scalar-index check compared three source months, four tile corners and both depths against the xarray vector-indexed CSV output: 24 checks, maximum absolute difference **0.0 kg m-2**. `validation_report.json` records this evidence. This verifies indexing, layer sums and preserved source values; it does not establish independent scientific validation of the model or MODIS. At the initial GLDAS extraction stage, fine-cell NDVI was pending; subsequent actual retrieval and integration are recorded below.

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

The existing 10° importer does not accept fine-grid IDs. Fine exports use the dedicated strict fine-grid validator and incremental importer described below before joining the soil series. Whole-Earth and 10° NDVI means cannot be reused as fine-cell NDVI. Existing coarse processed artifacts are retained independently.

## Expansion after the pilot

Use bounded, native-aligned tiles and viewport/catalog paging. A 1° tile contains 16 source cells; tile jobs can read existing monthly GLDAS files by native indices, request only the corresponding MODIS aggregates, and store per-tile provenance/completeness. Dataset-level statistics must disclose their actual tested region family; a one-tile preview must not be presented as global multiple-testing validation.

The GLDAS envelope includes the north pole. The prior full-world MODIS reduction has a documented polar-bounds failure. This midlatitude pilot does not resolve that issue, and no polar cell is clipped or silently reclassified. Global native-grid delivery needs explicit handling and validation of every supported tile, including those touching the pole, plus independent MODIS source-pixel and footprint review.

## Fine MODIS validation and incremental import

`scripts/merge_fine_modis.py` supports a read-only pilot check by default:

```sh
.venv/bin/python scripts/merge_fine_modis.py /actual/path/fine_pilot.csv --expected-month 2003-01-01
```

The validator checks the exact canonical 0.25° target IDs, cell geometry and area, requested tile ID, target resolution, complete requested cell set for every included month, dates, units, scaled NDVI range, source asset/month, QA rules, valid areas and the original native MODIS projection. Source image counts and missing-image flags must agree. The pilot should normally remain validation-only: annual requests can have a different configuration timestamp, and changed source provenance on overlapping January rows deliberately raises a conflict.

Explicitly ingest actual accepted source CSVs:

```sh
.venv/bin/python scripts/merge_fine_modis.py --ingest /actual/path/annual2003.csv /actual/path/annual2004.csv
```

Imports preserve all previously accepted dates. Identical repeated observations are idempotent; a changed value or provenance field requires `--replace`, which changes only overlapping rows. All 264 month slots are retained for every requested cell, with unexported observations blank/NaN and flagged `pending_export`. Exported missing/no-valid-pixel months remain distinct. Every NDVI row, including pending rows, carries the native grid row/column and positive full-cell area denominator.

Exact input bytes are retained under SHA-256 filenames in `data/raw/modis_earth_engine/fine/`. The cumulative `modis_source_manifest.json` records archive paths, original filenames and hashes. `accepted_modis_observations.csv` links each authoritative accepted row to its source file hash; this also identifies accepted replacements without requiring arbitrary archive-file ordering. GLDAS source CSVs and their original source manifest are never rewritten. Catalog geometry stays fixed; availability counts/variables update, and quality reports/provenance are refreshed. Rebuild statistical outputs and the frontend data bundle after an import.

Export identity now hashes only the target tile/IDs/geometry/areas rather than mutable availability fields. Legacy and current duplicate-export guards match project/tile/date range, so updating NDVI availability cannot accidentally authorize another identical export.

## Bounded direct retrieval for the small fine tile

The controller verified that the same fine-cell aggregation graph can return a small interactive response using the existing authorized account/project. `scripts/fetch_fine_modis.py` retrieves that unchanged graph for **at most 16 cells**, one month or calendar year per request. It creates no batch export tasks, changes no account/project to avoid a limit, disables automatic client retries, and stops on service/quota errors. Every request has a maximum 30-second deadline.

Preview without network calls:

```sh
.venv/bin/python scripts/fetch_fine_modis.py --project earthrisk-greenmirage --mode years
```

Explicitly retrieve the 22 annual requests after pilot review:

```sh
.venv/bin/python scripts/fetch_fine_modis.py --project earthrisk-greenmirage --mode years --fetch
```

Use `--first-year` and `--last-year` to request a smaller frozen-period subset. The default cache is ignored `.cache/fine_modis_direct/`. Exact raw service responses are saved **before** validation; failed checks therefore remain replayable without another account call. Successful responses must cover every requested native cell/month and pass source/QA/projection checks before they become completed source CSVs. Immutable CSV/raw-response hashes and request receipts support resuming: verified completed years are reused, and an incomplete request is not marked complete. Tampered cached bytes cause an error. `--refresh --fetch` explicitly retrieves a new version while preserving existing source files. Retrieval does not ingest data automatically.

## Native monthly mosaic origins

The actual 2003 annual response exposed a valid source-grid variation: November and December have native mosaic origins shifted south by 1,200 and 2,400 pixels. Their sinusoidal CRS and approximately 926.625 m native pixel spacing are unchanged. Cropped monthly tile inventories need not share the full-world mosaic's upper-left origin.

Validation now accepts only complete **1,200-pixel MODIS tile translations** on that original lattice, within the MODLAND horizontal/vertical tile extent. It still rejects half-pixel shifts, partial-tile shifts, changed pixel spacing, shear and out-of-range tile origins. The actual source transform is retained exactly; it is never relabeled as the reference origin or used to justify resampling.

Evidence is retained in `data/raw/modis_earth_engine/fine_validation/annual2003_native_projection_response.json` with its hash and all 12 monthly source transforms in `data/processed/fine/central_us/modis_projection_validation.json`. Replaying that real response through the corrected validator accepted 192 rows, all finite. This is a projection/metadata consistency check, not independent source-pixel scientific validation. The tile-lattice reference is NASA's [MODLAND grid](https://modis-land.gsfc.nasa.gov/MODLAND_grid.html).

The controller's actual retrieval completed all 22 calendar-year requests, each returning 192 fine-cell rows. The batch pilot had remained queued while the project reported a noncommercial quota restriction, but the service permitted these bounded interactive requests. Retrieval used the same authorized account, the same project and the unchanged native aggregation graph. It did not open another account/project, submit replacement batch tasks, retry rejected calls automatically, or change resolution/QA. Future calls remain subject to service-enforced quotas and stop if rejected. The controller owns final ingestion and the resulting release audit; source-pixel/model scientific review remains a separate requirement.

## Current integrated fine release

The controller completed the actual fine release: **12,672 rows** comprising 8,448 native GLDAS observations and 4,224 received NDVI month/cell slots. NDVI has **4,222 valid values and two source-QA gaps**. Those missing values are preserved; no interpolation or invented replacement was applied. All 16 cells have paired data sufficient for the configured statistical preview, with a 32-test tile-scoped family. The result contains 12 cells with no detected divergence, four uncertain cells and zero supported signals. The pipeline does not manufacture hotspots to populate the map.

The fine release audit passed 1,110 integrity checks. This confirms the documented source/archive, grid, temporal and interface consistency; it does not establish globally validated fine-cell coverage, independent adjacent-cell observations, or completed ecological/source-pixel scientific review. The real fine observations currently cover only the explicitly documented Central-US tile.
