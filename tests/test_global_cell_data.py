"""Read-only native lookup tests using copied real NASA source files."""
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
import pytest
import src.global_cell_data as mod
from src.fine_grid import cell_id

ROOT=Path(__file__).resolve().parents[1]


def one_real_month(tmp_path):
    raw=tmp_path/'raw';raw.mkdir()
    original=next((ROOT/'data/raw/gldas').glob('*A200301.*.nc4'))
    shutil.copy2(original,raw/original.name)
    return raw


def test_lookup_uses_real_native_values_preserves_gaps_and_caches(tmp_path):
    raw=one_real_month(tmp_path);cache=tmp_path/'cache';rid=cell_id(388,328)
    result=mod.load_global_cell(rid,raw_directory=raw,cache_directory=cache)
    frame=result['observations']
    assert len(frame)==528 and frame.value.notna().sum()==2
    assert frame.groupby('variable').size().eq(264).all()
    assert set(frame.unit)=={'kg m-2'} and set(frame.variable)=={'soil_water_0_10cm','soil_water_0_100cm'}
    assert frame.loc[frame.date>pd.Timestamp('2003-01-01'),'value'].isna().all()
    assert frame.loc[frame.date>pd.Timestamp('2003-01-01'),'quality_flag'].eq('missing').all()
    reference=pd.read_csv(ROOT/'data/processed/fine/central_us/gldas_monthly_timeseries.csv',float_precision='round_trip')
    for var in frame.variable.unique():
        actual=frame.loc[(frame.variable==var)&frame.date.eq(pd.Timestamp('2003-01-01')),'value'].iloc[0]
        expected=reference.loc[(reference.region_id==rid)&(reference.variable==var)&reference.date.eq('2003-01-01'),'value'].iloc[0]
        assert actual==expected
    assert result['status']=='soil_only_pending_ndvi' and not result['cache_hit']
    assert result['provenance']['source_months_available']==1 and result['provenance']['local_processed_at_utc']
    assert result['research_context']['jurisdictions'][0]['country_code']=='US'
    warm=mod.load_global_cell(rid,raw_directory=raw,cache_directory=cache)
    assert warm['cache_hit'] and warm['research_context']['dataset_version']==result['research_context']['dataset_version']
    pd.testing.assert_frame_equal(warm['observations'],result['observations'])
    # Adding actual missing input invalidates the source release and cached cell.
    extra=next((ROOT/'data/raw/gldas').glob('*A200302.*.nc4'));shutil.copy2(extra,raw/extra.name)
    updated=mod.load_global_cell(rid,raw_directory=raw,cache_directory=cache)
    assert not updated['cache_hit'] and updated['observations'].value.notna().sum()==4
    assert updated['research_context']['dataset_version']!=result['research_context']['dataset_version']


def test_ocean_fill_is_unsupported_not_finite_or_synthetic(tmp_path):
    raw=one_real_month(tmp_path);lookup=mod.locate_cell(-150,0)
    result=mod.load_global_cell(lookup['region_id'],raw_directory=raw,cache_directory=tmp_path/'cache')
    assert result['status']=='unsupported_gldas' and result['observations'].value.isna().all()
    january=result['observations'].loc[result['observations'].date.eq(pd.Timestamp('2003-01-01'))]
    assert january.quality_flag.eq('no_valid_pixels').all()
    assert result['screening'] is None and result['availability']['qa_reviewed'] is False
    assert result['research_context']['jurisdictions']==[]


def test_coordinate_and_missing_source_boundaries_are_explicit(tmp_path):
    outside=mod.locate_cell(40,-80)
    assert outside['region_id'] is None and outside['status']=='outside_gldas_extent'
    assert mod.locate_cell(180,0)['region_id']==mod.locate_cell(-180,0)['region_id']
    for point in [(181,0),(0,91),(np.nan,0),(True,20)]:
        with pytest.raises(ValueError):mod.locate_cell(*point)
    with pytest.raises(ValueError):mod.load_global_cell('../../escape')
    for directory in [tmp_path/'absent',tmp_path]:
        with pytest.raises(FileNotFoundError):
            mod.load_global_cell(cell_id(388,328),raw_directory=directory,cache_directory=tmp_path/'cache')


def test_tampered_cell_cache_fails_integrity_before_reuse(tmp_path):
    raw=one_real_month(tmp_path);cache=tmp_path/'cache';rid=cell_id(388,328)
    mod.load_global_cell(rid,raw_directory=raw,cache_directory=cache)
    (cache/rid/'monthly_timeseries.csv').write_text('SYNTHETIC_CORRUPTION')
    with pytest.raises(ValueError,match='cache integrity'):
        mod.load_global_cell(rid,raw_directory=raw,cache_directory=cache)
