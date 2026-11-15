import React from 'react';
import { Globe2, Navigation, Info, HelpCircle, FileText } from 'lucide-react';
import { GeoCoordinate, ModalType } from '../../types/globe';

import { formatCoordinates } from '../../utils/coordinates';

interface HeaderHUDProps {
  onOpenModal: (type: ModalType) => void;
  selectedCoordinate: GeoCoordinate | null;
}

export const HeaderHUD: React.FC<HeaderHUDProps> = ({
  onOpenModal,
  selectedCoordinate,
}) => {
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
                Explore our planet
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
          <span className="text-slate-400">LOCATION:</span>
          {selectedCoordinate ? (
            <span className="text-nasa-cyan font-semibold tracking-wide">
              {formatCoordinates(selectedCoordinate.lat, selectedCoordinate.lng)}
            </span>
          ) : (
            <span className="text-slate-400">SELECT A PLACE</span>
          )}
        </div>

        {/* Right: Controls & Navigation Modals */}
        <div className="flex items-center gap-2.5">
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
