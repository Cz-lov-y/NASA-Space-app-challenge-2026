"""Serve bounded native-cell releases through the existing scientific contract."""
import json
from pathlib import Path

from src.fine_grid import parse_cell_id
from src.regional_workflow import ROOT, load_region

FINE = ROOT / 'data/processed/fine/central_us'


def load_fine_region(region_id, *, directory=FINE):
    parse_cell_id(region_id)
    bundle = load_region(region_id, directory=directory)
    bundle['provenance']['resolution_notice'] = (
        'Original 0.25-degree GLDAS model cell. Consult paired screening for MODIS availability. '
        'This tile is a coverage pilot, not worldwide fine-resolution screening.')
    return bundle


def fine_map(*, directory=FINE):
    from src.regional_api import _file_digest
    directory = Path(directory)
    payload = json.loads((directory / 'map_screening.geojson').read_text())
    if (payload['source_csv_sha256'] != _file_digest(directory / 'monthly_timeseries.csv')
            or payload['source_catalog_sha256'] != _file_digest(directory / 'catalog.json')):
        raise ValueError('Fine release requires screening rebuild')
    return payload
