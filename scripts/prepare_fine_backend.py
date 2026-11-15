#!/usr/bin/env python3
"""Build statistics for the explicitly bounded fine pilot; no network calls."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
from io import BytesIO
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pandas as pd
from src.regional_statistics import build_regional_screening, build_screening_summary


def prepare(directory):
    directory = Path(directory)
    catalog_bytes = (directory / 'catalog.json').read_bytes()
    csv_bytes = (directory / 'monthly_timeseries.csv').read_bytes()
    catalog = json.loads(catalog_bytes)
    frame = pd.read_csv(BytesIO(csv_bytes), dtype={'unit': str})
    report = build_regional_screening(frame, catalog)
    report['source_csv_sha256'] = hashlib.sha256(csv_bytes).hexdigest()
    report['source_catalog_sha256'] = hashlib.sha256(catalog_bytes).hexdigest()
    report['multiple_testing']['scope'] = 'Only this frozen fine pilot catalog; never a worldwide or coarse-grid family.'
    identity={'regions':sorted(f['properties']['region_id'] for f in catalog['features']),
              'period':['2003-01-01','2024-12-31'],'variables':['ndvi','soil_water_0_100cm'],
              'grid':'gldas025'}
    report['multiple_testing']['family_id']='fine-pilot-'+hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    report['limitations'].append('Fine pilot only; neighboring native model cells may be spatially dependent. Worldwide fine coverage remains pending.')
    summary = build_screening_summary(report)
    for feature in summary['features']:
        feature['properties']['native_resolution_degrees'] = 0.25
    if (csv_bytes != (directory/'monthly_timeseries.csv').read_bytes()
            or catalog_bytes != (directory/'catalog.json').read_bytes()):
        raise ValueError('Fine inputs changed during processing; retry on a stable release')
    for name, payload in (('screening.json', report), ('map_screening.geojson', summary)):
        temporary = directory/(name+'.tmp')
        temporary.write_text(json.dumps(payload, indent=2, allow_nan=False)+'\n')
        temporary.replace(directory/name)
    return {'cells': len(catalog['features']), 'rows': len(frame),
            'finite_observations': int(frame.value.notna().sum()),
            'paired_eligible_cells': report['multiple_testing']['eligible_regions'],
            'testing_scope': report['multiple_testing']['scope']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=ROOT/'data/processed/fine/central_us')
    print(json.dumps(prepare(parser.parse_args().directory)))
