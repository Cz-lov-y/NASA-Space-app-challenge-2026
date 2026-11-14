# Reducing the global MODIS extraction

## Finding and recommendation — 2026-11-14

The six existing requests extract monthly whole-Earth MOD13A3.061 rasters at approximately 1 km for three layers. Splitting dates bypasses a per-request limit but does not reduce the total data or processing. The reported 17%/pending statuses suggest server-side extraction and queueing; they do not establish a slow local download connection. No task account/status was inspected here, and no existing job has been cancelled.

Member B ultimately needs one area-weighted NDVI value and its valid coverage per month, plus provenance and quality checks. The original B.docx specifies MOD13A3.061, both QA layers, and preservation of original inputs; its AppEEARS access route can be reconsidered in response to the user's request for alternatives. Retain the same monthly product and QA while moving the reduction to the data when possible. Do not drop QA or months to achieve a smaller file.

**Recommended pilot:** use the NASA MOD13A3.061 product hosted in Google Earth Engine, apply both QA filters at native resolution on Google's servers, and export only monthly statistics to CSV. The 2003–2024 period then has 264 NDVI rows. Requesting January 2003 through November 2026 gives 287 expected NDVI rows, including blank rows for unpublished months. These counts exclude the two GLDAS variables. Output should be kilobytes to well under a few megabytes, depending on metadata, instead of global raster archives; this is an estimate, not a measured export size. Global computation still costs time and is subject to cloud queues and quotas; no runtime speedup is promised.

Google Earth Engine is a Google processing service hosting NASA-produced data, **not a NASA-operated retrieval service**. Its catalog includes `NDVI`, `DetailedQA` (VI Quality) and `SummaryQA` (Pixel Reliability). NASA product identity, collection version and monthly cadence remain unchanged. Before replacing the workflow, verify a real export and compare representative output against source metadata and an independent calculation. Google ingestion/mosaicking and masks also need checking.

## Steps on the user's side

1. Open [Earth Engine](https://code.earthengine.google.com/). Sign in with a Google account, create/select a Cloud project, enable Earth Engine if requested, and complete [registration](https://developers.google.com/earth-engine/guides/access). Noncommercial unpaid access requires eligibility verification; it is not automatic for every project.
2. Open `scripts/export_modis_earth_engine.js` locally, copy its contents into a new Code Editor script and save it. Leave `MODE = 'pilot'`. This requests January 2003 only.
3. Click **Run**. Inspect the Console for available bands, projection and latest image date. The script creates an export task; clicking Run does not itself download a CSV. The initial pilot failed because an earlier script passed a WKT string as `crsTransform`; the corrected script passes the native Projection object directly. The corrected version still requires an authenticated pilot run.
4. Open **Tasks**, click **Run** beside `mod13a3_whole_earth_pilot_2003_01`, confirm the export settings and start it. Allow Google Drive authorization if requested. This is a batch computation of one full global month at the native grid.
5. When the task completes, find the CSV in the `NASA_member_B` folder in Google Drive. Download it to `data/raw/modis_earth_engine/`. Retain the exported provenance columns. The local assistant can then audit the CSV, scaling, coverage and native-grid metadata. The script has only been syntax-checked locally; authenticated execution has not been tested.
6. After the pilot is validated, set `MODE = 'years'` and Run again. The script creates one export per year, 2003–2026. Start those tasks from **Tasks**; the service decides concurrency. Years 2003–2024 are the required first milestone. The 2025–November 2026 extension must retain unavailable months as missing. A date request cannot create observations for an unfinished or unpublished month.
7. Save completed yearly CSVs in the same raw export directory. Keep the pilot for validation, but exclude its duplicated January 2003 row when merging yearly files. Recheck source availability and export metadata before claiming the extended dataset is complete.
8. Once this alternative is accepted and tested, cancel the obsolete AppEEARS jobs from their task controls if supported. If cancellation is unavailable, leave them unused. Keep the old request JSON files as provenance. Do not resubmit more full-world requests while testing.

## Processing details and limitations

The script keeps valid source masks and raw NDVI from −2000 through 10000, requires `(DetailedQA & 3) == 0` and `SummaryQA == 0`, and multiplies NDVI by 0.0001 once. It computes `sum(NDVI × valid_pixel_area) / sum(valid_pixel_area)` at the image's native projection and transform. It does not use a coarse display pyramid or enable `bestEffort` resolution changes. The denominator for `valid_area_fraction` is the entire spherical Earth, including oceans, using the MODIS sphere radius of 6,371,007.181 m; use a consistent area convention when comparing GLDAS coverage. Masked/fill observations are never interpreted as zero-valued measurements. Zeroes introduced for summation carry zero valid area.

Output retains month, source asset identifier, image count, source projection/transform, QA rule and configuration time. Missing months remain blank; unexpected duplicate monthly images are flagged rather than selected arbitrarily. Nonempty months are marked `coverage_review_required` because a suitable global land-coverage quality threshold has not been chosen. The regional prototype's 0.8 whole-region threshold remains unsuitable. Cloud execution, global/polar geometry, area totals and independent agreement require validation before these are accepted scientific results. Very large yearly tasks may need splitting by month if cloud limits are encountered.

This route preserves the script and cloud asset references, but a CSV export is **not a locally archived copy of all original rasters**. It therefore changes the original-input preservation approach in B.docx. Document that explicitly with the team; if local raw rasters are mandatory, retain/download them separately or use the NASA archive route below. The existing local regional raster processor does not directly consume these statistical CSV exports; an audited import/merge step is still needed. Existing GLDAS downloads can continue to be processed locally.

## Official NASA alternative: MOD13C2.061

[MOD13C2.061](https://doi.org/10.5067/MODIS/MOD13C2.061) is NASA's monthly global 0.05° Climate Modeling Grid vegetation product. It contains a 7,200 × 3,600 global grid (25,920,000 cells), NDVI, detailed VI Quality and pixel reliability, plus other fields. It can be obtained through NASA Earthdata Search/LP DAAC or [LAADS](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/MOD13C2), subject to archive access and authentication. AppEEARS' public product list checked on 2026-11-14 did not include MOD13C2, and `/api/product/MOD13C2.061` returned HTTP 404. Do not generate an AppEEARS request for an unsupported product.

At the equator 0.05° is approximately 5.6 km. Cell count is about 36 times smaller than a 0.008333° global geographic grid (43,200 × 21,600), illustrating a potential order-of-magnitude volume reduction. This is a grid-count comparison, **not** a measured reduction relative to the pending jobs: native sinusoidal tiling, land-only coverage, archive compression and which fields are retrieved change the actual bytes. Direct archive files may contain all 13 fields, rather than just our three selected layers.

This is a product/methodology change from the required 1 km MOD13A3, not just a download optimization. The [Collection 6.1 user guide, section 9](https://modis-land.gsfc.nasa.gov/pdf/MOD13_User_Guide_V61.pdf) says MOD13C2 uses 16-day CMG inputs with cloud gaps replaced using historical climatology. Its reliability classification includes an estimated-data category. Historical replacements can affect trend and missingness interpretation. Do not treat them as fresh observations, claim their coverage as observed, apply the MOD13A3 mask without reviewing CMG QA, or mix MOD13A3 and MOD13C2 months in a single unchanged series. A pilot, explicit treatment of estimated pixels and documented agreement on the product change are needed before adopting it. Using one CMG product consistently for the whole series is preferable to silently switching halfway through.

## Other changes and their effects

| Change | Effect | Suitability |
| --- | --- | --- |
| Cloud reduction of original MOD13A3 | Only statistics reach the laptop; native QA and product retained | Preferred test; requires Google account/project and cloud provenance decision |
| NASA MOD13C2 instead of MOD13A3 | Much coarser, already global monthly grid | Official NASA option; product and climatology caveats above |
| AppEEARS native projection | May avoid geographic reprojection work | Keeps substantial source volume; no promised speedup |
| Different raster format | May change compression/container overhead | Does not remove global source extraction |
| More date splits | Smaller individual jobs | Does not reduce total work or bytes |
| Drop QA layers | Smaller outputs but loses required screening information | Unsuitable |
| Point samples instead of the globe | Much smaller extraction | Changes the estimator; needs sampling design and uncertainty, not a replacement for an exact global average |
| Smaller geographical region | Much smaller extraction | Changes the user's whole-Earth study; not adopted |

The documented AppEEARS area-task schema provides layers, dates, geometry, format and projection. It does not expose a documented arbitrary output-resolution control. Adding an invented `resolution: 0.25` to the existing JSON is not a verified optimization. Raster reprojection/downsampling of NDVI and categorical QA without masking and area-aware aggregation can also change the result.

## Sources checked 2026-11-14

- [Earth Engine MOD13A3.061 catalog and band definitions](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13A3)
- [Earth Engine regional reductions](https://developers.google.com/earth-engine/apidocs/ee-image-reduceregion) and [table exports](https://developers.google.com/earth-engine/guides/exporting_tables)
- [Earth Engine access and project registration](https://developers.google.com/earth-engine/guides/access)
- [NASA MOD13C2.061 description](https://doi.org/10.5067/MODIS/MOD13C2.061) and [LAADS product page](https://ladsweb.modaps.eosdis.nasa.gov/missions-and-measurements/products/MOD13C2)
- [NASA MODIS VI Collection 6.1 user guide](https://modis-land.gsfc.nasa.gov/pdf/MOD13_User_Guide_V61.pdf)
- [AppEEARS API task schema](https://appeears.earthdatacloud.nasa.gov/api/) and live public product endpoints
