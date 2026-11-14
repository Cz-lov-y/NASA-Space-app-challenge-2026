"""Generate a synthetic B -> A -> C/D handoff example for review."""
import json
import numpy as np
import pandas as pd
from src.global_exploratory import analyze_global_exploratory


def build_example():
    dates = pd.date_range('2003-01-01', '2024-12-01', freq='MS')
    years = dates.year.to_numpy() - 2003
    season = np.sin(2 * np.pi * (dates.month.to_numpy() - 1) / 12)
    frames = []
    for name, unit, values in [('ndvi', '1', 0.3 + 0.002 * years + 0.03 * season),
                               ('soil_water_0_10cm', 'kg m-2', 30 - 0.04 * years + season)]:
        frames.append(pd.DataFrame({'date': dates.strftime('%Y-%m-%d'), 'value': values,
                                    'unit': unit, 'variable': name, 'source': 'SYNTHETIC_EXAMPLE',
                                    'region_id': 'whole_earth',
                                    'quality_flag': 'coverage_review_required',
                                    'valid_area_fraction': 0.17 if name == 'ndvi' else 0.26}))
    data = pd.concat(frames, ignore_index=True)
    analysis = analyze_global_exploratory(data, soil_moisture_variable='soil_water_0_10cm')
    metadata = {'spatial_coverage': 'Fictitious global example; no actual footprint',
                'time_range': {'start': '2003-01-01', 'end': '2024-12-31'},
                'temporal_resolution': 'synthetic monthly', 'dataset_version': 'synthetic-v1',
                'quality_control': 'No real QA; coverage values are illustrative'}
    return {'example_status': 'SYNTHETIC_EXAMPLE_NOT_OBSERVATIONS',
            'B_to_A': {'rows_excerpt': [f.iloc[0].to_dict() for f in frames],
                       'metadata_by_variable': {f.variable.iloc[0]: dict(metadata) for f in frames}},
            'A_to_C_D': analysis,
            'C_to_D_shape_only': {'region': 'whole_earth', 'policies': [], 'scientific_studies': [],
                                  'potential_policy_gaps': [], 'conservation_options': [],
                                  'citations': [], 'verification_status': 'not_started',
                                  'limitations': ['Synthetic shape-only example; no policy research performed.'],
                                  'candidate_sources': []}}


if __name__ == '__main__':
    print(json.dumps(build_example(), indent=2, allow_nan=False))
