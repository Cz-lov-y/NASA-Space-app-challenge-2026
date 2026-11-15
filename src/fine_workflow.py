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


TILE_INDEX = ROOT / 'data/processed/fine/tiles.json'
DEFAULT_TILE = 'central_us_1deg'


def _safe_directory(value, root):
    """Registry entries may reference only repository-local fine release paths."""
    path = Path(value)
    resolved = (Path(root)/path).resolve()
    allowed = (Path(root)/'data/processed/fine').resolve()
    if path.is_absolute() or not resolved.is_relative_to(allowed) or resolved == allowed:
        raise ValueError('Fine registry directory must be a local fine release')
    return resolved


def load_tile_index(*, index_path=TILE_INDEX, root=ROOT):
    """Validate the small frozen coverage registry; never materialize the globe."""
    from src.fine_grid import build_tile_catalog
    import re
    registry = json.loads(Path(index_path).read_text())
    if registry.get('schema_version') != 'fine-tiles-1' or not isinstance(registry.get('tiles'), list) or not 1 <= len(registry['tiles']) <= 64:
        raise ValueError('Invalid fine tile registry')
    _safe_directory(registry['collection_directory'], root)
    seen = set()
    previous = []
    for tile in registry['tiles']:
        tile_id = tile['id']
        if (not isinstance(tile_id,str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,63}',tile_id)
                or tile_id in seen or not isinstance(tile.get('name'),str) or not tile['name'].strip()):
            raise ValueError('Invalid or duplicate fine tile ID/name')
        seen.add(tile_id)
        _safe_directory(tile['directory'], root)
        bbox = tile['bbox']
        catalog = build_tile_catalog(bbox)
        west,south,east,north = bbox
        if west >= east or any(abs(v*4-round(v*4))>1e-9 for v in bbox):
            raise ValueError('Fine registry bboxes must align to native cells without crossing the dateline')
        for other in previous:
            if min(east,other[2])>max(west,other[0]) and min(north,other[3])>max(south,other[1]):
                raise ValueError('Frozen fine registry tiles overlap')
        previous.append(bbox)
        if not catalog['features']:
            raise ValueError('Fine registry tile contains no cells')
    return registry


def _tile(registry, tile_id):
    tile = next((t for t in registry['tiles'] if t['id']==tile_id),None)
    if tile is None:
        raise ValueError('Unknown fine tile ID')
    return tile


def _release_for_tile(registry, tile, root):
    collection = _safe_directory(registry['collection_directory'],root)
    # The map is a publication marker. After publication, a stale collection is
    # withheld rather than silently substituting an independent per-tile family.
    if (collection/'map_screening.geojson').is_file():
        return collection, 'joint_collection'
    return _safe_directory(tile['directory'],root), 'individual_tile_before_collection'



class FineCollectionStale(ValueError):
    """Published joint data must be rebuilt against current source tile files."""


def _validate_collection_inputs(directory, *, index_path, root):
    from src.regional_api import _file_digest
    import re
    try:
        registry=load_tile_index(index_path=index_path,root=root)
        manifest=json.loads((Path(directory)/'input_manifest.json').read_text())
        if manifest.get('schema_version')!='fine-collection-inputs-1':
            raise ValueError('Invalid collection manifest schema')
        records=manifest['files']
        if not isinstance(records,list) or not records:
            raise ValueError('Missing collection inputs')
        expected={}
        allowed=(Path(root)/'data/processed/fine').resolve()
        for record in records:
            name=Path(record['file'])
            path=(name if name.is_absolute() else Path(root)/name).resolve()
            digest=record['sha256']
            if (not path.is_relative_to(allowed) or path in expected
                    or not isinstance(digest,str) or not re.fullmatch('[a-f0-9]{64}',digest)
                    or not path.is_file() or _file_digest(path)!=digest):
                raise ValueError('Changed collection source input')
            expected[path]=digest
        index=Path(index_path).resolve()
        if expected.get(index)!=manifest['index_sha256']:
            raise ValueError('Unbound collection registry')
        indexed={t['id']:t for t in registry['tiles']}
        nested=manifest['tiles']
        if len(nested)!=len(indexed) or {t['id'] for t in nested}!=set(indexed):
            raise ValueError('Incomplete collection source tile list')
        required={'catalog.json','monthly_timeseries.csv','gldas_monthly_timeseries.csv','metadata.json','source_manifest.json'}
        optional={'modis_source_manifest.json','accepted_modis_observations.csv'}
        for tile in nested:
            canonical=indexed[tile['id']]
            if tile['directory']!=canonical['directory'] or not required.issubset(tile['files']):
                raise ValueError('Missing frozen tile inputs')
            source=_safe_directory(tile['directory'],root)
            for name,digest in tile['files'].items():
                if name not in required|optional or expected.get((source/name).resolve())!=digest:
                    raise ValueError('Unbound collection tile input')
            if any((source/name).exists() and name not in tile['files'] for name in optional):
                raise ValueError('New optional tile input requires collection rebuild')
    except (OSError,ValueError,KeyError,TypeError,AttributeError):
        raise FineCollectionStale('Fine collection source inputs changed; rebuild the joint collection') from None

def fine_tiles(*, index_path=TILE_INDEX, root=ROOT):
    """Small coverage index with current map readiness, without provider calls."""
    from copy import deepcopy
    registry = load_tile_index(index_path=index_path,root=root)
    result = deepcopy(registry)
    for tile in result['tiles']:
        release,kind = _release_for_tile(registry,tile,root)
        required = ('map_screening.geojson','screening.json','monthly_timeseries.csv','catalog.json','metadata.json')
        if not all((release/name).is_file() for name in required):
            tile['status'] = 'pending'
        else:
            try:
                registered_fine_map(tile['id'],index_path=index_path,root=root)
                tile['status'] = 'available'
            except (OSError,ValueError,KeyError,TypeError):
                tile['status'] = 'stale'
        tile['release_scope'] = kind
        tile['map_url'] = '/api/v1/fine-regions?tile_id='+tile['id']
    return result


def registered_fine_map(tile_id=DEFAULT_TILE, *, index_path=TILE_INDEX, root=ROOT):
    """Select a viewport from the frozen joint map without recomputing tests."""
    from copy import deepcopy
    from src.fine_grid import build_tile_catalog
    registry = load_tile_index(index_path=index_path,root=root)
    tile = _tile(registry,tile_id)
    release,kind = _release_for_tile(registry,tile,root)
    if kind=='joint_collection':
        _validate_collection_inputs(release,index_path=index_path,root=root)
    payload = fine_map(directory=release)
    expected = {f['id'] for f in build_tile_catalog(tile['bbox'])['features']}
    selected = [f for f in payload['features'] if f.get('id') in expected]
    if {f.get('id') for f in selected} != expected or len(selected)!=len(expected):
        raise ValueError('Fine collection does not cover every frozen tile cell')
    payload['features'] = selected
    payload['viewport'] = {'tile_id':tile_id,'name':tile['name'],'bbox':deepcopy(tile['bbox']),
        'feature_count':len(selected),'release_scope':kind,'selection_only':True,
        'family_regions':payload['multiple_testing']['catalog_regions']}
    # Family size, corrected tests, settings, hashes and limitations are retained
    # verbatim from the complete collection; filtering only changes geometry sent.
    return payload


def load_registered_fine_region(region_id, *, index_path=TILE_INDEX, root=ROOT):
    """Locate a native cell's registered tile and load its joint-family detail."""
    from copy import deepcopy
    from src.fine_grid import cell_bbox
    bbox = cell_bbox(*parse_cell_id(region_id))
    registry = load_tile_index(index_path=index_path,root=root)
    matches = [t for t in registry['tiles'] if t['bbox'][0]<=bbox[0] and t['bbox'][1]<=bbox[1]
               and t['bbox'][2]>=bbox[2] and t['bbox'][3]>=bbox[3]]
    if len(matches)!=1:
        raise ValueError('Native cell is not in a registered fine tile')
    tile = matches[0]
    release,kind = _release_for_tile(registry,tile,root)
    if kind=='joint_collection':
        _validate_collection_inputs(release,index_path=index_path,root=root)
    bundle = load_fine_region(region_id,directory=release)
    if bundle['feature']['properties']['bbox'] != bbox:
        raise ValueError('Fine release geometry does not match native cell')
    bundle['provenance']['fine_tile'] = {'id':tile['id'],'name':tile['name'],'bbox':deepcopy(tile['bbox']),
                                        'release_scope':kind}
    return bundle
