"""Readiness-first regional research CLI; --live explicitly enables providers.

Only literal .env assignments for the four documented service settings are read.
Values are never evaluated as shell code, expanded, printed, or included in output.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import shlex
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.regional_workflow import load_region, research_selected_region

SETTINGS = ("MODEL_API_KEY", "MODEL_BASE_URL", "MODEL_NAME", "POLICY_SEARCH_API_KEY")


def read_settings(path, *, environ=None):
    """Parse allowlisted literal assignments; never source or evaluate a file.

    Existing process settings take precedence. Shell substitutions and expansion
    are not supported: quoted strings are literal, not executable expressions.
    """
    values = {}
    path = Path(path)
    if path.exists():
        for number, line in enumerate(path.read_text().splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[7:].lstrip()
            match = re.fullmatch(r"([A-Za-z_][A-Za-z_0-9]*)\s*=(.*)", line)
            if not match:
                raise ValueError(f"Invalid settings assignment on line {number}")
            name, value = match.groups()
            if name not in SETTINGS:
                continue
            tokens = shlex.split(value, comments=True, posix=True)
            if len(tokens) > 1:
                raise ValueError(f"Invalid settings value on line {number}")
            values[name] = tokens[0] if tokens else ""
    existing = os.environ if environ is None else environ
    values.update({k: existing[k] for k in SETTINGS if k in existing})
    return values


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", required=True, help="B's actual catalog region_id")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--directory", type=Path, default=ROOT / "data/processed/regional")
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".cache/regional_research")
    parser.add_argument("--official-domain", action="append", default=[],
                        help="Trusted host suffix; only accepted for a single-jurisdiction cell")
    parser.add_argument("--live", action="store_true", help="Enable bounded paid provider requests; no retries")
    parser.add_argument("--output", type=Path, help="Save real report JSON; only valid with --live")
    args = parser.parse_args(argv)
    if args.output and not args.live:
        parser.error("--output requires --live; readiness never creates a research report")
    try:
        settings = read_settings(args.env_file)
        bundle = load_region(args.region, directory=args.directory)
        context = bundle["research_context"]
        if args.official_domain:
            if len(context["jurisdictions"]) != 1:
                raise ValueError("Official-domain override requires exactly one jurisdiction")
            domains = []
            for domain in args.official_domain:
                if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}", domain):
                    raise ValueError("Official domains must be hostnames without schemes or paths")
                domains.append(domain.lower())
            context["jurisdictions"][0]["official_domains"] = sorted(set(domains))
        ready = {name: bool(settings.get(name)) for name in SETTINGS}
        status = {"mode": "live" if args.live else "readiness_no_network", "region_id": args.region,
                  "bbox": context["bbox"], "jurisdictions": [j["name"] for j in context["jurisdictions"]],
                  "screening_status": bundle["screening_status"],
                  "paired_analysis_available": bool((bundle.get("screening") or {}).get("analysis")),
                  "configured": ready}
        if not args.live:
            print(json.dumps(status, indent=2))
            return 0
        if not all(ready.values()):
            raise ValueError("Live mode requires all four configured research settings")
        if bundle["screening_status"] != "current":
            raise ValueError("Rebuild current regional screening before live research")
        if not context["jurisdictions"]:
            raise ValueError("Live mode requires actual jurisdiction intersections")
        report = research_selected_region(bundle, environ=settings, cache_dir=args.cache_dir)
        report["run_context"] = deepcopy(context)
        report["run_context"]["paired_analysis_available"] = status["paired_analysis_available"]
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2, allow_nan=False))
        print(json.dumps({**status, "status": report["status"],
                          "verification_status": report["verification_status"],
                          "source_count": len(report["candidate_sources"]),
                          "citation_count": len(report["citations"]),
                          "qualitative_available": report["qualitative"] is not None,
                          "output_written": bool(args.output)}, indent=2))
        return 0 if report["qualitative"] else 2
    except (ValueError, OSError, KeyError, TypeError):
        # Never echo the raw exception or settings content into user logs.
        print("Research command could not complete; verify settings, catalog and screening readiness.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
