#!/usr/bin/env python3
"""Independent fine-cell MODIS pixel/area check; dry plan unless --verify.

Verification samples raw pixels once, then evaluates QA and exact native-pixel
intersections locally. It never calls the exporter's reduceRegions expression.
This is a bounded consistency check, not full independent product validation.
"""
import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import math
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.fine_grid import RADIUS_M, cell_bbox, parse_cell_id

DEFAULT_REGION = 'gldas025_r388_c0328'
DEFAULT_PROJECT = 'earthrisk-greenmirage'
BANDS = ('NDVI', 'DetailedQA', 'SummaryQA', 'ndvi_mask', 'detailed_mask', 'summary_mask', 'pixel_x', 'pixel_y')


def _geometry(bbox, steps=64):
    """Project a densified geographic rectangle to the equal-area MODIS sphere."""
    import numpy as np
    from shapely.geometry import Polygon
    west, south, east, north = bbox
    if not (-180 < west < east < 180 and -80 < south < north < 80 and east-west <= .25 and north-south <= .25):
        raise ValueError('Validator supports one nonpolar, non-dateline native cell only')
    ring = [(lon, south) for lon in np.linspace(west, east, steps+1)]
    ring += [(east, lat) for lat in np.linspace(south, north, steps+1)[1:]]
    ring += [(lon, north) for lon in np.linspace(east, west, steps+1)[1:]]
    ring += [(west, lat) for lat in np.linspace(north, south, steps+1)[1:]]
    target = Polygon([(RADIUS_M * math.radians(lon) * math.cos(math.radians(lat)),
                       RADIUS_M * math.radians(lat)) for lon, lat in ring])
    exact_area = RADIUS_M**2 * math.radians(east-west) * (math.sin(math.radians(north)) - math.sin(math.radians(south)))
    if abs(target.area/exact_area - 1) > 1e-5:
        raise ValueError('Densified target does not reproduce the analytic spherical area')
    return target, exact_area



def affine_values(value):
    """Decode EE Projection.transform() affine WKT or a six-value array."""
    if not isinstance(value, str):
        return value
    if not value.startswith('PARAM_MT["Affine"'):
        raise ValueError('Expected affine WKT or a six-element transform')
    items = re.findall(r'PARAMETER\["(elt_[0-2]_[0-2])",\s*([-+0-9.eE]+)\]', value)
    if len(dict(items)) != len(items):
        raise ValueError('Duplicate affine WKT parameters')
    parameters = {key: float(number) for key, number in items}
    required = ('elt_0_0', 'elt_0_2', 'elt_1_1', 'elt_1_2')
    if not all(key in parameters for key in required):
        raise ValueError('Affine WKT is missing native transform parameters')
    return [parameters['elt_0_0'], parameters.get('elt_0_1', 0), parameters['elt_0_2'],
            parameters.get('elt_1_0', 0), parameters['elt_1_1'], parameters['elt_1_2']]


def summarize_pixels(sample, projection, bbox):
    """Compute local raw-QA masks, scale and pixel intersections independently.

    sample is a dictionary of equally sized arrays from sampleRectangle. The
    affine maps pixel corners. Earth Engine samples half-integer pixel centers;
    these are normalized to corner indices. Integer-index offline fixtures are
    also accepted, but mixed or arbitrary fractional conventions are rejected.
    All sampled source cells, including invalid ones, must cover the target.
    """
    import numpy as np
    from shapely.geometry import Polygon
    if projection.get('crs') != 'SR-ORG:6974':
        raise ValueError('Expected native MODIS sinusoidal SR-ORG:6974 projection')
    transform = np.asarray(affine_values(projection['transform']), dtype=float)
    if transform.shape != (6,) or not np.isfinite(transform).all() or transform[1] != 0 or transform[3] != 0:
        raise ValueError('Expected finite six-element native affine with no shear')
    dx, _, tx, _, dy, ty = transform
    if not (900 < dx < 1000 and -1000 < dy < -900):
        raise ValueError('Unexpected MOD13A3 native pixel spacing')
    arrays = {name: np.asarray(sample[name], dtype=float) for name in BANDS}
    shape = arrays['NDVI'].shape
    if len(shape) != 2 or not 0 < math.prod(shape) <= 10000 or any(a.shape != shape for a in arrays.values()):
        raise ValueError('Expected matching bounded two-dimensional pixel arrays')
    coordinates = [arrays[name] for name in ('pixel_x', 'pixel_y')]
    if not all(np.isfinite(values).all() for values in coordinates):
        raise ValueError('Pixel coordinates must be finite')
    integer_indices = all(np.isclose(values, np.rint(values), rtol=0, atol=1e-9).all() for values in coordinates)
    half_centers = all(np.isclose(values, np.floor(values) + .5, rtol=0, atol=1e-9).all() for values in coordinates)
    if not integer_indices and not half_centers:
        raise ValueError('Pixel coordinates must use consistent integer indices or half-integer centers')
    coordinate_convention = 'half_integer_centers' if half_centers else 'integer_indices'
    if half_centers:
        arrays['pixel_x'] = np.floor(arrays['pixel_x'])
        arrays['pixel_y'] = np.floor(arrays['pixel_y'])
    xy = list(zip(arrays['pixel_x'].flat, arrays['pixel_y'].flat))
    if len(set(xy)) != len(xy):
        raise ValueError('Duplicate sampled native pixels')
    target, exact_area = _geometry(bbox)
    overlaps = []
    for col, row in xy:
        x, y = tx + col*dx, ty + row*dy
        pixel = Polygon([(x,y), (x+dx,y), (x+dx,y+dy), (x,y+dy)])
        overlaps.append(target.intersection(pixel).area)
    overlaps = np.asarray(overlaps).reshape(shape)
    covered = float(overlaps.sum())
    if abs(covered/exact_area - 1) > 1e-5:
        raise ValueError('Sampled pixels do not fully cover the target cell; enlarge the sample bounds')
    raw, detailed, summary = (arrays[name] for name in BANDS[:3])
    finite = np.isfinite(raw) & np.isfinite(detailed) & np.isfinite(summary)
    integer_qa = finite & (detailed == np.floor(detailed)) & (summary == np.floor(summary))
    detail_int = np.where(integer_qa, detailed, -1).astype('int64')
    valid = (finite & integer_qa & (raw >= -2000) & (raw <= 10000) & ((detail_int & 3) == 0)
             & (summary == 0) & (arrays['ndvi_mask'] > 0) & (arrays['detailed_mask'] > 0)
             & (arrays['summary_mask'] > 0))
    valid_area = float(overlaps[valid].sum())
    value = float(np.sum(raw[valid] * .0001 * overlaps[valid]) / valid_area) if valid_area else None
    boundary_count = int(((overlaps > 0) & (overlaps < abs(dx*dy) * (1 - 1e-10))).sum())
    edge_budget = boundary_count * abs(float(dx*dy)) / 256
    return {'value': value, 'unit': '1', 'valid_area_m2': valid_area,
            'valid_area_fraction': valid_area / exact_area, 'region_area_m2': exact_area,
            'sample_coordinate_convention': coordinate_convention,
            'sampled_pixels': int(math.prod(shape)), 'intersecting_pixels': int((overlaps > 0).sum()),
            'valid_intersecting_pixels': int((valid & (overlaps > 0)).sum()),
            'all_pixel_intersection_area_m2': covered,
            'geometry_area_relative_error': float(target.area/exact_area - 1),
            'boundary_pixels': boundary_count,
            'one_quantization_step_per_boundary_pixel_area_budget_m2': edge_budget,
            'one_quantization_step_coverage_budget': edge_budget / exact_area,
            'native_pixel_area_m2': abs(float(dx*dy)),
            'method': 'Local raw QA, one scale factor, densified sinusoidal equal-area polygon intersections; no EE regional reducer'}


def compare_export(local, csv_path, region_id, month):
    """Report numerical discrepancies without clipping coverage or promoting QA."""
    import pandas as pd
    path = Path(csv_path)
    frame = pd.read_csv(path, dtype={'unit': str})
    dates = pd.to_datetime(frame.date, errors='raise', utc=True).dt.strftime('%Y-%m-%d')
    rows = frame[(frame.region_id == region_id) & (dates == month) & (frame.variable == 'ndvi')]
    if len(rows) != 1:
        raise ValueError('Comparison CSV must contain exactly one matching cell/month NDVI row')
    row = rows.iloc[0]
    if row.unit != '1' or row.source != 'MOD13A3.061':
        raise ValueError('Comparison requires unconverted MOD13A3.061 NDVI unit1')
    def number(value):
        return float(value) if pd.notna(value) and math.isfinite(float(value)) else None
    exported = {key: number(row[key]) for key in ('value', 'valid_area_m2', 'valid_area_fraction', 'region_area_m2')}
    differences = {key: exported[key] - local[key] if exported[key] is not None and local[key] is not None else None for key in exported}
    coverage = exported['valid_area_fraction']
    area_difference = differences['valid_area_m2']
    edge_budget = local['one_quantization_step_per_boundary_pixel_area_budget_m2']
    return {'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'exported': exported, 'export_minus_local': differences,
            'coverage_exceeds_one': coverage is not None and coverage > 1,
            'coverage_below_zero': coverage is not None and coverage < 0,
            'area_difference_exceeds_boundary_quantization_budget': abs(area_difference) > edge_budget if area_difference is not None else None,
            'boundary_quantization_area_budget_m2': edge_budget,
            'status': 'review_required',
            'note': 'Any coverage above1 remains flagged. Pixel-fraction quantization may explain small edge differences; percent-level excess requires investigation, not clipping.'}


def verify(ee, project, region_id, month, *, raw_output=None):
    """One bounded read with existing OAuth; caller explicitly opts in."""
    bbox = cell_bbox(*parse_cell_id(region_id))
    _geometry(bbox)
    ee.Initialize(project=project)
    ee.data.setDeadline(30000)
    ee.data.setMaxRetries(0)
    asset = 'MODIS/061/MOD13A3/' + month.replace('-', '_')
    image = ee.Image(asset)
    raw = image.select('NDVI')
    detailed, summary = image.select('DetailedQA'), image.select('SummaryQA')
    projection = raw.projection()
    stack = raw.toInt32().unmask(-32768).addBands(detailed.toInt32().unmask(-32768)).addBands(summary.toInt32().unmask(-32768))
    stack = stack.addBands(raw.mask().unmask(0).rename('ndvi_mask')).addBands(detailed.mask().unmask(0).rename('detailed_mask')).addBands(summary.mask().unmask(0).rename('summary_mask'))
    stack = stack.addBands(ee.Image.pixelCoordinates(projection).rename(['pixel_x','pixel_y'])).reproject(projection).toDouble().unmask(-32768, False)
    west, south, east, north = bbox
    # Margin ensures every pixel touching the target is returned, including edges.
    region = ee.Geometry.Rectangle([west-.02, south-.02, east+.02, north+.02], None, False)
    # Every band is already unmasked; omit defaultValue to avoid inferred mask-band type ranges.
    sample = stack.sampleRectangle(region=region, properties=[])
    payload = ee.Dictionary({'sample': sample.toDictionary(), 'projection': {'crs': projection.crs(), 'transform': projection.transform()}}).getInfo()
    snapshot = {'region_id': region_id, 'month': month, 'bbox': bbox,
                'source_asset_id': asset, 'projection': payload['projection'], 'sample': payload['sample']}
    if raw_output:
        path = Path(raw_output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snapshot, allow_nan=False) + '\n')
    return {**snapshot, 'local': summarize_pixels(payload['sample'], payload['projection'], bbox)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--verify', action='store_true')
    mode.add_argument('--sample-json', type=Path, help='Replay an archived raw sample offline')
    parser.add_argument('--raw-output', type=Path, help='Archive server response before local processing')
    parser.add_argument('--project', default=DEFAULT_PROJECT)
    parser.add_argument('--region', default=DEFAULT_REGION)
    parser.add_argument('--month', default='2003-01-01')
    parser.add_argument('--csv', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    parsed = date.fromisoformat(args.month)
    if parsed.day != 1:
        parser.error('--month must be a first-of-month ISO date')
    bbox = cell_bbox(*parse_cell_id(args.region))
    if not args.verify and not args.sample_json:
        result = {'mode': 'dry_plan', 'region_id': args.region, 'bbox': bbox, 'month': args.month,
                  'project': args.project, 'network_calls': 0,
                  'method': 'Native raw pixel arrays + local QA/scaling + explicit sinusoidal pixel/target intersections',
                  'status': 'Source-pixel verification has not run. --verify uses existing OAuth and one bounded data read.'}
    else:
        if args.sample_json:
            snapshot = json.loads(args.sample_json.read_text())
            if snapshot.get('region_id') != args.region or snapshot.get('month') != args.month or snapshot.get('bbox') != bbox:
                parser.error('Archived sample identity must match requested region/month/boundary')
            verification = {**snapshot, 'local': summarize_pixels(snapshot['sample'], snapshot['projection'], bbox)}
        else:
            import ee
            raw_output = args.raw_output or (args.output.with_suffix('.pixels.json') if args.output else None)
            verification = verify(ee, args.project, args.region, args.month, raw_output=raw_output)
        result = {'mode': 'offline_replay' if args.sample_json else 'verified_read', 'region_id': args.region, 'bbox': bbox, 'month': args.month,
                  'processed_at_utc': datetime.now(timezone.utc).isoformat(), **verification,
                  'qa_reviewed': False, 'status': 'independent_consistency_review_required'}
        if args.csv:
            result['comparison'] = compare_export(result['local'], args.csv, args.region, args.month)
    rendered = json.dumps(result, indent=2, allow_nan=False) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered)


if __name__ == '__main__':
    main()
