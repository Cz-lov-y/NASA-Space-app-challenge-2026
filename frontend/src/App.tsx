import React, { useState, useEffect, useCallback, useRef } from 'react';
import { EarthCanvas } from './components/globe/EarthCanvas';
import { HeaderHUD } from './components/hud/HeaderHUD';
import { SlidingPanel } from './components/panel/SlidingPanel';
import { InfoModal } from './components/modals/InfoModal';
import { GeoCoordinate, ModalType, SelectedLocation } from './types/globe';
import { apiService } from './services/api';
import { mapRegion, fineGridId } from './services/regions';
import { RegionalDetail } from './types/contracts';

export const App: React.FC = () => {
  const [selectedCoordinate, setSelectedCoordinate] = useState<GeoCoordinate | null>(null);
  const [selectedLocation, setSelectedLocation] = useState<SelectedLocation | null>(null);
  const [activeModal, setActiveModal] = useState<ModalType>(null);
  const [visitedRegions, setVisitedRegions] = useState<SelectedLocation[]>([]);
  const [availableRegions, setAvailableRegions] = useState<SelectedLocation[]>([]);
  const [preparedRegions, setPreparedRegions] = useState<SelectedLocation[]>([]);
  const [analyzedRegions, setAnalyzedRegions] = useState<SelectedLocation[]>([]);
  const analyzedIds = useRef(new Set<string>());
  const [catalogError, setCatalogError] = useState(false);

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
    const candidates = [...preparedRegions, ...availableRegions.filter(r =>
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
          if (!result.hasData || !result.detail?.feature?.properties?.centroid) continue;
          const p = result.detail.feature.properties;
          const computed = mapRegion({properties: {...p,
            classification: result.detail.screening?.classification || 'pending',
            family_scope: result.detail.screening?.family_scope, indicators: {data: true}}});
          setAnalyzedRegions(current => [...current.filter(r => r.id !== computed.id), computed]);
        } catch {
          // A later catalog refresh can retry unavailable local data.
          analyzedIds.current.delete(region.regionId!);
        }
      }
    };
    void Promise.all([work(), work()]);
    return () => { active = false; };
  }, [preparedRegions, availableRegions]);

  const handleSelectCoordinate = useCallback((coord: GeoCoordinate) => {
    const regionId = fineGridId(coord.lat, coord.lng);
    const latStr = coord.lat >= 0 ? `${coord.lat.toFixed(2)}°N` : `${Math.abs(coord.lat).toFixed(2)}°S`;
    const lngStr = coord.lng >= 0 ? `${coord.lng.toFixed(2)}°E` : `${Math.abs(coord.lng).toFixed(2)}°W`;
    setSelectedCoordinate(coord);
    setSelectedLocation({
      id: regionId || `coord-${coord.lat.toFixed(2)}-${coord.lng.toFixed(2)}`,
      regionId: regionId || undefined,
      name: `Point (${latStr}, ${lngStr})`,
      lat: coord.lat, lng: coord.lng,
      hasObservationalData: false, isSyntheticDemo: false,
      country: 'Global Surface Point',
    });
  }, []);

  const handleSelectLocation = useCallback((location: SelectedLocation) => {
    setSelectedCoordinate({ lat: location.lat, lng: location.lng });
    setSelectedLocation(location);
  }, []);

  const recordDetail = useCallback((detail: RegionalDetail) => {
    const p = detail.feature?.properties;
    if (!p?.centroid || !detail.observations.some(o => o.value !== null)) return;
    const region = mapRegion({ properties: { ...p,
      classification: detail.screening?.classification || 'pending',
      family_scope: detail.screening?.family_scope,
      indicators: { data: true },
    } });
    setVisitedRegions(current => [...current.filter(r => r.id !== region.id), region]);
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

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-space-950 font-sans">
      <EarthCanvas selectedCoordinate={selectedCoordinate} onSelectCoordinate={handleSelectCoordinate}
        onDeselect={handleDeselect} regions={mapRegions} />
      <HeaderHUD onOpenModal={setActiveModal} selectedCoordinate={selectedCoordinate} />
      <div className="fixed top-20 left-4 z-30 w-56 max-w-[calc(100vw-2rem)] rounded-xl border border-cyan-500/20 bg-space-900/95 p-3 text-xs text-slate-200 shadow-lg backdrop-blur">
        <p className="font-semibold text-white">Explore Earth</p>
        <p className="mt-1 text-slate-400">Select a place on the globe to see its data.</p>
        <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 border-t border-slate-700 pt-2 text-[11px] text-slate-400" aria-label="Map legend">
          <span><span className="text-red-600">●</span> Stronger signal</span>
          <span><span className="text-yellow-600">●</span> Uncertain</span>
          <span><span className="text-green-600">●</span> No signal</span>
          <span><span className="text-slate-500">●</span> Not yet analyzed</span>
        </div>
        <div className="mt-3 border-t border-slate-700 pt-2">
          <p className="font-semibold text-white">Places with a stronger signal</p>
          {redRegions.length ? <ul className="mt-2 max-h-40 space-y-1 overflow-y-auto">
            {redRegions.map(region => <li key={region.id}><button type="button"
              onClick={() => handleSelectLocation(region)}
              className="w-full rounded-md px-2 py-1.5 text-left text-red-700 hover:bg-red-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-red-600">
              <span aria-hidden="true">● </span>{region.name}
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
