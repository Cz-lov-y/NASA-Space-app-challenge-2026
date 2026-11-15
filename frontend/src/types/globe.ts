export interface GeoCoordinate {
  lat: number;
  lng: number;
}

export interface SelectedLocation {
  id: string;
  name: string;
  lat: number;
  lng: number;
  hasObservationalData: boolean;
  isSyntheticDemo: boolean;
  regionId?: string;
  country?: string;
  description?: string;
  climateZone?: string;
  screeningStatus?: string;
  bbox?: [number, number, number, number];
  resolutionDegrees?: number;
  pairedYearCount?: number;
  isTileNavigation?: boolean;
  isExploratoryScreening?: boolean;
}

export type ModalType = 'intro' | 'instructions' | 'methodology' | null;
