# GLDAS regression fixture

`gldas_central_us_monthly.csv` is the processed regional surface soil-water
time series provided by Member B at repository commit
`1ea71d41adedd669c44fdcd21f3344f376e15339`, copied from
`data/processed/gldas_integration/monthly_timeseries.csv`. It is model-derived
NASA GLDAS data, not synthetic observations. See the original commit's
`data/processed/gldas_integration/metadata.md` and `source_manifest.json` for
regional coverage, processing, quality and source checksums.

This fixture contains monthly observations from 2003 through 2024 for
`central_us_sample`, variable `soil_water_0_10cm`, unit `kg m-2`. Three raw
months (2003-01, 2014-07, 2024-12) were independently recomputed; the entire
NetCDF-to-CSV extraction was not independently validated. Regression tests
protect numerical behavior, not the scientific correctness of the source data.

The CSV `date` field is a `YYYY-MM-DD` string. The regression test parses it
once with `pd.read_csv(..., parse_dates=["date"])`; the statistics preparation
step also normalizes dates with `pd.to_datetime` and accepts parsed datetimes.

The fixture includes B's extra per-month `quality_flag` and
`valid_area_fraction` columns. They originate from B's exported time series;
their counts and coverage summaries are recorded in B's quality report. These
columns are not among the six required `analyze_region` input fields and the
statistics module neither interprets nor filters them. The regression test
asserts the fixture's flags are `good` before analysis. Callers must review and
apply an appropriate QA policy to real input before calling the statistics API.
