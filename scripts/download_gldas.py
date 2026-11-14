#!/usr/bin/env python3
"""Download Harmony result links using an interactive Earthdata login."""
import argparse
import getpass
import os
from pathlib import Path
from urllib.parse import urlparse
import requests


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('links', help='Text file containing Harmony URLs, one per line')
    p.add_argument('--output', default='data/raw/gldas')
    args = p.parse_args()
    urls = Path(args.links).read_text().split()
    if not urls:
        p.error('The link file is empty')
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname != 'harmony.earthdata.nasa.gov' or not parsed.path.endswith('.nc4'):
            p.error('Expected HTTPS Harmony .nc4 links only')
    output = Path(args.output); output.mkdir(parents=True, exist_ok=True)
    username = input('Earthdata username: ')
    password = getpass.getpass('Earthdata password (typing is hidden): ')
    class EarthdataSession(requests.Session):
        def rebuild_auth(self, prepared_request, response):
            super().rebuild_auth(prepared_request, response)
            if urlparse(prepared_request.url).hostname == "urs.earthdata.nasa.gov":
                prepared_request.prepare_auth((username, password))

    session = EarthdataSession()
    failures = []
    for i, url in enumerate(urls, 1):
        name = Path(urlparse(url).path).name
        target = output / name
        temp = output / (name + '.part')
        if target.exists():
            with target.open('rb') as f: magic = f.read(8)
            if magic.startswith(b'CDF\x01') or magic.startswith(b'CDF\x02') or magic.startswith(b'CDF\x05') or magic == b'\x89HDF\r\n\x1a\n':
                print(f'[{i}/{len(urls)}] Already downloaded: {name}', flush=True); continue
            failures.append(name + ': existing file is not NetCDF; inspect it'); continue
        try:
            with session.get(url, stream=True, timeout=(30, 180)) as response:
                response.raise_for_status()
                with temp.open('wb') as f:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk: f.write(chunk)
            with temp.open('rb') as f: magic = f.read(8)
            if not (magic.startswith((b'CDF\x01', b'CDF\x02', b'CDF\x05')) or magic == b'\x89HDF\r\n\x1a\n'):
                raise ValueError('Response is not NetCDF/HDF5; check login, authorization, or expired links')
            os.replace(temp, target)
            print(f'[{i}/{len(urls)}] Saved {name}', flush=True)
        except (requests.RequestException, OSError, ValueError) as exc:
            temp.unlink(missing_ok=True)
            failures.append(f'{name}: {exc}')
            print(f'[{i}/{len(urls)}] Failed {name}: {exc}', flush=True)
            if i == 1: break
    print(f'Finished. Failed: {len(failures)}. Saved files: {output}')
    if failures: raise SystemExit(1)

if __name__ == '__main__': main()
