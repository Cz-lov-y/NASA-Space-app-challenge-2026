#!/usr/bin/env python3
"""Archive code, original data, and a coherent index of completed tiles."""
import io
import json
from pathlib import Path
import tarfile
import time

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'.cache/deployment/earthrisk-snapshot.tar.gz'
INDEX=ROOT/'data/processed/fine/global/index.json'


def main():
    data=INDEX.read_bytes();index=json.loads(data)
    tiles=index.get('tiles',{})
    # An incomplete release may exist on disk while the worker is writing it;
    # archive only the index's ready releases, captured before the scan begins.
    ready=[r for r in tiles.values() if r.get('ready')]
    index['tiles']={key:value for key,value in tiles.items() if value.get('ready')}
    index['completed_supported_tiles']=len(index['tiles'])
    index['worldwide_paired_complete']=False
    data=(json.dumps(index,indent=2)+'\n').encode()
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    with tarfile.open(OUTPUT,'w:gz',compresslevel=1) as archive:
        def add(path):
            source=ROOT/path
            if source.exists():archive.add(source,arcname=str(path),recursive=True)
        for path in [Path('src'),Path('scripts'),Path('deploy'),Path('frontend/dist'),Path('frontend/public/data/geography.json'),Path('data/raw'),Path('data/regions'),Path('data/requests')]:add(path)
        processed=ROOT/'data/processed'
        if processed.exists():
            for child in processed.iterdir():
                if child.name!='fine':add(child.relative_to(ROOT))
            fine=processed/'fine'
            if fine.exists():
                for child in fine.iterdir():
                    if child.name!='global':add(child.relative_to(ROOT))
        for record in ready:
            directory=Path(record['directory'])
            if directory.is_absolute() or '..' in directory.parts or not directory.is_relative_to(Path('data/processed/fine/global')):
                raise ValueError('Unsafe completed tile directory')
            add(directory)
        info=tarfile.TarInfo('data/processed/fine/global/index.json');info.size=len(data);info.mtime=int(time.time());archive.addfile(info,io.BytesIO(data))
        for path in ROOT.glob('requirements*.txt'):add(path.relative_to(ROOT))
    print(f'Snapshot ready: {len(ready)} completed tiles; {OUTPUT.stat().st_size // (1024*1024)} MiB')


if __name__=='__main__':main()
