# Member B revised plan after the team merge

Review baseline: commit `84c045b` on `feature/nasa-data`, 2026-11-14. This plan reorganizes remaining work; it does not change other members' implementation or declare the scientific milestone complete.

## Current team state

| Area | Present in merged code | Implication for B |
| --- | --- | --- |
| A: statistics | Annual aggregation, OLS, Theil–Sen, MK, reliability checks, schema 0.3; real central-US GLDAS regression fixture | Do not rebuild trend analysis. Supply contract-compliant observations and provenance. |
| B: data | Global MODIS exports plus repair; global GLDAS outputs; combined CSV, reports, plots and source manifests; separate central-US GLDAS sample | Required 2003–2024 period has 264 nonmissing months for each of three variables. Data exist, but loader and scientific validation remain incomplete. |
| C: evidence | Candidate discovery, human-reviewed evidence validation, explanation adapter and offline demo | Supply genuine region geometry and coverage limitations. Discovery/providers are optional and not configured by the app's default call. Whole-Earth means cannot identify a local policy jurisdiction. |
| D: frontend | Streamlit controls, plots, exports and research panels | App calls B's reader, which currently loads synthetic data only. App selector uses `soil_moisture`; observations use explicit depth-specific names. |

The README and some member guides still describe the repository as synthetic-only or refer to earlier stubs. This is partly stale: real data are present, while the default app is still synthetic. Update those statements in coordination with their owners after the integration change.

## Priority 1 — implement the real-data interface

**Progress:** real-data loading, preserved missing values, structured JSON provenance and core integration tests are implemented locally. Further review and frontend integration remain.

Owner B; start immediately. Depends on existing CSVs and current `docs/contracts.md`.

- Extend `src/nasa_data.get_timeseries(region, variable)` to load real, versioned datasets by supported region/variable, retaining the synthetic demo explicitly. Support `whole_earth` with NDVI and the two soil-water depth names; support `central_us_sample` with surface soil water only. Do not invent regional MODIS data for that sample.
- Preserve actual monthly NaNs, dates, coverage and quality flags. Refactor B's preprocessing carefully: its current validator rejects NaNs, contrary to contract v1. Reject malformed numeric text, invalid dates, infinities and duplicate months; do not weaken validation to allow silently coerced bad input. Update existing tests that currently require rejecting all missing observations.
- Attach the required `frame.attrs['metadata']` records: spatial coverage and CRS, native grid and weighting, time range, temporal resolution, product/version, and QA/fill/missing rules. Persist matching JSON sidecars so provenance survives concat/CSV exports. Markdown notes remain useful but do not satisfy the in-memory metadata contract by themselves.
- Add loader tests for real sources, demo separation, unknown region/variable errors, missing extension months, one-variable calls, units and durable metadata consistency.

Completion: a fresh checkout can call the public reader on real data without credentials or manual CSV loading; missing values and provenance are retained. This is integration readiness, not scientific approval.

## Priority 2 — connect B to A and D

**Progress:** a direct B-to-A example and test are in `docs/member_b_handoff.md` and `tests/test_data.py`. The Streamlit interface has a locally tested real-data path; Member D review is still needed.

B prepares the example/tests; coordinate app changes with D and any analysis API changes with A. Depends on Priority 1; can proceed while scientific validation continues if warnings remain visible.

- Keep canonical `ndvi`, `soil_water_0_10cm` and `soil_water_0_100cm` names and physical units. A already accepts explicit `soil_moisture_variable='soil_water_0_100cm'`; NDVI matching is case-insensitive. Do not silently rename soil storage to generic volumetric moisture.
- Demonstrate the primary pair only: NDVI plus 0–100 cm soil water, original 2003–2024 period. Surface soil water is an optional sensitivity input, not an automatically added third indicator that changes A's common-year window or multiple-testing family.
- Save provenance for each frame before concatenating; A does not propagate the metadata. Confirm 22 complete common annual means per variable and explicit exclusions for any extended-period analysis. A owns interpretation of slopes, p-values and supported-signal rules.
- Give D a region/variable catalog, explicit primary soil-variable configuration, boundary geometry and visible QA limitations. Supply a polygon for map support; adding a representative point to every aggregate observation does not create a spatial risk map.
- Coordinate D's schema-0.3 display migration: category/reasons, annual vs monthly counts, and preservation/export of B's QA and metadata. Keep the synthetic demonstration available and clearly labeled.

Completion: one real-data end-to-end smoke test works and shows provenance and unresolved QA warnings. Numerical classification must not be described as spatial or source-QA validation.

## Priority 3 — scientific data validation

**Progress:** `scripts/audit_member_b.py` verified all 343 stored file checksums and independently recomputed 16 GLDAS means across eight sample months. MODIS source-pixel validation and footprint overlap remain outstanding.

B leads with A's review. Can run in parallel with Priorities 1–2; required before calling the data scientifically validated.

- Independently verify MODIS scaling, QA masks, native-grid/polar/global area reduction and coverage for representative months, including seasonal extremes. Matching pilot and annual exports is a repeatability check, not an independent method. Choose a small regional source-raster comparison first to establish layer semantics, then assess the global calculation with a genuinely independent implementation or spatial partition. Additional source access or a small Earth Engine validation export may be needed; full raster re-downloads are not the default next step.
- Quantify varying MODIS coverage and compare with GLDAS. Both use the whole Earth's surface as denominator, but totals alone do not measure spatial overlap. Do not apply the regional 0.8 threshold globally or promote `coverage_review_required` to `good` automatically.
- Document the team decision: retain distinct-footprint global summaries with explicit limitations, or develop a common valid-footprint/mask analysis. The latter requires additional spatial data/processing and is a scope change. A whole-Earth region does not support identifying where greening and drying co-occur.
- Review GLDAS missing/fill handling, layer sum and physical plausibility across representative months; structural checks and a January weighted-mean check are already done, not a complete scientific review.
- Set defensible quality policies, documenting any excluded months and retaining original inputs. Review whether cloud asset references and aggregate exports meet the team's reproducibility needs in place of locally archived MODIS rasters.

Completion: written validation evidence and unresolved issues, with reviewer decisions. Do not assume A's `qa_reviewed=False` can be switched just because a provenance sidecar exists.

## Priority 4 — package and hand off

Depends on real loader integration and documented validation status; a provisional integration handoff may happen earlier.

- Provide a clear required-period view (792 rows: 264 months × 3 variables) alongside the existing extended dataset. Do not lose the extended index or fill missing months.
- Refresh combined quality reports, plots, JSON provenance, reproducibility commands and data catalog. Include thresholds, exclusions, source hashes and an explicit status for each remaining validation issue.
- Run B/A contract tests, regression tests and D's smoke tests on the supported Python version. Validate a clean checkout and preserve source exports.
- Commit to `feature/nasa-data`, push and open a reviewable PR into main through the team's workflow. Coordinate README/status updates with the team. Deployment and policy research remain D/C responsibilities.

## Later, optional work

The extension is not a prerequisite for the required 2003–2024 deliverable. MODIS currently has 286 valid months through October 2026 and a missing November 2026 row from the repair export. GLDAS has 282 valid months in the extended output through June 2026; July–November remain missing locally. Check availability later before requesting more data. Additional regions, regional MODIS exports, matching spatial masks, EVI and climate variables follow a team scope decision. No existing NASA downloads need to be repeated merely to implement the loader.

## Dependencies and user's next actions

`existing data → real loader + JSON provenance → A/D integration → final handoff`

`existing data → independent scientific checks + coverage decision → scientifically reviewed handoff`

The coding work, reports and local checks can be automated. The user/team needs to agree the footprint interpretation and raw-MODIS preservation approach, review the validation evidence and merge PRs. Further NASA/Google sign-in is only needed if independent validation requires additional inputs; no new bulk download is requested now.

## Review evidence and environment limitation

- Both NDVI and primary soil-water data cover 22 complete common years for 2003–2024 when passed directly to A's module.
- With A's default soil-variable name, classification reports a required indicator missing. Configuring the explicit 0–100 cm name enables pairing. The observed numerical Supported Signal is not independent provenance or spatial validation; the statistics module does not enforce B's coverage-review flags.
- The central-US GLDAS fixture is already covered by A's numerical regression test.
- Local full-suite collection encountered Python 3.9 incompatibility in C's `Callable | None` annotation. CI is configured for Python 3.12. Treat this as an environment mismatch, not evidence that CI fails; run the full suite on supported Python before handoff.
