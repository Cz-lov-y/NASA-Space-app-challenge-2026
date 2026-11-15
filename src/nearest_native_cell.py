"""Nearest actual GLDAS-supported centroid on the sphere; no cloud calls."""
from io import BytesIO
import hashlib
import json
from pathlib import Path
from threading import Lock

import numpy as np
from scipy.spatial import cKDTree
import xarray as xr

from src.fine_grid import cell_feature
from src.global_cell_data import _source_release,_atomic,ROOT

METHOD='native-soil-support-union-v2'
LAYERS=('SoilMoi0_10cm_inst','SoilMoi10_40cm_inst','SoilMoi40_100cm_inst')


class NearestNativeCell:
    """One bounded current-release index, rebuilt when source metadata changes."""
    def __init__(self,*,raw_directory=ROOT/'data/raw/gldas',cache_directory=ROOT/'.cache/global_screen'):
        self.raw_directory=Path(raw_directory);self.cache_directory=Path(cache_directory)
        self.lock=Lock();self._signature=None;self._index=None

    def _inventory(self):
        return tuple((str(p.resolve()),p.stat().st_size,p.stat().st_mtime_ns)
                     for p in sorted(self.raw_directory.glob('*.nc4')))

    def _load_support(self):
        by_month,release=_source_release(self.raw_directory,self.cache_directory,False)
        sha=release['source_sha256'];path=self.cache_directory/(METHOD+'_'+sha+'.npz')
        counts=None
        if path.is_file():
            try:
                with np.load(path,allow_pickle=False) as saved:
                    candidate=saved['counts'];metadata=json.loads(str(saved['metadata'].item()))
                digest=hashlib.sha256(candidate.tobytes()).hexdigest()
                if (candidate.shape==(600,1440) and candidate.dtype==np.uint16
                        and candidate.max(initial=0)<=len(by_month)
                        and metadata=={'source_release_sha256':sha,'method':METHOD,'counts_sha256':digest}):
                    counts=candidate
            except (OSError,ValueError,KeyError,TypeError):pass
        if counts is None:
            counts=np.zeros((600,1440),dtype=np.uint16)
            for month,path_source in sorted(by_month.items()):
                with xr.open_dataset(path_source,mask_and_scale=True) as ds:
                    if (ds.sizes.get('time')!=1 or str(ds.time.values[0])[:10]!=month
                            or ds.sizes.get('lat')!=600 or ds.sizes.get('lon')!=1440
                            or not np.allclose(ds.lat.values,np.arange(600)*.25-59.875)
                            or not np.allclose(ds.lon.values,np.arange(1440)*.25-179.875)):
                        raise ValueError('Unexpected native source coordinates/time')
                    arrays=[]
                    for layer in LAYERS:
                        variable=ds[layer]
                        if (variable.attrs.get('units')!='kg m-2' or variable.attrs.get('cell_methods')!='time: mean'
                                or variable.encoding.get('scale_factor',1)!=1 or variable.encoding.get('add_offset',0)!=0):
                            raise ValueError('Unexpected native source units/scaling')
                        arrays.append(np.asarray(variable.isel(time=0).transpose('lat','lon').values,dtype=float))
                    surface=arrays[0]
                    root=arrays[0]+arrays[1]+arrays[2]
                    counts+=(np.isfinite(surface)&(surface>=0)) | (np.isfinite(root)&(root>=0))
            metadata={'source_release_sha256':sha,'method':METHOD,
                      'counts_sha256':hashlib.sha256(counts.tobytes()).hexdigest()}
            buffer=BytesIO();np.savez_compressed(buffer,counts=counts,metadata=json.dumps(metadata,sort_keys=True))
            _atomic(path,buffer.getvalue())
        rows,cols=np.where(counts>0)
        if not len(rows):raise ValueError('No valid native GLDAS cells')
        lon=np.deg2rad(-179.875+cols*.25);lat=np.deg2rad(-59.875+rows*.25)
        vectors=np.column_stack((np.cos(lat)*np.cos(lon),np.cos(lat)*np.sin(lon),np.sin(lat)))
        return {'tree':cKDTree(vectors),'vectors':vectors,'rows':rows,'cols':cols,'counts':counts,
                'release':sha,'source_months_available':len(by_month)}

    def nearest(self,lon,lat):
        if isinstance(lon,bool) or isinstance(lat,bool):raise ValueError('Coordinates must be numeric')
        lon,lat=float(lon),float(lat)
        if not np.isfinite(lon) or not np.isfinite(lat) or not -180<=lon<=180 or not -90<=lat<=90:
            raise ValueError('Invalid world coordinate')
        if not self.lock.acquire(timeout=30):raise TimeoutError('Support index is busy')
        try:
            signature=self._inventory()
            if not signature:raise FileNotFoundError('Native GLDAS sources unavailable')
            if signature!=self._signature or self._index is None:
                index=self._load_support()
                if self._inventory()!=signature:raise ValueError('Native sources changed during support indexing')
                self._index=index;self._signature=signature
            index=self._index
            lng,phi=np.deg2rad([lon,lat])
            vector=np.array([np.cos(phi)*np.cos(lng),np.cos(phi)*np.sin(lng),np.sin(phi)])
            chord,nearest=index['tree'].query(vector,k=1)
            # Resolve true equal-distance ties by canonical row/column order.
            candidates=index['tree'].query_ball_point(vector,float(chord)+1e-12)
            distances=np.linalg.norm(index['vectors'][candidates]-vector,axis=1)
            best=float(distances.min())
            tied=[i for i,d in zip(candidates,distances) if abs(float(d)-best)<=1e-12]
            selected=min(tied,key=lambda i:(int(index['rows'][i]),int(index['cols'][i])))
            row,col=int(index['rows'][selected]),int(index['cols'][selected])
            feature=cell_feature(row,col);p=feature['properties']
            distance=2*6371.007181*np.arcsin(min(1.,best/2))
            return {'schema_version':'nearest-native-cell-1','region_id':feature['id'],
                    'bbox':p['bbox'],'centroid':p['centroid'],'feature':feature,'distance_km':float(distance),
                    'query_coordinates':{'lon':lon,'lat':lat},'status':'actual_gldas_support',
                    'source_release_sha256':index['release'],'source_months_available':index['source_months_available'],
                    'valid_soil_months':int(index['counts'][row,col]),'ndvi_status':'not_checked',
                    'detail_url':'/api/v1/regions/'+feature['id'],
                    'observations_url':'/api/v1/regions/'+feature['id']+'/observations',
                    'selection_basis':'Nearest actual valid GLDAS native-cell centroid by great-circle distance',
                    'limitations':['Nearest centroid is a different location from the requested point; no spatial interpolation.',
                        'Support means at least one finite nonnegative soil series/month, not complete coverage or native NDVI availability.',
                        'Native GLDAS supports part of Earth; Antarctica and oceans may be far from the selected source cell.']}
        finally:self.lock.release()
