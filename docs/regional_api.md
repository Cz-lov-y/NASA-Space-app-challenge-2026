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
| `GET /api/v1/regions` | `regional-map-1` GeoJSON with all 648 cells and existing dataset-derived statuses | No |
| `GET /api/v1/regions/{region_id}` | `regional-detail-1` transport plus research descriptor | No |
| `GET /api/v1/regions/{region_id}/research/cached` | Exact-context genuine cached machine report or explicit unavailable error | No |
| `POST /api/v1/regions/{region_id}/research` | Submit/reuse a bounded background job; empty JSON object required | Yes, if enabled and needed |
| `GET /api/v1/jobs/{request_id}?region_id=...&context_key=...` | Guarded job snapshot | No new work |

Region IDs are the actual B catalog identifiers, for example `grid_r14_c07`. Unsupported cells remain in the map with their unsupported status. Pending cells remain pending when paired indicators are unavailable. Synthetic demo identifiers are not exposed through these regional routes. The API never assigns a whole-Earth average to a grid cell.

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

1. Load the numeric detail immediately and retain the selected region ID.
2. Try the cached route. A successful report remains `machine_generated_unreviewed`; a stale matching report retains its original timestamps and `cache_stale=true`.
3. If there is no matching cache and the server permits live research, POST `{}` to the start URL. The server returns HTTP 202 and a descriptor such as:

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

The cached route first tries `.cache/regional_research/<exact-context-key>.json`, then the committed `data/research/<region_id>_context_brief.json`. It reuses only a compatible, complete machine report, validates source/citation correspondence and unreviewed labels, and replaces stored numerical analysis with the current analysis. It does not fall back to another region. If neither report is valid, the response is `matching_cached_research_unavailable`; this is not evidence that policies are absent.

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
