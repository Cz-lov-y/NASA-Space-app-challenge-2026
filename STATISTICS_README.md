# EarthRisk statistical module

Member A's implementation of the `analyze_region(data) -> dict` integration contract.
All example observations are **synthetic**. No NASA observations have been supplied
or authenticated, and this package does not claim real-world validation.

## Install and verify

Use Python 3.10 or later. From the repository root:

```sh
python -m pip install -r requirements-statistics.txt
python -m unittest discover -s tests -v
python -m examples.demo
```

Validated locally with Python 3.12.8, NumPy 2.2.6, pandas 2.3.3, SciPy 1.17.1.
The dependency ranges describe intended compatibility; only these exact installed
versions have been tested. Tests use the standard library's `unittest`.

## Integration

```python
import json
import pandas as pd
from src.statistics import analyze_region

# Member B supplies a quality-controlled regional long table.
data = pd.read_csv("regional_monthly.csv")
analysis = analyze_region(data)
print(analysis["trend_slopes"])
print(analysis["divergence"]["category"])

# Safe for the frontend and policy agent; undefined results use None/null.
payload = json.dumps(analysis, allow_nan=False)
```

Required columns:

| Column | Meaning |
| --- | --- |
| `date` | ISO date or datetime; numeric years are rejected |
| `value` | Scaled numeric observation, or NaN/null for missing data |
| `unit` | One consistent unit per variable, such as `1` for NDVI |
| `variable` | `NDVI`, `EVI`, `soil_moisture`, or another indicator |
| `source` | Stable dataset/product/version identifier per variable |
| `region_id` | Exactly one region per call |

For monthly input, each variable must have at most one row per calendar month.
Daily, 8-day and 16-day products must first be aggregated by Member B with a
documented temporal weighting and quality policy. This module rejects duplicate
months rather than guessing how to combine composites or spatial samples.

Defaults: `frequency="monthly"`, `alpha=0.05`, `min_years=8`,
`min_months_per_year=12`, `max_missing_fraction=0.2`.
`alpha` must lie strictly between 0 and 0.5. All alpha-taking public functions,
including `detect_divergence`, reject the endpoints; `alpha=0.5` raises
`ValueError`. This narrows the earlier `(0, 1)` range and is a compatibility change.
For annual data, explicitly pass `frequency="annual"`; each row must represent a
quality-controlled annual mean. Annual dates should use `YYYY-01-01`.
For a different moisture name, use `soil_moisture_variable="RootMoist"`.
Vegetation aliases can be passed as `vegetation_variables=("MODIS_NDVI",)`.
Matching is case-insensitive; ambiguous names are rejected.

## Public functions

| Function | Purpose |
| --- | --- |
| `linear_regression(x, y, alpha=0.05)` | OLS slope, centered intercept, p-value, slope CI |
| `theil_sen(x, y, alpha=0.05)` | Robust median slope and slope CI |
| `mann_kendall(values, alpha=0.05)` | Chronological monotonic-trend test with tie correction |
| `adjust_p_values(p_values)` | Benjamini-Hochberg adjustment |
| `analyze_timeseries(data, ...)` | One date/value series with quality and sensitivity diagnostics |
| `analyze_region(data, ...)` | Contract output, aligned indicators, adjusted tests, divergence |
| `estimate_trend(data)` | Exploratory raw-observation fit with missing-value diagnostics |
| `detect_divergence(analyses, ...)` | Classify aligned per-variable analysis results |

Low-level regression functions use the units of `x`; high-level functions use
actual calendar years and return slopes in input units/year. Low-level functions
reject missing values. `mann_kendall` expects values already sorted by time.
OLS predictions are `intercept + slope * (x - time_origin)`.

`estimate_trend` excludes NaN/null and positive/negative infinity without
imputation, keeps actual elapsed times, and reports `status="ok"` when at least
three finite observations remain. Its `n_observations` is the finite raw-point
count, and its `data_quality` includes `n_raw_rows`, `valid_observations`,
`dropped_observations` and `nonfinite_fraction` (fraction of supplied rows, not
calendar slots). Empty input or fewer than three finite points returns
`status="insufficient_data"` and null estimates, replacing the earlier exception.
An empty frame must still have all six schema columns; its variable/unit are null.
Invalid dates, duplicate timestamps (even on missing-value rows), nonnumeric text,
mixed metadata and missing schema columns still raise `ValueError`.

`analyze_region` includes all agreed fields: `region`, `observation_period`,
`variables`, `trend_slopes`, `confidence_intervals`, `p_values`, `data_quality`,
`divergence_detected`, `limitations`. Detailed results are under `analysis`.
The existing `from src.divergence import analyze_region` import remains supported.
Top-level `trend_slopes`, `confidence_intervals` and `p_values` retain the existing
OLS scalar/list/scalar mappings; robust estimates and MK p-values are in `analysis`.
BH-adjusted MK values are also exposed in `adjusted_p_values`. Regional quality
fields remain available, with per-variable detail in `data_quality.by_variable`.
Within each variable's quality record, `missing_fraction` and
`expected_observations` refer to the final analysis window, with
`analyzed_valid_observations` as the coverage numerator. The separate
`raw_missing_fraction` and `raw_expected_observations` preserve input coverage;
`valid_observations` remains the raw finite count. Window-external exclusions are
kept in `raw_excluded_years`; `excluded_years` is restricted to analysis bounds.
Interior unusable years still count as coverage gaps. No usable years produces
null analysis missing fraction. See the methodology for all quality fields.
**Count fields have different units:** `data_quality.n_raw_rows` is the total
number of input rows across all variables. Within regional `trends`, each
`trends[v].n_observations` counts the annual values actually fitted for variable v.
For example, two variables with 16 complete monthly years have 384 raw rows but
16 fitted observations per variable. Standalone `estimate_trend` operates on raw
points, so its own `n_observations` counts finite raw observations.

**Schema 0.3 migration:** replace regional `data_quality.n_observations` with
`data_quality.n_raw_rows`; the old ambiguous regional key has been removed.
Callers of `estimate_trend` should check `status` for insufficient data instead
of relying on the earlier less-than-three-observations exception. The explicit
alpha range above also applies to callers migrating from the earlier interface.

The classification meaning is intentionally strengthened in schema 0.2:
`divergence_detected=True` means **Supported Signal** under the documented rules,
rather than the scaffold's sign-only candidate. It is None when required inputs
or sufficient common years are unavailable, and otherwise False for unsupported
or absent divergence. `divergence_status` uses `supported_signal`, `uncertain_signal`
or `no_detected_divergence`. The updated `docs/contracts.md` records this change.
Always display `divergence.category` and its reasons.

The synthetic flag is deliberately conservative: if any source label contains
`SYNTHETIC` (case-insensitive), the whole result has `synthetic_demo=true`, including
mixed real/synthetic inputs. This label heuristic is stated in returned
`limitations`; it does not certify provenance or prove that every row is synthetic.

The repository's bundled demo has one June observation per year. Default monthly
analysis correctly returns insufficient complete-year data. It must not silently
treat these as annual means. Use this package's complete-month synthetic demo to
exercise the full classifier; the existing UI can still import and display results.

Invalid schemas, mixed units/sources, duplicate observations and invalid dates
raise `ValueError`. Short, missing or nonoverlapping records return structured
`insufficient_data` / **Uncertain Signal** results, not fabricated statistics.
Raw MK and OLS significance must not override reliability flags.

## Files to merge

- `src/statistics.py`, `src/divergence.py`: implementation.
- `tests/test_statistics.py`: 49 deterministic tests (also discoverable by pytest).
- `docs/methodology.md`: formulas, thresholds, assumptions, data handoff.
- `docs/contracts.md`: updated A-to-C/D contract, preserving B/C interfaces.
- `examples/demo.py`: explicitly labeled synthetic demo.
- `requirements-statistics.txt`: dependencies for Member D to merge.
- `STATISTICS_README.md`: this guide.
- `src/__init__.py`: the repository's unchanged package initializer.

Copy these files into the team's repository. Keep an existing `src/__init__.py`
if it already contains team code; importing `src.statistics` still works. The
separate dependency file and guide avoid replacing the team's `requirements.txt`
and `README.md`. Review conflicts if the repository already has any of these files.
Never upload `__pycache__`, local environments, credentials or intermediate files.

See [methodology](docs/methodology.md) before interpreting results. The next
scientific validation step is to run a provenance-documented NASA export supplied
by Member B and independently compare its fitted slopes and observation coverage.
