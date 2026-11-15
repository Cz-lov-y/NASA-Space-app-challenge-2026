"""Exploratory standalone native-cell GLDAS inference; no local NDVI invention."""
from copy import deepcopy
from functools import lru_cache
import hashlib
from io import StringIO
import json

import pandas as pd

from .fine_grid import cell_feature, parse_cell_id
from .preprocessing import validate_timeseries
from .regional_statistics import build_regional_screening

ADAPTER_VERSION = 'global-native-soil-diagnostic-1'
SOIL_VARIABLES = {'soil_water_0_10cm', 'soil_water_0_100cm'}
LIMITATION = ('On-demand single-cell soil diagnostic only. No native-cell NDVI is supplied; '
              '10-degree NDVI aggregates cannot establish a paired 0.25-degree signal. '
              'These p-values are exploratory and are not corrected across global cells or repeated selections.')


@lru_cache(maxsize=64)
def _derive(csv, feature_json, version):
    frame = pd.read_csv(StringIO(csv), dtype={'unit': str})
    feature = json.loads(feature_json)
    record = build_regional_screening(frame, [feature], dataset_version=version)['regions'][0]
    diagnostic = record.get('available_indicator_analysis')
    if diagnostic:
        diagnostic['limitations'].insert(0, LIMITATION)
        diagnostic['inference_scope'] = 'single_cell_single_indicator_exploratory'
    record['screening']['paired_testing_scope'] = 'No paired tests; native-cell NDVI unavailable'
    record['screening']['standalone_inference_scope'] = 'No correction across cells or repeated selections'
    return record


def analyze_global_cell(bundle: dict) -> dict:
    """Return B's source bundle with an isolated, version-bound scientific record.

    Only native soil observations may enter this adapter. Separate coarse NDVI
    context remains outside its input table, paired analysis and classification.
    Source values/flags are preserved; rejected QA rows affect analysis copies only.
    """
    region_id = bundle['region_id']
    canonical = cell_feature(*parse_cell_id(region_id))
    feature = deepcopy(bundle['feature'])
    props = feature['properties']
    if (props.get('region_id') != region_id or feature['geometry'] != canonical['geometry']
            or props.get('bbox') != canonical['properties']['bbox']):
        raise ValueError('On-demand analysis requires the exact native-cell geometry')
    raw = bundle['observations']
    if not raw.empty and pd.api.types.is_numeric_dtype(raw['date']):
        raise ValueError('Source dates must be calendar dates, not epoch numbers')
    frame = validate_timeseries(raw, allow_missing=True)
    if set(frame.region_id) != {region_id} or set(frame.variable) != SOIL_VARIABLES:
        raise ValueError('Native-cell analysis accepts exactly the two canonical soil series; keep coarse NDVI separate')
    if not frame.unit.eq('kg m-2').all():
        raise ValueError('Native GLDAS soil storage must remain kg m-2')
    expected = set(pd.date_range('2003-01-01', '2024-12-01', freq='MS').strftime('%Y-%m-%d'))
    dates = pd.to_datetime(frame.date, utc=True)
    if not dates.dt.day.eq(1).all() or not dates.eq(dates.dt.normalize()).all():
        raise ValueError('Native observations must use monthly calendar anchors')
    frame['date'] = dates.dt.strftime('%Y-%m-%d')
    for _, single in frame.groupby('variable'):
        if len(single) != 264 or set(single.date) != expected:
            raise ValueError('Preserve the full264-month2003-2024index, including missing months')
        if single.source.nunique() != 1:
            raise ValueError('Each native indicator must retain one source product')
    supported = bool(frame.value.notna().any())
    props['data_status'] = 'pending_ndvi' if supported else 'unsupported_gldas'
    csv = frame.to_csv(index=False, float_format='%.17g')
    feature_json = json.dumps(feature, sort_keys=True, allow_nan=False)
    raw_version = str(bundle.get('research_context', {}).get('dataset_version', ''))
    version = hashlib.sha256((ADAPTER_VERSION + raw_version + csv + feature_json).encode()).hexdigest()
    record = deepcopy(_derive(csv, feature_json, version))
    result = deepcopy(bundle)
    result.update(feature=feature, screening=record, screening_status='current',
                  analysis_scope='single_cell_single_indicator_exploratory', analysis_version=ADAPTER_VERSION)
    result['research_context']['raw_dataset_version'] = raw_version
    result['research_context']['dataset_version'] = version
    result['provenance']['resolution_notice'] = LIMITATION
    result['provenance']['analysis_scope'] = 'single_cell_single_indicator_exploratory'
    result['provenance']['qa_reviewed'] = False
    return result
