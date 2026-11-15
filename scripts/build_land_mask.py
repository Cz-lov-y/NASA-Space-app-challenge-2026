#!/usr/bin/env python3
"""Rasterize the bundled Natural Earth land polygons for globe cell masking."""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageChops

ROOT=Path(__file__).resolve().parents[1]
WIDTH, HEIGHT=8192,4096


def point(coordinate):
    lon,lat=coordinate
    return ((lon+180)*WIDTH/360,(90-lat)*HEIGHT/180)


def main():
    data=json.loads((ROOT/'frontend/public/data/geography.json').read_text())
    mask=Image.new('L',(WIDTH,HEIGHT),0)
    for country in data['countries']:
        geom=country['geometry']
        polygons=[geom['coordinates']] if geom['type']=='Polygon' else geom['coordinates']
        # Draw each country separately before union: another country can lie in
        # a hole (for example Lesotho), and must not be erased by that hole.
        layer=Image.new('L',(WIDTH,HEIGHT),0);draw=ImageDraw.Draw(layer)
        for polygon in polygons:
            if not polygon:continue
            draw.polygon([point(p) for p in polygon[0]],fill=255)
            for hole in polygon[1:]:draw.polygon([point(p) for p in hole],fill=0)
        mask=ImageChops.lighter(mask,layer)
    output=ROOT/'frontend/public/data/land-mask.png'
    mask.save(output,optimize=True)
    print(f'Wrote {output} ({WIDTH}x{HEIGHT})')


if __name__=='__main__':main()
