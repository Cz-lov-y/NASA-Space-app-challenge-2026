import { RegionalAnalysis, TimeSeriesObservation } from '../types/contracts';
import { DEMO_ANALYSIS, DEMO_TIMESERIES } from '../mock/mockData';
import { PRESET_REGIONS } from '../mock/regions';
import { SelectedLocation } from '../types/globe';

const API_BASE_URL = import.meta.env.VITE_API_URL || '';

export const apiService = {
  /**
   * Check if a location has observational data available
   */
  async getLocationData(location: SelectedLocation): Promise<{
    hasData: boolean;
    isSynthetic: boolean;
    observations?: TimeSeriesObservation[];
    analysis?: RegionalAnalysis;
    statusMessage: string;
  }> {
    // If backend URL is specified, try fetching from future FastAPI
    if (API_BASE_URL && location.regionId) {
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/regions/${location.regionId}/analysis`);
        if (res.ok) {
          const data = await res.json();
          return {
            hasData: true,
            isSynthetic: data.data_quality?.synthetic_demo ?? false,
            analysis: data,
            statusMessage: 'Observations verified via backend connection.',
          };
        }
      } catch {
        // Fall back to client-side logic
      }
    }

    // Client-side mock evaluation
    if (location.id === 'demo-region' || location.regionId === 'demo-region') {
      return {
        hasData: true,
        isSynthetic: true,
        observations: DEMO_TIMESERIES,
        analysis: DEMO_ANALYSIS,
        statusMessage: 'Synthetic demonstration dataset loaded for testing.',
      };
    }

    // Check if it's one of the other presets awaiting Member B's pipeline
    const preset = PRESET_REGIONS.find((p) => p.id === location.id);
    if (preset) {
      return {
        hasData: false,
        isSynthetic: false,
        statusMessage: `Target region registered (${preset.name}). Awaiting calibrated NASA MODIS/GLDAS pipeline integration.`,
      };
    }

    // Arbitrary clicked coordinate on Earth
    return {
      hasData: false,
      isSynthetic: false,
      statusMessage: `Geographic coordinate selected: (${location.lat.toFixed(4)}°, ${location.lng.toFixed(4)}°). No observational records currently registered for this coordinate. Select a designated target region to inspect data.`,
    };
  },
};
