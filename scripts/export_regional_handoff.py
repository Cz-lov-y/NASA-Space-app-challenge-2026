"""Export local region details for a frontend or teammate; no service requests."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.regional_workflow import REGIONAL, export_region, load_region


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=REGIONAL)
    parser.add_argument('--output', type=Path, default=ROOT / '.cache/regional_handoff')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--region')
    group.add_argument('--all', action='store_true')
    args = parser.parse_args(argv)
    catalog = json.loads((args.directory / 'catalog.json').read_text())
    ids = [f['properties']['region_id'] for f in catalog['features']] if args.all else [args.region]
    rows = []
    for region_id in ids:
        if not region_id.replace('_', '').isalnum():
            raise ValueError('Region ID cannot be used as a filename')
        bundle = load_region(region_id, directory=args.directory)
        if bundle['screening_status'] != 'current':
            raise ValueError('Rebuild current screening before exporting details')
        payload = export_region(bundle)
        args.output.mkdir(parents=True, exist_ok=True)
        filename = region_id + '.json'
        (args.output / filename).write_text(json.dumps(payload, allow_nan=False) + '\n')
        rows.append({'region_id': region_id, 'file': filename,
                     'observations': len(payload['observations']),
                     'status': bundle['screening']['status']})
    (args.output / 'manifest.json').write_text(json.dumps({
        'schema_version': 'regional-handoff-1', 'dataset_version': bundle['research_context']['dataset_version'],
        'regions': rows}, indent=2) + '\n')
    print(f'Exported {len(rows)} regions to {args.output}; no network requests')


if __name__ == '__main__':
    main()
