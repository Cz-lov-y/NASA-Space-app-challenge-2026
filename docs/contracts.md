# Integration contracts — freeze before independent development

## B → A: get_timeseries(region, variable) -> pandas.DataFrame

Required fields: `date` (ISO date), `value` (numeric), `unit`, `variable`, `source`, `region_id`. One row per regional observation. Store quality-control decisions, native spatial resolution, product version, geographic polygon/coverage and processing operations in separate provenance documentation. Avoid mixing different units or time aggregation without explicit conversion.

The scaffold supports `demo-region`, `ndvi`, and `soil_moisture` from SYNTHETIC data only.

## A → C/D: analyze_region(data) -> dict

Import from `src.divergence` (existing entry point) or `src.statistics`.
Schema version: 0.3. Defaults require monthly data and eight complete common years.
For quality-controlled annual means, pass `frequency="annual"` explicitly.
`alpha` must lie strictly between 0 and 0.5 for all alpha-taking statistical
functions and `detect_divergence`. Both endpoints, including `alpha=0.5`, raise
`ValueError`; callers relying on the earlier `(0, 1)` range must migrate.

Required output keys remain: `region`, `observation_period`, `variables`,
`trend_slopes`, `confidence_intervals`, `p_values`, `data_quality`,
`divergence_detected`, `limitations`.

The existing scalar OLS mappings remain: variable -> slope in `trend_slopes`,
variable -> two-element OLS slope interval in `confidence_intervals`, and variable
-> raw OLS p-value in `p_values`. Detailed OLS, Theil-Sen, Mann-Kendall, sensitivity
and reliability results are in `analysis[variable]`. Adjusted MK p-values are in
`adjusted_p_values`. The `trends` mapping retains flat estimate fields; its
`n_observations` counts analyzed annual values. Regional `data_quality.n_raw_rows`
counts all original input rows across indicators; schema 0.3 removes the old
regional `data_quality.n_observations` key. Update frontend consumers accordingly.
Other regional quality summary fields remain, with annual coverage detail in
`data_quality.by_variable`.

Per-variable `missing_fraction` is usable coverage within the final analyzed
calendar bounds, recomputed after annual filtering and alignment. Its numerator
is `analyzed_valid_observations` and denominator is `expected_observations`.
Interior excluded years count as gaps. Raw coverage is separately preserved in
`raw_missing_fraction`, `raw_expected_observations`, and the legacy raw finite
count `valid_observations`. `raw_excluded_years` preserves all annual-filter
exclusions; `excluded_years` is restricted to final analysis bounds.
`incomplete_retained_years` includes only incomplete years actually analyzed.
An empty analysis window has null `missing_fraction` and zero expected count.

Classification is intentionally stronger than the initial sign-only scaffold:

- `divergence_detected = true`: Supported Signal under the documented quality,
  direction, confidence-interval, robustness and adjusted-significance checks.
- `divergence_detected = null`: an indicator or sufficient common data is unavailable.
- `divergence_detected = false`: other uncertain or absent divergence.

Always display `divergence.category` and reasons. `divergence_status` now uses
`supported_signal`, `uncertain_signal`, or `no_detected_divergence`.
A Supported Signal is not established causal risk or verified ecological damage.
Source labels do not certify provenance; `qa_reviewed` remains false.
Synthetic inputs are flagged in `data_quality.synthetic_demo` and limitations.
If any source label contains `SYNTHETIC` (case-insensitive), the entire result is
flagged, including mixed real/synthetic inputs. This is a conservative label
heuristic and is explicitly described in returned limitations.
All high-level slopes are per calendar year in original variable units.

`estimate_trend(data)` remains an exploratory API; it does not run seasonal
aggregation or reliability classification. It excludes nonfinite values without
imputation and requires at least three finite raw observations for `status="ok"`.
Otherwise it returns `status="insufficient_data"` and null estimates instead of
raising for insufficient observations. Empty inputs must retain the six schema
columns. The standalone function's `n_observations` counts finite raw points;
`data_quality` reports `n_raw_rows`, `valid_observations`, `dropped_observations`
and `nonfinite_fraction` over supplied rows. Calendar gaps are not compressed.
Malformed schema/metadata, dates, duplicate timestamps and nonnumeric text still
raise `ValueError`, even on rows whose value would otherwise be excluded.
Its slope unit retains the scaffold's 365.25-day year convention. Legacy
`kendall_tau` now explicitly reports tau-a; `kendall_p_value` uses the documented
asymptotic, continuity-corrected MK test, not the scaffold's scipy Kendall test.
Interval fields ending in `95ci` are legacy names; with nondefault alpha, read
`analysis[variable][method].confidence_level` for the actual confidence level.

The current one-June-observation-per-year demo cannot support complete-year
monthly analysis. Use `python -m examples.demo` for a complete synthetic record.
See `docs/methodology.md` and `STATISTICS_README.md` for assumptions and usage.

## C → D: investigate_policy(analysis) -> dict

Keys: `policies[]`, `scientific_studies[]`, `potential_policy_gaps[]`, `conservation_options[]`, `citations[]`, `verification_status`. The scaffold returns empty arrays and `not_started`; it does NOT fetch government policies.

Policy findings must include jurisdiction, title, effective date/status if known, original official URL, retrieval time, evidence type, and uncertainty. Distinguish verified claims from candidates and inference. An absence of search results is NOT proof that a policy does not exist.

