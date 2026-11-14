#!/usr/bin/env python3
"""Produce the documented 2003–2024 central-US GLDAS integration sample."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/processed/gldas_integration'
OUT.mkdir(parents=True, exist_ok=True)
VAR = 'SoilMoi0_10cm_inst'
rows, sources = [], []
for date in pd.date_range('2003-01-01', '2024-12-01', freq='MS'):
    matches = sorted((ROOT / 'data/raw/gldas').glob(f'*A{date:%Y%m}.*_subsetted.nc4'))
    if len(matches) > 1:
        raise ValueError(f'duplicate sources for {date}')
    row = dict(date=date.strftime('%Y-%m-%d'), value=np.nan, unit='kg m-2', variable='soil_water_0_10cm', source='GLDAS_NOAH025_M.2.1', region_id='central_us_sample', valid_area_fraction=np.nan, quality_flag='missing')
    if matches:
        p = matches[0]
        with xr.open_dataset(p, mask_and_scale=True) as ds:
            if pd.Timestamp(ds.time.values[0]) != date or ds.sizes['time'] != 1:
                raise ValueError(f'incorrect time {p}')
            if ds[VAR].attrs.get('units') != 'kg m-2' or ds[VAR].attrs.get('cell_methods') != 'time: mean':
                raise ValueError(f'unexpected units or time method {p}')
            if ds[VAR].encoding.get('scale_factor', 1) != 1 or ds[VAR].encoding.get('add_offset', 0) != 0:
                raise ValueError(f'unexpected scaling {p}')
            a = ds[VAR].sel(lat=slice(35,45), lon=slice(-100,-90)).isel(time=0).transpose('lat','lon')
            lat, lon = a.lat.values, a.lon.values
            if len(lat) != 40 or len(lon) != 40 or not np.allclose(np.diff(lat),.25) or not np.allclose(np.diff(lon),.25):
                raise ValueError(f'unexpected grid {p}')
            values = a.values.astype(float)
            weights = np.broadcast_to(np.cos(np.deg2rad(lat))[:,None], values.shape)
            valid = np.isfinite(values)
            fraction = float(weights[valid].sum()/weights.sum())
            value = float(np.sum(values[valid]*weights[valid])/weights[valid].sum()) if valid.any() else np.nan
            flag = 'missing' if not valid.any() else ('negative_value' if np.any(values[valid]<0) else ('low_coverage' if fraction < .8 else 'good'))
            row.update(value=value, valid_area_fraction=fraction, quality_flag=flag)
        sources.append({'file':str(p.relative_to(ROOT)), 'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    rows.append(row)
df=pd.DataFrame(rows)
df.to_csv(OUT/'monthly_timeseries.csv',index=False)
report = pd.DataFrame([{'expected_months':len(df),'valid_months':int(df.value.notna().sum()),'missing_months':int(df.value.isna().sum()),'missing_month_list':';'.join(df.loc[df.value.isna(),'date']), 'missing_percent':float(df.value.isna().mean()*100), 'min_valid_area_fraction':df.valid_area_fraction.min(), 'mean_valid_area_fraction':df.valid_area_fraction.mean(), 'max_valid_area_fraction':df.valid_area_fraction.max(), 'quality_flag_counts':json.dumps(df.quality_flag.value_counts().to_dict(),sort_keys=True), 'minimum_value_kg_m-2':df.value.min(),'maximum_value_kg_m-2':df.value.max()}])
report.to_csv(OUT/'quality_report.csv',index=False)
(OUT/'source_manifest.json').write_text(json.dumps(sources,indent=2)+'\n')
print(report.to_string(index=False))
