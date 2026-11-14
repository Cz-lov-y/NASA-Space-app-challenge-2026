# Member A: regional screening implementation and handoff

## Delivered

`src.regional_statistics.build_regional_screening(monthly, catalog)` produces one
record for every catalog cell. `scripts/build_regional_screening.py` writes the
artifact used by the controller and frontend. The existing `analyze_region` API
and its within-region responses remain unchanged.

The analysis period is frozen at January 2003–December 2024. The primary pair is
`ndvi` (unit `1`) and `soil_water_0_100cm` (unit `kg m-2`). Surface soil water does
not enter this screening family. Annual values require 12 valid monthly values;
no observations are interpolated. At least eight common complete years are
required. Source data remain unchanged; analysis copies exclude rows explicitly
flagged `low_coverage`, `negative_value`, `missing`, `invalid`, `qa_rejected`,
`no_valid_data` or `no_valid_pixels`. `coverage_review_required` remains visible
and does not become a scientific approval.

## Shared artifact contract

Input catalog: `data/processed/regional/catalog.json`, a GeoJSON FeatureCollection.
The initial geometric fallback is `data/regions/grid_10deg.geojson`. Each feature
has a stable string `properties.region_id`; geometry, bbox, centroid and other
properties pass through to the output. Input observations:
`data/processed/regional/monthly_timeseries.csv`, with the existing six required
columns plus B's optional quality/coverage fields.

Output: `data/processed/regional/screening.json`.

```json
{
  "schema_version": "regional-screening-1",
  "dataset_version": "input-content-sha256",
  "observation_period": {"start": "2003-01-01", "end": "2024-12-31"},
  "primary_variables": ["ndvi", "soil_water_0_100cm"],
  "multiple_testing": {"method": "benjamini_hochberg", "family_size": 0},
  "regions": [
    {
      "region_id": "grid_r00_c00",
      "geometry": null,
      "bbox": [-180, -90, -170, -80],
      "centroid": [-175, -85],
      "properties": {},
      "status": "pending",
      "analysis": null,
      "available_indicator_analysis": null,
      "screening": {
        "category": null,
        "classification": "pending",
        "adjusted_p_values": {},
        "reasons": ["missing_primary_variable:ndvi"],
        "provisional": true,
        "qa_reviewed": false
      }
    }
  ]
}
```

This abbreviated example illustrates the schema, not real measurements or actual
support at that location. Actual records retain supplied geometry and properties.

| Status | Meaning |
| --- | --- |
| `pending` | A primary series has not been supplied. GLDAS-only cells remain pending while regional MODIS exports run. |
| `unsupported` | Catalog explicitly reports unsupported product coverage, including `unsupported_gldas`. |
| `insufficient` | Both primary series exist but have fewer than eight common complete years. |
| `eligible` | Both primary trend tests could be estimated; inspect screening classification and reliability reasons. |

Eligible classifications are `supported_signal`, `uncertain_signal` and
`no_detected_divergence`. An eligible cell need not pass robustness checks.
Unsupported and pending cells must not receive environmental classifications.

`available_indicator_analysis` provides a separate schema-0.3 diagnostic when a
primary indicator is missing but another has observations. Current GLDAS-only
cells carry the original `analyze_region` result for `soil_water_0_100cm` here:
actual soil trends, uncertainty, annual coverage and reliability are available
before NDVI arrives. Paired `analysis` remains null, map screening remains
`pending`, and these standalone tests never enter the paired worldwide family.
Their p-values are exploratory across cells. Do not use their single-indicator
Uncertain Signal category as a paired map classification. Unsupported cells and
complete paired records carry null in this field. Unreceived MODIS placeholder
rows (`pending_export` and all missing values) also preserve this pending state;
actual exports with no valid pixels instead produce insufficient paired analysis.

`analysis` contains the original schema-0.3 response. Its adjusted p-values cover
indicators within that one regional call. The separate `screening` object uses
worldwide-adjusted p-values and is the appropriate source for the map's category.
Do not substitute one adjustment for the other when describing significance.

## Worldwide adjustment and limits

The declared family includes both finite primary-indicator Mann–Kendall tests
from every eligible region in the supplied catalog. Inclusion does not depend on
slope direction, initial significance or reliability. All cells without sufficient
paired data are listed but do not supply an estimated test. When more regional
MODIS exports arrive, rerun the entire batch: family size and prior map categories
can change. A partial export is a provisional family, not a completed worldwide
screening.

The existing detector is applied to a copy of the detailed analyses with these
worldwide p-values. Directional Theil–Sen intervals, matched years, reliability,
leave-one-year-out stability, estimator agreement and autocorrelation screening
remain required for Supported Signal. Confidence intervals remain marginal.
BH assumes independence or suitable positive dependence; the spatial dependence
of these cells has not been validated. The autocorrelation diagnostic remains a
screen rather than a correction. All outputs explicitly retain `qa_reviewed=false`.

Neither a Supported Signal nor an AI policy brief establishes ecological damage,
causation or policy failure. Different MODIS/GLDAS valid footprints still require
B/A scientific review. The batch never assigns whole-Earth means to local cells.

## Run and validate

```bash
.venv/bin/python scripts/build_regional_screening.py
.venv/bin/python -m pytest -q tests/test_regional_statistics.py tests/test_statistics.py
```

When the default monthly file is absent, the CLI can still generate a pending
catalog artifact. It requires an existing catalog. No credentials or network are
used by these steps.

Ten focused tests passed during implementation (60 tests and 66 subtests passed
when run with the existing statistics suite). They verify known synthetic
slopes independently, period freezing, family adjustment, unchanged regional
responses, untouched inputs, geometry, missing months, quality exclusions,
unsupported/pending/insufficient states, standalone soil diagnostics, unreceived
export placeholders, strict JSON and malformed inputs. The
generated test data are explicitly marked `SYNTHETIC_TEST_ONLY`.

## Remaining member work and dependencies

1. **B → A:** supply the regional MODIS exports. Present whole-Earth MODIS means
   cannot replace regional measurements. Run the batch after each accepted import.
2. **A/controller:** inspect coverage/completeness and reasons in the rebuilt
   artifact; retain a record of family size and data version for any demonstration.
3. **D (human team):** read regional `screening.classification`, expose provisional
   and QA status, and retain `analysis` for the numerical panel and scientific audit.
4. **A/B scientific follow-up:** independently review regional MODIS pixel QA and
   geographic overlap before changing any source-review status. Review dependence
   assumptions and whether a common spatial footprint is needed.

No human decision blocks the current provisional backend. A scientifically
reviewed result requires team agreement on footprint comparability and statistical
limitations. These are not automatically approved by the implementation tests.
