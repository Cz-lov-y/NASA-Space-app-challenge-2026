import { LocationData, RegionalDetail } from '../types/contracts';
import { DEMO_ANALYSIS, DEMO_TIMESERIES } from '../mock/mockData';
import { SelectedLocation } from '../types/globe';
import { computeLiveScreening } from './liveScreening';

export const API_BASE_URL = import.meta.env.VITE_API_URL || '';
export async function apiJson(path: string, init?: RequestInit) {
  const res = await fetch(API_BASE_URL + path, init);
  if (!res.ok) throw new Error(`Request unavailable (${res.status})`);
  return res.json();
}
export function locationDataFromDetail(detail: RegionalDetail): LocationData {
  const analysis = detail.available_indicator_analysis || detail.paired_analysis || undefined;
  const hasData = detail.observations.some(o => o.value !== null);
  return { hasData, isSynthetic: false, observations: detail.observations, analysis, detail,
    statusMessage: hasData ? 'Real NASA-derived data · source QA review pending. ' +
      `Paired screening: ${detail.screening?.classification || 'unavailable'}.` :
      'No valid GLDAS land-model values are available for this cell. Ocean, ice and other masked areas can be unsupported.' };
}
export const apiService = {
  async getRegions() { return apiJson('/api/v1/regions'); },
  async getFineTiles() { return apiJson('/api/v1/fine-tiles'); },
  async getGlobalScreenedCells(offset = 0) { return apiJson(`/api/v1/global-screened-cells?limit=1000&offset=${offset}`); },
  async getFineRegions(tileId?: string) { return apiJson('/api/v1/fine-regions' + (tileId ? '?tile_id=' + encodeURIComponent(tileId) : '')); },
  async getLocationData(location: SelectedLocation): Promise<LocationData> {
    if (location.regionId === 'demo-region') return {
      hasData: true, isSynthetic: true, observations: DEMO_TIMESERIES,
      analysis: DEMO_ANALYSIS, statusMessage: 'Synthetic demonstration; not NASA observations.'
    };
    if (!location.regionId?.startsWith('grid_r') && !location.regionId?.startsWith('gldas025_')) return {
      hasData: false, isSynthetic: false, statusMessage: 'This point is outside the available GLDAS land grid. Select another location.'
    };
    try {
      if (location.regionId.startsWith('gldas025_')) {
        const raw = await apiJson(`/api/v1/regions/${encodeURIComponent(location.regionId)}/observations`);
        const detail = computeLiveScreening(raw, { startYear: 2003, endYear: 2024 });
        return { ...locationDataFromDetail(detail), rawObservations: raw };
      }
      const detail: RegionalDetail = await apiJson(`/api/v1/regions/${encodeURIComponent(location.regionId)}`);
      return locationDataFromDetail(detail);
    } catch (error) { return { hasData: false, isSynthetic: false,
      statusMessage: error instanceof Error && error.message.includes('(429)')
        ? 'Another cell is loading. Select this point again in a few seconds.'
        : 'Real-data service unavailable. Start the regional API on port 8000; no synthetic data substituted.' }; }
  },
};
