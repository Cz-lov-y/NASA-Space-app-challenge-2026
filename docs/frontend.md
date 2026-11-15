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

The globe no longer presents the six pilot areas as examples or uses their precomputed classifications for map colors. A selected native cell is analyzed in the browser using the same logic as its details panel. Previously processed cells on the first map page appear gray until explored; a session's stronger-signal cells appear as clickable locations in the side list. This session list is not a complete inventory of all screened cells and is reset on refresh. Existing pilot datasets remain available to the backend and are not deleted. Source observations from a prepared area can still be loaded, but their stored pilot screening result is not used to color the map.
