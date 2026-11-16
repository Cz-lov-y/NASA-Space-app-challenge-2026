> **Deployment note:** This document describes the loopback API. The public HTTPS site sits behind a separate gateway; see [deployment operations](WEB_DEPLOYMENT_PLAN.md).

# Local HTTP API for the React globe

The server provides the stored regional catalog, numerical detail, annual fits and optional background research. Data and cache reads perform no live research. It uses Python's standard library HTTP server and the existing processing modules; no new Python package is required.

## Start the backend

From the repository root:

```sh
.venv/bin/python scripts/serve_regional_api.py --port 8000
```

This binds `127.0.0.1:8000`, permits data/cache reads, and keeps live research disabled. It does not read `.env`. A cached Canadian report is available on a fresh checkout when its exact dataset/context still matches.

To deliberately permit research requests using the already configured local service accounts:

```sh
.venv/bin/python scripts/serve_regional_api.py --port 8000 --enable-live
```

This loads only the four allowlisted service settings from private `.env` using the existing literal parser. Existing process environment settings override the file. Actual credentials are never returned to the frontend or written to access logs. The server accepts no client API keys, provider URLs or model settings. It does not perform a search just because it starts. Each explicit research POST may consume the configured service credits; `ResearchJobs` deduplicates identical contexts and bounds concurrency/queue size.

Use Ctrl+C to stop the server. Queued jobs are suppressed at shutdown; a running provider request can finish until its HTTP timeout. `--directory` chooses a regional release and `--env-file` chooses private local settings. No public/network bind option is provided. This is a local, single-user development server without authentication or production hosting guarantees.

## Browser connection and CORS

The only accepted browser origins are exactly `http://localhost:3000` and `http://127.0.0.1:3000`. Start the React development server on port 3000. The API permits GET, POST and OPTIONS, accepts the Content-Type header, and does not enable credentialed CORS. An Origin with another scheme, host or port is rejected. The HTTP Host must also match the local backend host/port, limiting DNS-rebinding access. Command-line local requests without an Origin work.

POST requires `Content-Type: application/json` and a nonempty body no larger than one kibibyte. A research start body must be exactly `{}`. Form submissions, transfer-encoded requests, arbitrary settings and other payloads are rejected. CORS/Host validation is a local browser boundary, not user authentication; do not expose this server through a public tunnel or reverse proxy as a multi-user service.

## Routes

| Method and path | Result | Live research? |
| --- | --- | --- |
| `GET /health` or `/api/v1/health` | Server status, live enablement, credential-presence booleans and release-file presence | No |
| `GET /api/v1/fine-tiles` | Small frozen coverage registry, names, bboxes and available/pending/stale status | No |
| `GET /api/v1/fine-regions?tile_id=...` | One registered native-cell viewport with the original joint test-family metadata | No |
| `GET /api/v1/regions` | `regional-map-1` GeoJSON with all 648 cells and existing dataset-derived statuses | No |
| `GET /api/v1/regions/{region_id}` | `regional-detail-1` transport plus research descriptor | No |
| `GET /api/v1/regions/{region_id}/research/cached` | Exact-context genuine cached machine report or explicit unavailable error | No |
| `POST /api/v1/regions/{region_id}/research` | Submit/reuse a bounded background job; empty JSON object required | Yes, if enabled and needed |
| `GET /api/v1/jobs/{request_id}?region_id=...&context_key=...` | Guarded job snapshot | No new work |

Region IDs are the actual B catalog identifiers, for example `grid_r14_c07`, or native-cell IDs beginning `gldas025_` from the fine pilot. Default fine routing uses the frozen registry `data/processed/fine/tiles.json`. The default viewport is `central_us_1deg`; all registered cells use the published joint collection once available. Explicit `RegionalAPI(fine_directory=...)` retains isolated single-release behavior and does not discover the global registry. Fine maps represent limited coverage pilots, not worldwide fine-resolution screening. Unsupported cells remain in the map with their unsupported status. Pending cells remain pending when paired indicators are unavailable. Synthetic demo identifiers are not exposed through these regional routes. The API never assigns a whole-Earth average to a grid cell.

The map route checks its stored CSV/catalog hashes against the current release. Detail and research routes require a current screening artifact. Changed inputs can therefore return a rebuild-required response rather than stale numerical findings. Refreshing release files externally is supported through the existing workflow's revision-aware loader; partially updated releases should be rebuilt before use.

## Numeric detail and fit behavior

The detail handler uses `src.region_transport.build_region_detail(bundle)`, which preserves the existing dataset-derived detail fields and adds annual-fit transport. It does not refit a trend. Main fields include:

- `region_id`, `feature`, `dataset_version`, `screening_status`.
- `screening`, `paired_analysis`, `available_indicator_analysis`.
- `observations`, `provenance`, `annual_fits`, `scientific_display`.
- `research`: the exact context key, cached/start URLs, jurisdiction candidates, and `can_start_live`.

Use `paired_analysis` for paired scientific results only when present. The available single-indicator analysis is an explicitly scoped diagnostic; it is not a paired greening/drying result. When a newly ingested short NDVI record makes paired coverage insufficient, a separate longer soil-only diagnostic can remain available; the cached research numeric refresh prefers that explicit diagnostic while paired classification retains its insufficient/pending state. Use backend annual-fit coordinates and analyzed-year membership rather than constructing a new regression from the displayed monthly points. Missing values stay missing. QA warnings and footprint limits remain visible in the numerical payload.

For country context, the server adds `canada.ca` and `gc.ca` as trusted host suffixes for Canada, using the previously documented official government page checks. It modifies only the copied research context, not B's source catalog. Coarse country overlap and domain matching do not validate legal jurisdiction, current policy status, local applicability or claim support. Other countries retain unverified candidates unless server-owned mappings are deliberately added.

## Research flow for a selected region

1. Load the numeric detail immediately and retain the selected region ID. Display an explicit research button. Selecting a spot, opening the panel and loading numerical data must not automatically invoke external search/model services.
2. After the user clicks the research button, try the cached route. A successful report remains `machine_generated_unreviewed`; a stale matching report retains its original timestamps and `cache_stale=true`.
3. If the user explicitly requested research, there is no compatible stored report and the server permits live research, POST `{}` to the start URL. The server returns HTTP 202 and a descriptor such as:

   ```json
   {
     "request_id": "opaque request identifier",
     "region_id": "grid_r14_c07",
     "context_key": "opaque context fingerprint",
     "state": "queued",
     "error_code": null,
     "report": null,
     "poll_url": "/api/v1/jobs/REQUEST?region_id=grid_r14_c07&context_key=KEY"
   }
   ```

4. Store this request ID as the current selection's latest request, then poll its URL. Job states include `queued`, `loading`, `complete`, `failed`, `cancelled` and `timed_out`. A complete job contains `report`; inspect the report's own status because it may be partial/unavailable even though execution finished.
5. When selection changes, discard prior responses. Polling a job with the wrong region/context yields no report. Polling after the underlying data/context changes returns HTTP 409. The UI must also compare request IDs before rendering so an older selection cannot replace the latest one.
6. Render model prose as untrusted text, citations as validated HTTP(S) links, and numerical results from the detail/analysis fields. Preserve the source-review label and original retrieval time. A source URL's membership in a list does not establish that its claim is correct.

The server initially allows up to two worker threads and four waiting requests, deduplicates exact-context submissions, and keeps a bounded job history. A queue-full response is HTTP 429; the frontend should show a busy state rather than blindly retrying paid work. No live research is launched by health, map, detail, cache or poll requests. No endpoint accepts arbitrary source URLs or provider configuration from the browser.

## Cache handling

The cached route tries `.cache/regional_research/<exact-context-key>.json`, then `contexts/<qualitative-context-key>.json` within that cache directory, then the committed `data/research/<region_id>_context_brief.json`. It reuses only a compatible, complete machine report, validates source/citation correspondence and unreviewed labels, and replaces stored numerical analysis with current backend results. A numerical-data revision may reuse qualitative prose for the identical cell, boundary, period, jurisdiction/domain mapping and query version. Stored original context must be available and valid; `qualitative_reused_across_data_revision=true` discloses reuse. No numerical estimates are ever reused from the report. Different regions/geometry remain isolated. If no stored report is valid, the response is `matching_cached_research_unavailable`; this is not evidence that policies are absent.

Stored reports are reused even after their twenty-four-hour freshness interval, with original retrieval timestamps and `cache_stale=true`. Age does not automatically trigger any provider call. If research is explicitly requested for a cell without a report, persistent source-search entries are shared across neighboring cells by the exact search query, official-domain filter, query version, search depth and result limit. Policy and scientific/news queries stay distinct. Results and excerpt timestamps persist under `sources/`; stale excerpts remain reusable and visibly flagged. A fresh cell may need its own model draft, but it does not repeat identical cached country searches. Drafts are not transferred between cells because source applicability can differ.

Concurrent duplicate cache fills are serialized with thread and POSIX file locks, so neighboring jobs do not both pay for the same missing query. Same-cell qualitative generation is similarly serialized across data revisions. The locks and JSON storage support local Linux/macOS processes; this is not a distributed cache or multi-user authorization system. A process restart retains stored excerpts/reports. Existing job/context keys still include the current dataset fingerprint, so an old asynchronous response cannot replace a new selection's numerical results.

There is no HTTP automatic-refresh parameter: the research body remains `{}`. The Python API supports an explicitly requested `research_region(..., refresh=True)` for a controlled refresh, but this is not exposed by the browser endpoint. No timer, panel opening, background worker or expired timestamp silently refreshes research. Future refresh controls must require their own clear user action.

The genuine committed Canadian report provides national jurisdiction context alongside actual exploratory soil-water statistics. Regional NDVI is still missing in the current release, so it cannot establish paired divergence or ecological risk. Its federal wetland guide is historical and requires current-applicability review; its legislative soil report is distinct from peer-reviewed scientific research. See `docs/member_c_regional_steps.md` for generation history and limitations.

## Error behavior

Errors return a small JSON object, for example `{"error":{"code":"screening_rebuild_required"}}`. Raw filesystem paths, provider responses, exception messages and credentials are not returned.

| HTTP status | Typical meaning |
| --- | --- |
| 400 | Unexpected query, missing poll guards or invalid JSON/research body |
| 403 | Rejected origin/Host or live research disabled |
| 404 | Unknown route/region/job or no compatible cached research |
| 405 | Unsupported operation on a recognized regional route |
| 409 | Stale map/screening/context or unresolved research jurisdiction |
| 429 | Bounded research queue is full |
| 503 | Unavailable release, incomplete provider setup or invalid backend payload |

The health endpoint's `status=ok` means the HTTP service is running; file presence and credential booleans do not certify source QA, model quality, service billing, or legal validation. In read-only mode configured flags are false because credentials were deliberately not loaded.

## Validation

Run:

```sh
.venv/bin/python -m pytest -q tests/test_regional_api.py
```

Tests cover scientific transport delegation, no-network reads, unknown/synthetic IDs, source-hash staleness, server-only provider settings, empty-body enforcement, queue limits, guarded polling, cached numerical refresh and actual local HTTP CORS/Host/preflight behavior. Provider jobs are mocked. A real-release offline smoke check returned 648 map cells, real Canadian detail and the matching genuine cached report. No paid provider requests were made for this API milestone.

## Audit a fine release before serving newly imported NDVI

After importing actual fine MODIS exports, rebuild the fine statistics, then run the read-only audit:

```sh
.venv/bin/python scripts/prepare_fine_backend.py --directory data/processed/fine/central_us
.venv/bin/python scripts/audit_fine_release.py --directory data/processed/fine/central_us
```

The audit prints JSON and exits nonzero on integrity failure. By default it writes no files and never contacts a provider. An explicit `--output /path/to/report.json` saves the audit result. Run it after each incremental annual import so a valid partial release can be distinguished from a stale or inconsistent one.

Checks cover canonical native IDs/geometry/bounding boxes, unchanged soil storage units and values, full monthly indexes with missing slots preserved, coverage arithmetic and report counts, all GLDAS source hashes, archived MODIS hashes and authoritative ledger rows, source/projection/QA semantics through B's importer validator, current map/statistical source fingerprints, and a testing family restricted to this fine pilot. An accepted ledger row must match the actual archived bytes named by its source hash; changing both ledger and combined output cannot bypass that check. Statistical analyzed years must independently have twelve usable source months; diagnostic p-values must not become paired map significance.

Read `integrity_passed`, `full_required_period_complete`, `full_export_index_received`, `ndvi_pending_rows`, `ndvi_valid_rows` and `paired_eligible_cells` separately. For example, a genuine soil-only release can pass integrity while remaining incomplete for NDVI. One imported month keeps the remaining monthly slots pending and cannot support a paired trend. A fully received export can still contain valid missing/QA-rejected months; these are preserved and reviewed, not filled with invented values. Complete temporal coverage is still not independent source-pixel validation, common-footprint review, proof of environmental damage or worldwide screening coverage.

The audit does not refit numerical models or change the statistical family to force a supported signal. Its test fixtures include explicitly synthetic NDVI in temporary directories to exercise partial/full ingestion and corruption detection; those fixtures are never shipped as NASA observations. Run `tests/test_fine_audit.py` for the integrity regressions.


## Frozen multi-tile coverage and one statistical family

The registry uses schema `fine-tiles-1` with a repository-relative `collection_directory` and `tiles: [{id, name, bbox, directory}]`. The frozen six demo locations are `central_us_1deg`, `canada_1deg`, `iberia_1deg`, `sahel_1deg`, `se_australia_1deg` and `amazon_1deg`. Each one-degree tile contains sixteen native cells; the complete frozen collection contains ninety-six cells. These locations were selected as a demonstration set, not a representative or exhaustive worldwide sample.

`GET /api/v1/fine-tiles` returns this small coverage index plus `status`, `release_scope` and `map_url` per tile. Status is `pending` when required release files are not available, `stale` when published source/map consistency fails, or `available` when the map is current and covers the requested tile. It does not certify source QA or imply complete NDVI. Requests perform no provider access.

`GET /api/v1/fine-regions?tile_id=canada_1deg` sends only that registered tile's geometry. The query accepts exactly one known `tile_id`; unknown IDs return 404, duplicate/empty parameters or arbitrary directory/bbox parameters return 400. Omitting the query retains the central-US default. Directory paths are never accepted from the browser. Registry paths must resolve within repository-local `data/processed/fine`, cell boundaries must align to the native lattice, and overlapping/duplicate tile definitions are rejected.

Once `data/processed/fine/collection/map_screening.geojson` is published, every registered native detail and viewport uses that joint collection. The response filters map features for display and adds `viewport: {tile_id, name, bbox, feature_count, family_regions, release_scope, selection_only}`. The original multiple-testing family, corrected results, settings, source hashes and limitations are retained for the whole collection. A sixteen-cell viewport must not be described as a newly recomputed sixteen-cell statistical family. Partial NDVI in some tiles changes eligible-test counts but does not redefine the frozen catalog or select locations by significance.

The selected cell's native ID locates its registered bounding box; details load its observations, provenance and statistical record from the joint collection. Its provenance includes `fine_tile` with the registry name, boundary and release scope. Asynchronous research keys therefore bind to the actual joint dataset revision, and cached qualitative prose still cannot supply old numerical results.

Before the joint map is first published, an available individual registered tile may be served with `release_scope=individual_tile_before_collection`; other unavailable tiles remain pending. After joint publication, a stale collection is withheld rather than silently falling back to differently corrected per-tile results. An explicitly configured custom `fine_directory` remains a standalone release for tests and local tooling: it has no global registry endpoint and accepts no tile query.

Tests in `tests/test_fine_tiles.py` cover preservation of joint-family metadata during viewport selection, exact cell-to-tile detail routing, unsafe registry paths, duplicate/overlapping/unaligned boundaries, pre-publication availability and stale joint-family withholding. All tile/index/map/detail reads remain local and cannot initiate external research; the explicit research-button requirement still applies.

The published collection's `input_manifest.json` uses schema `fine-collection-inputs-1`. Serving verifies both the registry hash and the recorded source-tile CSV, catalog, immutable GLDAS baseline, metadata, source manifests and accepted MODIS ledger hashes. A newly appearing optional ledger/manifest also invalidates a snapshot that omitted it. Thus unchanged collection CSV/map files cannot silently conceal a newer individual-tile import. Matching hash computations are reused by file revision for efficient selection. A changed, missing or unsafe input marks the index stale and returns `fine_collection_rebuild_required` (HTTP 409) from map/detail requests until the joint collection is rebuilt. Validation does not initiate data downloads or research calls.


## Worldwide on-demand GLDAS cells

`GET /api/v1/cell?lon=<longitude>&lat=<latitude>` resolves valid coordinates to native cell geometry without claiming that the cell has data. Coordinates south of 60°S return `outside_gldas_extent`. `GET /api/v1/regions/{gldas025_id}` serves the existing joint collection first for its 96 registered cells. Other valid native IDs are extracted from the local original GLDAS files into a hash-verified per-cell cache, then receive only an exploratory standalone soil analysis. No coarse NDVI values or paired results are assigned.

The first cold cell scan may take several seconds. Same-cell concurrent requests join one bounded scan; a different simultaneous cold cell receives HTTP 429 and may be retried. Missing source files produce an explicit service error; fully masked cells remain unsupported. The small in-memory cache is bounded and invalidated when source or country-boundary files change; per-cell disk files live under ignored `.cache/global_cells/`. Country intersections are geographic candidates, not legal determinations. Map/detail reads make no policy or AI requests; external research still requires an explicit user-triggered POST.

### Nearest location with soil data

`GET /api/v1/cell/nearest?lon=<longitude>&lat=<latitude>` finds the closest GLDAS 0.25° cell center with at least one finite, nonnegative local soil observation during 2003–2024. Distance is measured on the sphere, including across the date line; the response identifies the requested point, selected cell, distance, source release and number of valid soil months. The first request builds a source-versioned local index; subsequent requests reuse it. Missing source files or an unavailable index produce an error rather than fabricated data. The lookup uses no Earth Engine or research API calls.

Soil support does not guarantee complete coverage or available NDVI. Selecting the suggested location may trigger the existing on-demand vegetation retrieval. The suggestion is a different geographic location; it is not an observation or interpolation for the original point. Synthetic demonstration records are no longer served by the frontend; synthetic fixtures remain in automated tests only.
