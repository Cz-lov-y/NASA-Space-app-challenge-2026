# Backend handoff for the human frontend

The human team owns D's design and code. No frontend was modified in this implementation.

## Local artifacts for the human frontend

`data/processed/regional/map_screening.geojson` contains all 648 geographic cells with compact stored trend facts and explicit pending/unsupported/classification states. Load this artifact for geographic display. It has source fingerprints and a declared provisional testing family; soil-only diagnostics must not be presented as paired greening/drying findings.

Export all region details without service requests:

```sh
.venv/bin/python scripts/export_regional_handoff.py --all
```

The default `.cache/regional_handoff/` contains `manifest.json` and one `<region_id>.json` per cell. Details include the original observations, geometry, provenance, paired analysis if available, and standalone diagnostics. Missing measurements serialize as JSON `null`. This generated directory is excluded from Git; it can be recreated locally or during a build. `--region grid_r14_c07 --output PATH` exports one region instead. The exported observations and statistics come from stored NASA-derived data, not AI.

Refresh all backend artifacts and audit with one local command:

```sh
.venv/bin/python scripts/prepare_regional_backend.py
# When actual regional exports arrive, add only the new files:
.venv/bin/python scripts/prepare_regional_backend.py --modis /path/to/new_export.csv
```

This sequence validates/imports supplied regional MODIS files, rebuilds statistical summaries, runs the release audit and exports details. It makes no research or cloud-export requests. Check the audit's data-readiness fields: passing integrity checks does not mean regional NDVI exists or the frontend is complete.

Regional snapshots are reused locally until a release file's modification time or size changes. Returned frames, geometry and statistical objects are independent copies. Current CSV/catalog hashes still gate stored screening and cache identity; changing observations invalidates old results.

```python
from src.regional_workflow import load_region, research_selected_region

bundle = load_region(selected_region_id)
# Immediate local data: no service keys or network calls.
observations = bundle['observations']  # pandas long table, missing values preserved
geometry = bundle['feature']['geometry']
screening = bundle['screening']  # None if absent or stale
screening_status = bundle['screening_status']

# Run in a background job after selection; this can use configured service credits.
# Keep the bundle's region/context identity with the job and discard stale responses.
report = research_selected_region(bundle, cache_dir='.cache/regional_research')
```

Read `data/processed/regional/catalog.json` for the globe/list. `centroid` uses `[longitude, latitude]`. Properties include bbox, variables, `data_status` and geographic jurisdiction candidates. The catalog retains unsupported cells; 301 cells currently have GLDAS observations, with regional NDVI pending. Do not color missing paired analysis as a detected environmental signal.

The existing public reader also accepts regional IDs:

```python
from src.nasa_data import get_timeseries
soil = get_timeseries('grid_r12_c08', 'soil_water_0_100cm')
```

Unknown IDs, unavailable series and unsupported cells fail explicitly. Read availability from the catalog before offering variable choices. DataFrame metadata includes boundary, source QA and units. Preserve that metadata separately when concatenating observations.

`screening.json` contains worldwide-adjusted `screening` separately from original within-region `analysis`. Display its categories and reasons, including pending/unsupported/insufficient. `load_region` checks the artifact's source CSV and catalog hashes and withholds stale screening. Rebuild after an import:

```sh
.venv/bin/python scripts/build_regional_screening.py
```

When paired analysis is pending, `available_indicator_analysis` exposes the existing soil-water statistics with their units, uncertainty and analyzed years. These diagnostics do not participate in the worldwide paired testing family; their significance is exploratory. Keep the paired status pending in the globe and identify the missing NDVI explicitly. `research_selected_region` preserves these genuine diagnostics in its quantitative payload while requesting only qualitative jurisdiction context from the model.

The research dataset fingerprint includes the actual monthly CSV, geographic catalog, metadata and source manifests. Changes to observations, boundaries or source context invalidate the previous qualitative cache identity. This is independent of checking that stored numerical screening is current.

The command-line handoff can check setup without spending service credits:

```sh
.venv/bin/python scripts/run_regional_research.py --region grid_r14_c07
```

Its explicit `--live` option makes bounded provider requests. Read the Member C guide before using that option or publishing a generated report. The CLI loads only supported literal configuration assignments from local `.env`; it does not execute shell code. Keep keys private and out of browser payloads.

Research output keeps `quantitative_analysis` separate from `qualitative`. A context-only brief may be requested while paired analysis is unavailable; the report discloses this. Source links and machine/unreviewed status must remain visible. Caching includes region, geography, jurisdictions, dataset fingerprint, period and query version. No credentials or original secret-bearing provider errors belong in browser payloads. See `member_c_regional_steps.md` for environment setup and the structured claim schema.

## Research jobs and offline rehearsal

`src.research_jobs.ResearchJobs` provides a process-local bounded background executor for selection-triggered research. Create it per user/session and keep credentials on the server. `submit(bundle, **provider_kwargs)` returns an opaque request ID and context key. Duplicate active/completed work for that context is reused. Poll with the current region and context; a mismatch returns `stale` with no report. Keep the latest request ID in the selection state. Cancellation suppresses delivery; it cannot forcibly stop a running HTTP request. The manager caps both workers and queued requests, sanitizes errors, and supports `close()` to release resources. This is a local backend utility, not a persistent deployment queue.

The genuine saved Canada brief can be rehearsed without credentials or service requests:

```sh
.venv/bin/python scripts/run_regional_research.py --region grid_r14_c07 \
  --cached-only --report-file data/research/grid_r14_c07_context_brief.json \
  --official-domain canada.ca --official-domain gc.ca
```

The reader validates exact geography, period, release fingerprint, query version and citation/source correspondence before exposing cached prose. It refreshes numerical results from current data. Machine/unreviewed labels and original retrieval time remain visible; mismatched reports fail rather than substituting another region's evidence.

D owns visible loading/cancellation states, selection identity checks, accessible fallback navigation and connecting the job manager to its interface. The backend has unit and integration tests; actual globe/browser interaction awaits human frontend code.
