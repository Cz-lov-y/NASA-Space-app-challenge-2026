import React, { useState, useEffect, useCallback } from 'react';
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
  useEffect(() => { let active = true; apiService.getFineRegions().then(data => {
    if (active) setFineRegions(data.features.map(mapRegion));
  }).catch(() => { if (active) setFineError(true); }); return () => { active = false; }; }, []);
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

    // Check if the clicked coordinate is close to any registered preset hotspot
    const matchedPreset = visibleRegions.find(r => r.id === (fineMode ? fineGridId(coord.lat, coord.lng) : gridId(coord.lat, coord.lng)));

    if (matchedPreset) {
      setSelectedLocation(matchedPreset);
    } else {
      const latStr = coord.lat >= 0 ? `${coord.lat.toFixed(2)}°N` : `${Math.abs(coord.lat).toFixed(2)}°S`;
      const lngStr = coord.lng >= 0 ? `${coord.lng.toFixed(2)}°E` : `${Math.abs(coord.lng).toFixed(2)}°W`;

      setSelectedLocation({
        id: `coord-${coord.lat.toFixed(2)}-${coord.lng.toFixed(2)}`,
        name: `Point (${latStr}, ${lngStr})`,
        lat: coord.lat,
        lng: coord.lng,
        hasObservationalData: false,
        isSyntheticDemo: false,
        country: 'Global Surface Point',
        description: fineMode ? 'Fine-cell data for this location have not been processed yet. Choose a downloaded 0.25° cell from the menu.' : 'No observations available for this location.',
      });
    }
  }, [visibleRegions, fineMode]);

  // Handle direct selection from Hotspots dropdown
  const handleSelectPreset = useCallback((location: SelectedLocation) => {
    setSelectedCoordinate({ lat: location.lat, lng: location.lng });
    setSelectedLocation(location);
  }, []);

  // Deselect and return Earth to centered initial state
  const handleDeselect = useCallback(() => {
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
        regions={visibleRegions}
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
        <p className="mt-2 text-slate-300">{fineMode ? `${fineRegions.length} real cells · Central US pilot · 2003–2024. Vegetation pairing pending. Select a cell from the menu.` : '10° legacy overview. Fine coverage is being prepared.'}</p>
        {fineMode && fineError && <p>Fine data service unavailable.</p>}
        {fineMode && fineRegions.length > 0 && <>
          <p className="mt-2">37–38°N, 98–97°W · north ↑</p>
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
