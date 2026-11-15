import { SelectedLocation } from '../types/globe';
const LABELS: Record<string, string> = {
  grid_r12_c08: 'Central US', grid_r12_c17: 'Iberia / NW Africa',
  grid_r10_c18: 'Central Sahel', grid_r05_c32: 'Southeast Australia',
  grid_r08_c12: 'Brazilian Amazon', grid_r14_c07: 'Canadian interior',
};
export function mapRegion(feature: any): SelectedLocation {
  const p = feature.properties;
  const [lng, lat] = p.centroid;
  const fine = p.region_id.startsWith('gldas025_');
  return { id: p.region_id, regionId: p.region_id,
    name: (fine ? `${Math.abs(lat).toFixed(3)}°${lat < 0 ? 'S' : 'N'}, ${Math.abs(lng).toFixed(3)}°${lng < 0 ? 'W' : 'E'}` : LABELS[p.region_id] || p.name || p.region_id) + (fine ? ' · 0.25° cell' : ' · 10° overview'), lat, lng,
    bbox: p.bbox, resolutionDegrees: fine ? 0.25 : 10,
    pairedYearCount: p.paired_year_count || 0,
    isExploratoryScreening: typeof p.family_scope === 'string' && p.family_scope.includes('exploratory'),
    hasObservationalData: Object.keys(p.indicators || {}).length > 0,
    isSyntheticDemo: false, screeningStatus: p.classification,
    description: `${p.region_id} · ${p.classification}. Source QA review pending.`,
    country: p.jurisdictions?.[0]?.name || LABELS[p.region_id] || 'Regional NASA observations' };
}
export function fineGridId(lat: number, lng: number): string | null {
  if (!Number.isFinite(lat) || !Number.isFinite(lng) || lat < -60 || lat > 90) return null;
  const row = Math.min(599, Math.floor((lat + 60) / 0.25));
  const lon = ((lng + 180) % 360 + 360) % 360 - 180;
  const col = Math.floor((lon + 180) / 0.25);
  return `gldas025_r${String(row).padStart(3,'0')}_c${String(col).padStart(4,'0')}`;
}
export function gridId(lat: number, lng: number): string {
  const row = Math.min(17, Math.max(0, Math.floor((lat + 90) / 10)));
  const lon = ((lng + 180) % 360 + 360) % 360 - 180;
  const col = Math.min(35, Math.max(0, Math.floor((lon + 180) / 10)));
  return `grid_r${String(row).padStart(2,'0')}_c${String(col).padStart(2,'0')}`;
}
export const DEMO_REGION_IDS = Object.keys(LABELS);
