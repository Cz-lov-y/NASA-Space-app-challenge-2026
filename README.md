# EarthRisk — Green Mirage

NASA Space Apps Challenge 2026 | Toronto | 14–15 November 2026

**Mission:** Screen for places where vegetation greenness is increasing
while soil moisture is declining, then connect reproducible environmental
measurements to verifiable government policy and conservation evidence.

## Current status

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
python -m pip install -r requirements.txt
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
