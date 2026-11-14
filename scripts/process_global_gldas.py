#!/usr/bin/env python3
"""Audit monthly GLDAS subsets and compute whole-Earth area-weighted soil water."""
from pathlib import Path
import hashlib
import json
import re
import numpy as np
import pandas as pd
import xarray as xr
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/gldas'
OUT = ROOT / 'data/processed/global_gldas'
LAYERS = ('SoilMoi0_10cm_inst', 'SoilMoi10_40cm_inst', 'SoilMoi40_100cm_inst')
RADIUS = 6371007.181
EARTH_AREA = 4 * np.pi * RADIUS**2


def summarize(values, weights):
    valid = np.isfinite(values)
    area = float(np.where(valid, weights, 0).sum())
    mean = float(np.where(valid, values, 0).__mul__(weights).sum() / area) if area else np.nan
    return mean, area / EARTH_AREA, bool(np.any(values[valid] < 0))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(RAW.glob('*.nc4'))
    by_month = {}
    manifest = []
    for p in files:
        match = re.fullmatch(r'GLDAS_NOAH025_M\.2\.1_GLDAS_NOAH025_M\.A(\d{6})\.021_subsetted\.nc4', p.name)
        if not match:
            raise ValueError(f'Unexpected source filename: {p}')
        month = pd.to_datetime(match.group(1), format='%Y%m')
        if month in by_month:
            raise ValueError(f'Duplicate source month: {month}')
        with xr.open_dataset(p, mask_and_scale=True) as ds:
            if ds.sizes.get('time') != 1 or pd.Timestamp(ds.time.values[0]) != month:
                raise ValueError(f'Time mismatch: {p}')
            if not all(k in ds for k in LAYERS):
                raise ValueError(f'Missing layer: {p}')
            lat, lon = ds.lat.values, ds.lon.values
            if (lat.shape != (600,) or lon.shape != (1440,) or
                not np.allclose(lat, np.arange(600)*.25-59.875, atol=1e-5) or
                not np.allclose(lon, np.arange(1440)*.25-179.875, atol=1e-5)):
                raise ValueError(f'Unexpected grid: {p}')
            arrays = []
            for name in LAYERS:
                v = ds[name]
                if v.attrs.get('units') != 'kg m-2' or v.attrs.get('cell_methods') != 'time: mean':
                    raise ValueError(f'Unexpected units or time method: {p} {name}')
                if v.encoding.get('scale_factor', 1) != 1 or v.encoding.get('add_offset', 0) != 0:
                    raise ValueError(f'Unexpected scale: {p} {name}')
                arrays.append(np.asarray(v.isel(time=0).transpose('lat','lon').values, dtype=float))
            lat_r = np.deg2rad(lat.astype(float))
            delta = np.deg2rad(.125)
            row_areas = RADIUS**2 * np.deg2rad(.25) * (np.sin(lat_r+delta)-np.sin(lat_r-delta))
            weights = np.broadcast_to(row_areas[:, None], arrays[0].shape)
            surface = arrays[0]
            total = arrays[0] + arrays[1] + arrays[2]
            by_month[month] = (summarize(surface, weights), summarize(total, weights))
        manifest.append({'file':str(p.relative_to(ROOT)), 'month':month.strftime('%Y-%m-%d'), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    rows = []
    for month in pd.date_range('2003-01-01','2026-11-01',freq='MS'):
        for idx, variable in enumerate(('soil_water_0_10cm','soil_water_0_100cm')):
            item = by_month.get(month)
            value, coverage, negative = item[idx] if item else (np.nan, np.nan, False)
            flag = 'missing' if item is None else ('no_valid_pixels' if not np.isfinite(value) else ('negative_value' if negative else 'coverage_review_required'))
            rows.append({'date':month.strftime('%Y-%m-%d'), 'region_id':'whole_earth', 'variable':variable, 'value':value, 'unit':'kg m-2', 'source':'GLDAS_NOAH025_M.2.1', 'valid_area_fraction':coverage, 'quality_flag':flag})
    table = pd.DataFrame(rows)
    table.to_csv(OUT/'monthly_timeseries.csv',index=False)
    reports=[]
    for variable, group in table.groupby('variable',sort=False):
        reports.append({'variable':variable,'expected_months':len(group),'valid_months':int(group.value.notna().sum()),'missing_months':int(group.value.isna().sum()), 'missing_dates':';'.join(group.loc[group.value.isna(),'date']), 'min_coverage':group.valid_area_fraction.min(),'mean_coverage':group.valid_area_fraction.mean(),'max_coverage':group.valid_area_fraction.max(),'flag_counts':json.dumps(group.quality_flag.value_counts().to_dict(),sort_keys=True),'min_value':group.value.min(),'max_value':group.value.max()})
    pd.DataFrame(reports).to_csv(OUT/'quality_report.csv',index=False)
    (OUT/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    fig, ax=plt.subplots(figsize=(12,4))
    for variable, group in table.groupby('variable',sort=False):
        ax.plot(pd.to_datetime(group.date), group.value, label=variable)
    ax.set(ylabel='Soil water storage (kg m-2)',title='GLDAS monthly global land-model means')
    ax.legend(); fig.tight_layout(); fig.savefig(OUT/'soil_water_timeseries.png',dpi=150); plt.close(fig)
    print(pd.DataFrame(reports).to_string(index=False))
    print(f'Audited {len(files)} files; available months {min(by_month):%Y-%m} to {max(by_month):%Y-%m}.')

if __name__ == '__main__':
    main()
