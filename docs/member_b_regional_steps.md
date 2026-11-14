# Member B: regional data and human handoff

The global globe demo needs regional observations. The existing whole-Earth mean cannot locate hotspots. The new backend uses 648 stable 10° cells covering the entire globe. IDs run south to north, west to east (`grid_r00_c00` through `grid_r17_c35`). Coarse cells are an initial screening resolution and can span several countries. Member D's humans own frontend design and implementation; these files supply their data interfaces.

## Completed automatically

- All 264 real GLDAS monthly inputs for January 2003–December 2024 processed into 301 cells with valid land-model data. Each cell has 264 observations for each of `soil_water_0_10cm` and `soil_water_0_100cm`: 158,928 real NASA-derived rows. The remaining 347 cells stay in the catalog as `unsupported_gldas`, including oceans and latitudes outside the product's support. Unsupported means unsupported by this indicator, not environmentally safe.
- Units remain `kg m-2`; 0–100 cm sums the three layers before averaging and requires all three finite at each native pixel. Monthly source means are preserved. Scaling is checked and applied through CF decoding once. Missing/fill values stay missing. Original raw inputs remain intact.
- Means use exact spherical native-cell areas. All 528 monthly/depth regional partitions reconcile with existing global GLDAS means to a maximum absolute difference of approximately 1.06e-12 kg m-2. This is a consistency check, not independent source QA approval.
- Natural Earth 1:110m country polygons provide country overlap candidates ranked by land overlap area. The public-domain boundary file and its hash are retained. These approximate geography records do not establish current legal authority or resolve disputed borders.
- Regional Earth Engine exporter, strict CSV merger and meaningful partition/provenance tests are available. No regional MODIS values have been invented. Current cells remain `pending_ndvi` until actual regional exports arrive.

## Files and interfaces for A, C and D

| File | Meaning |
| --- | --- |
| `data/regions/grid_10deg.geojson` | Exhaustive grid and geographic country candidates; initial data status |
| `data/processed/regional/catalog.json` | Current availability for every cell, geometry, bounding box, centroid, countries and variable names |
| `data/processed/regional/monthly_timeseries.csv` | Current observations, required six columns plus area coverage and quality flag |
| `data/processed/regional/gldas_monthly_timeseries.csv` | Reusable real GLDAS input to the MODIS merger |
| `data/processed/regional/metadata.json` | Product/version, processing, native resolution, missing rules and limitations |
| `data/processed/regional/source_manifest.json` | GLDAS source filenames and SHA-256 hashes |
| `data/processed/regional/quality_report.csv` | Per-region/variable temporal counts and min/max valid-area coverage |
| `data/processed/regional/validation_report.json` | Regional partition consistency results |

Catalog GeoJSON features contain `properties.region_id`, `bbox`, `centroid` in longitude/latitude order, `region_area_m2`, `variables`, `data_status`, `ndvi_status`, and `jurisdictions`. Country records contain `name`, `country_code`, `land_area_fraction`, `region_area_fraction`, source and uncertainty. Empty country lists are explicitly unresolved/no coarse-boundary overlap; do not substitute the centroid's country.

Coverage is valid source area divided by the **whole 10° cell including oceans**. Coastal or small-island cells may have low fractions and valid data. Do not reject every cell below 0.8. `coverage_review_required` stays visible; missing or changing support needs review before interpreting trends. MODIS and GLDAS supports may differ within a cell, so opposing regional trends are preliminary screening rather than proof of pixel-level co-occurrence.

## Human steps: acquire the missing regional MODIS

1. Open the [Earth Engine Code Editor](https://code.earthengine.google.com/) with the same approved account/project used for previous exports. This JavaScript runs in the Code Editor, not the Cloud Shell terminal.
2. Open local `scripts/export_regional_modis_earth_engine.js`, copy its contents into a new Code Editor script, and save it as `EarthRisk regional MODIS`.
3. Keep `MODE = 'pilot'` and click **Run** above the editor. Confirm the console region count is 648. In **Tasks**, click **Run** for `mod13a3_grid10_pilot_2003_01`; keep the proposed Google Drive CSV export settings and submit.
4. When the task completes, open Google Drive folder `NASA_member_B_regional`, download its pilot CSV, and make it available locally. The controller can validate it with the command below. A complete pilot has 648 rows, one region/month each; ocean cells can have blank NDVI and `no_valid_pixels`.
5. After pilot validation, change `MODE` to `'years'`, retain `FIRST_YEAR = 2003` and `LAST_YEAR = 2024`, and click **Run**. This prepares 22 yearly export tasks. Submit them in the Tasks panel. Do not raise the spatial scale or enable a coarse approximation to speed them up.
6. Each completed annual CSV should contain 7,776 rows (648 regions × 12 months). Download all completed annual CSVs from the same Drive folder into a local directory. Keep their filenames beginning `mod13a3_grid10_`. These are regional aggregates; the prior `whole_earth` exports cannot replace them.
7. Give the controller the downloaded directory path. It can merge available years immediately, preserve all unexported months as missing, rebuild screening results, and supply the updated catalog to A/C/D. Once full annual exports are available, exclude the pilot CSV from the merge because it duplicates January 2003.
8. If an annual task exceeds limits, set `MODE = 'month'` and `RETRY_MONTH = 'YYYY-MM-01'`, then run/export each month of that failed year. Keep exactly one accepted CSV per region/month: merge the 12 replacement monthly files **instead of** the failed/partial annual file. Report the exact error if the monthly retry also fails.

The cloud exporter is prepared but has not been executed or independently validated in this local session. Task completion and account permissions remain external dependencies. No deadline guarantees are attached to Earth Engine processing.

## Commands the controller can automate

From the repository root, using the existing Python 3.12 environment:

```sh
.venv/bin/python scripts/process_regional_gldas.py
.venv/bin/python -m pytest tests/test_regional_data.py -q
```

The first command rebuilds GLDAS outputs and resets the combined table to GLDAS only. Run the merger afterward to restore imported NDVI. Country enrichment is reproducible from the checked-in Natural Earth GeoJSON when that file is present.

Validate the pilot without changing any accepted dataset (replace the path with its real location):

```sh
.venv/bin/python scripts/merge_regional_timeseries.py --validate-only /absolute/path/mod13a3_grid10_pilot_2003_01.csv
```

The read-only audit reports month-level region counts, QA flags, valid area and the area-weighted partition NDVI mean. It verifies the source asset month and retained native sinusoidal affine transform. A complete pilot must show `all_exported_months_cover_full_grid: true`. The audit verifies structure and declared provenance; independent source-pixel validation is still pending. It creates no output files and never resets previously imported data.

Ingest annual files together, excluding the pilot:

```sh
.venv/bin/python scripts/merge_regional_timeseries.py /absolute/path/mod13a3_grid10_20[0-9][0-9].csv
```

Each merge uses the supplied exports as the full accepted MODIS input set; pass all accepted files again when adding another year. A guard rejects a merge that would discard previously imported region/months. `--replace` permits an intentional replacement and makes omitted observations pending again; it is not needed when simply adding annual files. Inputs are not automatically archived, so retain the accepted CSV files. Filenames and hashes are saved in `modis_source_manifest.json`. Keep the original downloaded CSVs: hashes identify inputs but cannot reproduce their contents without those source exports. The merger validates stable region IDs, month uniqueness, period, units, range/scaling, area coverage consistency, source assets/time and QA provenance. It preserves blank/unexported months and never turns them into zero. `ndvi_exported_months` records actual imported rows separately from `ndvi_valid_months`. Full exported coverage with missing observations is `complete_with_missing` / `incomplete_ndvi`; full exports with no valid observations are `no_valid_observations` / `unavailable_ndvi`. An exported month with no valid pixels is distinct from `pending_export`.

## Remaining human decisions and scientific work

- Confirm 10° screening is acceptable for the demo. A cell can contain several jurisdictions; policy research should identify its country choices explicitly.
- Launch and retrieve regional MODIS exports; local workers cannot grant account access or create export results without the authenticated account.
- Review scientific limitations and coverage decisions with Member A. Further independent MODIS pixel validation, common valid-footprint analysis and effect-size/serial-dependence review remain necessary for strong ecological claims.
- D's humans implement the interactive globe and region selection using this catalog and A's screening output. They must display pending/unsupported cells accurately and avoid presenting GLDAS-only cells as identified greening/drying hotspots.

## Exporter method review

The reduction receives the source NDVI `Projection` object, carrying its native affine transform. It sets neither an alternate scale nor `bestEffort`; the importer checks the retained native affine and CRS. The valid mask explicitly intersects the NDVI, DetailedQA and SummaryQA source masks before applying the range and QA rules. Masked QA values become invalid for both weighted NDVI and valid-area reductions. The exporter retains source assets and timestamps for every existing monthly image, including regions with zero valid pixels.

References checked during review: [Earth Engine reduceRegions](https://developers.google.com/earth-engine/apidocs/ee-image-reduceregions), [updateMask](https://developers.google.com/earth-engine/apidocs/ee-image-updatemask), and [MOD13A3.061 catalog](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13A3). These API and dataset checks support the intended calculation; cloud execution and independent source-pixel verification are still pending.

A bounded search of Downloads (three directory levels, `mod13a3_grid10*` names) found no regional exports during this session. The critical external action is still to run and retrieve the regional pilot, then the annual exports after pilot review. Local data processing and statistical readiness cannot substitute for those actual regional MODIS observations.
