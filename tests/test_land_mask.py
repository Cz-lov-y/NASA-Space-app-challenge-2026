"""Check known land/ocean points in the bundled approximate raster mask."""
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]


def test_mask_covers_land_and_excludes_open_ocean():
    with Image.open(ROOT/'frontend/public/data/land-mask.png') as mask:
        assert mask.size==(8192,4096)
        def pixel(lat,lon):
            return mask.getpixel((int((lon+180)*mask.width/360),int((90-lat)*mask.height/180)))
        assert pixel(51.0447,-114.0719)==255  # Calgary
        assert pixel(43.6532,-79.3832)==255   # Toronto
        assert pixel(0,-140)==0              # Pacific Ocean
        assert pixel(0,-30)==0               # Atlantic Ocean
