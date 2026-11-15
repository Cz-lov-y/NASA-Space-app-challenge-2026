"""Physical area-reference checks; no accounts or fabricated measurements."""
import math

import numpy as np
from pyproj import Geod, Transformer
import pytest

from scripts.export_fine_modis_earth_engine import CALCULATION_VERSION, NATIVE_PIXEL_AREA_M2
from scripts.merge_regional_timeseries import NATIVE_AFFINE
from src.fine_grid import RADIUS_M


def test_fine_native_area_uses_verified_sinusoidal_equal_area_affine():
    expected = abs(NATIVE_AFFINE['elt_0_0'] * NATIVE_AFFINE['elt_1_1'])
    assert NATIVE_PIXEL_AREA_M2 == expected
    assert CALCULATION_VERSION == 'modis_sinusoidal_sphere_native_pixel_v2'
    inverse = Transformer.from_crs(f'+proj=sinu +R={RADIUS_M} +units=m +no_defs','EPSG:4326',always_xy=True)
    sphere = Geod(a=RADIUS_M,b=RADIUS_M)
    for latitude in (13,37,54,-4):
        x, y = RADIUS_M*math.cos(math.radians(latitude)), RADIUS_M*math.radians(latitude)
        d = math.sqrt(NATIVE_PIXEL_AREA_M2)
        edge = np.linspace(0,d,129)
        points = [(x+t,y) for t in edge] + [(x+d,y+t) for t in edge[1:]]
        points += [(x+d-t,y+d) for t in edge[1:]] + [(x,y+d-t) for t in edge[1:]]
        lons,lats = inverse.transform(*zip(*points))
        area = abs(sphere.polygon_area_perimeter(lons,lats)[0])
        assert area == pytest.approx(NATIVE_PIXEL_AREA_M2,rel=1e-7)


def test_ellipsoidal_and_spherical_target_areas_have_material_latitude_dependent_bias():
    geod = Geod(ellps='WGS84')
    ratios = {}
    for latitude in (37,54,13,-4):
        west,south,east,north = 0,latitude,.25,latitude+.25
        edge = np.linspace(0,1,1001)
        ring = [(west+(east-west)*t,south) for t in edge]
        ring += [(east,south+(north-south)*t) for t in edge[1:]]
        ring += [(east-(east-west)*t,north) for t in edge[1:]]
        ring += [(west,north-(north-south)*t) for t in edge[1:]]
        ellipsoid = abs(geod.polygon_area_perimeter(*zip(*ring))[0])
        sphere = RADIUS_M**2*math.radians(east-west)*(math.sin(math.radians(north))-math.sin(math.radians(south)))
        ratios[latitude] = ellipsoid/sphere
    assert ratios[54] == pytest.approx(1.0043396169,abs=1e-9)
    assert ratios[37] == pytest.approx(1.0004033513,abs=1e-9)
    assert ratios[13] < .997
    assert ratios[-4] < .996
    # A wider coverage threshold would conceal a reference-system mismatch.
    assert ratios[54] - 1 > .001
