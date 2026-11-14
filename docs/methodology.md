# EarthRisk statistical methodology

## Scope and interpretation

This deterministic v0 module estimates trends and screens for greenness increase
accompanied by soil-moisture decrease. It does not measure ecological damage,
establish causality, fetch data, or verify NASA provenance. Tests and the runnable
demo use synthetic observations. The thresholds below are transparent engineering
defaults, not a validated ecological risk model.

## Input and annual aggregation

Each call represents one region. Timestamps are interpreted in UTC. Duplicate
monthly or annual periods are rejected, including multiple pixels or composite
observations in a period. Input must have one stable source and unit per variable.
Missing numeric values and infinities are treated as missing; nonnumeric text and
invalid timestamps raise errors. Finite fill codes such as -9999 are **not**
automatically recognized: replace product-specific fill codes upstream.

Monthly observations are converted into equal-weight calendar-year means. The
default requires 12 valid months per year, reducing seasonal composition bias.
This estimates a mean of monthly values, not a day-weighted yearly mean or annual
precipitation total. Such alternative quantities must be computed upstream and
provided as annual data with appropriate units. A relaxed month threshold is
available but retaining incomplete years blocks the reliable classification.
Annual aggregation discards subannual information and is not a seasonal MK test.

Two coverage measures distinguish input history from usable analysis coverage:

- `raw_missing_fraction` is `1 - finite input observations / raw_expected_observations`
  between the first and last supplied years, including partial endpoint years.
  `valid_observations` retains its legacy meaning: finite observations in the raw input.
- `missing_fraction` is `1 - analyzed_valid_observations / expected_observations`,
  recomputed after annual filtering and common-year alignment. Its denominator
  covers calendar slots between the first and last final analyzed years. Its
  numerator counts only finite source observations contributing to retained
  annual values. Boundary years outside that window do not affect reliability.
  Interior excluded years remain full gaps, even if they contained some raw
  observations: those observations did not contribute to the fitted series.
  This is usable-data coverage, not just raw physical missingness. With no final
  years, `missing_fraction` and `analysis_period` are null and expected count is 0;
  insufficient-data handling applies instead of a missingness threshold.

Default maximum analysis missing fraction is 0.2; the raw fraction is audit-only.
Neither measure can discover missing endpoint years outside the supplied record.
`raw_excluded_years` preserves all years rejected by the annual threshold;
`excluded_years` includes only those inside the final analysis bounds.
`raw_incomplete_retained_years` preserves incomplete years passing a relaxed
threshold before alignment; `incomplete_retained_years` lists only those actually
analyzed and is the list used by the seasonal-coverage check.
`missing_analysis_years` includes all interior gaps, including alignment losses.
`available_years` and `alignment_excluded_years` describe the prealignment selection
history and are not directly used as reliability penalties.

For example, one month in 2010 followed by complete years 2011-2020 yields raw
missing fraction 11/132 but analysis missing fraction 0. With a 0.05 threshold,
that discarded boundary year does not block reliability. An incomplete 2015
between complete 2010 and 2020 endpoints still counts as an interior analysis gap.

High-level analysis supports up to 500 calendar years; pairwise Sen calculations
and leave-one-year-out checks are intended for regional MVP workloads.

All variables in a region are analyzed on the intersection of their valid annual
years. This avoids comparing different historical periods. Interior gaps remain
gaps: slopes use elapsed calendar years, never compressed row numbers. Adding an
optional precipitation indicator can shorten the shared record. To avoid that,
analyze the vegetation/moisture pair separately from contextual indicators.

At least eight common valid years are required by default. A minimum of five may
be configured, but fewer than eight is flagged as unreliable because the MK normal
approximation is fragile. Eight years is not a guarantee of scientific adequacy.

## Trend estimators and intervals

The default significance level is `alpha=0.05`. `alpha` must lie strictly between
0 and 0.5; the same validation applies to the divergence detector. This is narrower
than the earlier `(0, 1)` API range: `alpha=0.5` now raises `ValueError`.
Supported confidence levels `1-alpha` therefore lie strictly between 0.5 and 1.

OLS fits `y = intercept + slope * (year - first_year)`. Its two-sided slope test
and confidence interval use residual degrees of freedom `n - 2`; the interval is
`slope +/- t(1 - alpha/2, n - 2) * slope_standard_error`. This inference assumes
independent, homoscedastic errors and, for exact finite-sample inference, normally
distributed errors. Constant observations return slope 0, CI [0, 0], p=1 and R2=0
as a documented convention; R2 is not informative for a constant response.

OLS, Theil-Sen and MK use the same numerical-constant rule:
`range(y) <= 100 * float64_epsilon * max(max(abs(y)), float64_tiny)`.
Such series return zero slopes, zero-width slope intervals and trend-test p=1.
MK treats the entire near-constant series as one tie group; other series retain
exact-value tie groups. Residual screening uses the same relative tolerance.
There is no unit-sized absolute floor, so rescaling small-valued observations
does not by itself erase a trend. This rule handles floating-point noise, not
practical ecological significance; meaningful effect-size thresholds must be
specified separately for each indicator and unit.

Theil-Sen takes the median of all pairwise slopes, with SciPy's separate-intercept
convention. SciPy supplies the slope confidence limits. Default intervals are
95% marginal intervals. They are not prediction intervals, intercept intervals,
simultaneous intervals or damage probabilities.

References: [SciPy linregress](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.linregress.html)
and [SciPy theilslopes](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.theilslopes.html).

## Mann-Kendall and multiple comparisons

For chronologically ordered observations:

```text
S = sum(sign(y[j] - y[i])) for all i < j
Var(S) = [n(n-1)(2n+5) - sum(t(t-1)(2t+5))] / 18
```

Each `t` is a tied-value group size. With nonzero variance, use
`Z = (S - sign(S))/sqrt(Var(S))`, including continuity correction.
The two-sided p-value is `2 * NormalSurvival(abs(Z))`. With zero variance use
Z=0 and p=1. `tau_a = S / (n(n-1)/2)` is explicitly tau-a, not tie-adjusted tau-b.
This is an asymptotic test, not an exact small-sample permutation test.

`analyze_region` applies Benjamini-Hochberg to the family of MK tests for all
indicators in that call. Sorted p-values are multiplied by `m/rank`, followed by
a reverse cumulative minimum and clipping at 1. Missing tests count as p=1 for
family size, while their returned adjusted values remain null. Significance uses
adjusted p < alpha. OLS p-values remain descriptive and unadjusted. The adjustment
does not control exploratory testing across regions, repeated time windows or
other calls, and BH guarantees require independence or suitable positive dependence.

## Serial dependence and sensitivity

For nonconstant OLS residuals, compute lag-one correlation only between observations
in adjacent calendar years. With at least five usable pairs and nonzero variance,
flag `abs(rho) > 1.96/sqrt(number_of_pairs)`. Otherwise label the screen
not assessable and block reliable classification. Zero residual variability is
reported separately. The threshold is an approximate diagnostic, not a calibrated
hypothesis test after detrending, and it can miss dependence, especially in short
records. It does not correct the MK p-value or either estimator's interval.

Every observed year is omitted once and the Theil-Sen slope is recomputed. A sign
change or zero crossing makes direction unstable. OLS and Sen slope signs must
also agree. These checks do not quantify significance stability, long-memory
dependence, nonlinear change, alternate study windows or spatial aggregation.

USGS discusses how seasonality and serial dependence complicate trend inference:
[Hirsch and Slack, 1984](https://pubs.usgs.gov/publication/70012890).
A subsequent production version should evaluate appropriate seasonal tests,
serial-dependence corrections or block resampling with an expert-reviewed design.

## Green Mirage categories

For each configured vegetation indicator and the moisture indicator:

Variable lookup is case-insensitive using `casefold()`, while reported names
retain their original spelling. Both regional analysis and direct detector
calls reject keys that collide under case folding. A missing required indicator
returns Uncertain Signal, never No Detected Divergence.

- **Supported Signal**: both analyses have enough common years; vegetation Sen
  slope > 0 and moisture Sen slope < 0; vegetation lower CI > 0 and moisture upper
  CI < 0; both BH-adjusted MK p-values < alpha; both pass missingness, seasonal
  coverage, autocorrelation and sensitivity checks.
- **Uncertain Signal**: required data are missing, quality or robustness checks
  fail, or opposing point estimates lack the necessary statistical support.
- **No Detected Divergence**: sufficient, reliable data do not show the required
  opposing directions. This is not evidence that environmental risk is absent.

If NDVI and EVI pairs yield different categories, the regional category is
Uncertain Signal and individual pair results remain available. A Supported Signal
is a screening result conditional on assumptions, not confirmed ecosystem damage.

## Data handoff for the supplied resources

The source-label heuristic marks the entire analysis `synthetic_demo=true` if
any source contains `SYNTHETIC`, case-insensitively. A mixture of real and synthetic
indicators is therefore flagged as a whole. Returned limitations state this rule;
the heuristic cannot independently establish whether individual rows are synthetic.

The supplied resource list contains portals, data collections and explanatory
articles; it does not specify a region, product/version, variable layer or date
range. Member B must select and document those before a real-data case is possible.

Giovanni's official guide documents time-series CSV downloads. Export the chosen
regional series, remove the metadata preamble as appropriate to the actual file,
and map its date/value columns to the shared schema. Do not hardcode a universal
CSV header offset. Preserve the export and query metadata alongside the analysis.
See the [Giovanni guide](https://giovanni.gsfc.nasa.gov/giovanni/doc/UsersManualworkingdocument.docx.html).

For AppEEARS exports, inspect the selected product's quality information, scaling
and units before aggregation. NASA's MOD13Q1 support response notes that AppEEARS
CSV output already incorporates scaling; do not apply it a second time blindly.
See [NASA Earthdata support](https://forum.earthdata.nasa.gov/viewtopic.php?t=5682)
and [AppEEARS](https://appeears.earthdatacloud.nasa.gov/).

For every source, record product/version, variable/layer, spatial bounds or polygon,
spatial weighting, soil layer/depth where applicable, original temporal resolution,
quality-mask rules, scale/offset state, fill values, units, retrieval date and export
identifier. Align the actual sampled area and temporal support across indicators;
matching `region_id` strings does not validate physical comparability. Store these
details with the data; the statistical module returns the supplied source label,
not an independent provenance certification. No account password belongs in code.

The remaining resources can inform later indicator selection or interpretation.
No adapters for CDO, RCM, SWOT, Geo.ca or raw SAR imagery are included in this
statistics-only deliverable. Their raw files are not assumed to fit this schema.

## Implementation boundaries and counts

`_analyze` coordinates four internal helpers: `_quality_gate` recomputes coverage
and checks data sufficiency; `_trend_estimates` computes OLS, Sen and MK results;
`_sensitivity` performs leave-one-year-out and method-agreement checks;
`_reliability` combines failure reasons without mutating its inputs. Residual
dependence screening remains in `_autocorrelation`. These are internal helpers,
not public schema contracts. This refactor retains the statistical rules above.

Regional `data_quality.n_raw_rows` counts all supplied rows across variables.
Regional `trends[v].n_observations` counts fitted annual values for that variable.
Schema 0.3 replaces the ambiguous regional `data_quality.n_observations` name.

Standalone `estimate_trend` is different: it fits raw finite observations with
actual elapsed times, measured in 365.25-day years. It drops NaN/null/infinities,
reports the dropped count and fraction of supplied rows, and does not impute or
compress time gaps. Its `n_observations` is the number of finite raw points.
Below three finite points, including empty input, it returns insufficient-data
status and null estimates. Invalid dates, duplicate timestamps, nonnumeric text
and malformed metadata still raise. Its p-values remain exploratory without the
annual quality gates, seasonal treatment or multiple-comparison adjustment.
