import { LocationData, RegionalDetail } from '../types/contracts';
import { DEMO_ANALYSIS, DEMO_TIMESERIES } from '../mock/mockData';
import { SelectedLocation } from '../types/globe';

export const API_BASE_URL = import.meta.env.VITE_API_URL || '';
export async function apiJson(path: string, init?: RequestInit) {
  const res = await fetch(API_BASE_URL + path, init);
  if (!res.ok) throw new Error(`Request unavailable (${res.status})`);
  return res.json();
}
export const apiService = {
  async getRegions() { return apiJson('/api/v1/regions'); },
  async getFineTiles() { return apiJson('/api/v1/fine-tiles'); },
  async getFineRegions(tileId?: string) { return apiJson('/api/v1/fine-regions' + (tileId ? '?tile_id=' + encodeURIComponent(tileId) : '')); },
  async getLocationData(location: SelectedLocation): Promise<LocationData> {
    if (location.regionId === 'demo-region') return {
      hasData: true, isSynthetic: true, observations: DEMO_TIMESERIES,
      analysis: DEMO_ANALYSIS, statusMessage: 'Synthetic demonstration; not NASA observations.'
    };
    if (!location.regionId?.startsWith('grid_r') && !location.regionId?.startsWith('gldas025_')) return {
      hasData: false, isSynthetic: false, statusMessage: 'Select a registered grid cell for real observations.'
    };
    try {
      const detail: RegionalDetail = await apiJson(`/api/v1/regions/${encodeURIComponent(location.regionId)}`);
      const analysis = detail.available_indicator_analysis || detail.paired_analysis || undefined;
      return { hasData: detail.observations.some(o => o.value !== null), isSynthetic: false,
        observations: detail.observations, analysis, detail,
        statusMessage: 'Real NASA-derived observations · source QA review pending. ' +
          `Paired screening: ${detail.screening?.classification || 'unavailable'}.` };
    } catch { return { hasData: false, isSynthetic: false,
      statusMessage: 'Real-data service unavailable. Start the regional API on port 8000; no synthetic data substituted.' }; }
  },
};
