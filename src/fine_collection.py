"""One frozen statistical family across bounded native-cell source releases."""
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from .divergence import detect_divergence
from .fine_grid import build_tile_catalog, cell_feature, grid_definition, parse_cell_id
from .regional_statistics import PRIMARY_VARIABLES, REJECT_FLAGS, build_regional_screening, build_screening_summary
from .regional_workflow import ROOT
from .statistics import mann_kendall

REQUIRED = ('catalog.json', 'monthly_timeseries.csv', 'gldas_monthly_timeseries.csv', 'metadata.json', 'source_manifest.json')
OPTIONAL = ('modis_source_manifest.json', 'accepted_modis_observations.csv')
PERIOD = ['2003-01-01', '2024-12-31']
AREA_METHOD = 'modis_sinusoidal_sphere_native_pixel_v2'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _json(value):
    return (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()


def _table(data):
    return pd.read_csv(BytesIO(data), dtype={'unit': str}, float_precision='round_trip')


def _path(name, root):
    path = Path(name)
    return path if path.is_absolute() else Path(root) / path


def _snapshot(index_path, root):
    index_path = Path(index_path).resolve()
    index_bytes = index_path.read_bytes()
    index = json.loads(index_bytes)
    if index.get('schema_version') != 'fine-tiles-1' or index.get('period', PERIOD) != PERIOD:
        raise ValueError('Expected fine-tiles-1 registry and frozen2003-2024period')
    tiles = index.get('tiles', [])
    if len(tiles) != 6 or len({tile['id'] for tile in tiles}) != 6:
        raise ValueError('Collection requires exactly six unique frozen tiles')
    snapshots, ids, paths = [], set(), set()
    for tile in tiles:
        directory = _path(tile['directory'], root).resolve()
        if directory in paths:
            raise ValueError('Duplicate tile directory')
        paths.add(directory)
        files = {name: (directory/name).read_bytes() for name in REQUIRED}
        files.update({name: (directory/name).read_bytes() for name in OPTIONAL if (directory/name).exists()})
        catalog = json.loads(files['catalog.json'])
        features = catalog['features']
        expected = {f['id'] for f in build_tile_catalog(tile['bbox'])['features']}
        actual = {f['properties']['region_id'] for f in features}
        if len(features) != 16 or len(actual) != 16 or actual != expected or actual & ids:
            raise ValueError('Frozen tiles require16distinct native cells each without overlap')
        for feature in features:
            p = feature['properties']
            canonical = cell_feature(*parse_cell_id(p['region_id']))
            if (feature.get('id') != p['region_id'] or feature['geometry'] != canonical['geometry'] or p['bbox'] != canonical['properties']['bbox']
                    or p.get('centroid') != canonical['properties']['centroid']
                    or not np.isclose(p['region_area_m2'], canonical['properties']['region_area_m2'], rtol=1e-12)):
                raise ValueError('Source catalog geometry must match canonical native cells')
            if p.get('tile_id') != tile['id']:
                raise ValueError('Registry tile_id must match source release identity')
        ids.update(actual)
        snapshots.append({'tile': deepcopy(tile), 'directory': directory, 'files': files, 'catalog': catalog})
    return index, index_bytes, snapshots


def _unchanged(index_path, index_bytes, snapshots):
    if Path(index_path).read_bytes() != index_bytes:
        raise ValueError('Fine registry changed during processing')
    for source in snapshots:
        directory = source['directory']
        for name in REQUIRED + OPTIONAL:
            before = source['files'].get(name)
            after = (directory/name).read_bytes() if (directory/name).exists() else None
            if before != after:
                raise ValueError('Fine tile inputs changed during collection processing')


def _merge_manifest(snapshots, name):
    by_file = {}
    for source in snapshots:
        for record in json.loads(source['files'].get(name, b'[]')):
            previous = by_file.get(record['file'])
            if previous is not None and (previous['sha256'] != record['sha256'] or previous.get('date') != record.get('date')):
                raise ValueError('Conflicting source manifests for the same archived file')
            by_file.setdefault(record['file'], deepcopy(record))
    return [by_file[name] for name in sorted(by_file)]


def _concat(snapshots, name):
    tables = [_table(source['files'][name]) for source in snapshots if name in source['files']]
    if not tables:
        return None
    result = pd.concat(tables, ignore_index=True)
    if result.duplicated(['region_id', 'variable', 'date']).any():
        raise ValueError('Duplicate observations across fine source releases')
    return result.sort_values(['region_id', 'variable', 'date'], kind='stable').reset_index(drop=True)



def _area_method_valid(frame, *, ledger=False):
    rows = frame[frame.variable == 'ndvi']
    if not ledger and 'quality_flag' in rows:
        rows = rows[rows.quality_flag != 'pending_export']
    return rows.empty or ('area_method' in rows and rows.area_method.eq(AREA_METHOD).all())


def _identity(index, catalog):
    return {'grid': 'gldas025', 'tiles': sorted(tile['id'] for tile in index['tiles']),
            'regions': sorted(f['properties']['region_id'] for f in catalog['features']),
            'period': PERIOD, 'variables': list(PRIMARY_VARIABLES)}


def _atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=path.name+'.', suffix='.tmp', delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(path)


def prepare_collection(index_path, output=None, *, root=ROOT):
    """Copy genuine source tables then estimate one96-cell joint family once."""
    root = Path(root).resolve()
    index_path = Path(index_path).resolve()
    index, index_bytes, sources = _snapshot(index_path, root)
    output = _path(output or index.get('collection_directory', 'data/processed/fine/collection'), root).resolve()
    if any(output == source['directory'] or output in source['directory'].parents for source in sources):
        raise ValueError('Collection output must not overwrite an input tile directory')
    features = []
    for source in sources:
        for feature in source['catalog']['features']:
            copied = deepcopy(feature)
            copied['properties']['collection_tile_id'] = source['tile']['id']
            features.append(copied)
    catalog = {'type': 'FeatureCollection', 'grid': grid_definition(), 'features': features}
    frame = _concat(sources, 'monthly_timeseries.csv')
    original = _concat(sources, 'gldas_monthly_timeseries.csv')
    if set(frame.region_id) != {f['properties']['region_id'] for f in features}:
        raise ValueError('Source observations must cover exactly all frozen96cells')
    source_manifest = _merge_manifest(sources, 'source_manifest.json')
    modis_manifest = _merge_manifest(sources, 'modis_source_manifest.json')
    ledger = _concat(sources, 'accepted_modis_observations.csv')
    if not _area_method_valid(frame) or (ledger is not None and not _area_method_valid(ledger, ledger=True)):
        raise ValueError('All received fine NDVI observations require uniform spherical native-pixel area_methodv2; reprocess legacy exports')
    inputs = {'schema_version': 'fine-collection-inputs-1', 'index_file': str(index_path.relative_to(root)) if index_path.is_relative_to(root) else str(index_path),
        'index_sha256': digest(index_bytes),
        'tiles': [{'id': source['tile']['id'], 'directory': source['tile']['directory'],
                   'files': {name: digest(data) for name, data in source['files'].items()}} for source in sources]}
    inputs['files'] = [{'file': inputs['index_file'], 'sha256': inputs['index_sha256']}]
    for source in sources:
        for name, data in source['files'].items():
            path = source['directory']/name
            inputs['files'].append({'file': str(path.relative_to(root)) if path.is_relative_to(root) else str(path),
                                    'sha256': digest(data)})
    release_id = digest(_json(inputs))
    family_id = 'fine-collection-' + digest(_json(_identity(index, catalog)))
    report = build_regional_screening(frame, catalog, dataset_version=release_id)
    csv_bytes = frame.to_csv(index=False, float_format='%.17g').encode()
    catalog_bytes = _json(catalog)
    report.update(source_csv_sha256=digest(csv_bytes), source_catalog_sha256=digest(catalog_bytes))
    report['multiple_testing'].update(family_id=family_id,
        scope='Only the six frozen native-grid tiles in this96-cell collection; not a worldwide or legacy coarse-grid family.',
        grid='gldas025', declared_tiles=[tile['id'] for tile in index['tiles']],
        declared_cell_count=96, selection_basis=index.get('selection_basis', 'Frozen geographically separated demonstration tiles'))
    report['limitations'].append('One joint family across six selected native-cell tiles; it is not representative or exhaustive worldwide coverage.')
    summary = build_screening_summary(report)
    for feature in summary['features']:
        props = feature['properties']
        props['native_resolution_degrees'] = .25
        props['tile_id'] = next(f['properties']['tile_id'] for f in features if f['id'] == feature['id'])
        props['collection_tile_id'] = props['tile_id']
    quality = frame.groupby(['region_id','variable']).agg(expected_months=('value','size'),
        valid_months=('value','count'), min_coverage=('valid_area_fraction','min'), max_coverage=('valid_area_fraction','max'))
    quality['missing_months'] = quality.expected_months-quality.valid_months
    synthetic = bool(frame.source.astype(str).str.contains('SYNTHETIC', case=False).any())
    metadata = {'schema_version': 'fine-collection-1', 'grid': 'gldas025', 'crs': 'EPSG:4326',
        'native_resolution_degrees': .25, 'period': PERIOD, 'tiles': index['tiles'],
        'data_kind': 'synthetic test inputs' if synthetic else 'real NASA-derived native-cell source releases; no synthetic observations',
        'dataset_version': release_id, 'family_id': family_id, 'input_manifest': 'input_manifest.json',
        'selection_basis': index.get('selection_basis'), 'qa_reviewed': False, 'area_method': AREA_METHOD,
        'limitations': report['limitations']}
    artifacts = {'catalog.json': catalog_bytes, 'monthly_timeseries.csv': csv_bytes,
        'gldas_monthly_timeseries.csv': original.to_csv(index=False, float_format='%.17g').encode(),
        'source_manifest.json': _json(source_manifest), 'modis_source_manifest.json': _json(modis_manifest),
        'input_manifest.json': _json(inputs), 'metadata.json': _json(metadata),
        'quality_report.csv': quality.to_csv(float_format='%.17g').encode(),
        'screening.json': _json(report), 'map_screening.geojson': _json(summary)}
    if ledger is not None:
        artifacts['accepted_modis_observations.csv'] = ledger.to_csv(index=False, float_format='%.17g').encode()
    _unchanged(index_path, index_bytes, sources)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Never publish a candidate that has not passed the independent audit.
    with tempfile.TemporaryDirectory(prefix='fine-collection-stage-', dir=output.parent) as stage_name:
        stage = Path(stage_name)
        for name, data in artifacts.items():
            (stage/name).write_bytes(data)
        audit = audit_collection(stage, root=root)
        if not audit['integrity_passed']:
            raise ValueError('Collection integrity audit failed: ' + '; '.join(audit['errors'][:5]))
        _unchanged(index_path, index_bytes, sources)
        artifacts['release_audit.json'] = _json(audit)
        for name, data in artifacts.items():
            if name != 'map_screening.geojson':
                _atomic(output/name, data)
        if ledger is None:
            (output/'accepted_modis_observations.csv').unlink(missing_ok=True)
        # Consumers check the map/source hashes; publish the map last.
        _atomic(output/'map_screening.geojson', artifacts['map_screening.geojson'])
    return audit


def audit_collection(directory, *, root=ROOT):
    """Read-only source-preservation and actual-value joint-family audit."""
    directory, root = Path(directory), Path(root)
    errors = []
    def check(condition, label):
        if not bool(condition):
            errors.append(label)
    def read(name):
        return json.loads((directory/name).read_text())
    inputs = read('input_manifest.json')
    index_path = _path(inputs['index_file'], root)
    check(digest(index_path.read_bytes()) == inputs['index_sha256'], 'Frozen registry fingerprint changed')
    index, _, sources = _snapshot(index_path, root)
    for source, recorded in zip(sources, inputs['tiles']):
        check(source['tile']['id'] == recorded['id'], 'Input tile order/identity changed')
        check({name: digest(data) for name,data in source['files'].items()} == recorded['files'], 'Source tile fingerprint changed')
    frame = _table((directory/'monthly_timeseries.csv').read_bytes())
    check(_area_method_valid(frame), 'Received NDVI uses mixed or legacy area_method')
    expected = _concat(sources, 'monthly_timeseries.csv')
    try:
        pd.testing.assert_frame_equal(frame, expected, check_dtype=False, check_exact=True)
    except AssertionError:
        errors.append('Collection observations differ from original source tile tables')
    original = _table((directory/'gldas_monthly_timeseries.csv').read_bytes())
    try:
        pd.testing.assert_frame_equal(original, _concat(sources, 'gldas_monthly_timeseries.csv'), check_dtype=False, check_exact=True)
    except AssertionError:
        errors.append('Collection native GLDAS baseline differs from source tiles')
    soil = frame[frame.variable.isin(['soil_water_0_10cm', 'soil_water_0_100cm'])].reset_index(drop=True)
    try:
        pd.testing.assert_frame_equal(soil[list(original.columns)], original, check_dtype=False, check_exact=True)
    except (AssertionError, KeyError):
        errors.append('Combined collection soil values differ from native baseline')
    expected_ledger = _concat(sources, 'accepted_modis_observations.csv')
    if expected_ledger is not None:
        check(_area_method_valid(expected_ledger, ledger=True), 'Accepted NDVI ledger uses mixed or legacy area_method')
        try:
            actual_ledger = _table((directory/'accepted_modis_observations.csv').read_bytes())
            pd.testing.assert_frame_equal(actual_ledger, expected_ledger, check_dtype=False, check_exact=True)
        except (AssertionError, FileNotFoundError):
            errors.append('Consolidated accepted ledger differs from original source ledgers')
    catalog, report, mapping = read('catalog.json'), read('screening.json'), read('map_screening.geojson')
    ids = {f['properties']['region_id'] for f in catalog['features']}
    expected_features = {f['id']: f for source in sources for f in source['catalog']['features']}
    check(len(catalog['features']) == len(ids) == len(expected_features) == 96 and ids == set(expected_features), 'Catalog must contain exactly the frozen96native cells')
    for feature in catalog['features']:
        expected_feature = expected_features.get(feature['id'])
        if expected_feature:
            check(feature['geometry'] == expected_feature['geometry'], 'Collection native geometry changed')
            p = deepcopy(feature['properties']); p.pop('collection_tile_id', None)
            check(p == expected_feature['properties'], 'Collection source properties changed')
    for payload in (report, mapping):
        check(payload.get('source_csv_sha256') == digest((directory/'monthly_timeseries.csv').read_bytes()) and payload.get('source_catalog_sha256') == digest((directory/'catalog.json').read_bytes()), 'Collection artifact source fingerprint mismatch')
        check(payload['multiple_testing']['family_id'] == 'fine-collection-'+digest(_json(_identity(index, catalog))), 'Joint family identity differs from frozen registry')
        check(payload['multiple_testing']['catalog_regions'] == 96 and payload['multiple_testing'].get('declared_cell_count') == 96, 'Joint family must declare96cells')
        check(payload['multiple_testing']['declared_tiles'] == [tile['id'] for tile in index['tiles']], 'Joint family must declare all six frozen tiles')
        check('six frozen' in payload['multiple_testing']['scope'] and payload['multiple_testing']['provisional'] is True, 'Joint family scope/provisional status incorrect')
    check(report['multiple_testing'] == mapping['multiple_testing'], 'Map and report joint-family metadata differ')
    for name in ('source_manifest.json', 'modis_source_manifest.json'):
        manifest = read(name)
        check(manifest == _merge_manifest(sources, name), 'Consolidated archive manifest differs from source tile manifests')
        for record in manifest:
            path = _path(record['file'], root)
            check(path.is_file() and digest(path.read_bytes()) == record['sha256'], 'Archived original source hash mismatch')
    # Revalidate original accepted MODIS rows against each tile's own catalog.
    from scripts.merge_fine_modis import validate_frame
    for source in sources:
        source_frame = _table(source['files']['monthly_timeseries.csv'])
        received = source_frame[(source_frame.variable == 'ndvi') & source_frame.source.eq('MOD13A3.061') & source_frame.quality_flag.ne('pending_export')]
        if 'accepted_modis_observations.csv' not in source['files']:
            check(received.empty, 'Received NASA MODIS observations require an authoritative archival ledger')
            continue
        accepted = validate_frame(_table(source['files']['accepted_modis_observations.csv']), source['catalog'])
        check(not accepted.duplicated(['region_id','date']).any(), 'Accepted MODIS ledger contains duplicate keys')
        accepted_keys = set(zip(accepted.region_id, accepted.date))
        check(accepted_keys == set(zip(received.region_id,received.date)), 'Source received MODIS rows differ from accepted ledger keys')
        try:
            columns = [name for name in accepted.columns if name in source_frame.columns]
            pd.testing.assert_frame_equal(accepted.set_index(['region_id','date']).sort_index()[[name for name in columns if name not in ('region_id','date')]],
                received.set_index(['region_id','date']).sort_index()[[name for name in columns if name not in ('region_id','date')]], check_dtype=False, check_exact=True)
        except (AssertionError,KeyError):
            errors.append('Source received MODIS observations differ from authoritative ledger')
        archives = json.loads(source['files'].get('modis_source_manifest.json', b'[]'))
        check(accepted.source_file_sha256.isin({record['sha256'] for record in archives}).all(), 'Accepted MODIS ledger references unknown archive hashes')
        active_hashes = set(accepted.source_file_sha256)
        for record in archives:
            # Historical processing versions remain archived and hash-checked
            # above. Only current ledger-authoritative files undergo v2 rules.
            if record['sha256'] not in active_hashes:
                continue
            archived = validate_frame(_table(_path(record['file'], root).read_bytes()), source['catalog'])
            authoritative = accepted[accepted.source_file_sha256 == record['sha256']].set_index(['region_id','date']).sort_index()
            archived = archived.set_index(['region_id','date']).sort_index()
            try:
                pd.testing.assert_frame_equal(authoritative[list(archived.columns)], archived.loc[authoritative.index], check_dtype=False, check_exact=True)
            except (AssertionError, KeyError):
                errors.append('Accepted MODIS source values/provenance differ from immutable archive')
    annual = {}
    check(set(frame.variable).issubset({'ndvi','soil_water_0_10cm','soil_water_0_100cm'}), 'Collection contains noncanonical indicators')
    required_months = set(pd.date_range('2003-01-01','2024-12-01',freq='MS').strftime('%Y-%m-%d'))
    for _, rows in frame.groupby(['region_id','variable']):
        check(len(rows) == 264 and set(rows.date) == required_months, 'Collection monthly index is not the complete264-month source index')
    clean = frame.copy()
    clean.loc[clean.quality_flag.isin(REJECT_FLAGS), 'value'] = np.nan
    clean['year'] = pd.to_datetime(clean.date, utc=True).dt.year
    for key, single in clean.groupby(['region_id','variable']):
        grouped = single.groupby('year').value
        annual[key] = grouped.mean()[grouped.count() == 12]
    records = {r['region_id']: r for r in report['regions']}
    mapped = {f['id']: f for f in mapping['features']}
    check(set(records) == ids and len(report['regions']) == 96 and set(mapped) == ids and len(mapping['features']) == 96, 'Joint statistical records must cover all96cells exactly once')
    family = []
    for rid in sorted(ids):
        record = records[rid]
        common = sorted(set(annual.get((rid,'ndvi'), pd.Series(dtype=float)).index) & set(annual.get((rid,'soil_water_0_100cm'), pd.Series(dtype=float)).index))
        eligible = len(common) >= report['settings']['min_years'] and record['properties'].get('data_status') != 'unsupported_gldas'
        check((record['status'] == 'eligible') == eligible, 'Eligibility differs from actual complete common years')
        check(record['screening']['qa_reviewed'] is False and record['screening']['provisional'] is True, 'Source QA was improperly promoted')
        if eligible:
            check(record['analysis']['observation_period']['years'] == common, 'Paired analyzed years differ from actual common years')
            for variable in PRIMARY_VARIABLES:
                p = mann_kendall(annual[(rid,variable)].reindex(common).to_numpy())['p_value']
                check(np.isclose(record['analysis']['analysis'][variable]['mann_kendall']['p_value'], p, rtol=1e-12, atol=1e-15), 'Stored MK test differs from original annual observations')
                family.append((rid,variable,p))
        else:
            check(not record['screening']['adjusted_p_values'] and record['screening']['category'] is None, 'Noneligible cell acquired paired significance')
    # Independent BH calculation from source-derived p-values, not stored q-values.
    ordered = sorted(family, key=lambda item: item[2]); m = len(ordered)
    adjusted = {(rid,var): min(1., min(m*ordered[j][2]/(j+1) for j in range(rank,m))) for rank,(rid,var,_) in enumerate(ordered)}
    for rid, record in records.items():
        if record['status'] == 'eligible':
            analyses = deepcopy(record['analysis']['analysis'])
            for var in PRIMARY_VARIABLES:
                q = adjusted[(rid,var)]
                check(np.isclose(record['screening']['adjusted_p_values'][var], q, rtol=1e-12, atol=1e-15), 'Stored q-value does not use the joint family')
                analyses[var]['adjusted_p_value'] = q
            expected = detect_divergence(analyses, vegetation_variables=('ndvi',), soil_moisture_variable='soil_water_0_100cm', alpha=report['settings']['alpha'])
            check(record['screening']['category'] == expected['category'], 'Paired category does not match jointly adjusted tests')
        check(mapped[rid]['properties']['classification'] == record['screening']['classification'], 'Map classification differs from joint report')
        for var, indicator in mapped[rid]['properties']['indicators'].items():
            q = adjusted.get((rid,var))
            check(indicator['worldwide_adjusted_p_value'] == record['screening']['adjusted_p_values'].get(var), 'Map q-value differs from joint report')
            check(indicator['worldwide_significant'] == (q < report['settings']['alpha'] if q is not None else None), 'Map significance differs from joint tests')
    check(report['multiple_testing']['family_size'] == m and report['multiple_testing']['eligible_regions'] == m//2, 'Joint family counts differ from source-derived tests')
    ndvi = frame[frame.variable == 'ndvi']
    return {'schema_version':'fine-collection-audit-1', 'integrity_passed':not errors, 'errors':errors,
        'tiles':6, 'native_cells':len(ids), 'rows':len(frame), 'gldas_source_files':len(read('source_manifest.json')),
        'ndvi_rows':len(ndvi), 'ndvi_finite_rows':int(ndvi.value.notna().sum()),
        'paired_eligible_cells':m//2, 'family_size':m, 'family_id':report['multiple_testing']['family_id'],
        'scope':report['multiple_testing']['scope'], 'scientific_review_status':'provisional; source QA and footprint review pending'}
