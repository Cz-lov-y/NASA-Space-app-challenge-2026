# EarthRisk handoff — 2026-11-15

> Update: The automatic pairing milestone described below was subsequently completed and committed. The sections describing an interrupted/uncommitted working tree are historical. See the latest section in `docs/team_demo_plan.md` for current status.

## User goal and working agreement

Deliver a hackathon demo where land is clickable at the finest practical resolution, NASA vegetation and soil data are aligned automatically, the code identifies potential problematic spots, the globe colors results by evidence, and the user can request AI policy/science context. The user prioritizes automation and a working demo; defer rigorous scientific review until afterward. Never invent measurements or call p-values a calibrated probability of environmental harm. AI research must run only after the user clicks its button; Earth Engine data retrieval may start on cell selection.

Work on `main`. After a **completed major milestone**, run appropriate checks, commit and push, then stop for human team review. The user wants raw data included in the repository. Keep credentials in ignored `.env` and Earth Engine OAuth storage; never print or commit them. The user chose to retain the existing free Earth Engine tier, even though the project is in restricted mode. Existing user-owned `.vscode/` is untracked and should be left alone.

## Git and current interruption

The last committed and pushed revision is `2b292da` (`Enable on-demand native GLDAS data for global land clicks`). The working tree now contains **uncommitted, unfinished changes** for automatic vegetation pairing and worldwide batch processing. Do not discard them. The previous turn was interrupted deliberately for this handoff; workers `/root/member_b` and `/root/member_c` were interrupted, and their edits may be incomplete. Inspect `git status --short` before resuming. Nothing in the current unfinished milestone has been committed or pushed.

## Committed baseline

- The globe supports clicks across the native GLDAS envelope, 60°S–90°N. For land cells with data it reads the original 0.25° GLDAS monthly files on demand, with 528 rows for two soil series over 2003–2024. First access takes roughly 6 seconds; cached access is faster. The 0–100 cm series sums three same-cell layers; units remain `kg m-2`. Ocean, masked cells and locations outside the envelope are explicitly unavailable.
- Six precomputed areas contain 96 native cells with MODIS NDVI and GLDAS soil data. Their jointly adjusted family contains 80 eligible cells and 160 tests; last committed results are 62 uncertain, 18 no detected divergence, 15 insufficient, one unsupported and zero supported signals. These are provisional, not a worldwide survey.
- The fine MODIS exporter uses the corrected `modis_sinusoidal_sphere_native_pixel_v2` area method. Legacy files are preserved as history, not active v2 values. Raw GLDAS and accepted fine export CSVs are tracked in Git. The six-area collection audit passed in the previous milestone.
- Policy/science research is cached and requires the user to click **Get policy & scientific context**. Source and narrative quality remain unreviewed. The project was configured locally for Earth Engine, DeepSeek and Tavily; no credentials belong in the handoff.

## Uncommitted work in progress

1. `src/global_screening.py` and `tests/test_global_screening.py`: a paired, single-native-cell adapter. It uses real monthly NDVI and soil records and the existing automated statistical detector. Its scope is a single-cell two-test BH family, explicitly not worldwide adjustment; `probability` is null because there is no calibrated harm probability. Member A reported 14 targeted tests passing, including the existing soil tests. Confirm this against the current tree before release.
2. `src/global_cell_modis.py` and `src/regional_api.py`: automatically queue native MODIS retrieval when an unregistered supported land cell is selected. One worker and one queued job use 22 resumable yearly requests, persist data under ignored `.cache/global_modis/`, merge real NDVI with the same GLDAS cell, and expose progress through `ndvi_retrieval` and `GET /api/v1/data-jobs/{id}`. `GET /api/v1/global-screened-cells` lists cached screening summaries and completed batch map shards with pagination. Explicit research routes must not start data jobs, and data selection must not start AI/search. Member C reported 24 mocked tests passing before the latest batch-index work; verify final integration and tests.
3. Frontend changes in `frontend/src/App.tsx`, `components/panel/SlidingPanel.tsx`, `components/globe/EarthGlobe.tsx`, services and types: load markers for all six prepared areas, show individually screened cells as diamonds, poll data-job progress, let users retry data retrieval, and show evidence categories rather than claiming a probability. The AI button remains explicit. These edits were not fully checked against the final API contract after the interruption. Earlier intermediate frontend builds passed, but **a final build and browser test have not yet been completed**.
4. `scripts/global_screen_earth_engine.py` and changes to `scripts/acquire_fine_tiles.py`: enumerate 1° tiles automatically from original GLDAS valid masks and run the existing native 16-cell MODIS acquisition/merge/statistics path. Default is a local plan; `--fetch` starts real Earth Engine requests. The global batch explicitly defers the heavy per-tile release audit for the demo, retaining provisional labels. It records per-tile results under `data/processed/fine/global/` and an index there. Per-tile results are not globally adjusted.
5. An actual bounded Mexico batch pilot completed for `global_r085_c078`, bbox `[-102,25,-101,26]`, containing 16 cells. Its processed directory, `data/processed/fine/global/index.json`, `data/requests/fine_global_r085_c078.json`, and 22 newly generated raw source CSVs under `data/raw/modis_earth_engine/fine/` are currently **untracked**. Retain them and include them in the eventual milestone commit after checking their role. The pilot's recorded output is `.cache/global_tile_pilot.json`.
6. Real on-demand tests completed for `gldas025_r448_c0800` (Poland: 792 soil+NDVI monthly rows, paired result insufficient) and `gldas025_r341_c0312` (Mexico: 792 rows, uncertain signal). These particular interactive outputs live in ignored `.cache/global_modis/`, not Git. The Mexico 16-cell batch above is independently retained as untracked repository data. Do not confuse cache availability on this machine with availability on a teammate's machine.

## Coverage, cost and scaling

The local source-mask scan found 242,753 native cells with some GLDAS soil support, grouped into 17,284 supported 1° tiles. The current exact workflow plans up to **380,248 annual Earth Engine requests**, plus pilots, before cache reuse. One processed tile is approximately 9.6 MB, plus raw archives and caches; a full run could consume hundreds of GB and take a long time in restricted mode. A worker was asked to add a minimum-free-disk guard, resumable error reporting and continuation past failed tiles; inspect `scripts/global_screen_earth_engine.py` to see whether that work landed before interruption. Do not claim the world is already paired, that all cells are statistically eligible, or that the global multiple-testing family is complete.

A possible faster future approach is 22 annual global aligned raster exports, estimated around 2.74 GB uncompressed for 36 float bands per year. Earth Engine's overlap weighting differs from the current polygon method, so it needs a distinct method/version and a working importer before it can replace the exact pipeline. No raster implementation or cloud submission was completed. See [Earth Engine reduceResolution documentation](https://developers.google.com/earth-engine/apidocs/ee-image-reduceresolution).

## Next steps for the receiving developer

1. Review the full working-tree diff and finish workers B/C's interrupted work. Confirm worldwide batch index lookup takes priority over on-demand retrieval after the original 96-cell collection, and that cached/batch marker pagination and source invalidation work. Preserve separate single-cell, per-tile and six-area testing scopes.
2. Inspect the global batch runner's disk guard and failure/resume behavior. The user authorized global automation but expects the free tier; avoid silently exhausting storage or claiming completion. The bounded pilot can be repeated with `--fetch --max-tiles 1 --bbox -102 25 -101 26`; the cached support plan is `.cache/world_native_plan.json`.
3. Complete and run focused tests for on-demand jobs, progress/retry, source changes, batch-index mapping and UI behavior. Run the full Python suite and frontend build once the tree is stable. Do not cause live AI/search calls during tests. The last fully completed previous milestone had 290 Python tests and 68 subtests passing; that count predates the current unfinished changes.
4. Restart the local backend to load the final code, then test a real unregistered land click end-to-end: soil appears, vegetation progresses to completion, category and scope appear, and no research request runs until the button is clicked. Test an ocean/masked point and a point south of 60°S. Confirm preloaded regions still use their joint-family results.
5. Update README/team plan with the final actual behavior, limitations, batch progress and next steps. Stage only intended source, documentation and pilot artifacts; keep `.env`, `.cache/` and `.vscode/` out. Scan staged content for configured secrets without printing them. Commit and push to `main` at the completed milestone, then stop for team review.

## Local commands and services

```sh
.venv/bin/python scripts/serve_regional_api.py --port 8000 --enable-live
cd frontend
npm run dev -- --host 127.0.0.1
```

The frontend is usually at `http://127.0.0.1:3000/` and API at `http://127.0.0.1:8000/`; verify ports/processes before restarting. Node 22 was installed locally under ignored `.cache/node-runtime/node-v22.23.5-darwin-arm64/bin` if it is not on PATH. Python 3.12 dependencies are in `.venv`; Earth Engine support additionally uses `requirements-earthengine.txt`. Runtime caches are machine-local and not deployed automatically.
