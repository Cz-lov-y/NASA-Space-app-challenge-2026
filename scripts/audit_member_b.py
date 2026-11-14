#!/usr/bin/env python3
"""Check export checksums and independently recompute seasonal GLDAS means."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/processed/global_combined/validation_report.json'


def main():
    combined = pd.read_csv(ROOT / 'data/processed/global_combined/monthly_timeseries.csv')
    manifests = ['data/processed/global_combined/modis_source_manifest.json', 'data/processed/global_gldas/source_manifest.json']
    counts = {}
    for name in manifests:
        entries = json.loads((ROOT / name).read_text())
        for entry in entries:
            path = ROOT / entry['file']
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                raise ValueError(f'Checksum mismatch: {path}')
        counts[name] = len(entries)
    checks = []
    for month in ('2003-01', '2003-04', '2003-07', '2003-10', '2014-01', '2014-07', '2024-01', '2024-07'):
        p = next((ROOT / 'data/raw/gldas').glob(f'*A{month.replace("-", "")}.*nc4'))
        with xr.open_dataset(p, mask_and_scale=True) as ds:
            arr = [ds[name].isel(time=0).transpose('lat','lon').values.astype(float) for name in ('SoilMoi0_10cm_inst','SoilMoi10_40cm_inst','SoilMoi40_100cm_inst')]
            weights = np.broadcast_to(np.cos(np.deg2rad(ds.lat.values.astype(float)))[:,None], arr[0].shape)
            negatives = [int(np.sum(np.isfinite(a) & (a < 0))) for a in arr]
            for var, values in [('soil_water_0_10cm',arr[0]), ('soil_water_0_100cm',arr[0]+arr[1]+arr[2])]:
                valid = np.isfinite(values)
                independent = float(np.average(values[valid], weights=weights[valid]))
                row = combined[(combined.date == month+'-01') & (combined.variable == var)].iloc[0]
                delta = abs(independent - row.value)
                if delta > 1e-8: raise ValueError(f'Mean mismatch: {month} {var}: {delta}')
                checks.append({'month':month,'variable':var,'mean':independent,'absolute_difference':delta,'negative_cells_by_layer':negatives})
    ndvi = combined[(combined.variable == 'ndvi') & combined.value.notna()]
    result = {'manifest_files_verified':counts, 'gldas_independent_seasonal_checks':checks,
              'modis_export_checks':{'valid_months':len(ndvi),'ndvi_min':float(ndvi.value.min()),'ndvi_max':float(ndvi.value.max()),'coverage_min':float(ndvi.valid_area_fraction.min()),'coverage_max':float(ndvi.valid_area_fraction.max())},
              'limitations':['Checksum checks establish consistency with stored manifests, not authenticity.', 'GLDAS checks cover eight selected months, not comprehensive scientific validation.', 'MODIS checks use exported aggregates; no independent source-pixel validation or footprint overlap measurement has been performed.']}
    OUT.write_text(json.dumps(result,indent=2)+'\n')
    print(f'Verified {sum(counts.values())} input checksums, {len(checks)} GLDAS means and {len(ndvi)} MODIS aggregate rows.')

if __name__ == '__main__': main()
