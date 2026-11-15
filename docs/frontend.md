# Member D — Frontend, Integration, Deployment

Member D owns `app.py`, `src/ui/`, the Streamlit theme, display
tests, and the deployment/demo experience. The architecture stays
Streamlit/Python, following the already-committed team scaffold.

## Independent startup (no other member needs to finish first)

1. Install Python 3.12, then run `python -m pip install -r requirements.txt`.
2. Run `python -m pytest -q`.
3. Run `streamlit run app.py`.
4. Enter region `demo-region` and select both indicators.
5. Observe the explicit **SYNTHETIC — NOT NASA** warning.
6. Click **Investigate This Region**: the current C stub returns no fabricated
   sources and clearly reports `not_started`.

## Integration responsibilities

| Producer | Import used by frontend | Contract |
| --- | --- | --- |
| B — NASA data | `src.nasa_data.get_timeseries(region, variable)` | DataFrame: `date,value,unit,variable,source,region_id` |
| A — statistics | `src.divergence.analyze_region(data)` | Trends, CI, p-values, divergence status, limitations, data quality |
| C — research | `src.policy_agent.investigate_policy(analysis)` | Policies, papers, gaps, options, citations, verification status |

The UI never replaces A's statistics with numbers invented by a language
model. It shows raw p-values, original units, and the statistical
limitations provided by A. Opposing signs trigger a **candidate** flag,
not a statement of causation, ecological harm or policy failure.

D accepts a free-text region ID rather than fabricating a region catalog;
when B delivers validated region IDs, the input can become a selector.
A geographic map appears only if B provides actual `latitude`/`longitude`
or `lat`/`lon` data. Do not plot guessed coordinates.

## Frontend smoke tests

- Open the default demo, inspect the synthetic warning, both time series,
  standardized z-score comparison, candidate-only status, and limitations.
- Turn off soil moisture: screening becomes **incomplete**.
- Shorten the time window to fewer than three observations: the page
  warns and avoids an invalid analysis.
- Enter an unknown region: the page shows the retrieval error and
  never manufactures observations.
- Click the policy button: a stub report contains no verified records.
- Download CSV observations, JSON statistics, and the JSON research brief.
- If B returns different observation dates, confirm the alignment warning.

## Deployment: Streamlit Community Cloud

1. After a passing CI run and teammate review, merge `feature/frontend` into `main`.
2. In Streamlit Community Cloud, select repository
   `Cz-lov-y/NASA-Space-app-challenge-2026`, branch `main`,
   and entry point `app.py`.
3. Use Python 3.12 (recommended for the project's pinned dependency ranges).
4. Set future external-service keys in Streamlit's private secrets
   management, never in GitHub files, commits, or the example environment file.
5. On the deployed URL, perform the smoke tests above. Keep the synthetic
   warning until real QA-reviewed NASA records are integrated.

## Production/demo readiness gate

- **B:** Product IDs, official source links, spatial boundaries, QA flags,
  temporal aggregation, sample size, and units are documented.
- **A:** Statistical assumptions, uncertainty, and any significance
  thresholds are independently checked.
- **C:** Government policies and papers have original URLs, jurisdictions,
  retrieval timestamps, and explicit verification status.
- **D:** Input validation, interface integration, visual caveats, exports,
  deployment, and a coherent demo narrative are working.

Do not claim a verified environmental finding until these gates are met.

The six pilot areas are integrated into the globe as ordinary native cells, without a separate example selector. Their source observations and eligible processed cells on the first map page are screened in the browser using the same method as the details panel; the background reads use local data and do not start Earth Engine requests. Cells remain gray while they are being analyzed. Stronger-signal cells appear as clickable locations in the sidebar. The list reflects loaded and analyzed cells, not a complete worldwide inventory; recently calculated results are restored after refresh. The original pilot datasets and stored pilot analyses remain intact.

Map classifications are stored in browser local storage for up to 24 hours so they remain visible across a refresh. They are recalculated from locally available observations after loading; changed data can therefore update the color. Only results for the default 2003–2024 window are persisted. Browser storage is local to the browser and may be cleared or unavailable.

Land clicks and geographic labels use the bundled Natural Earth public-domain 1:10m country and first-level administrative boundaries. `scripts/build_frontend_geography.py` rebuilds the browser file from the Natural Earth project repository. Country coastlines are simplified to 0.005° and subdivisions to 0.02°; the boundary mask is approximate, especially near coastlines, islands and borders. Country names are used where no subdivision contains a point. This boundary data does not make unsupported soil/vegetation data available.

The NDVI time-series chart shows dashed green model estimates across gaps of at most six consecutive months flagged `no_valid_pixels`, bounded on both sides by valid NDVI. The browser fits a linear trend plus annual sine/cosine cycle to valid observed NDVI, requiring at least 18 observations across at least three years and four distinct calendar months. It adjusts the fitted seasonal curve to the bounding observations and clips estimates to the product NDVI range [-0.2, 1]. Longer, unbounded, pending-export and other missing-data gaps remain blank. The browser screening uses the same modeled values as the dashed chart, so it can classify locations with insufficient complete observed years; observations and CSV downloads remain unchanged. Provenance records the model and estimated-month count, and quality metadata retains the original missing-month counts. **The estimates may not reflect actual winter greenness, and classifications may be inaccurate.** The model assumes one stable seasonal cycle and a linear trend; snow, cloud, vegetation type, changing phenology and persistent winter gaps can violate those assumptions. Statistical p-values, confidence intervals and multiple-testing adjustments do not account for model uncertainty and can be overconfident. These results are exploratory, not calibrated probabilities or independently validated findings. A future evaluation should compare modeled values with held-out real observations and incorporate imputation uncertainty before making scientific or policy claims.
