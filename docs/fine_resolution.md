# Native-resolution regional analysis

The current finest defensible support for a paired MODIS–GLDAS analysis is the
native **0.25° × 0.25° GLDAS cell**. The earlier 10° regional aggregation remains
a legacy overview; it does not limit the new geometry or replace finer inputs.
GLDAS-2.1 Noah is a land-surface-model product, so native grid spacing should not
be described as verified ecological detail or direct soil measurements. NASA
lists GLDAS spatial resolutions in its [dataset specifications](https://ldas.gsfc.nasa.gov/gldas/dataset)
and describes the model's soil layers in its [GLDAS specifications](https://ldas.gsfc.nasa.gov/gldas/specifications).

Using the pipeline's spherical radius, 0.25° corresponds to approximately 27.8 km
north–south. East–west width is approximately `27.8 × cos(latitude)` km and cell
areas vary with latitude. These are geometric calculations, not a claim that
model uncertainty or effective information resolution is uniform at that scale.

MOD13A3.061 supplies monthly vegetation indices at approximately 1 km; see the
[official Earth Engine product catalog](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13A3).
Standalone MODIS observations can therefore support finer vegetation-only views.
A paired result must aggregate MODIS onto the actual GLDAS cell support. Repeating
or interpolating one GLDAS value into smaller vegetation pixels would not create
independent fine-scale soil information. Product masks, valid areas and source QA
remain part of the scientific assessment even after the grid boundaries match.

## Grid definition and boundary rules

`src/fine_grid.py` implements a lazy, deterministic GLDAS lattice:

| Property | Value |
| --- | --- |
| CRS | EPSG:4326, coordinates `[longitude, latitude]` |
| Geometric extent | `[-180, -60, 180, 90]` |
| Grid spacing | 0.25° in both directions |
| Shape | 600 rows × 1,440 columns |
| Geometric cell count | 864,000; land/data availability is evaluated separately |
| Row origin/direction | Row 0 starts at −60°, increasing northward |
| Column origin/direction | Column 0 starts at −180°, increasing eastward |
| Stable ID | `gldas025_r{row:03d}_c{col:04d}` |
| First center | `[-179.875, -59.875]` |
| Last center | `[179.875, 89.875]` |

Cell boundaries are calculated from integer indices. Exact interior edges belong
to the cell to their north/east for point lookup. Longitude +180° is canonicalized
to −180°, so both map to column 0. The north outer boundary +90° maps to the final
row; longitude at the actual pole is geometrically arbitrary. The South Pole and
coordinates south of −60° fall outside this product lattice. These lookup rules
do not claim that polar or ocean cells contain valid source data.

Bounding boxes use `[west, south, east, north]`. A box with `west > east` crosses
the antimeridian. Iteration selects native cells with positive-area intersection;
if a request is not aligned to the grid, cells retain their original full support.
Touching aligned tiles share edges without duplicating cells. An invalid or
zero-width box is rejected rather than interpreted as a whole-world request.

```python
from src.fine_grid import (
    build_tile_catalog, cell_bbox, grid_definition,
    index_for_coordinate, iter_cells, parse_cell_id,
)

row, col = index_for_coordinate(-97.875, 37.125)  # (388, 328)
assert parse_cell_id('gldas025_r388_c0328') == (row, col)
assert cell_bbox(row, col) == [-98, 37, -97.75, 37.25]
pilot = build_tile_catalog([-98, 37, -97, 38])  # 16 geometric features
lattice = grid_definition()                    # small metadata dictionary
cells = iter_cells()                          # lazy iterator, not a global JSON
```

Catalog materialization defaults to a limit of 4,096 cells. A full 864,000-feature
request is rejected by `build_tile_catalog`; use bounded tiles or the iterator.
The module never reads observations or silently declares a cell supported.
Initial feature status is `availability_not_checked`, with no variables or inferred
jurisdictions. B's extraction supplies actual product availability and provenance.

## First real tile and data handoff

The initial 1° tile is `[-98, 37, -97, 38]`, with 16 native cells: rows 388–391,
columns 328–331. Its tile identifier is `central_us_1deg`; current output directory
is `data/processed/fine/central_us/`. This small real tile proves the native
processing path. Its existence does not establish completed global fine coverage.

B extracts each source cell directly from the existing monthly GLDAS files,
checking the source coordinate orientation before indexing. Source row order must
be verified against latitude values; the grid's south-to-north convention must not
be assumed for an arbitrary file. Preserve native `kg m-2` storage units, fill
values and missing months. The 0–100 cm series sums the three original model layers
only where all are valid. Native geometry covers all 864,000 possible cells while
valid source masks determine usable cells per month and variable.

Expected local handoff files are `catalog.json`, `monthly_timeseries.csv`,
`metadata.json` and `source_manifest.json`. The required period is January
2003–December 2024: 264 monthly rows per cell/variable, including any missing rows.
Both soil depths yield 8,448 rows for all 16 cells when indexed exhaustively.
Regional NDVI remains pending until an export for those same 16 native boundaries
arrives. Whole-Earth means and old 10° regional means cannot supply those values.

Use the existing `build_regional_screening` and transport APIs on the fine tile's
actual CSV and catalog. The six-column time-series contract, explicit soil depth
and units remain valid. GLDAS-only cells retain the 22-year standalone soil
analysis, with paired classification pending. Partial NDVI imports preserve that
standalone record until at least eight common complete years permit a paired
estimate. An eligible estimate still needs the existing reliability checks;
source QA remains unreviewed. The 0–10 cm input is a sensitivity series, while
NDVI + 0–100 cm soil water remains the primary pair.

The controller should serve the tile's own `export_region`/`build_region_detail`
payload through a separate dataset/directory identity, preserving source hashes
and tile/grid metadata. Native IDs distinguish these cells from `grid_rXX_cXX`
legacy cells. The fixed analysis period must accompany every slope, interval and
p-value. A source-cell storage trend is a diagnostic, not evidence that a smaller
point inside the cell shares the same environmental condition.

## Statistical family must be scoped to the native tile

Freeze the first family as **the 16 declared native cells in the central-US pilot,
2003–2024, NDVI and 0–100 cm soil storage**. This is a pilot family, not a worldwide
fine-grid screening. Eligible paired cells contribute two finite MK tests each;
unsupported/pending/insufficient cells remain listed without invented tests.
A complete eligible tile would contribute 32 tests. Before NDVI arrives, there
are zero paired tests; soil-only diagnostic p-values are exploratory across cells.

The existing batch accepts arbitrary catalogs and can compute this family, but its
legacy field names include `worldwide_adjusted_p_value`. For a fine pilot, retain
the numerical procedure while making the actual `multiple_testing.scope` and
family identity explicit in durable metadata and UI labels. Any field retaining
that legacy name must be described as **adjusted over the declared pilot family**.
Never reuse the coarse 10° map's adjusted p-values, categories or source hashes
for native cells. Controller integration should add a stable pilot family ID and
dataset/grid version before publishing the fine output.

When data arrive for additional pilot cells or years, recompute the whole declared
pilot family. Expansion to more tiles requires a newly declared family and a full
recalculation if claiming correction across those tiles; independently adjusted
tile p-values do not establish globally adjusted significance. Freeze the intended
selection before examining which cells show signals. Existing marginal confidence
intervals, independence/positive-dependence assumptions and source-footprint
limitations remain unchanged by reducing the grid size.

## Validation and remaining decisions

Eight geometry tests passed. They verify stable IDs and bounds, source-grid
centers, the exact 16-cell pilot, touching tiles, dateline crossing, pole/outer-edge
rules, area reconciliation over the native latitude band, lazy iteration and
rejection of invalid indices/requests. Tests create no invented observations.

B must verify extracted native source values and masks; MODIS cell aggregation
and the spatial overlap of each product's valid footprint still need independent
review. The team must decide the production statistical family when expanding
beyond the frozen pilot. No additional human choice is needed to extract and
serve the bounded native-resolution pilot with the limitations above visible.

## Independent local MODIS pixel comparison

`scripts/validate_fine_modis_pixels.py` checks one January 2003 native cell,
`gldas025_r388_c0328`. Its default is a local plan: it makes no account calls and
does not load Earth Engine. The controller can explicitly run a single bounded
source read using the existing OAuth session and project `earthrisk-greenmirage`:

```bash
.venv/bin/python scripts/validate_fine_modis_pixels.py
.venv/bin/python scripts/validate_fine_modis_pixels.py --verify \
  --output .cache/fine_pixel_check.json \
  --raw-output .cache/fine_pixel_sample.json \
  --csv .cache/fine_pilot_direct.csv
```

The verification initializes the session before setting a 30-second data-request
deadline and zero retries. It builds one bounded `getInfo` request for raw NDVI,
DetailedQA, SummaryQA, the three source masks, native pixel indices and projection
metadata. All bands are explicitly unmasked and sampled at the native projection;
no regional reducer from the exporter is called. The raw response is written
before local analysis so an account request need not be repeated to fix local
code. If `--output` is supplied without `--raw-output`, an adjacent
`*.pixels.json` file is used automatically. Replay an archived response offline:

```bash
.venv/bin/python scripts/validate_fine_modis_pixels.py \
  --sample-json .cache/fine_pixel_sample.json \
  --csv .cache/fine_pilot_direct.csv \
  --output .cache/fine_pixel_comparison.json
```

The local implementation independently checks raw NDVI range, all source masks,
DetailedQA low bits and SummaryQA, then applies 0.0001 once. The actual Earth Engine arrays contain half-integer pixel-center coordinates;
these are converted to integer corner indices before applying the source affine.
Arbitrary fractional or mixed coordinate conventions are rejected. It projects the
geographic target rectangle into the MODIS sinusoidal sphere, densifying its edges,
and intersects each source pixel polygon with that target using local geometry.
An area-weighted mean is calculated from those explicit intersections. The sum of
all pixel intersections must cover the analytic target area; missing source-array
coverage raises an error instead of introducing extra area or invented pixels.
The validator accepts at most 10,000 sampled pixels and supports one nonpolar,
non-dateline 0.25° cell. It decodes the actual affine WKT returned by
`Projection.transform()` as well as a six-number affine list.

This differs from the exporter's server-side weighted `reduceRegions` path.
Google documents that [`sampleRectangle` samples each band's input projection](https://developers.google.com/earth-engine/apidocs/ee-image-samplerectangle)
and that [weighted reductions quantize pixel-intersection weights to 256 levels](https://developers.google.com/earth-engine/guides/reducers_weighting).
Consequently, small differences between local continuous intersections and the
export's boundary fractions can be expected. The report includes a conservative
diagnostic budget of one quantization step per boundary pixel. That budget is
not an automatic source-QA acceptance threshold and does not cover wrong pixel
alignment, mismatched masks, duplicated data or incorrect denominators.

Coverage above one is always flagged and retained exactly in the comparison.
The script never clamps coverage and never changes `qa_reviewed` to true. A small
positive excess may be compatible with quantized boundary weights; percent-level
excess requires investigation. The report preserves the original exported area,
local area, mean differences, coverage differences and input CSV hash so the
controller can make a concrete assessment rather than silently widening tolerance.

Seventeen offline tests pass, using explicitly synthetic raw pixel fixtures only.
They cover scaling once, QA/mask rejection, valid negative NDVI, fractional edge
weights, exact area coverage, insufficient/duplicate arrays, unclamped coverage
excess, actual affine WKT parsing, half-integer native pixel centers, default no-account behavior, session/deadline
ordering and raw-response archival before local failures. No worker account calls
or production source values were generated by these tests.

This is an independent **calculation** on pixels retrieved from the same hosted
NASA-derived Earth Engine asset. It does not independently archive original NASA
tiles or prove all product QA semantics. One cell/month cannot validate the full
22-year or worldwide record, and source coverage overlap with GLDAS still requires
review. Actual execution results must be recorded separately from these offline
method tests; a dry plan or passing fixture is not evidence of successful NASA
pixel comparison.


### Actual January 2003 consistency evidence

The controller obtained one genuine source-pixel snapshot and the unmodified
fine-export graph's pilot CSV on 2026-11-15. The worker then replayed that saved
snapshot entirely offline for `gldas025_r388_c0328`, bbox
`[-98, 37, -97.75, 37.25]`. This is actual NASA-derived input, distinct from the
synthetic method tests above.

| Quantity | Local continuous pixel intersections | Exported weighted reducer |
| --- | --- | --- |
| NDVI | 0.45463846615120873 | 0.4545949434225114 |
| Valid area, m² | 616145968.5288681 | 616296987.7468138 |
| Valid-area fraction | 0.9999999996123066 | 1.000245102600236 |

The sampled rectangle contained 2,340 source pixels; 804 intersected the exact
cell, all passing the specified source QA rules. There were 167 boundary pixels.
Local geometry reproduced the analytic spherical area to approximately
`3.9e-10` relative error. The exported mean differed by `-4.35227e-5` NDVI and its
valid area exceeded the local sum by approximately 151,019 m². That area difference
is below the conservative one-step-per-boundary-pixel diagnostic budget of
approximately 560,125 m². The small positive exported coverage excess is compatible
with a boundary-weight quantization discrepancy at this cell; this numerical
comparison alone does not prove the exact internal rounding mechanism.

The exported fraction above one remains flagged and unclamped. Neither method
promotes `qa_reviewed`; both retain review-required status. This verifies one
calculation path for one cell/month, not all 16 pilot cells or the full time span.
The source CSV SHA-256 was
`40e667e8c7cdb42c4a91766b9629f7c7f915873f7e70656f80d96c3577a7212e`.
Local raw evidence is `.cache/fine_pixel_check.pixels.json`; the controller can
archive the replay/comparison report without a further account request.

## Six-tile collection and one joint testing family

`data/processed/fine/tiles.json` freezes six 1° source tiles: central US, Canadian
interior, Iberia, central Sahel, southeast Australia and the Brazilian Amazon.
Each contains 16 native GLDAS cells. Their 96 distinct cells form one declared
statistical collection; they are geographically separated demonstrations rather
than representative or exhaustive global coverage. The original central-US pilot
was already exploratory work; this expansion must not be described as a fully
confirmatory blind global sample.

Prepare the collection after source ingestion:

```bash
.venv/bin/python scripts/prepare_fine_collection.py
.venv/bin/python scripts/prepare_fine_collection.py --audit-only
```

`src.fine_collection.prepare_collection` reads and hashes the registry and each
tile's catalog, actual monthly table, original soil table, metadata, source
manifests and accepted MODIS ledger. It copies the actual observations and native
geometry into `data/processed/fine/collection/`; source releases remain intact.
Original `tile_id` values are retained and `collection_tile_id` identifies origin.
The 264 shared GLDAS source-file records are deduplicated; all historical MODIS
archives remain hash-checked. Only files currently authoritative in the accepted
ledger undergo current-method strict source/provenance validation. Superseded
archives remain immutable evidence rather than being mistaken for current data.

One call to the existing batch computes statistics across the entire 96-cell
catalog. Eligible paired cells each contribute two primary MK tests; the complete
collection can contain up to 192 tests. The family ID includes sorted native-cell
IDs, all six tile IDs, grid, fixed period and primary variables. Arrival of new
observations changes family size and adjusted values while preserving the declared
family identity. Standalone soil diagnostics remain separate. No previous
central-US-only or coarse-grid adjusted p-values are reused.

The output includes one full screening report and compact map, concatenated
original tables, quality counts, consolidated source manifests and an
`input_manifest.json`. The latter has flattened `{file, sha256}` records for the
registry and all source-release inputs, plus per-tile hashes. API consumers check
these fingerprints and withhold a collection when an upstream tile changes.
Viewport filtering may select fewer map features, but must retain the full joint
family metadata and adjusted values; it must not silently recompute a local family.

The collection audit independently reconciles source values, original soil
baselines, native catalogs, monthly indexes, immutable archives and ledger values.
It derives complete common annual years from actual observations, recomputes the
raw MK tests from those annual values and independently calculates the joint BH
adjustment. It checks the stored category with those joint values and ensures
map/report agreement. These integrity checks do not promote source QA or establish
spatial independence, causal effects or ecological damage.

Candidates are written to a temporary staging directory first. Only a successful
independent audit and a final unchanged-input check allow publication. Individual
files are replaced atomically, with the compact map published last as the visible
release marker. A failed candidate leaves the prior collection untouched.

## Spherical area-reference correction (calculation version 2)

The first fine exports used Earth Engine `pixelArea()` while the native target
cell denominator used the MODIS sinusoidal sphere, radius 6,371,007.181 m. A
high-latitude Canadian source check exposed a latitude-dependent coverage bias.
Independent `pyproj.Geod` calculations for densified 0.25° geographic rectangles
show these WGS84-ellipsoid/spherical-area ratios:

| Approximate southern latitude | Ellipsoidal area / spherical area |
| --- | --- |
| 37° N | 1.0004033513 |
| 54° N | 1.0043396169 |
| 13° N | 0.9962177484 |
| 4° S | 0.9955909858 |

The Canadian ratio closely matches the approximately 1.0042 excess that triggered
investigation. A single central-US comparison could not distinguish this reference
mismatch from boundary quantization because its discrepancy was smaller than the
conservative edge budget. The earlier January 2003 comparison table above records
that **legacy** calculation and must not be treated as validation of the corrected
processing version or a claim that quantization alone explained its area excess.

Fine exports now use the constant native sinusoidal pixel area
`abs(926.625433055833 × -926.6254330558334)` m², with the native projection applied
explicitly. This equal-area spherical reference matches the target denominator
at all latitudes. The version is
`modis_sinusoidal_sphere_native_pixel_v2`, recorded as `area_method` in fine CSVs
and in fetch/task cache identity. Shared coarse-export calculations are unaffected
by this fine-specific correction. No coverage threshold is widened to hide the
mismatch; any positive excess remains visible for boundary-weight review.

All received fine NDVI rows, including actual missing-image rows, must declare the
version-2 method before a collection can publish. Unreceived `pending_export`
placeholders have no source computation to certify. Legacy current rows require
deliberate reprocessing/replacement and new immutable source archives; mixing
versions in the active ledger is rejected. Previously archived version-1 files
are retained, hash-checked and excluded from the authoritative current ledger.
Two physical regression tests verify the native affine pixel area on the sphere
and the material latitude-dependent ellipsoid/sphere discrepancy.
