# Native-cell vegetation acquisition and release

Current active method: `modis_sinusoidal_sphere_native_pixel_v2`. Historical earlier-method CSVs are retained as evidence and rejected as active inputs. The current globe serves the audited six-area collection; the single-tile commands below remain useful for acquisition and diagnostics.

The frozen first tile has 16 original GLDAS 0.25° cells at `[-98,37,-97,38]`, with a required January 2003–December 2024 index. Source masks and missing values remain explicit. Existing 10° and whole-Earth NDVI averages cannot supply these observations.

## Validation and import

The fine exporter reduces original MOD13A3.061 pixels into the exact GLDAS cell footprints using the existing native projection, mask intersections, QA rules and one-time scale. The importer checks source assets/months, native projection/affine, units, physical range, coverage, complete cell sets and target boundaries. Its six-column observation contract is unchanged.

Read-only validation:

```sh
.venv/bin/python scripts/merge_fine_modis.py path/to/pilot.csv --expected-month 2003-01-01
```

Accepted imports preserve exact source CSV bytes under content hashes, cumulative source manifests and a per-observation archive ledger. Identical repeats are idempotent. Changed values or provenance require deliberate `--replace`. All 264 monthly slots remain present; unreceived months are missing with `pending_export`, exported invalid pixels retain their original status. Pilot validation does not import one month into the release, avoiding an unnecessary overlap conflict with annual exports.

```sh
.venv/bin/python scripts/merge_fine_modis.py path/to/annual.csv --ingest
.venv/bin/python scripts/prepare_fine_backend.py
.venv/bin/python scripts/audit_fine_release.py --output data/processed/fine/central_us/release_audit.json
```

Rebuilding assigns a stable identity to the declared native pilot testing family. Eligibility and any adjusted significance concern that family only, never worldwide fine coverage. A partial NDVI record preserves the longer standalone soil diagnostic; paired findings require the configured common complete years.

## Drive route

```sh
.venv/bin/python scripts/export_fine_modis_earth_engine.py --project earthrisk-greenmirage --status
.venv/bin/python scripts/sync_fine_modis_drive.py --report .cache/fine_drive_status.json
.venv/bin/python scripts/sync_fine_modis_drive.py --ingest
```

The synchronizer only reads the named `NASA_member_B_fine` folder and matching tile exports. It checks Drive size/MD5, immutable download hashes, complete annual month/cell coverage and ambiguous annual duplicates. Use `--file-id` to select reviewed versions. Pilot CSVs are validated and archived separately; `--include-pilot` explicitly opts into importing them. Normal annual ingestion also rebuilds the backend. No synchronization command starts cloud tasks or policy/AI research.

## Independent source-pixel comparison

```sh
.venv/bin/python scripts/validate_fine_modis_pixels.py
.venv/bin/python scripts/validate_fine_modis_pixels.py --verify --csv path/to/pilot.csv --output .cache/fine_pixel_check.json
```

The default prints a local plan. Explicit verification reads one bounded source-pixel array using existing OAuth, then independently applies QA/scaling and computes local sinusoidal pixel/target intersections. It reports numerical differences and coverage anomalies. This is a consistency check on one cell/month; human scientific approval and broader mask/footprint checks remain necessary.

## Compute quota and execution status

On November 15 the configured Earth Engine project reported exhausted noncommercial compute quota and restricted mode. Restricted mode reduces throughput but permits processing. The controller retired 17 unfinished obsolete 10° annual tasks; five terminal tasks and existing files were retained. The exact account actions are recorded in `data/requests/coarse_export_retirement.json`.

A bounded direct request successfully returned the fine January 2003 pilot using the unchanged export calculation graph. Its raw CSV and acquisition receipt are retained with the fine pilot audit. This method uses the same project and quota; it does not increase account entitlement. It avoids waiting for batch scheduling for small tiles. Do not expand direct requests to a worldwide feature collection.

Account tier/billing settings were not changed. If additional free noncommercial capacity is needed, a human project owner can review Contributor Tier requirements on [Google's official tier page](https://developers.google.com/earth-engine/guides/noncommercial_tiers). Keep the project noncommercial if eligible; any account/billing decision stays with the humans.


## Completed native pilot release — November 15

All 22 annual files were retrieved through bounded direct requests, validated and imported. The accepted release has 12,672 rows: 8,448 original soil observations and 4,224 NDVI slots, of which 4,222 are finite. Two QA-rejected NDVI months remain missing: `gldas025_r388_c0328` March 2010 and `gldas025_r391_c0330` January 2010. No export slots are pending. Repeating a download cannot restore a legitimately masked observation.

All sixteen cells are eligible for preliminary paired analysis with 21–22 common complete years, forming 32 primary tests in the declared pilot family. Twelve cells show no detected divergence and four uncertain signals; none satisfy the supported-signal gates. The release integrity audit passes 1,110 checks. This does not certify scientific validity or complete worldwide coverage.

The independent January 2003 check for `gldas025_r388_c0328` differs from the export by approximately 0.0000435 NDVI. The small coverage excess above one remains recorded and falls within the local conservative boundary quantization budget. Raw pixel evidence, comparison, projection-origin evidence and source CSV hashes are retained in the fine release and raw validation folder. Broader coverage/footprint review is still required.

To resume verified direct retrieval without repeating successful requests:

```sh
.venv/bin/python scripts/fetch_fine_modis.py --project earthrisk-greenmirage --mode years --fetch
```

The default without `--fetch` is a local plan. Interactive retrieval is capped at 16 cells per request and one calendar year at a time; each call has a 30-second deadline and stops on service errors. Raw responses are saved before validation, verified CSVs and receipts are immutable/hash-addressed, and successful requests are reused. `--refresh` is deliberate and may create provenance conflicts requiring reviewed replacement. No batch tasks or policy/AI calls are started.

The source mosaic projection can have origins shifted by complete 1,200-pixel MODIS tiles while retaining the same native grid. Validation accepts only those aligned translations with unchanged scale/shear and valid tile bounds; it rejects partial-pixel shifts and changed resolution. Actual monthly transforms remain preserved. See NASA's [MODLAND grid documentation](https://modis-land.gsfc.nasa.gov/MODLAND_grid.html).


## Six-area collection and navigation

The frozen registry is `data/processed/fine/tiles.json`. `scripts/acquire_fine_tiles.py` provides a read-only plan by default; `--fetch` reuses audited completed tiles and resumes outstanding native requests. Reprocessing an earlier area method requires explicit `--fetch --reprocess --replace`; no mixed-method remainder is allowed.

```sh
.venv/bin/python scripts/acquire_fine_tiles.py
.venv/bin/python scripts/acquire_fine_tiles.py --fetch
.venv/bin/python scripts/prepare_fine_collection.py
.venv/bin/python scripts/prepare_fine_collection.py --audit-only
```

The collection directory stores one joint 96-cell statistical family, original source-tile fingerprints and deduplicated raw-file manifests. Publishing audits a temporary candidate first. The API serves a small six-area index and one selected 16-cell tile while preserving collection-wide corrected statistics. The UI Area selector and white markers navigate between real source regions; opening cells sends no research requests.

Current source-QA gaps are expected missing observations, not pending downloads. Scientific common-footprint/coverage review and global geographic expansion remain separate next tasks. The Canadian winter gaps are preserved under the same complete-year requirement as all other areas.
