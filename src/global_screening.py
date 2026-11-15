"""Single-native-cell paired screening with explicit exploratory significance.

No fitted p-value is an environmental harm probability. Worldwide discovery
requires a separately declared joint family across the tested cells.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
from io import StringIO
import json

import numpy as np
import pandas as pd

from .fine_grid import cell_feature, parse_cell_id
from .global_cell_analysis import analyze_global_cell
from .preprocessing import validate_timeseries
from .regional_statistics import build_regional_screening

VERSION = 'native-paired-single-cell-screening-1'
AREA_METHOD = 'modis_sinusoidal_sphere_native_pixel_v2'
SCOPE = 'single-cell exploratory; not adjusted across regions'
NOTICE = ('Single-cell exploratory screening: BH covers only the two primary-indicator MK tests in this cell. '
          'Results have not been corrected across regions, repeated selections or a worldwide search. '
          'A p-value is not the probability of harm; no calibrated environmental-risk probability is available.')


def _decorate(record):
    decision = record['screening']
    category = decision.get('category')
    evidence = {'Supported Signal':'provisional_supported', 'Uncertain Signal':'uncertain',
                'No Detected Divergence':'not_detected'}.get(category, record['status'])
    labels = {'provisional_supported':'Provisional statistical support; source review pending',
              'uncertain':'Uncertain statistical evidence', 'not_detected':'No detected paired divergence',
              'insufficient':'Insufficient common complete years', 'pending':'Native NDVI pending',
              'unsupported':'No valid paired product support'}
    family_size = 2 if record['status'] == 'eligible' else 0
    decision.update(probability=None, probability_status='not_calibrated', evidence_level=evidence,
        confidence_label=labels[evidence], family_scope=SCOPE, provisional=True,
        multiple_testing={'method':'benjamini_hochberg', 'family_size':family_size,
                          'scope':SCOPE, 'globally_adjusted':False})
    decision['limitations'] = [NOTICE]
    for field in ('analysis', 'available_indicator_analysis'):
        if record.get(field):
            record[field]['limitations'].insert(0, NOTICE)
            record[field]['inference_scope'] = SCOPE
    return record


@lru_cache(maxsize=128)
def _derive(csv, feature_json, version):
    frame = pd.read_csv(StringIO(csv), dtype={'unit':str}, float_precision='round_trip')
    record = build_regional_screening(frame, [json.loads(feature_json)], dataset_version=version)['regions'][0]
    return _decorate(record)


def screen_global_cell(bundle: dict) -> dict:
    """Return the usual workflow bundle, using only actual same-cell monthly data.

    Both full monthly indexes retain null months. Missing/partial QA rejects can
    reduce analyzed common years; at least eight complete years are required.
    Additional surface soil observations are retained but do not join the pair.
    """
    if 'ndvi' not in set(bundle['observations'].variable):
        result = analyze_global_cell(bundle)
        result['screening'] = _decorate(result['screening'])
        result['analysis_scope'] = SCOPE
        return result
    rid = bundle['region_id']
    canonical = cell_feature(*parse_cell_id(rid))
    feature = deepcopy(bundle['feature'])
    p = feature['properties']
    if p.get('region_id') != rid or p.get('bbox') != canonical['properties']['bbox'] or feature['geometry'] != canonical['geometry']:
        raise ValueError('Paired observations require the same canonical native-cell geometry')
    raw = bundle['observations']
    if pd.api.types.is_numeric_dtype(raw.date):
        raise ValueError('Monthly dates must be calendar anchors, not epoch numbers')
    frame = validate_timeseries(raw, allow_missing=True)
    if set(frame.region_id) != {rid} or not {'ndvi','soil_water_0_100cm'} <= set(frame.variable) <= {'ndvi','soil_water_0_100cm','soil_water_0_10cm'}:
        raise ValueError('Require native-cell NDVI and canonical root-zone soil storage')
    expected = set(pd.date_range('2003-01-01','2024-12-01',freq='MS').strftime('%Y-%m-%d'))
    dates = pd.to_datetime(frame.date, utc=True)
    if not dates.dt.day.eq(1).all() or not dates.eq(dates.dt.normalize()).all():
        raise ValueError('Use first-of-month calendar dates')
    frame['date'] = dates.dt.strftime('%Y-%m-%d')
    for variable, single in frame.groupby('variable'):
        if len(single) != 264 or set(single.date) != expected:
            raise ValueError('Preserve each264-month index, including missing months')
        if single.source.nunique() != 1 or set(single.unit) != ({'1'} if variable == 'ndvi' else {'kg m-2'}):
            raise ValueError('Product sources and physical units must remain consistent')
    ndvi = frame[frame.variable == 'ndvi']
    actual = ndvi[~ndvi.quality_flag.eq('pending_export')] if 'quality_flag' in ndvi else ndvi
    if not actual.empty:
        if 'area_method' not in actual or not actual.area_method.eq(AREA_METHOD).all():
            raise ValueError('Native NDVI requires declared spherical native-pixel area_methodv2')
        if 'target_resolution_degrees' in actual and not actual.target_resolution_degrees.eq(.25).all():
            raise ValueError('Coarse NDVI cannot be paired with a native soil cell')
        if 'region_area_m2' not in actual or not np.allclose(actual.region_area_m2, canonical['properties']['region_area_m2'], rtol=1e-8):
            raise ValueError('NDVI footprint denominator must match the exact native-cell area')
    if not ndvi.loc[ndvi.value.notna(),'value'].between(-.2,1).all():
        raise ValueError('NDVI must be scaled once to its physical range')
    p['data_status'] = 'available' if frame.loc[frame.variable == 'soil_water_0_100cm','value'].notna().any() else 'unsupported_gldas'
    csv = frame.to_csv(index=False,float_format='%.17g')
    geometry_json = json.dumps(feature,sort_keys=True,allow_nan=False)
    raw_version = str(bundle.get('research_context',{}).get('dataset_version',''))
    version = hashlib.sha256((VERSION+raw_version+csv+geometry_json).encode()).hexdigest()
    result = deepcopy(bundle)
    result.update(feature=feature, screening=deepcopy(_derive(csv,geometry_json,version)),
                  screening_status='current', analysis_scope=SCOPE, analysis_version=VERSION)
    result['research_context']['raw_dataset_version'] = raw_version
    result['research_context']['dataset_version'] = version
    result['provenance']['resolution_notice'] = ('Native MODIS is aggregated into this exact0.25-degree GLDAS cell boundary; differing monthly valid footprints still require review. ' + NOTICE)
    result['provenance']['screening_scope'] = SCOPE
    result['provenance']['screening_limitations'] = [NOTICE]
    result['provenance']['qa_reviewed'] = False
    return result


def analyze_paired_cell(bundle: dict, ndvi_frame: pd.DataFrame) -> dict:
    """Attach a verified native NDVI monthly frame to a soil-only source bundle."""
    if 'ndvi' in set(bundle['observations'].variable):
        raise ValueError('Pass a soil-only bundle; native NDVI is supplied explicitly once')
    if not isinstance(ndvi_frame,pd.DataFrame) or set(ndvi_frame.variable) != {'ndvi'}:
        raise ValueError('ndvi_frame must contain only native monthly NDVI observations')
    combined = deepcopy(bundle)
    combined['observations'] = pd.concat([bundle['observations'],ndvi_frame],ignore_index=True)
    return screen_global_cell(combined)
