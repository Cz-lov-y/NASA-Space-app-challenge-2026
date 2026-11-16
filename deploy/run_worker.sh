#!/bin/sh
# Restart after transient source failures, but stop on completion or disk limits.
set -u
/opt/earthrisk/.venv/bin/python scripts/global_screen_earth_engine.py \
  --project tactical-attic-456217-t0 --priority-canada-prairies \
  --fetch --request-workers 4 --min-free-gib 20
status=$?
if [ "$status" -ne 0 ]; then
  exit "$status"
fi
/opt/earthrisk/.venv/bin/python -c 'import json, sys; p=json.load(open("data/processed/fine/global/index.json")); sys.exit(1 if p.get("last_stop_reason") == "source_or_service_blocked" else 0)'
