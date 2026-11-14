# Statistical methodology (Member A)

Current code computes ordinary least squares slopes (per year), nominal 95% t-based confidence intervals, Theil–Sen slopes/intervals, and Kendall rank correlation as a basic monotonic-trend screen. With evenly collected independent observations and suitable assumptions these can be useful exploratory summaries.

**Incomplete scientific work:** Test seasonality, serial dependence/autocorrelation, outliers, nonstationarity, missingness mechanisms, region selection bias, pixel-to-region aggregation uncertainty and multiplicity. Confirm Mann–Kendall assumptions and apply an appropriate correction before interpreting statistical significance. Use aligned and comparable MODIS and GLDAS periods/coverage.

The current Green Mirage rule is only `NDVI slope > 0 AND soil moisture slope < 0`. This is a **candidate divergence flag**, not an assessment of risk magnitude, policy failure, desertification, or causation. Define reproducible scientific thresholds and falsification checks before making stronger claims.
