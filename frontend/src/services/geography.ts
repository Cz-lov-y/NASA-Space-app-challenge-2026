type Position = [number, number];
type Ring = Position[];
type Polygon = Ring[];
interface Boundary {
  name: string;
  country: string;
  bbox: [number, number, number, number];
  geometry: { type: 'Polygon' | 'MultiPolygon'; coordinates: Polygon | Polygon[] };
}
interface GeographyData { countries: Boundary[]; regions: Boundary[] }
export interface Place { name: string; country: string }

type Index = Map<string, Boundary[]>;
function indexBoundaries(features: Boundary[]): Index {
  const index: Index = new Map();
  for (const f of features) {
    const [w,s,e,n] = f.bbox;
    for (let x = Math.max(0, Math.floor((w + 180) / 10)); x <= Math.min(35, Math.floor((e + 180) / 10)); x++)
      for (let y = Math.max(0, Math.floor((s + 90) / 10)); y <= Math.min(17, Math.floor((n + 90) / 10)); y++) {
        const key = `${x},${y}`; const group = index.get(key) || [];
        group.push(f); index.set(key, group);
      }
  }
  return index;
}
function inRing(lon: number, lat: number, ring: Ring): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if ((yi > lat) !== (yj > lat) && lon < (xj - xi) * (lat - yi) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
function contains(feature: Boundary, lon: number, lat: number): boolean {
  const [w,s,e,n] = feature.bbox;
  if (lon < w || lon > e || lat < s || lat > n) return false;
  const polygons = feature.geometry.type === 'Polygon' ? [feature.geometry.coordinates as Polygon] : feature.geometry.coordinates as Polygon[];
  return polygons.some(p => p.length > 0 && inRing(lon, lat, p[0]) && !p.slice(1).some(hole => inRing(lon, lat, hole)));
}
export class Geography {
  private countries: Index;
  private regions: Index;
  constructor(data: GeographyData) {
    this.countries = indexBoundaries(data.countries);
    this.regions = indexBoundaries(data.regions);
  }
  lookup(lat: number, lon: number): Place | null {
    if (!Number.isFinite(lat) || !Number.isFinite(lon) || lat < -90 || lat > 90 || lon < -180 || lon > 180) return null;
    const key = `${Math.min(35, Math.floor((lon + 180) / 10))},${Math.min(17, Math.floor((lat + 90) / 10))}`;
    const country = (this.countries.get(key) || []).find(f => contains(f, lon, lat));
    if (!country) return null;
    const region = (this.regions.get(key) || []).find(f => f.country === country.name && contains(f, lon, lat));
    return {name: region?.name || country.name, country: country.name};
  }
}
export async function loadGeography(): Promise<Geography> {
  const response = await fetch('/data/geography.json');
  if (!response.ok) throw new Error('Land boundaries unavailable');
  return new Geography(await response.json());
}
export function placeLabel(place: Place): string {
  return place.name === place.country ? place.country : `${place.name}, ${place.country}`;
}
