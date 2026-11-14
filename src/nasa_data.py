"""B -> A time series reader for explicitly identified real and demo data."""
import json
from pathlib import Path

import pandas as pd
from src.preprocessing import validate_timeseries

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT / 'data/sample/demo_timeseries.csv'
CATALOG = ROOT / 'data/processed/series_metadata.json'


def get_timeseries(region: str, variable: str) -> pd.DataFrame:
    """Return one series with missing months, QA flags and provenance intact."""
    if region == 'demo-region':
        frame = pd.read_csv(SAMPLE_PATH, dtype={'unit': str})
        subset = frame[(frame.region_id == region) & (frame.variable == variable)]
        if subset.empty:
            raise ValueError(f'No demo timeseries for region={region!r}, variable={variable!r}')
        result = validate_timeseries(subset)
        result.attrs['metadata'] = {
            'spatial_coverage': 'Fictional demo region; no geographic boundary',
            'time_range': {'start': result.date.min().strftime('%Y-%m-%d'), 'end': result.date.max().strftime('%Y-%m-%d')},
            'temporal_resolution': 'Synthetic demo observations; not a complete monthly series',
            'dataset_version': 'SYNTHETIC_DEMO',
            'quality_control': 'Synthetic values; no NASA quality assessment',
        }
        return result
    catalog = json.loads(CATALOG.read_text())
    entry = catalog.get(region, {}).get(variable)
    if entry is None and region.startswith('grid_r'):
        from src.regional_workflow import load_region
        bundle = load_region(region)
        subset = bundle['observations']
        subset = subset[subset.variable == variable]
        if subset.empty:
            raise ValueError(f'No timeseries for region={region!r}, variable={variable!r}')
        result = validate_timeseries(subset, allow_missing=True)
        if result.date.dt.to_period('M').duplicated().any():
            raise ValueError('Duplicate monthly observations')
        if any(result[col].nunique() != 1 for col in ('unit', 'source', 'variable', 'region_id')):
            raise ValueError('Mixed source, unit, variable or region')
        provenance = bundle['provenance']
        props = bundle['feature']['properties']
        result.attrs['metadata'] = {
            **provenance,
            'spatial_coverage': {'bbox': props['bbox'], 'crs': 'EPSG:4326',
                'geometry': bundle['feature']['geometry'],
                'aggregation': provenance.get('modis', {}).get('aggregation') if variable == 'ndvi' else provenance.get('aggregation'),
                'native_resolution': provenance.get('native_resolution_degrees') if variable != 'ndvi' else 'MODIS sinusoidal approximately 1 km'},
            'time_range': {'start': result.date.min().strftime('%Y-%m-%d'), 'end': result.date.max().strftime('%Y-%m-%d')},
            'temporal_resolution': 'monthly regional area-weighted mean',
            'dataset_version': 'MOD13A3.061' if variable == 'ndvi' else provenance['dataset_version'],
            'quality_control': {'status': 'scientific review pending',
                'rules': provenance.get('modis', {}).get('qa') if variable == 'ndvi' else provenance['quality_rules'],
                'missing_values': 'NaN; no imputation'},
        }
        return result
    if entry is None:
        raise ValueError(f'No timeseries for region={region!r}, variable={variable!r}')
    frame = pd.read_csv(ROOT / entry['csv'], dtype={'unit': str})
    subset = frame[(frame.region_id == region) & (frame.variable == variable)]
    if subset.empty:
        raise ValueError(f'No timeseries for region={region!r}, variable={variable!r}')
    result = validate_timeseries(subset, allow_missing=True)
    if result.date.dt.to_period('M').duplicated().any():
        raise ValueError('Duplicate monthly observations')
    if any(result[col].nunique() != 1 for col in ('unit', 'source', 'variable', 'region_id')):
        raise ValueError('Mixed source, unit, variable or region')
    result.attrs['metadata'] = entry['metadata']
    return result
