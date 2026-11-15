#!/usr/bin/env python3
"""Build an offline search index from public-domain Natural Earth geography."""
import json
from pathlib import Path
from urllib.request import urlopen
from shapely.geometry import shape

ROOT=Path(__file__).resolve().parents[1]
URL='https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_populated_places.geojson'


def main():
    boundaries=json.loads((ROOT/'frontend/public/data/geography.json').read_text())
    entries=[]
    for group in ('countries','regions'):
        for feature in boundaries[group]:
            if not feature.get('name'):continue
            p=shape(feature['geometry']).representative_point()
            entries.append({'name':feature['name'],'country':feature['country'],'area':'',
                'lat':round(p.y,5),'lng':round(p.x,5),'population':0,'kind':'country' if group=='countries' else 'region'})
    with urlopen(URL,timeout=60) as response:places=json.load(response)['features']
    for feature in places:
        props=feature['properties'];name=props.get('NAME') or props.get('NAMEASCII')
        coords=feature.get('geometry',{}).get('coordinates',[])
        if not name or len(coords)<2:continue
        entries.append({'name':name,'area':props.get('ADM1NAME') or '', 'country':props.get('ADM0NAME') or '',
            'lat':round(coords[1],5),'lng':round(coords[0],5),'population':props.get('POP_MAX') or 0,'kind':'city'})
    path=ROOT/'frontend/public/data/search-places.json'
    path.write_text(json.dumps(entries,ensure_ascii=False,separators=(',',':')))
    print('Searchable places:',len(entries))

if __name__=='__main__':main()
