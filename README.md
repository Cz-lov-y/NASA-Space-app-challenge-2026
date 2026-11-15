# EarthRisk — Green Mirage

NASA Space Apps Challenge 2026 | Toronto | 14–15 November 2026

**Mission:** Screen for places where vegetation greenness is increasing
while soil moisture is declining, then connect reproducible environmental
measurements to verifiable government policy and conservation evidence.

## Current status

The globe now offers **96 native 0.25° cells in six areas**: Central US, Canadian
interior, Iberia, Central Sahel, southeast Australia and Brazilian Amazon. The
2003–2024 collection has 76,032 monthly records. All NDVI export slots arrived;
1,566 QA-masked values remain missing, and one cell lacks GLDAS support.

Eighty cells have sufficient complete paired years. The declared 96-cell family
contains 160 tests, producing 62 uncertain signals, 18 no-detected-divergence
results, 15 insufficient cells and one unsupported cell; none meets the supported
signal gates. Results remain provisional and the collection is exploratory.
Worldwide fine coverage and scientific review remain next.

### Click worldwide land cells

Click any point inside the native GLDAS envelope (60°S–90°N) to load the original 0.25° soil-water cell directly from the existing local NASA monthly files. The first load takes a few seconds; subsequent selections reuse a verified local cache. Country candidates use coarse Natural Earth boundaries. The six prepared areas retain their joint MODIS/GLDAS paired screening. Outside those areas, soil-only statistics are exploratory and native NDVI/paired screening remain pending. Oceans, masked cells and areas south of 60°S return an explicit unavailable state; no values are invented. Local raw GLDAS files are required for on-demand cells.

### Run the real-data globe locally

Use Python 3.12 with `requirements-data.txt` and Node 22. From the repository root,
start the backend in one terminal:

```sh
.venv/bin/python scripts/serve_regional_api.py --port 8000
```

Start the frontend in another terminal:

```sh
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:3000/ and select a **0.25° cell** from the left-hand pilot
grid or the real-data menu. Use the **Area** selector to switch between the six available tiles. White globe markers also navigate to areas. The checkbox
also offers the historical 10° overview. Measurements belong to cell footprints.

Policy/scientific research requires clicking **Get policy & scientific context**.
The default API permits saved research only. To permit external research after
that click, restart the backend with `--enable-live`; private `.env` settings stay
server-side. Saved reports and source queries are reused before new requests.
Selecting a cell never launches a search or model call. See [the HTTP API guide](docs/regional_api.md).

Fine-cell acquisition and validation commands are in [the pipeline guide](docs/fine_data_pipeline.md).
All 132 current-method annual files have been retrieved, validated, archived and imported.
The joint collection audit passes while preserving source-QA gaps and unsupported model cells. The old coarse export batch was retired after the resolution change.

Cloud tooling needs optional `requirements-earthengine.txt` and authorized
Earth Engine access. The six prepared areas read checked-in processed data; on-demand land cells additionally require the checked-in raw GLDAS files and data dependencies. Polar acquisition and worldwide fine tiles remain future work.

### Existing Streamlit demonstration

The coordinated regional backend work is described in [the team delivery plan](docs/team_demo_plan.md).
Real regional GLDAS observations now cover 301 supported 10° cells for 2003–2024;
the catalog retains all 648 worldwide cells. Regional NDVI exports are still required
before paired regional screening can run. The new optional research backend supports
DeepSeek configuration and a separate Tavily search key. The human team supplied the
globe frontend; the existing dashboard below has not been changed.

An interactive **Streamlit frontend demo** exists with:

- Regional and observation-window selection.
- NDVI and soil-moisture trends, per-year slopes and confidence intervals.
- Standardized time-series comparison, raw p-values and method caveats.
- Conservative Green Mirage candidate screening.
- Source/QA warnings, agent evidence panels, and CSV/JSON exports.
- A future-ready geographic panel that never fabricates map coordinates.

**The default demo uses SYNTHETIC observations.** Preliminary NASA-derived
global MODIS and GLDAS data are also included and can be selected with region
`whole_earth`; their spatial coverage and scientific QA remain under review.
They do not establish a verified environmental finding or policy assessment.
The agent currently returns an empty, unverified report until real research
integration is completed.

## Quick start (Python 3.12 recommended)

~~~bash
git clone https://github.com/Cz-lov-y/NASA-Space-app-challenge-2026.git
cd NASA-Space-app-challenge-2026
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-data.txt
python -m pytest -q
streamlit run app.py
~~~

Windows virtual environment activation: `.venv\Scripts\activate`.

The default demo region is `demo-region`. Select both NDVI and soil moisture.
For preliminary real data, enter `whole_earth` and select NDVI and 0–100 cm
soil water storage. Review the coverage warning and provenance before interpreting results.
The **Investigate This Region** button exercises Member C's interface; it
does not generate verified policy documents until C implements retrieval.

## Team ownership

| Member | Branch | Owned work |
| --- | --- | --- |
| A — Statistics / team lead | `feature/statistics` | `src/statistics.py`, `src/divergence.py`, statistical tests, methodology |
| B — NASA data | `feature/nasa-data` | `src/nasa_data.py`, `src/preprocessing.py`, real NASA observations, QA |
| C — Policy/literature agent | `feature/policy-agent` | `src/policy_agent.py`, `src/literature.py`, `src/evidence.py` |
| D — Frontend/integration | `feature/frontend` | `app.py`, `src/ui/`, display tests, theme, launch |

The team works independently on assigned branches and opens PRs into
`main`. Keep `main` runnable and never commit API keys.

## Integration contracts

1. **B → A/D:** `get_timeseries(region, variable) -> pandas.DataFrame`
2. **A → C/D:** `analyze_region(data) -> dict`
3. **C → D:** `investigate_policy(analysis) -> dict`

Details: `docs/contracts.md`, `docs/architecture.md`,
`docs/team_workflow.md` and `docs/frontend.md`.

## Scientific and research safeguards

- A positive NDVI slope and negative moisture slope is a **candidate
  opposite-trend signal** only, not proof of causation or harm.
- Trend statistics may need correction for seasonality, serial dependence,
  spatial correlation and multiple comparisons.
- The comparative z-score chart shows relative trajectories, **not** an
  environmental risk score or the original unit magnitudes.
- Missing indicators, mismatched dates, uncertain data QA, and missing
  source verification are visible, not silently filled.
- Agent evidence must retain original source links and verification
  statuses; a failed search does not establish that no policy exists.

## Deployment

After team review and green tests, deploy `main` / `app.py` to Streamlit
Community Cloud. Requirements are in `requirements.txt` and
`.streamlit/config.toml`. No credentials are necessary for the synthetic
demo; any future API keys belong in private deployment secrets.

See `docs/frontend.md` for detailed integration, smoke-test, and
deployment checklists.


### Native-cell product update

The globe uses original **0.25° GLDAS native cells** with MODIS NDVI, grouped into six areas and one jointly adjusted analysis collection. The 10° view is a labeled legacy overview. Worldwide fine coverage remains pending. See [the updated team plan](docs/team_demo_plan.md) and [resolution specification](docs/fine_resolution.md).

Policy/scientific research requires clicking **Get policy & scientific context**. Saved reports and source searches are reused on disk, including stale context with visible retrieval dates; selecting a cell never starts external research. Keep `.cache/regional_research` between server restarts to retain this cache. Qualitative reports remain machine-generated and unreviewed.

Rebuild the fine pilot offline with `.venv/bin/python scripts/process_fine_gldas.py` followed by `.venv/bin/python scripts/prepare_fine_backend.py`. Cloud acquisition commands and remaining validation are in [B's fine-resolution handoff](docs/member_b_resolution.md).


The fine pilot acquisition, strict importer, resumable direct retrieval and Drive synchronization are documented in [the fine-data pipeline](docs/fine_data_pipeline.md). The current collection declares all 96 cells before joint adjustment; source review remains pending and no cell passes the supported-signal gates.


The native MODIS area calculation is now versioned as `modis_sinusoidal_sphere_native_pixel_v2`: native pixel areas and geographic cell areas use the same sinusoidal sphere. Earlier fine source files remain archived as historical evidence. See [the resolution and collection methodology](docs/fine_resolution.md).
