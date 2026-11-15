import React, { useState, useEffect, useCallback, useRef } from 'react';
import { EarthCanvas } from './components/globe/EarthCanvas';
import { HeaderHUD } from './components/hud/HeaderHUD';
import { SlidingPanel } from './components/panel/SlidingPanel';
import { InfoModal } from './components/modals/InfoModal';
import { GeoCoordinate, ModalType, SelectedLocation } from './types/globe';
import { apiService } from './services/api';
import { mapRegion, fineGridId } from './services/regions';
import { RegionalDetail } from './types/contracts';
import { cachedMapRegions, forgetMapRegion, rememberMapRegion } from './services/mapCache';
import { Geography, loadGeography, placeLabel } from './services/geography';

export const App: React.FC = () => {
  const [selectedCoordinate, setSelectedCoordinate] = useState<GeoCoordinate | null>(null);
  const [selectedLocation, setSelectedLocation] = useState<SelectedLocation | null>(null);
  const [activeModal, setActiveModal] = useState<ModalType>(null);
  const [visitedRegions, setVisitedRegions] = useState<SelectedLocation[]>([]);
  const [availableRegions, setAvailableRegions] = useState<SelectedLocation[]>([]);
  const [preparedRegions, setPreparedRegions] = useState<SelectedLocation[]>([]);
  const [restoredRegions] = useState(cachedMapRegions);
  const [analyzedRegions, setAnalyzedRegions] = useState<SelectedLocation[]>(restoredRegions);
  const analyzedIds = useRef(new Set<string>());
  const [catalogError, setCatalogError] = useState(false);
  const [geography, setGeography] = useState<Geography | null>(null);
  const [geographyError, setGeographyError] = useState(false);
  useEffect(() => { let active = true; loadGeography().then(value => { if (active) setGeography(value); })
    .catch(() => { if (active) setGeographyError(true); }); return () => { active = false; }; }, []);

  // Previously processed cells indicate where data are available. Their stored
  // classifications can use a different statistical family, so the map uses
  // the same browser calculation for colors as the location panel instead.
  useEffect(() => {
    let active = true;
    const refresh = () => apiService.getGlobalScreenedCells().then(data => {
      if (!active) return;
      setAvailableRegions(data.features.map((f: any) => mapRegion({ ...f, properties: {
        ...f.properties,
        indicators: f.properties.classification === 'unsupported' ? {} : { data: true },
      } })));
      setCatalogError(false);
    }).catch(() => { if (active) setCatalogError(true); });
    void refresh();
    const timer = setInterval(refresh, 20000);
    return () => { active = false; clearInterval(timer); };
  }, []);

  // The six original areas remain ordinary native cells, using the same live
  // calculation and source observations as every other prepared cell.
  useEffect(() => {
    let active = true;
    apiService.getFineTiles().then(data => Promise.all(
      data.tiles.filter((tile: any) => tile.status === 'available')
        .map((tile: any) => apiService.getFineRegions(tile.id))
    )).then(maps => {
      if (active) setPreparedRegions(maps.flatMap((m: any) => m.features.map(mapRegion)));
    }).catch(() => {});
    return () => { active = false; };
  }, []);

  useEffect(() => {
    let active = true;
    // Pilot cells and other completed paired cells use the same browser
    // computation. Cached-only requests never start Earth Engine retrievals.
    const candidates = [...preparedRegions, ...restoredRegions, ...availableRegions.filter(r =>
      ['supported_signal', 'uncertain_signal', 'no_detected_divergence'].includes(r.screeningStatus || ''))];
    const queued = new Set<string>();
    const unique = candidates.filter(region => {
      if (!region.regionId || analyzedIds.current.has(region.regionId) || queued.has(region.regionId)) return false;
      queued.add(region.regionId);
      return true;
    });
    let next = 0;
    const work = async () => {
      while (active && next < unique.length) {
        const region = unique[next++];
        analyzedIds.current.add(region.regionId!);
        try {
          const result = await apiService.getCachedLocationData(region.regionId!);
          if (!active) { analyzedIds.current.delete(region.regionId!); return; }
          if (!result.hasData || !result.detail?.feature?.properties?.centroid) {
            forgetMapRegion(region.regionId!);
            setAnalyzedRegions(current => current.filter(r => r.id !== region.id));
            continue;
          }
          const p = result.detail.feature.properties;
          const computed = mapRegion({properties: {...p,
            classification: result.detail.screening?.classification || 'pending',
            family_scope: result.detail.screening?.family_scope, indicators: {data: true}}});
          rememberMapRegion(computed);
          setAnalyzedRegions(current => [...current.filter(r => r.id !== computed.id), computed]);
        } catch {
          // A later catalog refresh can retry unavailable local data.
          analyzedIds.current.delete(region.regionId!);
        }
      }
    };
    void Promise.all([work(), work()]);
    return () => { active = false; };
  }, [preparedRegions, availableRegions, restoredRegions]);

  const handleSelectCoordinate = useCallback((coord: GeoCoordinate) => {
    const place = geography?.lookup(coord.lat, coord.lng);
    if (!place) return;
    const regionId = fineGridId(coord.lat, coord.lng);
    setSelectedCoordinate(coord);
    setSelectedLocation({
      id: regionId || `coord-${coord.lat.toFixed(2)}-${coord.lng.toFixed(2)}`,
      regionId: regionId || undefined,
      name: placeLabel(place),
      lat: coord.lat, lng: coord.lng,
      hasObservationalData: false, isSyntheticDemo: false,
      country: place.country,
    });
  }, [geography]);

  const handleSelectLocation = useCallback((location: SelectedLocation) => {
    const place = geography?.lookup(location.lat, location.lng);
    setSelectedCoordinate({ lat: location.lat, lng: location.lng });
    setSelectedLocation(place ? { ...location, name: placeLabel(place), country: place.country } : location);
  }, [geography]);

  const recordDetail = useCallback((detail: RegionalDetail) => {
    const p = detail.feature?.properties;
    if (!p?.centroid || !detail.observations.some(o => o.value !== null)) return;
    const region = mapRegion({ properties: { ...p,
      classification: detail.screening?.classification || 'pending',
      family_scope: detail.screening?.family_scope,
      indicators: { data: true },
    } });
    setVisitedRegions(current => [...current.filter(r => r.id !== region.id), region]);
    const window = detail.provenance?.live_analysis?.window;
    if (window?.[0] === 2003 && window?.[1] === 2024) {
      rememberMapRegion(region);
      setAnalyzedRegions(current => [...current.filter(r => r.id !== region.id), region]);
    }
  }, []);

  const handleDeselect = useCallback(() => {
    setSelectedCoordinate(null);
    setSelectedLocation(null);
  }, []);
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (activeModal) setActiveModal(null);
        else if (selectedCoordinate) handleDeselect();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeModal, selectedCoordinate, handleDeselect]);

  const visitedIds = new Set(visitedRegions.map(r => r.id));
  const liveRegions = [...visitedRegions, ...analyzedRegions.filter(r => !visitedIds.has(r.id))];
  const liveIds = new Set(liveRegions.map(r => r.id));
  const pendingRegions = [...preparedRegions, ...availableRegions]
    .filter((region, index, all) => !liveIds.has(region.id) && all.findIndex(r => r.id === region.id) === index)
    .map(region => ({ ...region, screeningStatus: 'pending' }));
  const mapRegions = [...liveRegions, ...pendingRegions];
  const redRegions = liveRegions.filter(r => r.screeningStatus === 'supported_signal');
  const redPlaces = new Map<string, { location: SelectedLocation; count: number }>();
  redRegions.forEach(region => {
    const place = geography?.lookup(region.lat, region.lng);
    const label = place ? placeLabel(place) : (region.country && region.country !== 'Regional NASA observations' ? region.country : 'Land location');
    const existing = redPlaces.get(label);
    if (existing) existing.count++;
    else redPlaces.set(label, { location: region, count: 1 });
  });

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-space-950 font-sans">
      <EarthCanvas selectedCoordinate={selectedCoordinate} onSelectCoordinate={handleSelectCoordinate}
        onDeselect={handleDeselect} regions={mapRegions} />
      <HeaderHUD onOpenModal={setActiveModal} selectedCoordinate={selectedCoordinate} />
      <div className="fixed top-20 left-4 z-30 w-56 max-w-[calc(100vw-2rem)] rounded-xl border border-cyan-500/20 bg-space-900/95 p-3 text-xs text-slate-200 shadow-lg backdrop-blur">
        <p className="font-semibold text-white">Explore Earth</p>
        <p className="mt-1 text-slate-400">{geographyError ? 'Land map unavailable. Refresh to try again.' : geography ? 'Select a place on land to see its data.' : 'Loading land map…'}</p>
        <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 border-t border-slate-700 pt-2 text-[11px] text-slate-400" aria-label="Map legend">
          <span><span className="text-red-600">●</span> Stronger signal</span>
          <span><span className="text-yellow-600">●</span> Uncertain</span>
          <span><span className="text-green-600">●</span> No signal</span>
          <span><span className="text-slate-500">●</span> Not yet analyzed</span>
        </div>
        <div className="mt-3 border-t border-slate-700 pt-2">
          <p className="font-semibold text-white">Places with a stronger signal</p>
          {redPlaces.size ? <ul className="mt-2 max-h-40 divide-y divide-slate-200 overflow-y-auto">
            {Array.from(redPlaces, ([label, item]) => <li key={label}><button type="button"
              onClick={() => handleSelectLocation(item.location)}
              title={item.count > 1 ? `View one of ${item.count} matching locations` : `View ${label}`}
              className="flex w-full items-center gap-2 rounded-md px-1 py-2 text-left text-slate-700 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-red-600">
              <span aria-hidden="true" className="h-2 w-2 shrink-0 rounded-full bg-red-600" />
              <span className="min-w-0 flex-1">{label}</span>
              {item.count > 1 && <span className="text-slate-500">{item.count}</span>}
            </button></li>)}
          </ul> : <p className="mt-1 text-slate-400">No stronger signals identified yet.</p>}
        </div>
      </div>
      {catalogError && <div className="fixed bottom-4 left-4 z-40 bg-space-900 p-3 text-amber-200 text-xs">Location data are temporarily unavailable. Please try again shortly.</div>}
      <SlidingPanel location={selectedLocation} onClose={handleDeselect} onSelectPreset={handleSelectLocation} onDetail={recordDetail} />
      <InfoModal type={activeModal} isOpen={Boolean(activeModal)} onClose={() => setActiveModal(null)} />
    </div>
  );
};

export default App;
