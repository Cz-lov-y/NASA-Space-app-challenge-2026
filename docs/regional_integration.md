# Backend handoff for the human frontend

The human team owns D's design and code. No frontend was modified in this implementation.

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

The loader uses local artifacts and does not schedule background work. D owns loading/cancellation states, duplicate-job suppression, selection identity checks and accessible fallback navigation. The backend has unit and integration tests; actual globe/browser interaction awaits human frontend code.
