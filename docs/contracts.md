# Integration contracts — freeze before independent development

## B → A: get_timeseries(region, variable) -> pandas.DataFrame

Required fields: `date` (ISO date), `value` (numeric), `unit`, `variable`, `source`, `region_id`. One row per regional observation. Store quality-control decisions, native spatial resolution, product version, geographic polygon/coverage and processing operations in separate provenance documentation. Avoid mixing different units or time aggregation without explicit conversion.

The scaffold supports `demo-region`, `ndvi`, and `soil_moisture` from SYNTHETIC data only.

## A → C/D: analyze_region(data) -> dict

Keys: `region`, `observation_period`, `variables`, `trend_slopes`, `confidence_intervals`, `p_values`, `data_quality`, `divergence_detected`, `limitations`. Extra keys `trends` and `divergence_status` contain detailed estimates and conservative screening status.

`divergence_detected = null` if one indicator is unavailable. `true` means **candidate opposite trend signs**, not established causal risk. All slopes are expressed **per year**, retaining their original variable units. Real results require scientific and data QA review.

## C → D: investigate_policy(analysis) -> dict

Keys: `policies[]`, `scientific_studies[]`, `potential_policy_gaps[]`, `conservation_options[]`, `citations[]`, `verification_status`. The scaffold returns empty arrays and `not_started`; it does NOT fetch government policies.

Policy findings must include jurisdiction, title, effective date/status if known, original official URL, retrieval time, evidence type, and uncertainty. Distinguish verified claims from candidates and inference. An absence of search results is NOT proof that a policy does not exist.
