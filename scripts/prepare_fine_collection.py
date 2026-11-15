#!/usr/bin/env python3
"""Build or audit one joint family across the frozen six-tile native collection."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.fine_collection import audit_collection, prepare_collection


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, default=ROOT/'data/processed/fine/tiles.json')
    parser.add_argument('--output', type=Path, default=ROOT/'data/processed/fine/collection')
    parser.add_argument('--audit-only', action='store_true')
    args = parser.parse_args(argv)
    report = audit_collection(args.output) if args.audit_only else prepare_collection(args.index, args.output)
    print(json.dumps(report, indent=2, allow_nan=False))
    return 0 if report['integrity_passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
