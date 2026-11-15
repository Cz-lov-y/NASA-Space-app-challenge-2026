"""Standalone global-cell inference: synthetic fixtures and one real soil sample."""
from copy import deepcopy
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.fine_grid import cell_feature
from src.global_cell_analysis import analyze_global_cell
from src.region_transport import build_region_detail


@pytest.fixture
def bundle():
    feature = cell_feature(388,328)
    rid = feature['id']
    dates = pd.date_range('2003-01-01','2024-12-01',freq='MS')
    year = dates.year-2003
    frames = []
    for var,value in [('soil_water_0_10cm',30-.1*year),('soil_water_0_100cm',100-2*year)]:
        frames.append(pd.DataFrame({'date':dates,'value':value,'variable':var,'unit':'kg m-2',
            'source':'SYNTHETIC_TEST_ONLY','region_id':rid,'quality_flag':'coverage_review_required',
            'valid_area_fraction':1.,'valid_area_m2':feature['properties']['region_area_m2'],
            'region_area_m2':feature['properties']['region_area_m2']}))
    return {'region_id':rid,'feature':feature,'observations':pd.concat(frames,ignore_index=True),
            'provenance':{'data_kind':'SYNTHETIC_TEST_ONLY'},'screening':None,'screening_status':'pending_ndvi',
            'research_context':{'region_id':rid,'bbox':feature['properties']['bbox'],'jurisdictions':[],
                'dataset_version':'SYNTHETIC_RAW_VERSION','period':['2003-01-01','2024-12-31']}}


def test_standalone_native_soil_has_no_paired_or_worldwide_classification(bundle):
    original = bundle['observations'].copy(deep=True)
    result = analyze_global_cell(bundle)
    detail = build_region_detail(result)
    record = result['screening']
    assert result['screening_status'] == 'current'
    assert record['analysis'] is None
    assert record['screening']['category'] is None
    assert record['screening']['classification'] == 'pending'
    assert record['screening']['adjusted_p_values'] == {}
    diagnostic = record['available_indicator_analysis']
    assert diagnostic['variables'] == ['soil_water_0_100cm']
    assert diagnostic['trend_slopes']['soil_water_0_100cm'] == pytest.approx(-2)
    assert diagnostic['observation_period']['years'] == list(range(2003,2025))
    assert diagnostic['divergence_detected'] is None
    assert diagnostic['inference_scope'] == 'single_cell_single_indicator_exploratory'
    assert 'not corrected across global cells' in diagnostic['limitations'][0]
    assert not diagnostic['data_quality']['qa_reviewed']
    assert diagnostic['data_quality']['synthetic_demo']
    assert len(detail['observations']) == 528
    assert len(detail['annual_fits']['soil_water_0_100cm']['points']) == 22
    pd.testing.assert_frame_equal(bundle['observations'],original)
    assert bundle['screening'] is None


def test_qc_missing_months_stay_missing_and_exclude_whole_calendar_year(bundle):
    frame = bundle['observations']
    indices = frame.index[frame.variable == 'soil_water_0_100cm']
    frame.loc[indices[0],'value'] = np.nan
    frame.loc[indices[1],'quality_flag'] = 'low_coverage'
    original_second = frame.loc[indices[1],'value']
    result = analyze_global_cell(bundle)
    diagnostic = result['screening']['available_indicator_analysis']
    assert 2003 not in diagnostic['observation_period']['years']
    assert len(diagnostic['observation_period']['years']) == 21
    assert result['observations'].loc[indices[1],'value'] == original_second
    assert pd.isna(result['observations'].loc[indices[0],'value'])
    assert build_region_detail(result)['screening']['category'] is None


def test_no_valid_land_support_is_unsupported_without_fake_trends(bundle):
    bundle['observations']['value'] = np.nan
    bundle['observations']['quality_flag'] = 'no_valid_pixels'
    result = analyze_global_cell(bundle)
    assert result['screening']['status'] == 'unsupported'
    assert result['screening']['screening']['classification'] == 'unsupported'
    assert result['screening']['available_indicator_analysis'] is None
    assert build_region_detail(result)['annual_fits'] == {}


def test_coarse_ndvi_cannot_be_inserted_into_native_cell_analysis(bundle):
    coarse = bundle['observations'].iloc[:1].copy()
    coarse['variable'] = 'ndvi'
    coarse['unit'] = '1'
    coarse['source'] = 'SYNTHETIC_COARSE_CONTEXT_ONLY'
    bundle['observations'] = pd.concat([bundle['observations'],coarse])
    with pytest.raises(ValueError,match='keep coarse NDVI separate'):
        analyze_global_cell(bundle)


def test_cached_outputs_are_isolated_and_identity_changes_with_source_revision(bundle):
    first = analyze_global_cell(bundle)
    original_version = first['research_context']['dataset_version']
    first['screening']['available_indicator_analysis']['trend_slopes']['soil_water_0_100cm'] = 123
    again = analyze_global_cell(bundle)
    assert again['screening']['available_indicator_analysis']['trend_slopes']['soil_water_0_100cm'] == pytest.approx(-2)
    assert again['research_context']['dataset_version'] == original_version
    changed = deepcopy(bundle)
    changed['research_context']['dataset_version'] = 'NEW_SYNTHETIC_RAW_VERSION'
    assert analyze_global_cell(changed)['research_context']['dataset_version'] != original_version
    changed = deepcopy(bundle)
    changed['observations'].loc[0,'value'] += 1
    assert analyze_global_cell(changed)['research_context']['dataset_version'] != original_version


def test_bad_units_geometry_or_month_index_are_rejected(bundle):
    bad = deepcopy(bundle)
    bad['observations']['unit'] = 'm3 m-3'
    with pytest.raises(ValueError,match='kg m-2'):
        analyze_global_cell(bad)
    bad = deepcopy(bundle)
    bad['feature']['properties']['bbox'] = [-100,30,-90,40]
    with pytest.raises(ValueError,match='exact native'):
        analyze_global_cell(bad)
    bad = deepcopy(bundle)
    bad['observations'] = bad['observations'].iloc[1:]
    with pytest.raises(ValueError,match='264-month'):
        analyze_global_cell(bad)


def test_actual_native_gldas_sample_remains_real_standalone22_years():
    path = Path(__file__).resolve().parents[1]/'data/processed/fine/central_us/gldas_monthly_timeseries.csv'
    frame = pd.read_csv(path,dtype={'unit':str},float_precision='round_trip')
    feature = cell_feature(388,328); rid = feature['id']
    source = frame[frame.region_id == rid].copy()
    real = {'region_id':rid,'feature':feature,'observations':source,
            'provenance':{'dataset_version':'GLDAS_NOAH025_M.2.1'},
            'research_context':{'region_id':rid,'dataset_version':hashlib.sha256(path.read_bytes()).hexdigest()},
            'screening':None,'screening_status':'pending_ndvi'}
    detail = build_region_detail(analyze_global_cell(real))
    assert detail['paired_analysis'] is None
    assert detail['available_indicator_analysis']['observation_period']['years'] == list(range(2003,2025))
    assert not detail['scientific_display']['synthetic_demo']
    assert len(detail['annual_fits']['soil_water_0_100cm']['points']) == 22
    soil = pd.DataFrame(detail['observations']).query("variable == 'soil_water_0_100cm'")
    assert soil.source.eq('GLDAS_NOAH025_M.2.1').all()
    assert soil.unit.eq('kg m-2').all()
