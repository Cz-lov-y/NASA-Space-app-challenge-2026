# Frontend/backend integration review

Review: merged frontend at `203e7a4`, against the actual regional Python/artifact
contracts. Source inspection only; this review makes no frontend changes or
browser-performance claims. The controller owns build verification.

## Controller verification

The controller fast-forwarded local main to the frontend merge, installed its locked dependencies with an isolated Node 22 runtime, and ran `npm run build` successfully. Vite reported a large JavaScript chunk warning; this was not a build failure. A local Vite preview is available on port 3000 while that process is running.

A headless Google Chrome check rendered the globe, selected the Synthetic Demo Region, displayed its explicit synthetic warning, and opened the Scientific Audit tab with no JavaScript page errors. Screenshots are retained locally under `.cache/frontend_review/` (`globe.png`, `synthetic_panel.png`, `audit.png`). These checks exercise the synthetic presentation; they do not verify real NASA-data integration, API transport or research behavior.

The merged `frontend/test_browser.py` is a manual machine-specific harness: it requires Playwright, a running localhost server and a Chrome installation, and writes artifacts to its author's absolute home path at import time. Standard Python test discovery is now explicitly scoped to `tests/` in `pytest.ini`; this harness is run separately after configuring its environment. CI includes a separate locked-dependency frontend build job.

The globe, sliding panel, chart controls and explicit synthetic-data warning
provide a usable presentation structure. The current data path still uses a
synthetic demonstration and future-API assumptions. A successful frontend build
would not establish that real observations or scientific classifications are
connected.

## Blocking findings and precise handoff

| Priority | Evidence | Consequence | Required integration change |
| --- | --- | --- | --- |
| P0 | `frontend/src/services/api.ts:19`–`34`; `frontend/src/components/panel/SlidingPanel.tsx:206` | The proposed `/api/v1/regions/{id}/analysis` response contains only `analysis`; the panel renders charts only when `observations` also exists. A successful request can show a green success state with no real charts. No HTTP service is supplied by the current Python artifact loader. | Connect a defined transport to the existing `regional-detail-1` export, including observations, geometry, paired analysis, available-indicator analysis and screening. Keep source-unavailable, request failure and pending paired analysis distinguishable. An HTTP adapter or published static exports are implementation choices, not existing endpoints. |
| P0 | `frontend/src/types/contracts.ts:36`–`68` | These types do not mirror schema 0.3. `observation_period` is an object `{start,end,years,aggregation}`, not a tuple. Slopes, intervals, p-values and robust estimates may be null for insufficient data. Category is `analysis.divergence.category`, not `analysis.divergence_category`. | Define nullable result fields, the actual observation-period object, detailed `analysis`/`data_quality.by_variable`, and a separate regional-detail/map-screening wrapper. Preserve `screening_status` and source-version identity. |
| P0 | `frontend/src/components/charts/StatisticalAudit.tsx:33`–`55`, `:59`–`99`; `frontend/src/utils/statistics.ts:14`–`28` | Audit slopes are recomputed from raw monthly observations using a minimum of three points, then combined with backend confidence intervals, p-values and Sen slopes from complete annual common-year analysis. Changing the displayed window mixes different estimands. Sign-only client classification claims compliance with Member A's stronger contract. | Treat backend stored results as scientific authority. Display `screening.classification/category/reasons` for paired worldwide-adjusted screening; use paired or explicitly standalone analysis for numerical cards. Client chart filters may change the displayed observations; label the fixed analyzed period separately. Reanalysis of a new window must run the backend method and declare its testing family. |
| P0 | `frontend/src/components/panel/SlidingPanel.tsx:46`–`52`, `:91`, `:242`–`243`; `frontend/src/components/charts/StatisticalAudit.tsx:20`–`24`, `:61`; `frontend/src/components/charts/ZScoreChart.tsx:19`, `:32`; `frontend/src/components/charts/TimeseriesChart.tsx:23`–`28` | Actual primary soil data use `soil_water_0_100cm`, with optional `soil_water_0_10cm`. Hardcoded `soil_moisture` selectors omit real soil observations; temperature and precipitation are synthetic-only here. Slider bounds remain 2015–2024 although real data begin in 2003. | Discover available variables/date bounds from the actual selected region. Keep canonical depth names and `kg m-2` units; add human-readable labels without renaming the data. Show missing NDVI as pending and allow real GLDAS-only charts/diagnostics. |
| P0 | `frontend/src/components/charts/StatisticalAudit.tsx:144`–`174` | Every p-value below .001 is displayed as the invented exact value .0001. Null backend p-values pass the `!== undefined` check and compare below .001 in JavaScript. Other nullable fields can display `+null` or invalid intervals. The fallback `±1.96 SE` is neither a pair of slope bounds nor the backend Student-t interval, and uses different input data. | Require finite numbers before formatting. Show `N/A` with a reason for absent estimates. Format small actual p-values using scientific notation or a truthful threshold; never invent an exact value. Display the backend confidence interval and configured confidence level. |
| P0 | `frontend/src/services/api.ts:27`–`29`; `frontend/src/components/charts/StatisticalAudit.tsx:190`–`214` | HTTP success is described as verified observations. Missing regional `missing_fraction` becomes `0.0%`, although the backend reports per-variable coverage and unknown values must remain unknown. QA=false is labeled raw scaffold, although actual NASA-derived data are also currently unreviewed. | Report connection success separately from provenance/QA. Use each variable's `data_quality.by_variable[variable]` and B's QA metadata. Distinguish raw missingness, analyzed missingness and geographic valid-area coverage. Unknown values display unavailable; `qa_reviewed=false` displays review pending. |
| P1 | `frontend/src/components/charts/StatisticalAudit.tsx:48`, `:119`; `frontend/src/types/contracts.ts:37`; `frontend/src/components/charts/TimeseriesChart.tsx:129`–`148` | The displayed count is all raw monthly rows, including missing values, alongside inference based on annual means. The plotted trend is a separate client monthly fit. | Label raw rows, finite monthly observations and analyzed annual observations separately. Use backend annual fit information for the scientific trend, or label an optional client curve exploratory and keep it out of the audit/classification. |
| P1 | `frontend/src/components/charts/StatisticalAudit.tsx:36`; `frontend/src/components/panel/SlidingPanel.tsx:68`; `frontend/src/components/charts/TimeseriesChart.tsx:52`; `frontend/src/components/charts/ZScoreChart.tsx:17` | `new Date('YYYY-MM-DD').getFullYear()` parses the source date at UTC but reads the local year. In western time zones, January 1 can be classified as December 31 of the preceding year, dropping/misgrouping observations. | Use UTC calendar access or parse the ISO calendar year directly for monthly source dates. Verify boundary months in the intended browser time zone. |
| P1 | `frontend/src/utils/statistics.ts:80`–`98`; `frontend/src/components/charts/ZScoreChart.tsx:36`–`48` | Z-score preparation discards missing dates; its axis union can erase a month missing in both indicators. The number filter excludes NaN but accepts infinity. | Compute scaling from finite values while preserving the source monthly index and null gaps. Keep the existing dimensionless/non-hazard explanation. Validate finite observations at the transport boundary. |

## Actual backend fields to consume

`src.regional_workflow.export_region(bundle)` emits `schema_version:
regional-detail-1` with `region_id`, `feature`, `observations`, `provenance`,
`screening_status`, `screening`, `paired_analysis` and
`available_indicator_analysis`. Read this wrapper rather than assuming a single
analysis JSON also contains raw observations. Consult `docs/regional_integration.md`
for the transport-independent Python handoff and export commands.

Use `data/processed/regional/map_screening.geojson` for compact catalog geometry,
ID, status, categories and stored primitive statistics. Pending, unsupported and
insufficient cells retain explicit states; a real GLDAS-only cell can contain
standalone soil trends while paired map screening stays pending. Those diagnostic
p-values are not worldwide-adjusted paired tests. `screening.json` retains full
annual uncertainty, reliability reasons and family metadata. Check source hashes
and versions before combining cached artifacts.

Backend `RegionalAnalysis` has three distinct significance sources: raw OLS
p-values, within-call adjusted MK p-values, and the map's separate worldwide
adjusted MK values. Label them explicitly. A backend Supported Signal is provisional
statistical screening and does not certify environmental damage or source-QA
review. Hiding an indicator in the UI must not silently alter the declared family.

`TimeSeriesObservation` should retain B's optional `quality_flag`,
`valid_area_fraction`, `valid_area_m2` and `region_area_m2` fields. Provenance types
at `frontend/src/types/contracts.ts:15`–`33` also require adaptation: actual spatial
metadata includes CRS/bbox/aggregation and actual quality metadata does not require
the frontend's invented `description`, `missing_count` and
`missing_value_encoding` structure.

## Verification required for the human frontend integration

1. Select a real grid ID and display its actual soil measurements before NDVI is
   available; paired classification must stay pending.
2. Exercise null estimates, a missing month, unsupported coverage, failed network
   request and mismatched source versions without synthetic fallback masquerading
   as a real response.
3. Display the fixed scientific analysis period alongside a narrower chart window;
   all uncertainty/p-value fields must refer to the same analyzed annual record.
4. Verify a complete paired test result against the stored backend category and
   worldwide family, then test insufficient years and reliability failure.
5. Verify January date filtering in a western time zone and preservation of blank
   months in both raw and standardized plots.

Policy-report schema and live research integration need Member C's separate review;
this review's scope is the numerical/statistical and observation-data path.
