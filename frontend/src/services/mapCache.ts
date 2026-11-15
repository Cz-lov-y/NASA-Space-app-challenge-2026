import { SelectedLocation } from '../types/globe';

const KEY = 'earthrisk-map-screening-v1';
const MAX_AGE_MS = 24 * 60 * 60 * 1000;
const MAX_ENTRIES = 2000;
const STATUSES = new Set(['supported_signal', 'uncertain_signal', 'no_detected_divergence', 'insufficient', 'pending', 'unsupported']);
type Entry = { region: SelectedLocation; savedAt: number };

function readEntries(): Entry[] {
  try {
    const value: unknown = JSON.parse(localStorage.getItem(KEY) || '[]');
    if (!Array.isArray(value)) return [];
    return value.filter((entry): entry is Entry => {
      const r = entry?.region;
      return typeof entry?.savedAt === 'number' && entry.savedAt <= Date.now() && Date.now() - entry.savedAt < MAX_AGE_MS &&
        typeof r?.id === 'string' && /^gldas025_r\d{3}_c\d{4}$/.test(r.id) && r.regionId === r.id &&
        Number.isFinite(r.lat) && Number.isFinite(r.lng) && r.lat >= -60 && r.lat <= 90 && r.lng >= -180 && r.lng <= 180 &&
        Array.isArray(r.bbox) && r.bbox.length === 4 && r.bbox.every(Number.isFinite) &&
        typeof r.name === 'string' && STATUSES.has(r.screeningStatus);
    }).slice(-MAX_ENTRIES);
  } catch { return []; }
}

export function cachedMapRegions(): SelectedLocation[] {
  return readEntries().map(entry => entry.region);
}

export function rememberMapRegion(region: SelectedLocation): void {
  if (!region.screeningStatus || !STATUSES.has(region.screeningStatus)) return;
  try {
    const entries = readEntries().filter(entry => entry.region.id !== region.id);
    entries.push({region, savedAt: Date.now()});
    localStorage.setItem(KEY, JSON.stringify(entries.slice(-MAX_ENTRIES)));
  } catch { /* Browser storage may be disabled or full; calculations still work. */ }
}

export function forgetMapRegion(regionId: string): void {
  try { localStorage.setItem(KEY, JSON.stringify(readEntries().filter(entry => entry.region.id !== regionId))); }
  catch { /* Storage is optional. */ }
}
