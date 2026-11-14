#!/usr/bin/env python3
"""Process AppEEARS monthly GeoTIFF triplets and gridded GLDAS NetCDF files."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from pyproj import CRS, Transformer
from rasterio.transform import rowcol
from shapely.geometry import box, shape
from shapely.ops import transform, unary_union
import xarray as xr

MONTHS = pd.date_range('2003-01-01', '2024-12-01', freq='MS')
LAYERS = ['SoilMoi0_10cm_inst', 'SoilMoi10_40cm_inst', 'SoilMoi40_100cm_inst']


def region_geometry(path):
    doc = json.loads(Path(path).read_text())
    if doc.get('crs') and 'CRS84' not in str(doc['crs']) and '4326' not in str(doc['crs']):
        raise ValueError('Region GeoJSON must use WGS84 longitude/latitude')
    if doc['type'] == 'FeatureCollection':
        geom = unary_union([shape(f['geometry']) for f in doc['features']])
    else:
        geom = shape(doc['geometry'] if doc['type'] == 'Feature' else doc)
    if geom.is_empty or not geom.is_valid or geom.geom_type not in ('Polygon', 'MultiPolygon'):
        raise ValueError('Region must be a valid nonempty Polygon or MultiPolygon')
    minx, miny, maxx, maxy = geom.bounds
    if minx < -180 or maxx > 180 or miny < -90 or maxy > 90 or maxx - minx > 180:
        raise ValueError('Unsupported coordinates or antimeridian-crossing region')
    center = geom.representative_point()
    equal_area = CRS.from_proj4(f'+proj=laea +lat_0={center.y} +lon_0={center.x} +datum=WGS84 +units=m')
    return geom, equal_area


def weights(region, equal_area, crs, affine, height, width):
    """Intersect pixel polygons with region in a local equal-area CRS."""
    to_grid = Transformer.from_crs('EPSG:4326', crs, always_xy=True).transform
    to_area = Transformer.from_crs(crs, equal_area, always_xy=True).transform
    reg_grid = transform(to_grid, region)
    reg_area = transform(Transformer.from_crs('EPSG:4326', equal_area, always_xy=True).transform, region)
    if affine.b != 0 or affine.d != 0:
        raise ValueError('Rotated grids are not supported')
    minx, miny, maxx, maxy = reg_grid.bounds
    rows, cols = zip(*(rowcol(affine, x, y) for x in (minx, maxx) for y in (miny, maxy)))
    result = np.zeros((height, width), dtype=float)
    for r in range(max(0, min(rows)-1), min(height, max(rows)+2)):
        for c in range(max(0, min(cols)-1), min(width, max(cols)+2)):
            x1, y1 = affine * (c, r)
            x2, y2 = affine * (c+1, r+1)
            pixel = box(min(x1,x2), min(y1,y2), max(x1,x2), max(y1,y2))
            if pixel.intersects(reg_grid):
                result[r,c] = transform(to_area, pixel).intersection(reg_area).area
    return result, reg_area.area


def aggregate(values, valid, w, area):
    mask = valid & np.isfinite(values) & (w > 0)
    covered = w[mask].sum()
    return (float(np.sum(values[mask] * w[mask]) / covered) if covered else np.nan,
            min(1.0, float(covered / area)))


def modis(manifest, region, equal_area):
    table = pd.read_csv(manifest, dtype=str).fillna('')
    required = {'date', 'ndvi', 'vi_quality', 'pixel_reliability', 'scale'}
    if not required.issubset(table.columns):
        raise ValueError(f'MODIS manifest requires columns {sorted(required)}')
    result = {}
    for _, item in table.iterrows():
        date = pd.Timestamp(item.date).to_period('M').to_timestamp()
        if date in result:
            raise ValueError(f'Duplicate MODIS month: {date}')
        if item['scale'] not in ('raw', 'scaled'):
            raise ValueError('MODIS scale must be explicitly raw or scaled')
        paths = [Path(manifest).parent / item[k] for k in ('ndvi','vi_quality','pixel_reliability')]
        with rasterio.open(paths[0]) as a, rasterio.open(paths[1]) as b, rasterio.open(paths[2]) as c:
            if a.crs is None or any((x.crs != a.crs or x.transform != a.transform or x.shape != a.shape or x.count != 1) for x in (b,c)) or a.count != 1:
                raise ValueError(f'MODIS layers must be aligned single-band rasters: {date}')
            ndvi, qa, reliability = (x.read(1, masked=True) for x in (a,b,c))
            w, area = weights(region, equal_area, a.crs, a.transform, a.height, a.width)
            v = np.asarray(ndvi.filled(np.nan), dtype=float) if np.issubdtype(ndvi.dtype, np.floating) else ndvi.astype(float).filled(np.nan)
            if item['scale'] == 'raw':
                v *= 0.0001
            q = qa.filled(65535).astype(np.uint16)
            valid = (~np.ma.getmaskarray(ndvi) & ~np.ma.getmaskarray(qa) & ~np.ma.getmaskarray(reliability)
                     & (q != 65535) & ((q & 3) == 0) & (reliability.filled(-1) == 0)
                     & (v >= -0.2) & (v <= 1.0))
            result[date] = aggregate(v, valid, w, area)
    return result


def gldas(files, region, equal_area):
    from rasterio.transform import from_origin
    result = {}
    for filename in files:
        with xr.open_dataset(filename, mask_and_scale=True) as ds:
            if not all(k in ds for k in LAYERS):
                raise ValueError(f'{filename}: missing one or more GLDAS layers')
            latname = 'lat' if 'lat' in ds.coords else 'latitude'
            lonname = 'lon' if 'lon' in ds.coords else 'longitude'
            if latname not in ds.coords or lonname not in ds.coords or 'time' not in ds.coords:
                raise ValueError(f'{filename}: expected time, latitude and longitude coordinates')
            ds = ds.sortby(latname, ascending=False).sortby(lonname)
            lat, lon = ds[latname].values, ds[lonname].values
            if len(lat) < 2 or len(lon) < 2 or not np.allclose(np.diff(lat), -0.25) or not np.allclose(np.diff(lon), 0.25):
                raise ValueError('Expected regular 0.25 degree GLDAS grid with at least two cells per axis')
            if np.max(lon) > 180 or np.min(lon) < -180:
                raise ValueError('GLDAS longitude must use -180 to 180 convention')
            for layer in LAYERS:
                units = ds[layer].attrs.get('units', '').replace(' ', '').replace('**','^')
                if units not in ('kg/m2', 'kgm-2', 'kgm^-2', 'kg/m^2'):
                    raise ValueError(f'{filename}: unexpected or missing units for {layer}: {units!r}')
            affine = from_origin(float(lon[0])-0.125, float(lat[0])+0.125, 0.25, 0.25)
            w, area = weights(region, equal_area, 'EPSG:4326', affine, len(lat), len(lon))
            for index, time in enumerate(ds.time.values):
                date = pd.Timestamp(time).to_period('M').to_timestamp()
                if date in result:
                    raise ValueError(f'Duplicate GLDAS month: {date}')
                arrays = [np.asarray(ds[k].isel(time=index).transpose(latname, lonname).values, dtype=float) for k in LAYERS]
                surface = arrays[0]
                total = arrays[0] + arrays[1] + arrays[2]
                result[date] = (aggregate(surface, np.isfinite(surface), w, area),
                                aggregate(total, np.logical_and.reduce([np.isfinite(x) for x in arrays]), w, area))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--region', required=True, help='WGS84 GeoJSON boundary')
    p.add_argument('--region-id', required=True)
    p.add_argument('--modis-manifest', required=True)
    p.add_argument('--gldas', nargs='+', required=True, help='Gridded GLDAS monthly NetCDF files')
    p.add_argument('--output', default='data/processed')
    p.add_argument('--min-coverage', type=float, default=0.8)
    args = p.parse_args()
    if not 0 <= args.min_coverage <= 1:
        p.error('--min-coverage must be between 0 and 1')
    region, equal_area = region_geometry(args.region)
    vi = modis(args.modis_manifest, region, equal_area)
    sm = gldas(args.gldas, region, equal_area)
    rows = []
    for date in MONTHS:
        for variable, source, unit, item in [
            ('ndvi', 'MOD13A3.061', '1', vi.get(date)),
            ('soil_water_0_10cm', 'GLDAS_NOAH025_M.2.1', 'kg m-2', sm.get(date, (None,None))[0]),
            ('soil_water_0_100cm', 'GLDAS_NOAH025_M.2.1', 'kg m-2', sm.get(date, (None,None))[1]),
        ]:
            value, coverage = item if item is not None else (np.nan, np.nan)
            flag = 'missing' if not np.isfinite(value) else ('low_coverage' if coverage < args.min_coverage else 'good')
            rows.append(dict(date=date, region_id=args.region_id, variable=variable, value=value,
                             unit=unit, source=source, valid_area_fraction=coverage, quality_flag=flag))
    frame = pd.DataFrame(rows)
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out/'monthly_timeseries.csv', index=False, date_format='%Y-%m-%d', na_rep='')
    summary = []
    for var, group in frame.groupby('variable', sort=False):
        valid = group['value'].dropna(); coverage = group.valid_area_fraction.dropna()
        summary.append(dict(variable=var, expected_months=len(group), valid_months=len(valid), missing_percent=100*(1-len(valid)/len(group)), minimum=valid.min(), maximum=valid.max(), coverage_min=coverage.min(), coverage_median=coverage.median(), coverage_max=coverage.max(), low_coverage_months=int((group.quality_flag == 'low_coverage').sum()), suspicious_negative_months=int((valid < 0).sum()) if var.startswith('soil_') else 0))
    pd.DataFrame(summary).to_csv(out/'quality_report.csv', index=False, na_rep='')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    for var in ('ndvi', 'soil_water_0_100cm'):
        group = frame[frame.variable == var]
        fig, ax = plt.subplots(figsize=(12,4)); ax.plot(group.date, group.value, linewidth=1)
        ax.set(title=f'{args.region_id}: {var}', xlabel='Date', ylabel=group.unit.iloc[0]); fig.tight_layout()
        fig.savefig(out/f'{var}.png', dpi=150); plt.close(fig)
    print(f'Wrote {len(frame)} rows and quality report to {out}')


if __name__ == '__main__':
    main()
