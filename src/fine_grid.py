"""Lazy GLDAS native 0.25-degree geometry; availability requires actual data.

Rows increase northward from -60 degrees, columns eastward from -180 degrees.
Coordinates use half-open cells, with +180 canonicalized to -180 and the north
outer boundary +90 assigned to the last row. No soil observation is interpolated.
"""
from collections.abc import Iterator, Sequence
import math
from numbers import Integral, Real
import re

RESOLUTION_DEGREES = 0.25
WEST, SOUTH, EAST, NORTH = -180.0, -60.0, 180.0, 90.0
N_ROWS, N_COLS = 600, 1440
GEOMETRIC_CELL_COUNT = N_ROWS * N_COLS
RADIUS_M = 6371007.181
_ID = re.compile(r"gldas025_r([0-9]{3})_c([0-9]{4})")


def _index(value, limit, name):
    if not isinstance(value, Integral) or isinstance(value, bool) or not 0 <= value < limit:
        raise ValueError(f"{name} must be an integer in [0, {limit - 1}]")
    return int(value)


def _coordinate(value, name):
    if not isinstance(value, Real) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite numeric coordinate")
    return float(value)


def cell_id(row: int, col: int) -> str:
    return f"gldas025_r{_index(row, N_ROWS, 'row'):03d}_c{_index(col, N_COLS, 'col'):04d}"


def parse_cell_id(region_id: str) -> tuple[int, int]:
    match = _ID.fullmatch(region_id) if isinstance(region_id, str) else None
    if match is None:
        raise ValueError("Expected canonical gldas025_rRRR_cCCCC region ID")
    row, col = map(int, match.groups())
    return _index(row, N_ROWS, "row"), _index(col, N_COLS, "col")


def cell_bbox(row: int, col: int) -> list[float]:
    row, col = _index(row, N_ROWS, "row"), _index(col, N_COLS, "col")
    west, south = WEST + col * RESOLUTION_DEGREES, SOUTH + row * RESOLUTION_DEGREES
    return [west, south, west + RESOLUTION_DEGREES, south + RESOLUTION_DEGREES]


def index_for_coordinate(lon: float, lat: float) -> tuple[int, int]:
    """Map a point to its native cell; the geometric extent includes no land mask.

    Exact interior boundaries belong to the north/east cell. +180 and -180 are
    the same longitude (column 0). +90 belongs to row 599 for deterministic
    display lookup; longitude at a geographic pole is intrinsically arbitrary.
    Points south of -60, including the South Pole, are outside this grid.
    """
    lon, lat = _coordinate(lon, "longitude"), _coordinate(lat, "latitude")
    if not WEST <= lon <= EAST or not SOUTH <= lat <= NORTH:
        raise ValueError("Coordinate outside GLDAS geometric extent [-180,-60,180,90]")
    lon = WEST if lon == EAST else lon
    row = N_ROWS - 1 if lat == NORTH else math.floor((lat - SOUTH) / RESOLUTION_DEGREES)
    col = math.floor((lon - WEST) / RESOLUTION_DEGREES)
    return row, col


def grid_definition() -> dict:
    """Small serializable lattice description; never expands 864,000 cells."""
    return {"grid_id": "gldas025", "crs": "EPSG:4326", "bbox": [WEST, SOUTH, EAST, NORTH],
            "native_resolution_degrees": RESOLUTION_DEGREES,
            "rows": N_ROWS, "columns": N_COLS, "geometric_cell_count": GEOMETRIC_CELL_COUNT,
            "row_direction": "south_to_north", "column_direction": "west_to_east",
            "id_pattern": "gldas025_r{row:03d}_c{col:04d}",
            "first_center": [-179.875, -59.875], "last_center": [179.875, 89.875],
            "availability": "Geometry only; evaluate actual product fill/valid masks per variable and month.",
            "coordinate_edges": "Interior north/east ownership; +180 maps to -180; +90 maps to final row."}


def cell_feature(row: int, col: int) -> dict:
    bbox = cell_bbox(row, col)
    west, south, east, north = bbox
    region_id = cell_id(row, col)
    area = RADIUS_M**2 * math.radians(east - west) * (math.sin(math.radians(north)) - math.sin(math.radians(south)))
    return {"type": "Feature", "id": region_id,
            "geometry": {"type": "Polygon", "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]]},
            "properties": {"region_id": region_id, "name": region_id,
                "bbox": bbox, "centroid": [(west + east) / 2, (south + north) / 2],
                "region_area_m2": area, "crs": "EPSG:4326", "grid_row": int(row), "grid_col": int(col),
                "native_resolution_degrees": RESOLUTION_DEGREES,
                "data_status": "availability_not_checked", "variables": [],
                "jurisdictions": [], "jurisdiction_status": "not_resolved"}}


def _ranges(bbox):
    if not isinstance(bbox, Sequence) or isinstance(bbox, (str, bytes)) or len(bbox) != 4:
        raise ValueError("bbox must be [west, south, east, north]")
    west, south, east, north = [_coordinate(value, "bbox") for value in bbox]
    if not WEST <= west <= EAST or not WEST <= east <= EAST or not SOUTH <= south < north <= NORTH or west == east:
        raise ValueError("bbox must have positive area within the native geometric extent")
    segments = [(west, east)] if west < east else [(west, EAST), (WEST, east)]
    segments = [(a, b) for a, b in segments if a < b]
    if not segments:
        raise ValueError("bbox must have positive longitudinal width")
    rows = range(math.floor((south - SOUTH) / RESOLUTION_DEGREES), math.ceil((north - SOUTH) / RESOLUTION_DEGREES))
    cols = [range(math.floor((a - WEST) / RESOLUTION_DEGREES), math.ceil((b - WEST) / RESOLUTION_DEGREES)) for a, b in segments]
    return rows, cols


def iter_cells(bbox=None) -> Iterator[dict]:
    """Lazily yield full native cells with positive-area intersection with bbox.

    bbox may cross the antimeridian (west > east). Bounds need not be grid-aligned;
    cells retain their complete native boundaries rather than being clipped.
    Adjacent aligned tiles share boundaries without duplicating cells.
    """
    rows, columns = _ranges([WEST, SOUTH, EAST, NORTH] if bbox is None else bbox)
    for row in rows:
        for cols in columns:
            for col in cols:
                yield cell_feature(row, col)


def build_tile_catalog(bbox, *, max_cells: int = 4096) -> dict:
    """Materialize a bounded tile; large full-grid JSON construction is rejected."""
    if not isinstance(max_cells, Integral) or isinstance(max_cells, bool) or max_cells < 1:
        raise ValueError("max_cells must be a positive integer")
    rows, columns = _ranges(bbox)
    count = len(rows) * sum(len(cols) for cols in columns)
    if count > max_cells:
        raise ValueError(f"Requested {count} cells exceeds max_cells={max_cells}; use bounded tiles or iter_cells")
    return {"type": "FeatureCollection", "grid": grid_definition(), "requested_bbox": list(bbox),
            "features": list(iter_cells(bbox))}
