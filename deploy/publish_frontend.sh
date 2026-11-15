#!/usr/bin/env bash
# Publish a built frontend without interrupting the live worker or API.
set -euo pipefail
root_dir=$(cd "$(dirname "$0")/.." && pwd)
archive=$(mktemp "${TMPDIR:-/tmp}/earthrisk-frontend.XXXXXX")
trap 'rm -f "$archive"' EXIT
if [[ ! -f "$root_dir/frontend/dist/index.html" ]]; then echo 'Build frontend/dist first.' >&2; exit 1; fi
COPYFILE_DISABLE=1 tar -czf "$archive" -C "$root_dir/frontend/dist" .
gcloud compute scp "$archive" earthrisk-demo:~/earthrisk-frontend-release.tar.gz --project=tactical-attic-456217-t0 --zone=us-central1-a --quiet
gcloud compute ssh earthrisk-demo --project=tactical-attic-456217-t0 --zone=us-central1-a --quiet --command='set -eu; stage=$(mktemp -d); trap "rm -rf $stage" EXIT; tar -xzf ~/earthrisk-frontend-release.tar.gz -C "$stage"; sudo rsync -r --exclude=/index.html "$stage/" /opt/earthrisk/frontend/dist/; sudo chown -R earthrisk:earthrisk /opt/earthrisk/frontend/dist; sudo install -o earthrisk -g earthrisk -m 644 "$stage/index.html" /opt/earthrisk/frontend/dist/index.html.next; sudo mv /opt/earthrisk/frontend/dist/index.html.next /opt/earthrisk/frontend/dist/index.html; rm -f ~/earthrisk-frontend-release.tar.gz'
