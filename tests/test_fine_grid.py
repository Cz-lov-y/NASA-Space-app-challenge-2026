"""Native-grid geometry checks; no invented NASA measurements are used."""
from collections.abc import Iterator
import math

import pytest

from src.fine_grid import (GEOMETRIC_CELL_COUNT, N_COLS, N_ROWS, RADIUS_M,
    build_tile_catalog, cell_bbox, cell_feature, cell_id, grid_definition,
    index_for_coordinate, iter_cells, parse_cell_id)


def test_native_lattice_extent_centers_and_stable_ids():
    definition = grid_definition()
    assert definition['bbox'] == [-180, -60, 180, 90]
    assert (N_ROWS, N_COLS, GEOMETRIC_CELL_COUNT) == (600, 1440, 864000)
    assert definition['first_center'] == [-179.875, -59.875]
    assert definition['last_center'] == [179.875, 89.875]
    assert cell_bbox(0, 0) == [-180, -60, -179.75, -59.75]
    assert cell_bbox(599, 1439) == [179.75, 89.75, 180, 90]
    for row, col in [(0, 0), (599, 1439), (388, 328), (391, 331)]:
        assert parse_cell_id(cell_id(row, col)) == (row, col)
        feature = cell_feature(row, col)
        assert index_for_coordinate(*feature['properties']['centroid']) == (row, col)
        assert feature['geometry']['coordinates'][0][0] == feature['geometry']['coordinates'][0][-1]
        assert feature['properties']['data_status'] == 'availability_not_checked'
        assert feature['properties']['variables'] == []


def test_initial_one_degree_tile_has_exact_16_native_cells_and_no_overlap():
    features = build_tile_catalog([-98, 37, -97, 38])['features']
    assert len(features) == len({f['id'] for f in features}) == 16
    assert [parse_cell_id(f['id']) for f in features] == [(row, col) for row in range(388, 392) for col in range(328, 332)]
    assert features[0]['properties']['bbox'] == [-98, 37, -97.75, 37.25]
    assert features[-1]['properties']['bbox'] == [-97.25, 37.75, -97, 38]
    for i in range(4):
        row = features[i*4:(i+1)*4]
        assert all(a['properties']['bbox'][2] == b['properties']['bbox'][0] for a, b in zip(row, row[1:]))
    area = sum(f['properties']['region_area_m2'] for f in features)
    expected = RADIUS_M**2 * math.radians(1) * (math.sin(math.radians(38)) - math.sin(math.radians(37)))
    assert area == pytest.approx(expected, rel=1e-13)
    # Two touching aligned halves do not duplicate cells on their shared edge.
    left = {f['id'] for f in iter_cells([-98, 37, -97.5, 38])}
    right = {f['id'] for f in iter_cells([-97.5, 37, -97, 38])}
    assert not left & right
    assert left | right == {f['id'] for f in features}


def test_dateline_point_alias_and_wrapped_tiles_remain_exact():
    assert index_for_coordinate(-180, 0) == index_for_coordinate(180, 0) == (240, 0)
    assert index_for_coordinate(179.999, 0) == (240, 1439)
    features = build_tile_catalog([179.75, 0, -179.75, .25])['features']
    assert [parse_cell_id(f['id']) for f in features] == [(240, 1439), (240, 0)]
    assert [f['properties']['bbox'] for f in features] == [[179.75, 0, 180, .25], [-180, 0, -179.75, .25]]
    assert len(build_tile_catalog([180, 0, -179.75, .25])['features']) == 1
    with pytest.raises(ValueError, match='positive longitudinal'):
        build_tile_catalog([180, 0, -180, .25])


def test_poles_and_exact_boundaries_follow_documented_ownership():
    assert index_for_coordinate(-98, 37) == (388, 328)
    assert index_for_coordinate(-97.75, 37.25) == (389, 329)
    assert index_for_coordinate(0, -60) == (0, 720)
    assert index_for_coordinate(0, 90) == (599, 720)
    last = build_tile_catalog([179.75, 89.75, 180, 90])['features']
    assert len(last) == 1 and last[0]['id'] == 'gldas025_r599_c1439'
    assert last[0]['properties']['region_area_m2'] > 0
    for coordinate in [(0, -90), (0, -60.0001), (0, 90.0001), (-180.0001, 0), (180.0001, 0)]:
        with pytest.raises(ValueError, match='outside'):
            index_for_coordinate(*coordinate)


def test_native_area_matches_geometric_latitude_band_without_ocean_assumption():
    row_areas = [cell_feature(row, 0)['properties']['region_area_m2'] for row in range(600)]
    expected = 2 * math.pi * RADIUS_M**2 * (1 - math.sin(math.radians(-60)))
    assert sum(row_areas) * 1440 == pytest.approx(expected, rel=1e-13)
    assert row_areas[-1] < row_areas[240]


def test_non_aligned_request_keeps_native_support_instead_of_resampling():
    feature = build_tile_catalog([-97.99, 37.01, -97.98, 37.02])['features']
    assert len(feature) == 1
    assert feature[0]['properties']['bbox'] == [-98, 37, -97.75, 37.25]


def test_global_iteration_is_lazy_and_global_materialization_requires_tiling():
    cells = iter_cells()
    assert isinstance(cells, Iterator)
    assert next(cells)['id'] == 'gldas025_r000_c0000'
    assert next(cells)['id'] == 'gldas025_r000_c0001'
    with pytest.raises(ValueError, match='864000'):
        build_tile_catalog([-180, -60, 180, 90])
    with pytest.raises(ValueError, match='max_cells'):
        build_tile_catalog([-98, 37, -97, 38], max_cells=15)


def test_invalid_indices_ids_and_coordinates_are_rejected():
    for row, col in [(-1, 0), (600, 0), (0, 1440), (True, 0), (0, 1.5)]:
        with pytest.raises(ValueError):
            cell_bbox(row, col)
    for text in ['gldas025_r600_c0000', 'gldas025_r000_c1440', 'gldas025_r0_c0', 'gldas025_r000_c0000\n', None]:
        with pytest.raises(ValueError):
            parse_cell_id(text)
    for value in [True, '0', float('nan'), float('inf')]:
        with pytest.raises(ValueError):
            index_for_coordinate(value, 0)
    for bbox in [[0, 0, 0, 1], [0, 1, 1, 0], [0, -61, 1, 0], 'bbox', [0, 1, 2], [0, 0, float('nan'), 1]]:
        with pytest.raises(ValueError):
            build_tile_catalog(bbox)
