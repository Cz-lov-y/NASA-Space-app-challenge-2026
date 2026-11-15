"""Frozen tile registry and joint-family viewport invariants, without providers."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import pytest

from src.fine_grid import cell_feature
from src.fine_workflow import load_tile_index,fine_tiles,registered_fine_map,load_registered_fine_region


@pytest.fixture
def collection(tmp_path):
    root=tmp_path
    base=root/'data/processed/fine'
    base.mkdir(parents=True)
    features=[cell_feature(388,328),cell_feature(456,296)]
    tiles=[{'id':'central_us_1deg','name':'US test cell','bbox':features[0]['properties']['bbox'],
            'directory':'data/processed/fine/us'},
           {'id':'canada_1deg','name':'Canada test cell','bbox':features[1]['properties']['bbox'],
            'directory':'data/processed/fine/canada'}]
    registry={'schema_version':'fine-tiles-1','collection_directory':'data/processed/fine/collection','tiles':tiles}
    path=base/'tiles.json';path.write_text(json.dumps(registry))
    release=base/'collection';release.mkdir()
    (release/'monthly_timeseries.csv').write_text('SYNTHETIC_TEST_SOURCE_BYTES_ONLY')
    (release/'catalog.json').write_text(json.dumps({'features':features}))
    (release/'metadata.json').write_text('{}')
    (release/'screening.json').write_text('{}')
    family={'catalog_regions':2,'family_size':4,'eligible_regions':2,'scope':'Frozen joint test family'}
    payload={'type':'FeatureCollection','features':features,'multiple_testing':family,
             'source_csv_sha256':hashlib.sha256((release/'monthly_timeseries.csv').read_bytes()).hexdigest(),
             'source_catalog_sha256':hashlib.sha256((release/'catalog.json').read_bytes()).hexdigest()}
    (release/'map_screening.geojson').write_text(json.dumps(payload))
    manifest={'schema_version':'fine-collection-inputs-1','index_file':str(path.relative_to(root)),
              'index_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'tiles':[],
              'files':[{'file':str(path.relative_to(root)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]}
    for tile in tiles:
        source=root/tile['directory'];source.mkdir()
        hashes={}
        for name in ('catalog.json','monthly_timeseries.csv','gldas_monthly_timeseries.csv','metadata.json','source_manifest.json'):
            target=source/name
            target.write_text('SYNTHETIC_TEST_INPUT '+name)
            digest=hashlib.sha256(target.read_bytes()).hexdigest()
            hashes[name]=digest
            manifest['files'].append({'file':str(target.relative_to(root)),'sha256':digest})
        manifest['tiles'].append({'id':tile['id'],'directory':tile['directory'],'files':hashes})
    (release/'input_manifest.json').write_text(json.dumps(manifest))
    return root,path,release,registry,features


def test_viewport_keeps_joint_family_and_source_hashes(collection):
    root,path,release,registry,features=collection
    result=registered_fine_map('canada_1deg',index_path=path,root=root)
    assert [f['id'] for f in result['features']]==[features[1]['id']]
    assert result['multiple_testing']['catalog_regions']==2
    assert result['multiple_testing']['family_size']==4
    assert result['viewport']['family_regions']==2
    assert result['viewport']['release_scope']=='joint_collection'
    assert result['viewport']['selection_only']
    # A viewport never writes back a one-cell replacement of the two-cell map.
    original=json.loads((release/'map_screening.geojson').read_text())
    assert len(original['features'])==2
    assert result['source_csv_sha256']==original['source_csv_sha256']
    index=fine_tiles(index_path=path,root=root)
    assert [t['status'] for t in index['tiles']]==['available','available']


def test_registered_detail_uses_collection_and_identifies_tile(collection,monkeypatch):
    import src.fine_workflow as workflow
    root,path,release,registry,features=collection
    calls=[]
    def load(region_id,**kwargs):
        calls.append((region_id,kwargs['directory']))
        feature=next(f for f in features if f['id']==region_id)
        return {'feature':deepcopy(feature),'provenance':{},'screening_status':'current'}
    monkeypatch.setattr(workflow,'load_fine_region',load)
    result=load_registered_fine_region(features[1]['id'],index_path=path,root=root)
    assert calls[0][1]==release
    assert result['provenance']['fine_tile']['id']=='canada_1deg'
    assert result['provenance']['fine_tile']['release_scope']=='joint_collection'
    with pytest.raises(ValueError,match='registered'):
        load_registered_fine_region('gldas025_r000_c0000',index_path=path,root=root)


@pytest.mark.parametrize('bad',['absolute','traversal','duplicate','overlap','unaligned','unknown'])
def test_registry_rejects_unsafe_or_ambiguous_selection(collection,bad):
    root,path,release,registry,features=collection
    if bad=='absolute':
        registry['tiles'][0]['directory']='/etc'
    elif bad=='traversal':
        registry['tiles'][0]['directory']='data/processed/fine/../../../..'
    elif bad=='duplicate':
        registry['tiles'][1]['id']=registry['tiles'][0]['id']
    elif bad=='overlap':
        registry['tiles'][1]['bbox']=registry['tiles'][0]['bbox']
    elif bad=='unaligned':
        registry['tiles'][0]['bbox'][0]+=.01
    else:
        with pytest.raises(ValueError,match='Unknown'):
            registered_fine_map('../../secret',index_path=path,root=root)
        return
    path.write_text(json.dumps(registry))
    with pytest.raises(ValueError):
        load_tile_index(index_path=path,root=root)


def test_published_stale_collection_is_withheld_not_replaced_by_individual_family(collection):
    root,path,release,registry,features=collection
    # Even if an individual tile has files, stale joint statistics must fail.
    (release/'monthly_timeseries.csv').write_text('NEW_TEST_SOURCE_REVISION')
    with pytest.raises(ValueError,match='rebuild'):
        registered_fine_map('central_us_1deg',index_path=path,root=root)
    index=fine_tiles(index_path=path,root=root)
    assert all(t['status']=='stale' for t in index['tiles'])


def test_before_collection_publication_only_available_registered_tile_is_served(collection):
    root,path,release,registry,features=collection
    (release/'map_screening.geojson').unlink()
    individual=root/registry['tiles'][0]['directory']
    for name in ('monthly_timeseries.csv','catalog.json','metadata.json','screening.json'):
        (individual/name).write_bytes((release/name).read_bytes())
    payload={'features':[features[0]],'multiple_testing':{'catalog_regions':1,'family_size':2},
             'source_csv_sha256':hashlib.sha256((individual/'monthly_timeseries.csv').read_bytes()).hexdigest(),
             'source_catalog_sha256':hashlib.sha256((individual/'catalog.json').read_bytes()).hexdigest()}
    (individual/'map_screening.geojson').write_text(json.dumps(payload))
    selected=registered_fine_map('central_us_1deg',index_path=path,root=root)
    assert selected['viewport']['release_scope']=='individual_tile_before_collection'
    index=fine_tiles(index_path=path,root=root)
    assert [t['status'] for t in index['tiles']]==['available','pending']


@pytest.mark.parametrize('changed',['monthly_timeseries.csv','catalog.json','metadata.json','source_manifest.json','accepted_modis_observations.csv'])
def test_changed_individual_tile_input_invalidates_unchanged_collection_snapshot(collection,changed):
    from src.fine_workflow import FineCollectionStale
    root,path,release,registry,features=collection
    source=root/registry['tiles'][1]['directory']/changed
    source.write_text('NEW_SYNTHETIC_SOURCE_REVISION')
    # Collection CSV/catalog/map bytes have not changed, yet serving the old
    # snapshot as current would ignore a new input tile revision.
    with pytest.raises(FineCollectionStale,match='source inputs changed'):
        registered_fine_map('central_us_1deg',index_path=path,root=root)
    index=fine_tiles(index_path=path,root=root)
    assert all(tile['status']=='stale' for tile in index['tiles'])
