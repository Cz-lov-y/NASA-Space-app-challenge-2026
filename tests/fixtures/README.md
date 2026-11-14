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
