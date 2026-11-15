"""Explicitly synthetic paired cases; probabilities must never be fabricated."""
from copy import deepcopy

import numpy as np
import pandas as pd
import pytest

from src.fine_grid import cell_feature
from src.global_screening import AREA_METHOD, SCOPE, analyze_paired_cell, screen_global_cell
from src.region_transport import build_region_detail


@pytest.fixture
def inputs():
    feature = cell_feature(388,328); rid = feature['id']
    dates = pd.date_range('2003-01-01','2024-12-01',freq='MS'); years=dates.year-2003
    frames=[]
    for variable,values,unit in [('ndvi',.2+.01*years,'1'),('soil_water_0_100cm',100-2*years,'kg m-2'),('soil_water_0_10cm',30-.1*years,'kg m-2')]:
        frames.append(pd.DataFrame({'date':dates,'value':values,'variable':variable,'unit':unit,
            'source':'SYNTHETIC_TEST_ONLY','region_id':rid,'quality_flag':'coverage_review_required',
            'valid_area_fraction':1.,'valid_area_m2':feature['properties']['region_area_m2'],
            'region_area_m2':feature['properties']['region_area_m2'],
            'area_method':AREA_METHOD if variable=='ndvi' else None,'target_resolution_degrees':.25}))
    bundle={'region_id':rid,'feature':feature,'observations':pd.concat(frames[1:],ignore_index=True),
        'provenance':{'data_kind':'SYNTHETIC_TEST_ONLY'},'screening':None,'screening_status':'pending_ndvi',
        'research_context':{'region_id':rid,'dataset_version':'SYNTHETIC_SOURCE_VERSION'}}
    return bundle,frames[0]


def test_supported_within_cell_signal_exposes_evidence_and_no_risk_probability(inputs):
    bundle,ndvi=inputs; original=bundle['observations'].copy(deep=True)
    result=analyze_paired_cell(bundle,ndvi)
    record=result['screening']; decision=record['screening']
    assert decision['category']=='Supported Signal'
    assert decision['classification']=='supported_signal'
    assert decision['evidence_level']=='provisional_supported'
    assert decision['probability'] is None and decision['probability_status']=='not_calibrated'
    assert decision['family_scope']==SCOPE
    assert decision['multiple_testing']['family_size']==2
    assert not decision['multiple_testing']['globally_adjusted']
    assert decision['provisional'] and not decision['qa_reviewed']
    assert 'source review pending' in decision['confidence_label']
    assert 'p-value is not the probability' in decision['limitations'][0]
    assert decision['adjusted_p_values']==record['analysis']['adjusted_p_values']
    assert len(build_region_detail(result)['annual_fits']['ndvi']['points'])==22
    pd.testing.assert_frame_equal(bundle['observations'],original)


def test_nonopposing_trends_do_not_get_promoted_to_problem_probability(inputs):
    bundle,ndvi=inputs
    water=bundle['observations'].variable.eq('soil_water_0_100cm')
    bundle['observations'].loc[water,'value'] *= -1
    # Keep the unit-test values positive with a positive trend.
    bundle['observations'].loc[water,'value'] += 200
    decision=analyze_paired_cell(bundle,ndvi)['screening']['screening']
    assert decision['classification']=='no_detected_divergence'
    assert decision['evidence_level']=='not_detected'
    assert decision['probability'] is None


def test_missing_month_changes_eight_complete_years_to_insufficient_without_imputation(inputs):
    bundle,ndvi=inputs
    missing=ndvi.date.dt.year >= 2011
    ndvi.loc[missing,'value']=np.nan
    ndvi.loc[missing,'quality_flag']='no_valid_pixels'
    assert analyze_paired_cell(bundle,ndvi)['screening']['status']=='eligible'
    ndvi.loc[0,'value']=np.nan
    ndvi.loc[0,'quality_flag']='no_valid_pixels'
    result=analyze_paired_cell(bundle,ndvi)
    record=result['screening']
    assert record['status']=='insufficient'
    assert record['screening']['category'] is None
    assert record['screening']['evidence_level']=='insufficient'
    assert record['screening']['multiple_testing']['family_size']==0
    assert len(record['available_indicator_analysis']['observation_period']['years'])==22
    assert result['observations'].query("variable=='ndvi'").value.isna().sum()==ndvi.value.isna().sum()


def test_no_native_ndvi_stays_pending_and_never_emits_a_paired_probability(inputs):
    bundle,_=inputs
    decision=screen_global_cell(bundle)['screening']['screening']
    assert decision['classification']=='pending'
    assert decision['evidence_level']=='pending'
    assert decision['multiple_testing']['family_size']==0
    assert decision['probability'] is None


def test_legacy_area_coarse_support_and_duplicate_ndvi_are_rejected(inputs):
    bundle,ndvi=inputs
    bad=ndvi.copy();bad['area_method']='legacy_ellipsoidal_area'
    with pytest.raises(ValueError,match='area_methodv2'):
        analyze_paired_cell(bundle,bad)
    bad=ndvi.copy();bad['region_area_m2'] *= 1600
    with pytest.raises(ValueError,match='exact native-cell area'):
        analyze_paired_cell(bundle,bad)
    bad=deepcopy(bundle);bad['feature']['properties']['bbox']=[-100,30,-90,40]
    with pytest.raises(ValueError,match='same canonical native'):
        analyze_paired_cell(bad,ndvi)
    result=analyze_paired_cell(bundle,ndvi)
    with pytest.raises(ValueError,match='soil-only'):
        analyze_paired_cell(result,ndvi)


def test_cached_classifications_are_isolated_and_changed_data_changes_identity(inputs):
    bundle,ndvi=inputs
    first=analyze_paired_cell(bundle,ndvi)
    version=first['research_context']['dataset_version']
    first['screening']['screening']['probability']=.99
    second=analyze_paired_cell(bundle,ndvi)
    assert second['screening']['screening']['probability'] is None
    assert second['research_context']['dataset_version']==version
    changed=ndvi.copy();changed.loc[0,'value'] += .001
    assert analyze_paired_cell(bundle,changed)['research_context']['dataset_version'] != version


def test_real_native_pair_uses_original_within_cell_tests_not_collection_q_values():
    import json
    from pathlib import Path
    directory=Path(__file__).resolve().parents[1]/'data/processed/fine/collection'
    frame=pd.read_csv(directory/'monthly_timeseries.csv',dtype={'unit':str},float_precision='round_trip')
    catalog=json.loads((directory/'catalog.json').read_text())
    feature=catalog['features'][0];rid=feature['properties']['region_id']
    single=frame[frame.region_id==rid]
    ndvi=single[single.variable=='ndvi'].copy()
    bundle={'region_id':rid,'feature':feature,'observations':single[single.variable!='ndvi'].copy(),
        'provenance':{'data_kind':'real NASA-derived existing native-cell release'},
        'research_context':{'region_id':rid,'dataset_version':'existing-real-source-comparison'}}
    result=analyze_paired_cell(bundle,ndvi)
    original=next(record for record in json.loads((directory/'screening.json').read_text())['regions'] if record['region_id']==rid)
    actual=result['screening']['analysis']
    assert actual['observation_period']==original['analysis']['observation_period']
    for variable in ('ndvi','soil_water_0_100cm'):
        assert actual['adjusted_p_values'][variable]==pytest.approx(original['analysis']['adjusted_p_values'][variable])
    assert not actual['data_quality']['synthetic_demo']
    assert result['screening']['screening']['probability'] is None
    assert result['screening']['screening']['multiple_testing']['family_size']==2
