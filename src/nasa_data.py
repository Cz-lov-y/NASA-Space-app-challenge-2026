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
