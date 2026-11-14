/**
 * TypeScript definitions mirroring Member B, A, C contracts
 * as specified in docs/contracts.md
 */

export interface TimeSeriesObservation {
  date: string; // ISO date
  value: number | null;
  unit: string;
  variable: 'ndvi' | 'soil_moisture' | string;
  source: string;
  region_id: string;
}

export interface ProvenanceMetadata {
  spatial_coverage: {
    description: string;
    geometry?: any;
    coordinates?: [number, number]; // [lon, lat]
    bbox?: [number, number, number, number];
  };
  time_range: {
    start: string;
    end: string;
  };
  temporal_resolution: string;
  dataset_version: string;
  quality_control: {
    description: string;
    missing_value_encoding: string;
    missing_count: number;
    qa_reviewed?: boolean;
  };
}

export interface TrendResult {
  n_observations: number;
  slope_per_year: number;
  unit: string;
  slope_95ci: [number, number];
  p_value: number;
  theil_sen_slope_per_year?: number;
  kendall_tau?: number;
}

export interface RegionalDataQuality {
  n_raw_rows: number;
  qa_reviewed: boolean;
  synthetic_demo: boolean;
  sources: string[];
  missing_fraction?: number;
}

export type DivergenceCategory = 'Supported Signal' | 'Uncertain Signal' | 'No Detected Divergence';

export interface RegionalAnalysis {
  region: string;
  observation_period: [string, string];
  variables: string[];
  trend_slopes: Record<string, number>;
  confidence_intervals: Record<string, [number, number]>;
  p_values: Record<string, number>;
  data_quality: RegionalDataQuality;
  divergence_detected: boolean | null;
  divergence_status?: 'supported_signal' | 'uncertain_signal' | 'no_detected_divergence';
  divergence_category?: DivergenceCategory;
  limitations: string[];
  trends?: Record<string, TrendResult>;
}

export interface PolicyReport {
  region: string;
  policies: Array<{
    title: string;
    jurisdiction?: string;
    effective_date?: string;
    summary?: string;
    source_type?: string;
    official_url?: string;
    verification_status?: string;
  }>;
  scientific_studies: Array<{
    title: string;
    authors?: string[];
    year?: number;
    summary?: string;
    doi_url?: string;
    verification_status?: string;
  }>;
  potential_policy_gaps: string[];
  conservation_options: string[];
  citations: string[];
  verification_status: 'not_started' | 'in_progress' | 'verified';
  limitations: string[];
}
