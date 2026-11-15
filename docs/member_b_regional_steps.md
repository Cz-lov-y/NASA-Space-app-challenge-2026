# Member B: regional data and human handoff

## Latest execution checkpoint

The full-world polar-bounds defect remains unresolved, but the explicit nonpolar pilot has now **completed**. Task `ELF7RDWO3DRQGYIJY2PJWY6Q` exported January 2003 for 576 unchanged cells. The controller downloaded the CSV through authorized Drive access and verified the Drive checksum. Strict read-only validation passed: 249 finite NDVI means, including 205 in GLDAS-supported cells; remaining requested cells report `no_valid_pixels` rather than invented values. The raw pilot and audit are retained under `data/raw/modis_earth_engine/regional_validation/` and `data/processed/regional/modis_pilot_audit.json`.

This partial pilot intentionally omits 72 polar grid cells, including 16 supported northern cells. `all_exported_months_cover_full_grid: false` is expected for this scope. No region boundary, source resolution, scaling or QA rule changed. All 648 cells remain in the local catalog. Independent pixel validation and the full polar export fix are pending. One month cannot supply statistical trends, and the pilot has not been imported into the accepted release. No yearly export tasks were launched; resume after the team reviews this milestone.

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

**Use the approved nonpolar scope:** authentication works and the 576-cell nonpolar pilot CSV passed structural/provenance checks. Full-world mode still fails on polar bounds. The controller can now submit annual nonpolar exports and automate their retrieval; the manual steps below are a fallback.

1. Open the [Earth Engine Code Editor](https://code.earthengine.google.com/) with the same approved account/project used for previous exports. This JavaScript runs in the Code Editor, not the Cloud Shell terminal.
2. Open local `scripts/export_regional_modis_earth_engine.js`, copy its contents into a new Code Editor script, and save it as `EarthRisk regional MODIS`.
3. Set `NONPOLAR_ONLY = true` and keep `MODE = 'pilot'` and click **Run** above the editor. Confirm the console export-region count is 576; the local catalog still contains 648 cells. In **Tasks**, click **Run** for `mod13a3_grid10_pilot_2003_01`; keep the proposed Google Drive CSV export settings and submit.
4. When the task completes, open Google Drive folder `NASA_member_B_regional`, download its pilot CSV, and make it available locally. The controller can validate it with the command below. A complete nonpolar pilot has 576 rows, one region/month each; ocean cells can have blank NDVI and `no_valid_pixels`.
5. After pilot validation, change `MODE` to `'years'`, retain `FIRST_YEAR = 2003` and `LAST_YEAR = 2024`, and click **Run**. This prepares 22 yearly export tasks. Submit them in the Tasks panel. Do not raise the spatial scale or enable a coarse approximation to speed them up.
6. Each completed nonpolar annual CSV should contain 6,912 rows (576 regions × 12 months). Download all completed annual CSVs from the same Drive folder into a local directory. Keep their filenames beginning `mod13a3_grid10_`. These are regional aggregates; the prior `whole_earth` exports cannot replace them.
7. Give the controller the downloaded directory path. It can merge available years immediately, preserve all unexported months as missing, rebuild screening results, and supply the updated catalog to A/C/D. Once full annual exports are available, exclude the pilot CSV from the merge because it duplicates January 2003.
8. If an annual task exceeds limits, set `MODE = 'month'` and `RETRY_MONTH = 'YYYY-MM-01'`, then run/export each month of that failed year. Keep exactly one accepted CSV per region/month: merge the 12 replacement monthly files **instead of** the failed/partial annual file. Report the exact error if the monthly retry also fails.

The full-world Python pilot failed on polar bounds. The separate nonpolar pilot completed and produced the checked-in validation CSV; structural and source-provenance checks passed. Independent source-pixel validation remains pending. Account/project authentication has succeeded.

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
.venv/bin/python scripts/merge_regional_timeseries.py /absolute/path/mod13a3_grid10_20[0-9][0-9]_nonpolar.csv
```

Imports are incremental. Pass only newly completed annual or monthly CSVs: previously accepted regional months remain in `accepted_modis_observations.csv` and are preserved in the combined release. Exact repeat observations are idempotent, including identical pilot/annual overlap. A changed existing measurement **or provenance field**, including `configured_at_utc`, is rejected unless `--replace` explicitly accepts the changed overlapping row. The last supplied version wins under `--replace`; unrelated accepted dates remain. Because the pilot and annual tasks normally have different configuration timestamps, either omit an unimported pilot from the annual import or use `--replace` for that deliberate overlap. The read-only pilot audit does not import the pilot.

Every successfully accepted source CSV is automatically copied byte-for-byte into `data/raw/modis_earth_engine/regional/<sha256>.csv`. Archived bytes are never overwritten; a hash mismatch stops the import. `modis_source_manifest.json` retains cumulative source hashes, archive paths and original filenames, including historical source files superseded by explicit replacements. Each accepted row links to its source file hash. Existing GLDAS observations and original raw files are preserved. The archive contains source exports, not authentication tokens or task credentials.

The merger validates stable region IDs, month uniqueness, period, units, range/scaling, area coverage consistency, native source projection, source asset/month and QA provenance. It preserves blank/unexported months and never turns them into zero. `ndvi_exported_months` records actual imported rows separately from `ndvi_valid_months`. Full exported coverage with missing observations is `complete_with_missing` / `incomplete_ndvi`; full exports with no valid observations are `no_valid_observations` / `unavailable_ndvi`. An exported month with no valid pixels is distinct from `pending_export`.


## Remaining human decisions and scientific work

- Confirm 10° screening is acceptable for the demo. A cell can contain several jurisdictions; policy research should identify its country choices explicitly.
- The user has authenticated Earth Engine and the controller has verified project `earthrisk-greenmirage`. The controller can now submit and monitor exports using the Python command below. Pilot completion, source-pixel review and retrieval of actual CSVs remain external data dependencies.
- Review scientific limitations and coverage decisions with Member A. Further independent MODIS pixel validation, common valid-footprint analysis and effect-size/serial-dependence review remain necessary for strong ecological claims.
- D's humans implement the interactive globe and region selection using this catalog and A's screening output. They must display pending/unsupported cells accurately and avoid presenting GLDAS-only cells as identified greening/drying hotspots.

## Exporter method review

The reduction receives the source NDVI `Projection` object, carrying its native affine transform. It sets neither an alternate scale nor `bestEffort`; the importer checks the retained native affine and CRS. The valid mask explicitly intersects the NDVI, DetailedQA and SummaryQA source masks before applying the range and QA rules. Masked QA values become invalid for both weighted NDVI and valid-area reductions. The exporter retains source assets and timestamps for every existing monthly image, including regions with zero valid pixels.

References checked during review: [Earth Engine reduceRegions](https://developers.google.com/earth-engine/apidocs/ee-image-reduceregions), [updateMask](https://developers.google.com/earth-engine/apidocs/ee-image-updatemask), and [MOD13A3.061 catalog](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13A3). These API and dataset checks support the intended calculation; cloud execution and independent source-pixel verification are still pending.

A bounded search of Downloads (three directory levels, `mod13a3_grid10*` names) found no regional exports during this session. The critical external action is still to run and retrieve the regional pilot, then the annual exports after pilot review. Local data processing and statistical readiness cannot substitute for those actual regional MODIS observations.

## Authenticated Python export automation

Optional environment tooling is declared in `requirements-earthengine.txt`. It is separate from app/runtime requirements. The controller has obtained account authorization; credentials stay in the normal Earth Engine credential store outside Git. Project ID `earthrisk-greenmirage` has passed a basic Earth Engine service check. The nonpolar pilot has now passed structural/provenance review; the controller owns annual task submission.

Preview the exact task plan without loading Earth Engine or contacting cloud services:

```sh
.venv/bin/python scripts/export_regional_modis_earth_engine.py --project earthrisk-greenmirage --mode pilot
```

Submit the single pilot explicitly:

```sh
.venv/bin/python scripts/export_regional_modis_earth_engine.py --project earthrisk-greenmirage --mode pilot --nonpolar --submit
```

The Python exporter uses the same grid, explicit intersected source masks, native projection, QA, scaling, coverage denominator and CSV columns as the Code Editor script. Task IDs are stored locally in ignored `.cache/regional_modis_tasks.json`. A duplicate recorded project/date range is blocked while its status is active, completed or unknown; `--force` intentionally resubmits it. A known failed/cancelled task can be retried. Monitor existing task IDs without creating exports:

```sh
.venv/bin/python scripts/export_regional_modis_earth_engine.py --project earthrisk-greenmirage --status
```

After pilot review, the controller can use `--mode years --first-year 2003 --last-year 2024 --nonpolar --submit` to create annual tasks, or `--mode month --month YYYY-MM-01 --nonpolar --submit` for a failed month's retry. These actions still require the existing account/project permissions. Outputs go to Drive folder `NASA_member_B_regional` and can be imported incrementally after retrieval. Authentication does not itself supply regional observations or complete source validation.

## Read-only regional release audit

```sh
.venv/bin/python scripts/audit_regional_release.py
```

This verifies source hashes, catalog geometry/counts, 264-month indexes, units and QA flags, accepted-source archive links, GLDAS preservation, coverage areas, regional/global area sums and weighted means, and quality-report consistency. It writes no files. Integrity failures exit with status 1. `full_required_period_complete` means every supported cell has all required NDVI observations; it is separate from `paired_preview_eligible_regions`, which counts statistically eligible cells only when the stored screening hashes match current data. Neither field certifies scientific validation or completion of the human-owned frontend.

## Current cloud pilot failure and bounded diagnosis

Authenticated task `ABTFV56ARF7J26CDWYOZC62A` failed with `Failed to compute bounds of <Geometry>`. This is an actual export failure, rather than an authentication or missing-credentials error. The controller has the task state in ignored `.cache/regional_modis_tasks.json`.

Read-only service probes isolated the following behavior:

- The unchanged QA/scaling/native-projection calculation succeeds for a tiny midlatitude region.
- Every 10° cell can compute its geometric bounds in the native projection, including the polar and antimeridian cells.
- Raster-reduction graphs for either polar band (80–90°N or 80–90°S), and individual polar cells, fail with the same error. The nonpolar 576-cell graph passes its size probe; this is not a completed 576-cell data export or independent pixel validation.
- Removing output geometries, and explicitly transforming input geometries into the native projection, do not resolve the polar reduction failure.
- Restricting the graph to the 301 GLDAS-supported cells also fails: 16 supported cells intersect the 80–90°N band. Omitting those cells would remove potentially valid paired observations and is not an accepted fix.

No arbitrary polar clipping, source-resolution change, invented missing values, or unsupported reclassification has been applied. The grid and real GLDAS outputs remain intact. No further export tasks were submitted during these diagnostic probes. The remaining engineering task is to resolve the native-grid polar raster-reduction bounds, then retry one pilot and verify its actual regional CSV before submitting annual tasks. Until then, repeating the unchanged cloud script is expected to fail.

## Explicit partial fallback after the polar failure

The controller approved a partial pilot using `--nonpolar`. This exports the **576 complete original cells** whose boundaries do not touch either pole. It preserves their boundaries, source QA, native projection and resolution. It does not clip a polar cell or reclassify it as unsupported. All 648 cells stay in the local catalog. In particular, the 16 GLDAS-supported north-polar cells retain `pending_export` NDVI until the full-world reduction defect is resolved.

```sh
.venv/bin/python scripts/export_regional_modis_earth_engine.py --project earthrisk-greenmirage --mode pilot --nonpolar --submit
```

The nonpolar pilot has now completed and passed the stored structural/provenance audit. Its description/filename ends in `_nonpolar`; task metadata records `scope: nonpolar` and `region_count: 576`. The duplicate guard distinguishes this explicit partial scope from the failed full-world scope. The controller has approved annual nonpolar export submission after reviewing that CSV. A nonpolar annual export contains 6,912 rows (576 × 12), and only 285 of the 301 GLDAS-supported cells can acquire paired observations from that scope. The remaining supported cells stay visibly pending.

The existing read-only CSV audit continues to report the full-grid denominator of 648; a complete nonpolar pilot therefore intentionally reports 72 absent full-grid cells and `all_exported_months_cover_full_grid: false`. Verify its actual 576 distinct region IDs against `export_grid(nonpolar=True)` rather than relabeling it as whole-world completion. The incremental importer can accept these source files and preserve explicit missing months for the omitted supported cells. The Code Editor equivalent is `NONPOLAR_ONLY = true`; its default remains the full-world graph with the documented defect.

## Automatic Drive synchronization

The successful pilot is retained at `data/raw/modis_earth_engine/regional_validation/mod13a3_grid10_pilot_2003_01_nonpolar.csv`, with audit `data/processed/regional/modis_pilot_audit.json`. It contains 576 region rows, 249 finite NDVI values and 327 `no_valid_pixels` rows for January 2003. It is a real NASA-derived validation export, kept separate from annual imports. Structural/provenance acceptance does not complete independent source-pixel validation.

The controller can retrieve completed annual exports using the existing Earth Engine OAuth credentials; the sync never opens a browser or creates export tasks:

```sh
.venv/bin/python scripts/sync_regional_modis_drive.py --list-only
.venv/bin/python scripts/sync_regional_modis_drive.py --poll-tasks
```

The first command lists matching annual files without writing a download cache. The second refreshes recorded task states once and downloads matching completed annual CSVs; it never waits for running tasks. Both inspect only folders named exactly `NASA_member_B_regional`. Only filenames `mod13a3_grid10_2003_nonpolar.csv` through `mod13a3_grid10_2024_nonpolar.csv` are selected. Pilot, retry, full-world, unrelated and out-of-period files are excluded automatically.

Downloaded bytes go to ignored `.cache/regional_modis_drive/` under immutable Drive-ID/content-hash names. Drive MD5 and size are checked, then SHA-256 is recorded. Unchanged remote versions with verified local hashes are skipped. A changed remote version creates a new immutable cache file and preserves previous bytes. Progress is saved after each completed file so rerunning resumes with remaining files; an interrupted individual file restarts cleanly rather than retaining unverified partial bytes.

Import actual annual observations explicitly:

```sh
.venv/bin/python scripts/sync_regional_modis_drive.py --ingest
```

Every candidate must pass the strict source/QA/native-grid checks and contain exactly the 576 requested region IDs × all 12 months of its filename year. Validated inputs then use the existing incremental merger and permanent raw archive. GLDAS inputs are preserved. An import changes data fingerprints: the controller must rebuild statistics, screening and the frontend data bundle afterward.

Drive permits duplicate filenames. The sync tracks files by Drive ID and never overwrites one file with another sharing its name. If different contents exist for the same annual year, automatic ingestion stops rather than selecting an arbitrary copy. Use repeated `--file-id ID` arguments to identify the accepted files from the listing. Exact duplicate content is safe to repeat. `--replace --ingest` explicitly accepts changed observations/provenance against previously accepted source rows; it does not resolve an ambiguous choice between multiple different Drive IDs for one year.

No credentials, access tokens or OAuth refresh tokens are printed or included in the cache/source manifests. Existing OAuth scopes must permit Drive reads; a scope/API access failure is reported without triggering reauthentication. The Drive implementation follows the primary [files.list](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list) and [files.get](https://developers.google.com/workspace/drive/api/reference/rest/v3/files/get) API documentation.
