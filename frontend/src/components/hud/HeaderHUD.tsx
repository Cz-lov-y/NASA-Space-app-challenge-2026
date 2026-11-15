import React from 'react';
import { Globe2, Info, HelpCircle, FileText } from 'lucide-react';
import { GeoCoordinate, ModalType } from '../../types/globe';

import { LocationSearch, SearchPlace } from './LocationSearch';

interface HeaderHUDProps {
  onOpenModal: (type: ModalType) => void;
  selectedCoordinate: GeoCoordinate | null;
  onSearchSelect: (place: SearchPlace) => void;
}

export const HeaderHUD: React.FC<HeaderHUDProps> = ({
  onOpenModal,
  selectedCoordinate,
  onSearchSelect,
}) => {
  return (
    <>
      {/* Top Telemetry Header Bar */}
      <header className="fixed top-0 left-0 right-0 z-50 gap-2 px-3 sm:px-6 py-3 flex items-center justify-between glass-hud border-b border-cyan-500/20">
        {/* Brand / Mission Identity */}
        <div className="flex items-center gap-3">
          <div className="hidden sm:flex w-8 h-8 rounded-full bg-space-900 border border-nasa-cyan/40 flex items-center justify-center shadow-glow-cyan">
            <Globe2 className="w-4 h-4 text-nasa-cyan animate-pulse" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-bold tracking-widest text-white uppercase">
                EarthRisk
              </span>
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-nasa-red" />
              <span className="hidden lg:inline-block text-[10px] font-mono tracking-wider text-nasa-cyan uppercase bg-cyan-950/70 px-1.5 py-0.5 rounded border border-cyan-800/40">
                Explore our planet
              </span>
            </div>
            <div className="hidden sm:block text-[11px] text-slate-400 font-mono tracking-wider">
              GREEN MIRAGE · NASA SPACE APPS 2026
            </div>
          </div>
        </div>

        <LocationSearch onSelect={onSearchSelect} />

        {/* Right: Controls & Navigation Modals */}
        <div className="flex items-center gap-1 sm:gap-2.5">
          {/* Navigation Modal Triggers */}
          <button
            onClick={() => onOpenModal('intro')}
            aria-label="Introduction"
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-space-850 hover:bg-space-800 border border-slate-700 hover:border-cyan-500/50 text-xs font-mono text-slate-300 hover:text-white transition-colors"
          >
            <Info className="w-3.5 h-3.5 text-nasa-cyan" />
            <span className="hidden sm:inline">Introduction</span>
          </button>

          <button
            onClick={() => onOpenModal('instructions')}
            aria-label="Instructions"
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-space-850 hover:bg-space-800 border border-slate-700 hover:border-cyan-500/50 text-xs font-mono text-slate-300 hover:text-white transition-colors"
          >
            <HelpCircle className="w-3.5 h-3.5 text-nasa-cyan" />
            <span className="hidden sm:inline">Instructions</span>
          </button>

          <button
            onClick={() => onOpenModal('methodology')}
            aria-label="Methodology"
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-space-850 hover:bg-space-800 border border-slate-700 hover:border-cyan-500/50 text-xs font-mono text-slate-300 hover:text-white transition-colors"
          >
            <FileText className="w-3.5 h-3.5 text-nasa-cyan" />
            <span className="hidden sm:inline">Methodology</span>
          </button>
        </div>
      </header>

      {/* Subtle Interaction Hint at Bottom Center */}
      {!selectedCoordinate && (
        <div className="hidden sm:block fixed bottom-6 left-1/2 -translate-x-1/2 z-20 pointer-events-none">
          <div className="px-5 py-2.5 rounded-full glass-hud border border-cyan-500/30 text-xs font-mono text-slate-300 flex items-center gap-2 shadow-2xl animate-bounce">
            <span className="inline-block w-2 h-2 rounded-full bg-nasa-cyan animate-ping" />
            <span>Drag to rotate • Scroll to zoom • Click land to explore a location</span>
          </div>
        </div>
      )}
    </>
  );
};
