#!/usr/bin/env python3
"""Build the local globe land mask and place labels from Natural Earth 1:10m.

Source files are Natural Earth public-domain GeoJSON from the project's official
repository. This script downloads them; the generated browser file works offline.
"""
import json
from pathlib import Path
from urllib.request import urlopen
from shapely.geometry import shape, mapping

BASE = 'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/'
OUT = Path(__file__).resolve().parents[1] / 'frontend/public/data/geography.json'


def rounded(value):
    if isinstance(value, (list, tuple)):
        return [rounded(v) for v in value]
    return round(value, 4) if isinstance(value, float) else value


def build(name, tolerance, regional):
    with urlopen(BASE + name, timeout=60) as response:
        features = json.load(response)['features']
    result = []
    for feature in features:
        geom = shape(feature['geometry']).simplify(tolerance, preserve_topology=True)
        if geom.is_empty:
            continue
        props = feature['properties']
        label = (props.get('name_en') or props.get('name')) if regional else (props.get('NAME_EN') or props.get('ADMIN') or props.get('NAME'))
        result.append({'name': label, 'country': (props.get('admin') or '') if regional else label,
            'bbox': rounded(geom.bounds),
            'geometry': {'type': geom.geom_type, 'coordinates': rounded(mapping(geom)['coordinates'])}})
    return result


def main():
    data = {'source': 'Natural Earth 1:10m admin-0 simplified 0.005°, admin-1 simplified 0.02°',
        'countries': build('ne_10m_admin_0_countries.geojson', .005, False),
        'regions': build('ne_10m_admin_1_states_provinces.geojson', .02, True)}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(',', ':'), ensure_ascii=False), encoding='utf-8')
    print(f'Wrote {len(data["countries"])} countries and {len(data["regions"])} subdivisions to {OUT}')


if __name__ == '__main__':
    main()
