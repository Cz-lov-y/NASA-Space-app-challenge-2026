import React, { useState, useEffect, useCallback } from 'react';
import { EarthCanvas } from './components/globe/EarthCanvas';
import { HeaderHUD } from './components/hud/HeaderHUD';
import { SlidingPanel } from './components/panel/SlidingPanel';
import { InfoModal } from './components/modals/InfoModal';
import { GeoCoordinate, ModalType, SelectedLocation } from './types/globe';
import { PRESET_REGIONS } from './mock/regions';

export const App: React.FC = () => {
  const [selectedCoordinate, setSelectedCoordinate] = useState<GeoCoordinate | null>(null);
  const [selectedLocation, setSelectedLocation] = useState<SelectedLocation | null>(null);
  const [activeModal, setActiveModal] = useState<ModalType>(null);

  // Handle geographic point click on the 3D globe
  const handleSelectCoordinate = useCallback((coord: GeoCoordinate) => {
    setSelectedCoordinate(coord);

    // Check if the clicked coordinate is close to any registered preset hotspot
    const matchedPreset = PRESET_REGIONS.find((preset) => {
      const dLat = Math.abs(preset.lat - coord.lat);
      const dLng = Math.abs(preset.lng - coord.lng);
      return dLat < 2.5 && dLng < 2.5;
    });

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
        description: 'Interactive point sampled via precision 3D raycasting on the Earth digital twin.',
      });
    }
  }, []);

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
      />

      {/* Top Telemetry Header HUD */}
      <HeaderHUD
        onOpenModal={setActiveModal}
        selectedCoordinate={selectedCoordinate}
        selectedLocation={selectedLocation}
        onSelectPreset={handleSelectPreset}
      />

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
