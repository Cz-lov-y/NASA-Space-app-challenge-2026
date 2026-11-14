import { RegionalAnalysis, TimeSeriesObservation } from '../types/contracts';

export const DEMO_TIMESERIES: TimeSeriesObservation[] = [
  { date: '2015-06-01', region_id: 'demo-region', variable: 'ndvi', value: 0.38, unit: 'index', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2016-06-01', region_id: 'demo-region', variable: 'ndvi', value: 0.39, unit: 'index', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2017-06-01', region_id: 'demo-region', variable: 'ndvi', value: 0.42, unit: 'index', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2018-06-01', region_id: 'demo-region', variable: 'ndvi', value: 0.43, unit: 'index', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2019-06-01', region_id: 'demo-region', variable: 'ndvi', value: 0.44, unit: 'index', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2020-06-01', region_id: 'demo-region', variable: 'ndvi', value: 0.47, unit: 'index', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2021-06-01', region_id: 'demo-region', variable: 'ndvi', value: 0.49, unit: 'index', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2022-06-01', region_id: 'demo-region', variable: 'ndvi', value: 0.51, unit: 'index', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2023-06-01', region_id: 'demo-region', variable: 'ndvi', value: 0.53, unit: 'index', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2024-06-01', region_id: 'demo-region', variable: 'ndvi', value: 0.56, unit: 'index', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2015-06-01', region_id: 'demo-region', variable: 'soil_moisture', value: 26.1, unit: 'kg/m2', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2016-06-01', region_id: 'demo-region', variable: 'soil_moisture', value: 25.8, unit: 'kg/m2', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2017-06-01', region_id: 'demo-region', variable: 'soil_moisture', value: 24.6, unit: 'kg/m2', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2018-06-01', region_id: 'demo-region', variable: 'soil_moisture', value: 24.0, unit: 'kg/m2', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2019-06-01', region_id: 'demo-region', variable: 'soil_moisture', value: 23.2, unit: 'kg/m2', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2020-06-01', region_id: 'demo-region', variable: 'soil_moisture', value: 22.4, unit: 'kg/m2', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2021-06-01', region_id: 'demo-region', variable: 'soil_moisture', value: 21.9, unit: 'kg/m2', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2022-06-01', region_id: 'demo-region', variable: 'soil_moisture', value: 20.8, unit: 'kg/m2', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2023-06-01', region_id: 'demo-region', variable: 'soil_moisture', value: 19.7, unit: 'kg/m2', source: 'SYNTHETIC_DEMO_NOT_NASA' },
  { date: '2024-06-01', region_id: 'demo-region', variable: 'soil_moisture', value: 19.0, unit: 'kg/m2', source: 'SYNTHETIC_DEMO_NOT_NASA' },
];

export const DEMO_ANALYSIS: RegionalAnalysis = {
  region: 'demo-region',
  observation_period: ['2015-06-01', '2024-06-01'],
  variables: ['ndvi', 'soil_moisture'],
  trend_slopes: {
    ndvi: 0.020,
    soil_moisture: -0.793,
  },
  confidence_intervals: {
    ndvi: [0.018, 0.022],
    soil_moisture: [-0.852, -0.734],
  },
  p_values: {
    ndvi: 0.0001,
    soil_moisture: 0.0001,
  },
  data_quality: {
    n_raw_rows: 20,
    qa_reviewed: false,
    synthetic_demo: true,
    sources: ['SYNTHETIC_DEMO_NOT_NASA'],
  },
  divergence_detected: true,
  divergence_status: 'supported_signal',
  divergence_category: 'Supported Signal',
  limitations: [
    'Synthetic demonstration record only — not actual NASA satellite observations.',
    'Ten annual June snapshots cannot substitute for full 12-month calendar-year desequencing.',
    'Opposing trend signs establish a candidate divergence signal, not physical proof of ecological damage or irrigation depletion.',
  ],
  trends: {
    ndvi: {
      n_observations: 10,
      slope_per_year: 0.020,
      unit: 'index',
      slope_95ci: [0.018, 0.022],
      p_value: 0.0001,
      theil_sen_slope_per_year: 0.020,
      kendall_tau: 0.98,
    },
    soil_moisture: {
      n_observations: 10,
      slope_per_year: -0.793,
      unit: 'kg/m2',
      slope_95ci: [-0.852, -0.734],
      p_value: 0.0001,
      theil_sen_slope_per_year: -0.800,
      kendall_tau: -0.98,
    },
  },
};
