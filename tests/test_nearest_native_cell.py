"""Nearest support uses actual source masks; small geometry fixtures are synthetic."""
import json
from pathlib import Path
import shutil

import numpy as np
import pytest
from scipy.spatial import cKDTree

from src.fine_grid import cell_feature
from src.global_cell_data import ROOT
from src.nearest_native_cell import NearestNativeCell


def synthetic_index(cells):
    rows=np.array([r for r,c in cells]);cols=np.array([c for r,c in cells])
    lng=np.deg2rad(-179.875+cols*.25);phi=np.deg2rad(-59.875+rows*.25)
    vectors=np.column_stack((np.cos(phi)*np.cos(lng),np.cos(phi)*np.sin(lng),np.sin(phi)))
    counts=np.zeros((600,1440),dtype=np.uint16)
    counts[rows,cols]=7
    return {'tree':cKDTree(vectors),'vectors':vectors,'rows':rows,'cols':cols,'counts':counts,
            'release':'SYNTHETIC_GEOMETRY_ONLY','source_months_available':7}


def test_global_nearest_uses_spherical_distance_dateline_and_deterministic_ties(tmp_path,monkeypatch):
    finder=NearestNativeCell(raw_directory=tmp_path,cache_directory=tmp_path/'cache')
    index=synthetic_index([(240,0),(240,1439),(388,328)])
    monkeypatch.setattr(finder,'_inventory',lambda:('fixed-source-version',))
    monkeypatch.setattr(finder,'_load_support',lambda:index)
    east=finder.nearest(179.99,.125)
    assert east['region_id']=='gldas025_r240_c1439'
    assert east['centroid']==[179.875,.125]
    tie=finder.nearest(180,.125)
    assert tie['region_id']=='gldas025_r240_c0000'
    # The requested point is not reinterpreted as the source cell's location.
    assert tie['query_coordinates']=={'lon':180.,'lat':.125}
    assert tie['distance_km']>0 and tie['valid_soil_months']==7
    south=finder.nearest(0,-90)
    assert south['region_id'] is not None
    assert south['centroid'][1]>=-60 and south['distance_km']>3000


def test_source_revision_rebuilds_support_index_and_invalid_coordinates_fail(tmp_path,monkeypatch):
    finder=NearestNativeCell(raw_directory=tmp_path,cache_directory=tmp_path/'cache')
    version=['first'];calls=[]
    monkeypatch.setattr(finder,'_inventory',lambda:tuple(version))
    def build():
        calls.append(version[0]);return synthetic_index([(388,328)])
    monkeypatch.setattr(finder,'_load_support',build)
    finder.nearest(-98,37);finder.nearest(-98,37)
    assert calls==['first']
    version[0]='second';finder.nearest(-98,37)
    assert calls==['first','second']
    for point in ((np.nan,0),(0,91),(181,0),(True,0)):
        with pytest.raises(ValueError):finder.nearest(*point)
    empty=NearestNativeCell(raw_directory=tmp_path/'missing',cache_directory=tmp_path/'cache2')
    with pytest.raises(FileNotFoundError):empty.nearest(0,0)


def test_real_nasa_native_support_is_persisted_and_bound_to_source_hash(tmp_path):
    raw=tmp_path/'raw';raw.mkdir()
    source=next((ROOT/'data/raw/gldas').glob('*.A200301.*.nc4'))
    shutil.copyfile(source,raw/source.name)
    finder=NearestNativeCell(raw_directory=raw,cache_directory=tmp_path/'cache')
    real=finder.nearest(-97.875,37.125)
    assert real['region_id']=='gldas025_r388_c0328'
    assert real['distance_km']<1e-8
    assert real['valid_soil_months']==1 and real['source_months_available']==1
    files=list((tmp_path/'cache').glob('native-soil-support-union-v2_*.npz'))
    assert len(files)==1
    with np.load(files[0],allow_pickle=False) as stored:
        metadata=json.loads(str(stored['metadata'].item()))
        assert metadata['source_release_sha256']==real['source_release_sha256']
        assert stored['counts'].dtype==np.uint16
    second=NearestNativeCell(raw_directory=raw,cache_directory=tmp_path/'cache')
    assert second.nearest(-97.875,37.125)['region_id']==real['region_id']
