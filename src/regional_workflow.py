"""B → A → C backend handoff for the human-owned frontend.

Loading stored numbers never triggers network research. A caller starts research
explicitly after selection and owns asynchronous scheduling and stale responses.
"""
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REGIONAL = ROOT / 'data/processed/regional'


def load_region(region_id: str, *, directory=REGIONAL) -> dict:
    """Return stored observations, geometry, screening and research context."""
    directory = Path(directory)
    catalog_bytes = (directory / 'catalog.json').read_bytes()
    catalog = json.loads(catalog_bytes)
    feature = next((f for f in catalog['features']
                    if f['properties']['region_id'] == region_id), None)
    if feature is None:
        raise ValueError(f'Unknown regional ID: {region_id!r}')
    csv_bytes = (directory / 'monthly_timeseries.csv').read_bytes()
    csv_hash = hashlib.sha256(csv_bytes).hexdigest()
    catalog_hash = hashlib.sha256(catalog_bytes).hexdigest()
    observations = pd.read_csv(BytesIO(csv_bytes), dtype={'unit': str})
    observations = observations.loc[observations.region_id == region_id].copy()
    observations['date'] = pd.to_datetime(observations.date)
    provenance = json.loads((directory / 'metadata.json').read_text())
    # Source manifests and metadata bind research caching to the data release.
    digest = hashlib.sha256()
    digest.update(csv_hash.encode())
    digest.update(catalog_hash.encode())
    for name in ('metadata.json', 'source_manifest.json', 'modis_source_manifest.json'):
        path = directory / name
        if path.exists():
            digest.update(name.encode())
            digest.update(path.read_bytes())
    screening_path = directory / 'screening.json'
    record = None
    screening_status = 'not_built'
    if screening_path.exists():
        screening = json.loads(screening_path.read_text())
        if (screening.get('source_csv_sha256') == csv_hash
                and screening.get('source_catalog_sha256') == catalog_hash):
            record = next((r for r in screening['regions'] if r['region_id'] == region_id), None)
            screening_status = 'current'
        else:
            screening_status = 'stale_rebuild_required'
    props = feature['properties']
    return {'region_id': region_id, 'feature': deepcopy(feature),
            'observations': observations, 'provenance': provenance,
            'screening': record, 'screening_status': screening_status,
            'research_context': {'region_id': region_id, 'bbox': props['bbox'],
                'jurisdictions': deepcopy(props.get('jurisdictions', [])),
                'dataset_version': digest.hexdigest(),
                'period': ['2003-01-01', '2024-12-31']}}


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
