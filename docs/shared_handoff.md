# Shared screening handoff proposal

Status: **proposed, pending B/C/D confirmation**. This document records A's
proposed interface freeze; it does not claim team agreement. The proposed
primary screening window is 2003-01-01 through 2024-12-31 inclusive, with
monthly inputs. Proposed primary variables are MODIS `ndvi` (unit `1`, product
`MOD13A3.061`) and GLDAS `soil_water_0_10cm` (unit `kg m-2`, source
`GLDAS_NOAH025_M.2.1`). The 0–100 cm total is a secondary indicator, not a
drop-in substitute; changing the indicator or adding it changes the question
and can change common-year coverage and the multiple-testing family. These
are analysis settings for agreement, not independently verified findings.

## One shared runnable example

`examples/shared_schema_example.json` is the shared example; regenerate it with
`python -m examples.shared_schema`. The command prints JSON for all three handoffs.
It generates 2003–2024 synthetic data and emits two B -> A example rows,
per-variable provenance, an actual A -> C/D wrapper result and a C -> D
shape-only empty report. **Every value is illustrative; there are no verified
NASA observations or policy findings in this example.** It does not claim B,
C or D have adopted the proposed primary indicators or schema.

## B -> A

`get_timeseries(region, variable) -> pandas.DataFrame`: one variable and one
region per call; required fields `date`, `value`, `unit`, `variable`, `source`,
`region_id`; `quality_flag` and `valid_area_fraction` are optional extra fields
which must be preserved when present. `date` represents a month, missing values
are null/NaN, not finite fill sentinels, and inputs are scaled physical values.
One unique row per variable per calendar month; a missing month is not zero.
Per-series `attrs['metadata']` and a durable sidecar must document spatial
coverage, time range, frequency, dataset version, QA and missing-value rules.
Capture metadata before concatenation. B's current reader uses the lowercase
catalog names above; confirm aliases with B rather than assuming `NDVI` works
at the B reader boundary. A's indicator matching is case-insensitive.

## A -> C and D

For `whole_earth` source aggregates, filter the agreed period and select the two
indicators, then call `analyze_global_exploratory(...,
soil_moisture_variable='soil_water_0_10cm')`. This is the global output schema
`global-exploratory-0.2`: `scope=global_exploratory`, `region`,
`observation_period`, `variables`, descriptive `analysis`, `data_quality`,
`global_exploratory`, `limitations`, and `divergence_status=not_assessed`.
`divergence_detected` is null. There are no inference fields or Green Mirage
classification. C and D must not infer co-located divergence from opposing global
slopes. The wrapper does not apply quality flags or establish source QA / spatial
overlap. Retain the input provenance separately. Review each source's coverage
before use. `analyze_region` remains the distinct regional interface; it must not
be used to bypass the global boundary. See `docs/global_exploratory.md`.

## C -> D

The example illustrates `investigate_policy(analysis) -> dict` with `region`,
`policies`, `scientific_studies`, `potential_policy_gaps`, `conservation_options`,
`citations`, `verification_status`, `candidate_sources` and `limitations`.
It is a shape example, not a call or a verified research report. Empty search
results do not establish absence of policy. C must propagate global scope and
limitations to any generated explanation and verify that reports do not infer
Green Mirage. D must preserve scope, null status, sources and limitations in UI
and exports; do not convert null to false or show an unsupported classification.

## Confirmation and unresolved integration

- B: **pending** — confirm selected products, names, metadata, QA rules and
  2003–2024 window. Global inputs are preliminary; their valid footprints differ.
- C: **pending** — confirm global wrapper consumption, policy report fields and
  protection against unsupported divergence claims in generated text.
- D: **pending** — current frontend selects `soil_moisture`, calls
  `analyze_region`, and reads legacy inferential fields. It needs an explicit
  global path using `soil_water_0_10cm` and this wrapper before deployment.
- A: proposed the primary indicators and period; review by the team is required.

Record actual B/C/D responses or an agreed team decision before changing this
status to frozen. Do not present this proposal as team-confirmed until then.
