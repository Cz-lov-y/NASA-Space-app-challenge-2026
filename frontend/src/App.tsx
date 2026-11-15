import React, { useState, useEffect, useCallback, useRef } from 'react';
import { EarthCanvas } from './components/globe/EarthCanvas';
import { HeaderHUD } from './components/hud/HeaderHUD';
import { SlidingPanel } from './components/panel/SlidingPanel';
import { InfoModal } from './components/modals/InfoModal';
import { GeoCoordinate, ModalType, SelectedLocation } from './types/globe';
import { PRESET_REGIONS } from './mock/regions';
import { apiService } from './services/api';
import { mapRegion, gridId, fineGridId, DEMO_REGION_IDS } from './services/regions';
import { RegionalDetail } from './types/contracts';

export const App: React.FC = () => {
  const [selectedCoordinate, setSelectedCoordinate] = useState<GeoCoordinate | null>(null);
  const [selectedLocation, setSelectedLocation] = useState<SelectedLocation | null>(null);
  const [activeModal, setActiveModal] = useState<ModalType>(null);

  const [regions, setRegions] = useState<SelectedLocation[]>([]);
  const [fineRegions, setFineRegions] = useState<SelectedLocation[]>([]);
  const [preparedRegions, setPreparedRegions] = useState<SelectedLocation[]>([]);
  const [visitedRegions, setVisitedRegions] = useState<SelectedLocation[]>([]);
  const [savedRegions, setSavedRegions] = useState<SelectedLocation[]>([]);
  const [screenedTotal, setScreenedTotal] = useState(0);
  const [screenedOffset, setScreenedOffset] = useState(0);
  const [fineError, setFineError] = useState(false);
  const [fineMode, setFineMode] = useState(true);
  const [tiles, setTiles] = useState<any[]>([]);
  const [tileId, setTileId] = useState('central_us_1deg');
  const [tileLoading, setTileLoading] = useState(false);
  const [family, setFamily] = useState<any>(null);
  const pendingPoint = useRef<GeoCoordinate | null>(null);
  useEffect(() => {
    let active = true;
    const refresh = () => apiService.getGlobalScreenedCells(screenedOffset).then(data => {
      if (active) { setScreenedTotal(data.total || 0); setSavedRegions(data.features.map((f: any) => mapRegion({ ...f, properties: { ...f.properties, indicators: f.properties.classification === 'unsupported' ? {} : { data: true } } }))); }
    }).catch(() => {});
    void refresh(); const timer = setInterval(refresh, 20000);
    return () => { active = false; clearInterval(timer); };
  }, [screenedOffset]);
  useEffect(() => { let active = true; apiService.getFineTiles().then(data => {
    if (active) setTiles(data.tiles);
  }).catch(() => { if (active) setFineError(true); }); return () => { active = false; }; }, []);
  useEffect(() => {
    let active = true;
    if (tiles.length) Promise.all(tiles.filter(t => t.status === 'available').map(t => apiService.getFineRegions(t.id)))
      .then(maps => { if (active) setPreparedRegions(maps.flatMap(m => m.features.map(mapRegion))); })
      .catch(() => { if (active) setPreparedRegions([]); });
    return () => { active = false; };
  }, [tiles]);
  useEffect(() => {
    let active = true; setTileLoading(true); setFineError(false); setFineRegions([]); setFamily(null);
    apiService.getFineRegions(tileId).then(data => {
      if (!active) return;
      const loaded = data.features.map(mapRegion);
      setFineRegions(loaded); setFamily(data.multiple_testing);
      const point = pendingPoint.current;
      if (point) setSelectedLocation(loaded.find((r: SelectedLocation) => r.id === fineGridId(point.lat,point.lng)) || null);
    }).catch(() => { if (active) setFineError(true); }).finally(() => { if (active) setTileLoading(false); });
    return () => { active = false; };
  }, [tileId]);
  const navigateTile = useCallback((id: string, point: GeoCoordinate | null = null) => {
    pendingPoint.current = point; setSelectedLocation(null); setSelectedCoordinate(point); setTileId(id);
  }, []);
  const [catalogError, setCatalogError] = useState(false);
  useEffect(() => { let active = true; apiService.getRegions().then(data => {
    if (active) setRegions(data.features.map(mapRegion));
  }).catch(() => { if (active) setCatalogError(true); }); return () => { active = false; }; }, []);
  const visibleRegions = fineMode ? fineRegions : regions;
  const menuRegions = fineMode ? [...fineRegions, PRESET_REGIONS[0]] : [...DEMO_REGION_IDS.map(id => regions.find(r => r.id === id)).filter((r): r is SelectedLocation => !!r),
    ...regions.filter(r => r.hasObservationalData && !DEMO_REGION_IDS.includes(r.id)), PRESET_REGIONS[0]];

  // Handle geographic point click on the 3D globe
  const handleSelectCoordinate = useCallback((coord: GeoCoordinate) => {
    setSelectedCoordinate(coord);

    if (fineMode) {
      const tile = tiles.find(t => coord.lng >= t.bbox[0] && coord.lng < t.bbox[2] && coord.lat >= t.bbox[1] && coord.lat < t.bbox[3]);
      if (tile && tile.id !== tileId) { navigateTile(tile.id, coord); return; }
    }
    // Resolve a point to its actual stored native cell.
    const matchedPreset = visibleRegions.find(r => r.id === (fineMode ? fineGridId(coord.lat, coord.lng) : gridId(coord.lat, coord.lng)));

    if (matchedPreset) {
      setSelectedLocation(matchedPreset);
    } else {
      const latStr = coord.lat >= 0 ? `${coord.lat.toFixed(2)}°N` : `${Math.abs(coord.lat).toFixed(2)}°S`;
      const lngStr = coord.lng >= 0 ? `${coord.lng.toFixed(2)}°E` : `${Math.abs(coord.lng).toFixed(2)}°W`;

      const nativeId = fineMode ? fineGridId(coord.lat, coord.lng) : null;
      setSelectedLocation({
        id: nativeId || `coord-${coord.lat.toFixed(2)}-${coord.lng.toFixed(2)}`,
        regionId: nativeId || undefined,
        name: `Point (${latStr}, ${lngStr})`,
        lat: coord.lat,
        lng: coord.lng,
        hasObservationalData: false,
        isSyntheticDemo: false,
        country: 'Global Surface Point',
        description: nativeId ? 'Native 0.25° GLDAS cell at this point. Vegetation data and paired analysis may be pending.' : 'This point is outside the available native GLDAS grid.',
      });
    }
  }, [visibleRegions, fineMode, tiles, tileId, navigateTile]);

  // Handle direct selection from Hotspots dropdown
  const handleSelectPreset = useCallback((location: SelectedLocation) => {
    setSelectedCoordinate({ lat: location.lat, lng: location.lng });
    setSelectedLocation(location);
  }, []);

  const recordDetail = useCallback((detail: RegionalDetail) => {
    const p = detail.feature?.properties;
    if (!p?.centroid || !detail.observations.some(o => o.value !== null)) return;
    const region = mapRegion({ properties: { ...p, classification: detail.screening?.classification || 'pending', family_scope: detail.screening?.family_scope || (detail.ndvi_retrieval ? 'single-cell exploratory' : undefined),
      indicators: { data: true } } });
    setVisitedRegions(current => [...current.filter(r => r.id !== region.id), region]);
  }, []);

  // Deselect and return Earth to centered initial state
  const handleDeselect = useCallback(() => {
    pendingPoint.current = null;
    setSelectedCoordinate(null);
    setSelectedLocation(null);
  }, []);

  // Keyboard accessibility: ESC key resets selection or closes modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (activeModal) {
          setActiveModal(null);
        } else if (selectedCoordinate) {
          handleDeselect();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [activeModal, selectedCoordinate, handleDeselect]);

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-space-950 font-sans">
      {/* 3D Earth Canvas Viewport */}
      <EarthCanvas
        selectedCoordinate={selectedCoordinate}
        onSelectCoordinate={handleSelectCoordinate}
        onDeselect={handleDeselect}
        regions={fineMode ? [...visibleRegions, ...preparedRegions.filter(r => !visibleRegions.some(v => v.id === r.id)), ...visitedRegions.filter(r => !visibleRegions.some(v => v.id === r.id) && !preparedRegions.some(v => v.id === r.id)), ...savedRegions.filter(r => !visibleRegions.some(v => v.id === r.id) && !preparedRegions.some(v => v.id === r.id) && !visitedRegions.some(v => v.id === r.id)), ...tiles.filter(t => t.id !== tileId).map(t => ({
          id: `tile-${t.id}`, name: t.name, lat: (t.bbox[1]+t.bbox[3])/2, lng: (t.bbox[0]+t.bbox[2])/2,
          hasObservationalData: false, isSyntheticDemo: false, isTileNavigation: true,
        }))] : visibleRegions}
      />

      {/* Top Telemetry Header HUD */}
      <HeaderHUD
        onOpenModal={setActiveModal}
        selectedCoordinate={selectedCoordinate}
        selectedLocation={selectedLocation}
        onSelectPreset={handleSelectPreset}
        regions={menuRegions}
      />

      <div className="fixed top-20 left-4 z-30 w-56 max-w-[calc(100vw-2rem)] rounded-xl border border-cyan-500/20 bg-space-900/95 p-3 text-xs text-slate-200 shadow-lg backdrop-blur">
        <p className="font-semibold text-white">Explore Earth</p>
        <p className="mt-1 text-slate-400">Select a place on the globe to see its data.</p>
        {fineMode && <label className="mt-3 block text-slate-400">Visit an example
          <select aria-label="Fine data area" className="mt-1 block w-full rounded-lg border border-slate-700 bg-space-950 p-2 text-slate-100" value={tileId}
            onChange={e => {
              const tile = tiles.find(t => t.id === e.target.value);
              navigateTile(e.target.value, tile ? { lat: (tile.bbox[1] + tile.bbox[3]) / 2, lng: (tile.bbox[0] + tile.bbox[2]) / 2 } : null);
            }}>
            {tiles.map(t => <option key={t.id} value={t.id}>{t.name}{t.status === 'pending' ? ' · pending' : ''}</option>)}
          </select>
        </label>}
        {fineMode && tileLoading && <p className="mt-2 text-slate-400">Loading area…</p>}
        {fineMode && fineError && <p className="mt-2 text-amber-300">Area data unavailable.</p>}
        <div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 border-t border-slate-700 pt-2 text-[11px] text-slate-400" aria-label="Map legend">
          <span><span className="text-red-600">●</span> Stronger signal</span>
          <span><span className="text-yellow-600">●</span> Uncertain</span>
          <span><span className="text-green-600">●</span> No signal</span>
          <span><span className="text-slate-500">●</span> Pending</span>
        </div>
        <details className="mt-2 text-[11px] text-slate-400">
          <summary className="cursor-pointer text-cyan-200">About this map</summary>
          <p className="mt-2">Red shows stronger evidence of opposing trends, yellow uncertain evidence, green no detected divergence, and gray insufficient or pending data. These are preliminary categories, not probabilities of harm or proof of safety. Circles use the six-area analysis; diamonds are individually screened cells. Global screening is still in progress.</p>
          {fineMode && family && <p className="mt-1">The six-area analysis includes {family.catalog_regions} cells and {family.family_size} tests.</p>}
          {fineMode && screenedTotal > 0 && <p className="mt-1">{screenedTotal} additional cells screened.</p>}
          {fineMode && screenedTotal > 1000 && <p className="mt-1"><button type="button" disabled={!screenedOffset} onClick={() => setScreenedOffset(Math.max(0, screenedOffset - 1000))} className="text-cyan-300 underline disabled:text-slate-600">Previous</button>{' · '}<button type="button" disabled={screenedOffset + 1000 >= screenedTotal} onClick={() => setScreenedOffset(screenedOffset + 1000)} className="text-cyan-300 underline disabled:text-slate-600">Next</button></p>}
          <label className="mt-2 flex items-center gap-2"><input type="checkbox" checked={fineMode} onChange={e => { setFineMode(e.target.checked); handleDeselect(); }} /> Native 0.25° cells</label>
        </details>
      </div>
      {catalogError && <div className="fixed bottom-4 left-4 z-40 bg-space-900 p-3 text-amber-200 text-xs">Regional API unavailable; synthetic demonstration remains available.</div>}

      {/* Sliding Right-side Telemetry & Information Panel */}
      <SlidingPanel
        location={selectedLocation}
        onClose={handleDeselect}
        onSelectPreset={handleSelectPreset}
        onDetail={recordDetail}
      />

      {/* Radix UI Accessible Modal Dialogs (Intro, Instructions, Methodology) */}
      <InfoModal
        type={activeModal}
        isOpen={Boolean(activeModal)}
        onClose={() => setActiveModal(null)}
      />
    </div>
  );
};

export default App;
