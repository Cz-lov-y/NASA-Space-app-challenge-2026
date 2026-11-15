import React, { useState, useEffect, useCallback, useRef } from 'react';
import { EarthCanvas } from './components/globe/EarthCanvas';
import { HeaderHUD } from './components/hud/HeaderHUD';
import { SlidingPanel } from './components/panel/SlidingPanel';
import { InfoModal } from './components/modals/InfoModal';
import { GeoCoordinate, ModalType, SelectedLocation } from './types/globe';
import { PRESET_REGIONS } from './mock/regions';
import { apiService } from './services/api';
import { mapRegion, gridId, fineGridId, DEMO_REGION_IDS } from './services/regions';

export const App: React.FC = () => {
  const [selectedCoordinate, setSelectedCoordinate] = useState<GeoCoordinate | null>(null);
  const [selectedLocation, setSelectedLocation] = useState<SelectedLocation | null>(null);
  const [activeModal, setActiveModal] = useState<ModalType>(null);

  const [regions, setRegions] = useState<SelectedLocation[]>([]);
  const [fineRegions, setFineRegions] = useState<SelectedLocation[]>([]);
  const [fineError, setFineError] = useState(false);
  const [fineMode, setFineMode] = useState(true);
  const [tiles, setTiles] = useState<any[]>([]);
  const [tileId, setTileId] = useState('central_us_1deg');
  const [tileLoading, setTileLoading] = useState(false);
  const [family, setFamily] = useState<any>(null);
  const pendingPoint = useRef<GeoCoordinate | null>(null);
  useEffect(() => { let active = true; apiService.getFineTiles().then(data => {
    if (active) setTiles(data.tiles);
  }).catch(() => { if (active) setFineError(true); }); return () => { active = false; }; }, []);
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
  const currentTile = tiles.find(t => t.id === tileId);
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
        regions={fineMode ? [...visibleRegions, ...tiles.filter(t => t.id !== tileId).map(t => ({
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

      <div className="fixed top-20 left-4 z-30 rounded-lg bg-space-900/95 border border-cyan-500/30 p-3 text-xs text-cyan-100 max-w-xs">
        <label className="flex items-center gap-2"><input type="checkbox" checked={fineMode} onChange={e => { setFineMode(e.target.checked); handleDeselect(); }} />Native 0.25° cells</label>
        <p className="mt-2 text-slate-300">{fineMode ? `${fineRegions.length} real cells · ${currentTile?.name || 'Loading area'} · 2003–2024. ${fineRegions.filter(r => (r.pairedYearCount || 0) >= 8).length} cells with sufficient paired years. Source QA review pending.` : '10° legacy overview. Fine coverage is being prepared.'}</p>
        {fineMode && <label className="block mt-2">Area
          <select aria-label="Fine data area" className="block mt-1 w-full rounded bg-space-950 border border-cyan-700 p-2" value={tileId}
            onChange={e => navigateTile(e.target.value)}>
            {tiles.map(t => <option key={t.id} value={t.id}>{t.name}{t.status === 'pending' ? ' · pending' : ''}</option>)}
          </select>
        </label>}
        {fineMode && tileLoading && <p className="mt-2">Loading native cells…</p>}
        {fineMode && family && <p className="mt-2 text-slate-400">The six marked areas have {family.catalog_regions} declared cells and {family.family_size} tests. The grid below shows one area; cells elsewhere are not in this family.</p>}
        {fineMode && <p className="mt-2 text-slate-400">Click land between 60°S and 90°N for its 0.25° soil history. Paired vegetation results are currently available in the six marked areas. Oceans and some land cells have no GLDAS values.</p>}
        {fineMode && fineError && <p>Fine data for this area are unavailable.</p>}
        {fineMode && fineRegions.length > 0 && <>
          <p className="mt-2">{currentTile ? `${currentTile.bbox.join(', ')} · north ↑` : 'Native cells · north ↑'}</p>
          <div className="grid grid-cols-4 gap-1 mt-2" aria-label="Native cell pilot map">
            {[...fineRegions].sort((a,b) => b.lat-a.lat || a.lng-b.lng).map(r => <button key={r.id}
              title={r.name} aria-label={`Select ${r.name}`} onClick={() => handleSelectPreset(r)}
              className={`border p-2 text-[10px] ${selectedLocation?.id === r.id ? 'bg-cyan-700 border-cyan-100' : 'bg-cyan-950 border-cyan-600'}`}>
              {r.lat.toFixed(3)}<br />{r.lng.toFixed(3)}
            </button>)}
          </div>
        </>}
      </div>
      {catalogError && <div className="fixed bottom-4 left-4 z-40 bg-space-900 p-3 text-amber-200 text-xs">Regional API unavailable; synthetic demonstration remains available.</div>}

      {/* Sliding Right-side Telemetry & Information Panel */}
      <SlidingPanel
        location={selectedLocation}
        onClose={handleDeselect}
        onSelectPreset={handleSelectPreset}
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
