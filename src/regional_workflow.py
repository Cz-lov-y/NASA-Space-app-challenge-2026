"""B → A → C backend handoff for the human-owned frontend.

Loading stored numbers never triggers network research. A caller starts research
explicitly after selection and owns asynchronous scheduling and stale responses.
"""
from copy import deepcopy
import hashlib
from io import BytesIO
from functools import lru_cache
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REGIONAL = ROOT / 'data/processed/regional'


def _signature(directory):
    names = ('catalog.json', 'monthly_timeseries.csv', 'metadata.json',
             'source_manifest.json', 'modis_source_manifest.json', 'screening.json')
    return tuple((name, path.stat().st_mtime_ns, path.stat().st_size)
                 for name in names if (path := directory / name).exists())


@lru_cache(maxsize=2)
def _read_release(directory, signature):
    """Read a release once per file revision; callers receive independent copies."""
    directory = Path(directory)
    catalog_bytes = (directory / 'catalog.json').read_bytes()
    catalog = json.loads(catalog_bytes)
    csv_bytes = (directory / 'monthly_timeseries.csv').read_bytes()
    csv_hash = hashlib.sha256(csv_bytes).hexdigest()
    catalog_hash = hashlib.sha256(catalog_bytes).hexdigest()
    frame = pd.read_csv(BytesIO(csv_bytes), dtype={'unit': str})
    frame['date'] = pd.to_datetime(frame.date)
    provenance = json.loads((directory / 'metadata.json').read_text())
    digest = hashlib.sha256()
    digest.update(csv_hash.encode())
    digest.update(catalog_hash.encode())
    for name in ('metadata.json', 'source_manifest.json', 'modis_source_manifest.json'):
        path = directory / name
        if path.exists():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    screening_path = directory / 'screening.json'
    records, status = {}, 'not_built'
    if screening_path.exists():
        screening = json.loads(screening_path.read_text())
        if (screening.get('source_csv_sha256') == csv_hash
                and screening.get('source_catalog_sha256') == catalog_hash):
            records = {r['region_id']: r for r in screening['regions']}
            status = 'current'
        else:
            status = 'stale_rebuild_required'
    if _signature(directory) != signature:
        raise ValueError('Regional release changed while loading; retry after processing finishes')
    return catalog, frame, provenance, digest.hexdigest(), records, status


def load_region(region_id: str, *, directory=REGIONAL) -> dict:
    """Return stored observations, geometry, screening and research context.

    Local snapshots are reused until a release file's size or nanosecond mtime
    changes. Callers may mutate returned objects without changing cached data.
    """
    directory = Path(directory).resolve()
    catalog, frame, provenance, version, records, status = _read_release(
        str(directory), _signature(directory))
    feature = next((f for f in catalog['features']
                    if f['properties']['region_id'] == region_id), None)
    if feature is None:
        raise ValueError(f'Unknown regional ID: {region_id!r}')
    props = feature['properties']
    return {'region_id': region_id, 'feature': deepcopy(feature),
            'observations': frame.loc[frame.region_id == region_id].copy(deep=True),
            'provenance': deepcopy(provenance),
            'screening': deepcopy(records.get(region_id)), 'screening_status': status,
            'research_context': {'region_id': region_id, 'bbox': deepcopy(props['bbox']),
                'jurisdictions': deepcopy(props.get('jurisdictions', [])),
                'dataset_version': version,
                'period': ['2003-01-01', '2024-12-31']}}


def export_region(bundle: dict) -> dict:
    """JSON-compatible dataset details for a region panel, without network access."""
    record = bundle.get('screening') or {}
    return {'schema_version': 'regional-detail-1', 'region_id': bundle['region_id'],
            'feature': deepcopy(bundle['feature']),
            'dataset_version': bundle['research_context']['dataset_version'],
            'screening_status': bundle['screening_status'],
            'screening': deepcopy(record.get('screening')),
            'paired_analysis': deepcopy(record.get('analysis')),
            'available_indicator_analysis': deepcopy(record.get('available_indicator_analysis')),
            'observations': json.loads(bundle['observations'].to_json(
                orient='records', date_format='iso', double_precision=15)),
            'provenance': deepcopy(bundle['provenance'])}


def research_selected_region(bundle: dict, **kwargs) -> dict:
    """Run C's optional workflow using A's stored analysis and B's context.

    Missing NDVI is disclosed; a qualitative jurisdiction brief cannot substitute
    for missing local measurements. kwargs accepts C's cache/provider settings.
    """
    from src.regional_research import research_region
    record = bundle.get('screening') or {}
    analysis = deepcopy(record.get('analysis') or record.get('available_indicator_analysis') or {
        'region': bundle['region_id'],
        'data_quality': {'qa_reviewed': False, 'synthetic_demo': False},
        'limitations': ['Paired regional statistical analysis is not available.'],
    })
    report = research_region(analysis, bundle['research_context'], **kwargs)
    if not record.get('analysis'):
        report['limitations'].append('Regional paired analysis is unavailable; any available single-indicator statistics are exploratory, and research provides jurisdiction context only.')
    return report
