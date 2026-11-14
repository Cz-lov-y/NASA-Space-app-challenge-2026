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
from src.regional_statistics import REQUIRED_COLUMNS, build_regional_screening, build_screening_summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "data/processed/regional/monthly_timeseries.csv")
    parser.add_argument("--catalog", type=Path, default=ROOT / "data/processed/regional/catalog.json")
    parser.add_argument("--output", type=Path, default=ROOT / "data/processed/regional/screening.json")
    parser.add_argument("--map-output", type=Path, default=ROOT / "data/processed/regional/map_screening.geojson")
    args = parser.parse_args(argv)
    if args.output.resolve() == args.map_output.resolve():
        parser.error("--output and --map-output must be different paths")
    catalog_path = args.catalog
    if not catalog_path.exists() and catalog_path == ROOT / "data/processed/regional/catalog.json":
        catalog_path = ROOT / "data/regions/grid_10deg.geojson"
    source_paths = {args.input.resolve(), catalog_path.resolve()}
    if args.output.resolve() in source_paths or args.map_output.resolve() in source_paths:
        parser.error("output paths must not overwrite source observations or catalog")
    catalog = json.loads(catalog_path.read_text())
    frame = pd.read_csv(args.input, dtype={"unit": str}) if args.input.exists() else pd.DataFrame(columns=REQUIRED_COLUMNS)
    report = build_regional_screening(frame, catalog)
    report['source_csv_sha256'] = hashlib.sha256(args.input.read_bytes()).hexdigest() if args.input.exists() else None
    report['source_catalog_sha256'] = hashlib.sha256(catalog_path.read_bytes()).hexdigest()
    summary = build_screening_summary(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.map_output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    args.map_output.write_text(json.dumps(summary, separators=(",", ":"), allow_nan=False) + "\n")
    print(f"Wrote {len(report['regions'])} regions; {report['multiple_testing']['family_size']} worldwide tests to {args.output}")


if __name__ == "__main__":
    main()
