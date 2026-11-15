#!/usr/bin/env python3
"""Archive complete tiles added since the VM baseline, after stopping writer."""
import io
import json
from pathlib import Path
import tarfile
import time

ROOT=Path(__file__).resolve().parents[1]
BASELINE=ROOT/'.cache/deployment/baseline-index.json'
OUTPUT=ROOT/'.cache/deployment/earthrisk-delta.tar.gz'


def safe_relative(value, prefix):
    path=Path(value)
    if path.is_absolute() or '..' in path.parts or not path.is_relative_to(prefix):
        raise ValueError('Unsafe snapshot path')
    return path


def main():
    baseline=json.loads(BASELINE.read_text()).get('tiles',{})
    index=json.loads((ROOT/'data/processed/fine/global/index.json').read_text())
    complete={key:value for key,value in index['tiles'].items() if value.get('ready')}
    changed=[record for key,record in complete.items() if baseline.get(key)!=record]
    index['tiles']=complete;index['completed_supported_tiles']=len(complete);index['worldwide_paired_complete']=False
    data=(json.dumps(index,indent=2)+'\n').encode();archives=set()
    with tarfile.open(OUTPUT,'w:gz',compresslevel=1) as tar:
        for record in changed:
            directory=safe_relative(record['directory'],Path('data/processed/fine/global'))
            source=ROOT/directory
            if not source.is_dir():raise FileNotFoundError(f'Missing completed directory: {directory}')
            tar.add(source,arcname=str(directory))
            manifest=source/'modis_source_manifest.json'
            if manifest.exists():
                for entry in json.loads(manifest.read_text()):archives.add(safe_relative(entry['file'],Path('data/raw/modis_earth_engine')))
            request=Path('data/requests')/f"fine_{record['source_tile_id']}.json"
            if (ROOT/request).is_file():tar.add(ROOT/request,arcname=str(request))
        for path in sorted(archives):
            if not (ROOT/path).is_file():raise FileNotFoundError(f'Missing source archive: {path}')
            tar.add(ROOT/path,arcname=str(path))
        info=tarfile.TarInfo('data/processed/fine/global/index.json');info.size=len(data);info.mtime=int(time.time());tar.addfile(info,io.BytesIO(data))
    print(f'Delta ready: {len(changed)} updated tiles, {len(archives)} source archives, {OUTPUT.stat().st_size//(1024*1024)} MiB')

if __name__=='__main__':main()
