# Global exploratory analysis interface

This wrapper presents descriptive trends for whole-Earth aggregate time series.
It does not assess Green Mirage, a colocated vegetation–soil divergence, damage
or causation. Global NDVI and soil-water series can reflect different and
time-varying geographic footprints. A common calendar period does not establish
common observed land or spatial overlap.

## Call

```python
import pandas as pd
from src.global_exploratory import analyze_global_exploratory

data = pd.read_csv("data/processed/global_combined/monthly_timeseries.csv",
                   dtype={"unit": str})
data = data.loc[
    data["date"].between("2003-01-01", "2024-12-01")
    & data["variable"].isin(["ndvi", "soil_water_0_10cm"])
].copy()

# Review quality_flag, spatial provenance and the intended QA policy first.
result = analyze_global_exploratory(data)
assert result["scope"] == "global_exploratory"
assert result["divergence_status"] == "not_assessed"
```

`dtype={"unit": str}` preserves dimensionless `1` as a string. Every row must
have `region_id="whole_earth"` and the six usual columns `date`, `value`, `unit`,
`variable`, `source`, `region_id`. Supply a single selected soil variable;
the default is `soil_water_0_10cm`. Set `soil_moisture_variable` explicitly for
another name such as `soil_water_0_100cm`. Single-variable inputs and missing
coverage columns are accepted, but never produce a divergence assessment.
The default monthly aggregation and statistical settings are inherited from
`analyze_region`; see `docs/methodology.md`. All variables passed to a call
are aligned to common valid years, and all their MK tests enter the same BH
family. Passing both soil layers reduces the common period if coverage differs
and changes the multiple-testing family. Select indicators intentionally.

## Output and UI / agent rules

The underlying regional engine runs unchanged for per-variable trend estimates,
confidence intervals, p-values, statistical reliability, data quality and
sensitivity. Its pairwise divergence result is discarded; it is not embedded
elsewhere in the output. The wrapper always returns:

```text
scope = "global_exploratory"
divergence_detected = null
divergence_status = "not_assessed"
divergence.category = "Not assessed"
global_exploratory.green_mirage_assessed = false
global_exploratory.spatial_overlap = "not_established"
```

These values remain fixed even if the underlying unwrapped detector would return
Supported Signal or No Detected Divergence. UI and agent code must display
"Global exploratory trends; Green Mirage not assessed" and communicate the
returned limitations. Do not translate `null` into `false`, label a signal
confirmed, or infer same-place changes from global averages. Existing regional
`analyze_region` callers and classifications are unchanged.

`global_exploratory.coverage_by_variable` reports input row and finite-value
counts, counts of supplied `quality_flag` values, and min/max/mean of supplied
`valid_area_fraction`. The summaries cover **all input rows before annual
filtering and alignment**; they are not a common-footprint calculation. Missing
flag columns or coverage fields are reported as unavailable, never inferred as
good or complete. A missing coverage entry is allowed; nonnumeric or out-of-range
fractions fail explicitly. Coverage values are caller-supplied and their
denominator is not automatically verified.

**QA flags are not applied or interpreted.** In particular,
`coverage_review_required`, `low_coverage` and other flags do not trigger filtering
or change statistical reliability. The caller must review provenance and apply
and document a policy upstream, without silently marking data validated. The
wrapper sets `quality_flags_applied=false` and records this limitation. A
per-variable `reliable=true` only means the engine's statistical screening passed;
it does not establish valid source QA, spatial overlap or ecological significance.
Retain source metadata and any QA decisions separately; `DataFrame.attrs` may be
lost on concatenation and is not verified by this interface.

## Data validation and remaining work

The wrapper is an interpretation boundary, not a spatial processing algorithm.
B's global source reports separate NDVI and GLDAS valid-area fractions, not their
intersection; its global observations carry `coverage_review_required`. Review
space/time coverage and native QA, independently verify source aggregation, and
derive comparable matched-footprint time series before attempting any regional
divergence assessment. A common-mask analysis requires suitable gridded data and
an explicitly reviewed design; this wrapper never assumes it exists.
