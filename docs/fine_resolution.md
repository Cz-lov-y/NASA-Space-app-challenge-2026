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
