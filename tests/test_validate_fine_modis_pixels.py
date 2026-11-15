"""Local synthetic pixel fixtures only; tests make no Earth Engine requests."""
import importlib.util
import json
import math
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location('validate_fine_modis_pixels', Path(__file__).resolve().parents[1] / 'scripts/validate_fine_modis_pixels.py')
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)
BBOX = [-98, 37, -97.75, 37.25]
TRANSFORM = [926.625433055833, 0, -20015109.354, 0, -926.625433055833, 10007554.677003]
PROJECTION = {'crs': 'SR-ORG:6974', 'transform': TRANSFORM}


def pixels():
    target, _ = MOD._geometry(BBOX)
    xmin, ymin, xmax, ymax = target.bounds
    dx, _, tx, _, dy, ty = TRANSFORM
    cols = range(math.floor((xmin-tx)/dx)-1, math.floor((xmax-tx)/dx)+2)
    rows = range(math.floor((ymax-ty)/dy)-1, math.floor((ymin-ty)/dy)+2)
    x, y = np.meshgrid(cols, rows)
    result = {name: np.ones(x.shape) for name in MOD.BANDS}
    result.update(NDVI=np.full(x.shape, 4000), DetailedQA=np.zeros(x.shape), SummaryQA=np.zeros(x.shape), pixel_x=x, pixel_y=y)
    return result


def test_all_valid_constant_raw_pixels_are_scaled_once_and_cover_target():
    result = MOD.summarize_pixels(pixels(), PROJECTION, BBOX)
    assert result['value'] == pytest.approx(.4)
    assert result['unit'] == '1'
    assert result['valid_area_fraction'] == pytest.approx(1, abs=1e-7)
    assert result['valid_area_m2'] == pytest.approx(result['region_area_m2'], rel=1e-7)
    assert result['boundary_pixels'] > 0
    assert abs(result['geometry_area_relative_error']) < 1e-7
    assert result['sampled_pixels'] > result['intersecting_pixels'] > result['boundary_pixels']
    assert result['native_pixel_area_m2'] == pytest.approx(TRANSFORM[0] ** 2)


@pytest.mark.parametrize('band,value', [('DetailedQA', 1), ('SummaryQA', 1), ('NDVI', -32768), ('ndvi_mask', 0), ('detailed_mask', 0), ('summary_mask', 0)])
def test_invalid_raw_qa_or_source_masks_remain_missing(band, value):
    sample = pixels()
    sample[band] = np.full_like(sample[band], value)
    result = MOD.summarize_pixels(sample, PROJECTION, BBOX)
    assert result['value'] is None
    assert result['valid_area_m2'] == result['valid_area_fraction'] == 0
    assert result['valid_intersecting_pixels'] == 0
    json.dumps(result, allow_nan=False)


def test_only_detailed_low_bits_are_used_and_negative_valid_ndvi_is_retained():
    sample = pixels()
    sample['DetailedQA'][:] = 4
    sample['NDVI'][:] = -2000
    result = MOD.summarize_pixels(sample, PROJECTION, BBOX)
    assert result['value'] == pytest.approx(-.2)
    assert result['valid_area_fraction'] == pytest.approx(1, abs=1e-7)


def test_fractional_edge_pixel_is_area_weighted_instead_of_counted_whole():
    from shapely.geometry import box
    sample = pixels()
    target, area = MOD._geometry(BBOX)
    dx, _, tx, _, dy, ty = TRANSFORM
    found = None
    for i, j in np.ndindex(sample['NDVI'].shape):
        col, row = sample['pixel_x'][i, j], sample['pixel_y'][i, j]
        x, y = tx+col*dx, ty+row*dy
        overlap = target.intersection(box(x, y+dy, x+dx, y)).area
        if 0 < overlap < abs(dx*dy) / 2:
            found = i, j, overlap
            break
    assert found is not None
    i, j, overlap = found
    sample['ndvi_mask'][:] = 0
    sample['ndvi_mask'][i, j] = 1
    result = MOD.summarize_pixels(sample, PROJECTION, BBOX)
    assert result['value'] == pytest.approx(.4)
    assert result['valid_area_m2'] == pytest.approx(overlap)
    assert result['valid_area_fraction'] == pytest.approx(overlap / area)
    assert result['valid_area_m2'] < result['native_pixel_area_m2'] / 2


def test_insufficient_or_duplicate_arrays_fail_without_silent_area_correction():
    sample = pixels()
    cropped = {key: values[:1, :1] for key, values in sample.items()}
    with pytest.raises(ValueError, match='fully cover'):
        MOD.summarize_pixels(cropped, PROJECTION, BBOX)
    sample['pixel_x'][:] = sample['pixel_x'][0, 0]
    sample['pixel_y'][:] = sample['pixel_y'][0, 0]
    with pytest.raises(ValueError, match='Duplicate'):
        MOD.summarize_pixels(sample, PROJECTION, BBOX)
    with pytest.raises(ValueError, match='sinusoidal'):
        MOD.summarize_pixels(pixels(), {'crs': 'EPSG:4326', 'transform': TRANSFORM}, BBOX)


def test_export_comparison_flags_coverage_above_one_without_clipping(tmp_path):
    local = MOD.summarize_pixels(pixels(), PROJECTION, BBOX)
    csv = tmp_path / 'SYNTHETIC_PROTOCOL_FIXTURE.csv'
    pd.DataFrame([{'date': '2003-01-01', 'region_id': MOD.DEFAULT_REGION,
        'variable': 'ndvi', 'source': 'MOD13A3.061', 'unit': '1', 'value': .4,
        'valid_area_m2': local['region_area_m2'] * 1.03,
        'valid_area_fraction': 1.03, 'region_area_m2': local['region_area_m2']}]).to_csv(csv, index=False)
    report = MOD.compare_export(local, csv, MOD.DEFAULT_REGION, '2003-01-01')
    assert report['coverage_exceeds_one']
    assert report['exported']['valid_area_fraction'] == 1.03
    assert report['export_minus_local']['valid_area_fraction'] == pytest.approx(.03, abs=1e-7)
    assert report['status'] == 'review_required'


def test_default_plan_does_not_initialize_or_contact_earth_engine(monkeypatch, capsys):
    import sys
    def forbidden(**kwargs):
        raise AssertionError('Default plan must never initialize Earth Engine')
    monkeypatch.setitem(sys.modules, 'ee', SimpleNamespace(Initialize=forbidden))
    MOD.main([])
    output = json.loads(capsys.readouterr().out)
    assert output['mode'] == 'dry_plan'
    assert output['network_calls'] == 0
    assert output['region_id'] == MOD.DEFAULT_REGION


def test_verify_initializes_session_before_setting_http_deadline():
    events = []
    def initialize(**kwargs):
        events.append('initialize')
    def deadline(ms):
        assert events == ['initialize']
        events.append('deadline')
    def retries(count):
        assert events == ['initialize', 'deadline']
        events.append('retries')
    def image(asset):
        assert events == ['initialize', 'deadline', 'retries']
        raise RuntimeError('stop before building any server expression')
    ee = SimpleNamespace(Initialize=initialize, data=SimpleNamespace(setDeadline=deadline, setMaxRetries=retries), Image=image)
    with pytest.raises(RuntimeError, match='stop before'):
        MOD.verify(ee, MOD.DEFAULT_PROJECT, MOD.DEFAULT_REGION, '2003-01-01')


def test_actual_earth_engine_affine_wkt_matches_numeric_transform():
    wkt = ('PARAM_MT["Affine", PARAMETER["num_row", 3], PARAMETER["num_col", 3], '
           'PARAMETER["elt_0_0", 926.625433055833], PARAMETER["elt_0_2", -20015109.354], '
           'PARAMETER["elt_1_1", -926.625433055833], PARAMETER["elt_1_2", 10007554.677003]]')
    actual = MOD.summarize_pixels(pixels(), {'crs': 'SR-ORG:6974', 'transform': wkt}, BBOX)
    expected = MOD.summarize_pixels(pixels(), PROJECTION, BBOX)
    assert actual == expected
    with pytest.raises(ValueError, match='missing'):
        MOD.affine_values('PARAM_MT["Affine", PARAMETER["elt_0_0", 926.6]]')


def test_archived_sample_replays_offline_with_identity_validation(tmp_path, monkeypatch, capsys):
    import sys
    snapshot = {'region_id': MOD.DEFAULT_REGION, 'month': '2003-01-01', 'bbox': BBOX,
        'source_asset_id': 'SYNTHETIC_TEST_ONLY', 'projection': PROJECTION,
        'sample': {k: value.tolist() for k, value in pixels().items()}}
    path = tmp_path / 'SYNTHETIC_PIXEL_FIXTURE.json'
    path.write_text(json.dumps(snapshot))
    monkeypatch.setitem(sys.modules, 'ee', None)
    MOD.main(['--sample-json', str(path)])
    report = json.loads(capsys.readouterr().out)
    assert report['mode'] == 'offline_replay'
    assert not report['qa_reviewed']
    assert report['local']['value'] == pytest.approx(.4)
    with pytest.raises(SystemExit):
        MOD.main(['--sample-json', str(path), '--month', '2004-01-01'])


def test_raw_payload_is_archived_before_local_validation_can_fail(tmp_path):
    payload = {'sample': {key: value.tolist() for key, value in pixels().items()},
               'projection': {'crs': 'SYNTHETIC_BAD_PROJECTION', 'transform': TRANSFORM}}
    class Node:
        def __getattr__(self, key):
            return lambda *args, **kwargs: self
        def getInfo(self):
            return payload
    class Image(Node):
        def __init__(self, *args):
            pass
        @staticmethod
        def pixelCoordinates(projection):
            return Node()
    ee = SimpleNamespace(Initialize=lambda **kwargs: None,
        data=SimpleNamespace(setDeadline=lambda ms: None, setMaxRetries=lambda n: None),
        Image=Image, Geometry=SimpleNamespace(Rectangle=lambda *args: Node()), Dictionary=lambda obj: Node())
    archived = tmp_path / 'archived.json'
    with pytest.raises(ValueError, match='sinusoidal'):
        MOD.verify(ee, MOD.DEFAULT_PROJECT, MOD.DEFAULT_REGION, '2003-01-01', raw_output=archived)
    saved = json.loads(archived.read_text())
    assert saved['sample'] == payload['sample']
    assert saved['region_id'] == MOD.DEFAULT_REGION


def test_actual_earth_engine_half_integer_centers_map_to_correct_pixel_corners():
    sample = pixels()
    expected = MOD.summarize_pixels(sample, PROJECTION, BBOX)
    sample['pixel_x'] = sample['pixel_x'] + .5
    sample['pixel_y'] = sample['pixel_y'] + .5
    actual = MOD.summarize_pixels(sample, PROJECTION, BBOX)
    assert actual['sample_coordinate_convention'] == 'half_integer_centers'
    assert expected['sample_coordinate_convention'] == 'integer_indices'
    for field in ('value', 'valid_area_m2', 'valid_area_fraction', 'sampled_pixels', 'boundary_pixels'):
        assert actual[field] == expected[field]
    sample['pixel_x'][0,0] += .1
    with pytest.raises(ValueError, match='consistent'):
        MOD.summarize_pixels(sample, PROJECTION, BBOX)
