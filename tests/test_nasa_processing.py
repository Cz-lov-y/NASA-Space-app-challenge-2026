import numpy as np
import pandas as pd
import pytest
import rasterio
from rasterio.transform import from_origin
import xarray as xr

from scripts.process_nasa_data import modis, gldas, region_geometry


def test_grid_processing_masks_scales_and_sums(tmp_path):
    region = tmp_path / 'region.geojson'
    region.write_text('{"type":"Polygon","coordinates":[[[0,0],[0.5,0],[0.5,0.5],[0,0.5],[0,0]]]}')
    geometry, crs = region_geometry(region)
    transform = from_origin(0, .5, .25, .25)
    for name, values, dtype, nodata in [
        ('ndvi', [[5000, 1000], [-3000, 7000]], 'int16', -3000),
        ('qa', [[0, 1], [0, 0]], 'uint16', 65535),
        ('reliability', [[0, 0], [0, 1]], 'int16', -1),
    ]:
        with rasterio.open(tmp_path / (name + '.tif'), 'w', driver='GTiff', width=2, height=2,
                           count=1, dtype=dtype, crs='EPSG:4326', transform=transform, nodata=nodata) as dst:
            dst.write(np.array(values, dtype=dtype), 1)
    manifest = tmp_path / 'manifest.csv'
    manifest.write_text('date,ndvi,vi_quality,pixel_reliability,scale\n2003-01-01,ndvi.tif,qa.tif,reliability.tif,raw\n')
    value, coverage = modis(manifest, geometry, crs)[pd.Timestamp('2003-01-01')]
    assert value == pytest.approx(.5)
    assert coverage == pytest.approx(.25, rel=.002)
    ds = xr.Dataset({name: (('time','lat','lon'), np.full((1,2,2), v), {'units':'kg m-2'})
                     for name, v in zip(['SoilMoi0_10cm_inst','SoilMoi10_40cm_inst','SoilMoi40_100cm_inst'], [10,20,30])},
                    coords={'time':pd.to_datetime(['2003-01-01']), 'lat':[.375,.125], 'lon':[.125,.375]})
    nc = tmp_path / 'gldas.nc'; ds.to_netcdf(nc)
    surface, total = gldas([nc], geometry, crs)[pd.Timestamp('2003-01-01')]
    assert surface[0] == pytest.approx(10)
    assert total[0] == pytest.approx(60)
    assert total[1] == pytest.approx(1, rel=.001)


def test_global_boundary_rejected_until_global_safe(tmp_path):
    with pytest.raises(ValueError, match='antimeridian'):
        region_geometry('data/regions/whole_earth.geojson')
