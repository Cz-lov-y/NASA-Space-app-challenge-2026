# EarthRisk — Green Mirage

**[Open the live demo](https://34-31-40-122.sslip.io/)** · NASA Space Apps Challenge 2026 · Toronto

EarthRisk explores a possible “green mirage”: vegetation becoming greener while water stored in the root-zone soil decreases. Search for a place or click land on the globe to see its historical vegetation and soil-water records, an explanation of the trend comparison, and links to policy and scientific context.

## Try it

1. Open the [public demo](https://34-31-40-122.sslip.io/); no account or passcode is required.
2. Search for a city, province, state, or country, or select a point on land. Use **North up**, zoom and reset to navigate.
3. Read **What this means** and explore the trend chart. Colored cells indicate the browser's screening category: red is a supported opposing-trend signal, yellow is uncertain, green means no detected divergence, and gray means not yet analyzed or insufficient.
4. Select **Get policy & scientific context** when you want an AI-generated, sourced overview. Research is requested only when that button is clicked. Live requests are limited to three per IP address per hour and 30 across the deployment per rolling 24 hours; cached reports can still be read. People behind the same network may share an IP limit.

The globe defaults to North America. Clicking a grouped area in the stronger-signal list repeatedly cycles through its cells. Cell colors are preliminary evidence categories, **not probabilities of damage or proof that a place is safe**.

## Data and methodology

- **Soil water:** NASA GLDAS Noah `GLDAS_NOAH025_M.2.1` monthly land-model data, on its native 0.25° grid. Root-zone storage combines the 0–10, 10–40 and 40–100 cm layers and is expressed in `kg m-2`, not volumetric water content.
- **Vegetation:** NASA MODIS [MOD13A3.061 monthly NDVI](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13A3), obtained via Google Earth Engine at its native approximately 1 km source resolution, filtered by quality flags and aggregated to the GLDAS cells. NDVI is scaled by 0.0001 once.
- **Analysis period:** the current aligned monthly workflow uses 2003–2024. Each displayed cell represents an area, not a point measurement. Ocean, ice and other locations can be missing or outside GLDAS coverage.
- **Seasonal gaps:** the browser may estimate short, bounded NDVI gaps with a seasonal curve. Dashed green chart segments are estimates; original observations and downloadable records remain unchanged. The same estimates can contribute to the displayed classification. The model can be inaccurate and its uncertainty is not propagated into significance tests or confidence intervals. See [frontend methodology](docs/frontend.md).
- **Screening:** the browser compares annual vegetation and soil-water trends for the selected cell and period. Inference is exploratory for an individual cell/window; it is not globally adjusted and does not establish causation. Data footprints and source quality still require independent review. AI context is machine-generated and source links should be checked before use.

The cloud worker continues retrieving and processing historical Earth Engine records, currently prioritizing the southern Canadian Prairies and then Canada. It publishes completed tiles to the deployed site's data index; the browser refreshes approximately every 20 seconds. The present map loads only the first 1,000 summary cells, so it does **not** show every completed or supported cell worldwide. Results in an already open panel are not automatically refreshed. This is ongoing processing of historical data, not a real-time satellite feed.

## Run locally

Requirements: Python 3.12, Node 22, and the repository's original GLDAS source files. The repository contains raw NASA GLDAS inputs and a point-in-time snapshot of 347 completed global tiles with their archived MODIS source CSVs; current cloud-generated tiles continue to be produced separately. A clone is therefore large.

```bash
git clone https://github.com/Cz-lov-y/NASA-Space-app-challenge-2026.git
cd NASA-Space-app-challenge-2026
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-data.txt -r requirements-earthengine.txt
python scripts/serve_regional_api.py --port 8000
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open `http://127.0.0.1:3000/`. New on-demand MODIS retrieval requires authorized Earth Engine credentials for the configured project. To enable the optional AI research action locally, put the server-only settings from `.env.example` into `.env` and start the API with `--enable-live`. Never commit credentials. The local API is designed for a trusted local user and must not be directly exposed to the internet.

```bash
python -m pytest -q
npm --prefix frontend run build
```

The older `app.py` Streamlit prototype and synthetic fixtures are retained for development; the public globe uses NASA-derived records and does not offer the synthetic demo.

## Operations and documentation

- [Current handoff and active worker](docs/HANDOFF_CURRENT.md)
- [Deployment and operations](docs/WEB_DEPLOYMENT_PLAN.md)
- [Frontend, screening and seasonal estimation](docs/frontend.md)
- [Data pipeline and provenance](docs/fine_data_pipeline.md)
- [API contracts](docs/regional_api.md)
- [Team and historical planning](docs/team_demo_plan.md)

The live VM, disk, network and external provider calls can incur charges. The VM is the sole writer for the live Earth Engine queue; do not start another worker against the same shared index. Submission reviewers should use the live link above; documentation and code describe the prototype's remaining coverage and scientific limitations.
