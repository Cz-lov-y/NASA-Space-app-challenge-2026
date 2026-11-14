import React from 'react';
import { Globe2, Navigation, Info, HelpCircle, FileText, ChevronDown } from 'lucide-react';
import { GeoCoordinate, ModalType, SelectedLocation } from '../../types/globe';
import { PRESET_REGIONS } from '../../mock/regions';
import { formatCoordinates } from '../../utils/coordinates';

interface HeaderHUDProps {
  onOpenModal: (type: ModalType) => void;
  selectedCoordinate: GeoCoordinate | null;
  selectedLocation: SelectedLocation | null;
  onSelectPreset: (location: SelectedLocation) => void;
}

export const HeaderHUD: React.FC<HeaderHUDProps> = ({
  onOpenModal,
  selectedCoordinate,
  selectedLocation,
  onSelectPreset,
}) => {
  const [isDropdownOpen, setIsDropdownOpen] = React.useState(false);
  return (
    <>
      {/* Top Telemetry Header Bar */}
      <header className="fixed top-0 left-0 right-0 z-30 px-6 py-3 flex items-center justify-between glass-hud border-b border-cyan-500/20">
        {/* Brand / Mission Identity */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-space-900 border border-nasa-cyan/40 flex items-center justify-center shadow-glow-cyan">
            <Globe2 className="w-4 h-4 text-nasa-cyan animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-bold tracking-widest text-white uppercase">
                EarthRisk
              </span>
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-nasa-red" />
              <span className="text-[10px] font-mono tracking-wider text-nasa-cyan uppercase bg-cyan-950/70 px-1.5 py-0.5 rounded border border-cyan-800/40">
                3D Mission Control
              </span>
            </div>
            <div className="text-[11px] text-slate-400 font-mono tracking-wider">
              GREEN MIRAGE · NASA SPACE APPS 2026
            </div>
          </div>
        </div>

        {/* Center: Live Coordinate Telemetry readout */}
        <div className="hidden md:flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-space-950/80 border border-slate-700/60 font-mono text-xs">
          <Navigation className="w-3.5 h-3.5 text-nasa-cyan" />
          <span className="text-slate-400">TELEMETRY:</span>
          {selectedCoordinate ? (
            <span className="text-nasa-cyan font-semibold tracking-wide">
              {formatCoordinates(selectedCoordinate.lat, selectedCoordinate.lng)}
            </span>
          ) : (
            <span className="text-slate-400">AWAITING TARGET COORDINATE SELECTION</span>
          )}
        </div>

        {/* Right: Controls & Navigation Modals */}
        <div className="flex items-center gap-2.5">
          {/* Preset Hotspot Dropdown */}
          <div className="relative">
            <button
              onClick={() => setIsDropdownOpen(!isDropdownOpen)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-space-850 hover:bg-space-800 border border-cyan-500/30 text-xs font-mono text-cyan-200 transition-colors"
            >
              <span>{selectedLocation ? selectedLocation.name : 'Target Hotspots'}</span>
              <ChevronDown className="w-3.5 h-3.5 text-cyan-400" />
            </button>
            {isDropdownOpen && (
              <div className="absolute right-0 mt-1.5 w-60 py-1 rounded-xl bg-space-900/95 border border-cyan-500/30 shadow-2xl backdrop-blur-xl z-40 animate-in fade-in slide-in-from-top-1">
                <div className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider text-slate-400 border-b border-slate-800">
                  Registered Regions
                </div>
                {PRESET_REGIONS.map((preset) => (
                  <button
                    key={preset.id}
                    onClick={() => {
                      onSelectPreset(preset);
                      setIsDropdownOpen(false);
                    }}
                    className="w-full text-left px-3 py-2 text-xs font-mono hover:bg-nasa-blue/20 hover:text-nasa-cyan flex flex-col gap-0.5 transition-colors border-l-2 border-transparent hover:border-nasa-cyan"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-200">{preset.name}</span>
                      {preset.isSyntheticDemo && (
                        <span className="text-[9px] px-1 rounded bg-amber-500/20 text-amber-300">DEMO</span>
                      )}
                    </div>
                    <span className="text-[10px] text-slate-400">{preset.country}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Navigation Modal Triggers */}
          <button
            onClick={() => onOpenModal('intro')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-space-850 hover:bg-space-800 border border-slate-700 hover:border-cyan-500/50 text-xs font-mono text-slate-300 hover:text-white transition-colors"
          >
            <Info className="w-3.5 h-3.5 text-nasa-cyan" />
            <span className="hidden sm:inline">Introduction</span>
          </button>

          <button
            onClick={() => onOpenModal('instructions')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-space-850 hover:bg-space-800 border border-slate-700 hover:border-cyan-500/50 text-xs font-mono text-slate-300 hover:text-white transition-colors"
          >
            <HelpCircle className="w-3.5 h-3.5 text-nasa-cyan" />
            <span className="hidden sm:inline">Instructions</span>
          </button>

          <button
            onClick={() => onOpenModal('methodology')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-space-850 hover:bg-space-800 border border-slate-700 hover:border-cyan-500/50 text-xs font-mono text-slate-300 hover:text-white transition-colors"
          >
            <FileText className="w-3.5 h-3.5 text-nasa-cyan" />
            <span className="hidden sm:inline">Methodology</span>
          </button>
        </div>
      </header>

      {/* Subtle Interaction Hint at Bottom Center */}
      {!selectedCoordinate && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-20 pointer-events-none">
          <div className="px-5 py-2.5 rounded-full glass-hud border border-cyan-500/30 text-xs font-mono text-slate-300 flex items-center gap-2 shadow-2xl animate-bounce">
            <span className="inline-block w-2 h-2 rounded-full bg-nasa-cyan animate-ping" />
            <span>Drag to rotate • Scroll to zoom • Click anywhere on Earth to inspect coordinates</span>
          </div>
        </div>
      )}
    </>
  );
};
