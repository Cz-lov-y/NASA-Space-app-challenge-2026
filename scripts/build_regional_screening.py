#!/usr/bin/env python3
"""Build the provisional global-grid statistics artifact without network access."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.regional_statistics import REQUIRED_COLUMNS, build_regional_screening


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/processed/regional/monthly_timeseries.csv")
    parser.add_argument("--catalog", type=Path, default=ROOT / "data/processed/regional/catalog.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/regional/screening.json")
    args = parser.parse_args(argv)
    catalog_path = args.catalog
    if not catalog_path.exists() and catalog_path == ROOT / "data/processed/regional/catalog.json":
        catalog_path = ROOT / "data/regions/grid_10deg.geojson"
    catalog = json.loads(catalog_path.read_text())
    frame = pd.read_csv(args.input, dtype={"unit": str}) if args.input.exists() else pd.DataFrame(columns=REQUIRED_COLUMNS)
    report = build_regional_screening(frame, catalog)
    report['source_csv_sha256'] = hashlib.sha256(args.input.read_bytes()).hexdigest() if args.input.exists() else None
    report['source_catalog_sha256'] = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(f"Wrote {len(report['regions'])} regions; {report['multiple_testing']['family_size']} worldwide tests to {args.output}")


if __name__ == "__main__":
    main()
