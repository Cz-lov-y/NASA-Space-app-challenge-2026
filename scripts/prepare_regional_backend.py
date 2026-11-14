"""Refresh the regional backend and handoff locally; never calls paid providers."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modis', type=Path, nargs='+', help='New regional exports to validate, archive and ingest')
    parser.add_argument('--details-output', type=Path, default=ROOT / '.cache/regional_handoff')
    args = parser.parse_args(argv)

    def run(script, *arguments, capture=False):
        return subprocess.run([sys.executable, str(ROOT / 'scripts' / script),
                               *map(str, arguments)], cwd=ROOT, check=True,
                              text=True, capture_output=capture)

    if args.modis:
        exports = [p.resolve() for p in args.modis]
        run('merge_regional_timeseries.py', '--validate-only', *exports)
        run('merge_regional_timeseries.py', *exports)
    run('build_regional_screening.py')
    audit = json.loads(run('audit_regional_release.py', capture=True).stdout)
    output = ROOT / 'data/processed/regional/release_audit.json'
    output.write_text(json.dumps(audit, indent=2, allow_nan=False) + '\n')
    run('export_regional_handoff.py', '--all', '--output', args.details_output)
    print('Backend refreshed. Review release_audit.json; pending regional NDVI remains a data dependency.')


if __name__ == '__main__':
    main()
