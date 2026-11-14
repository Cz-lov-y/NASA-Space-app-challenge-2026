import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Compass,
  Database,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  TrendingUp,
  RotateCcw,
  Sparkles,
} from 'lucide-react';
import { SelectedLocation } from '../../types/globe';
import { formatCoordinates } from '../../utils/coordinates';
import { apiService } from '../../services/api';

interface SlidingPanelProps {
  location: SelectedLocation | null;
  onClose: () => void;
  onSelectPreset: (location: SelectedLocation) => void;
}

export const SlidingPanel: React.FC<SlidingPanelProps> = ({
  location,
  onClose,
  onSelectPreset,
}) => {
  const [dataStatus, setDataStatus] = useState<{
    hasData: boolean;
    isSynthetic: boolean;
    statusMessage: string;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!location) {
      setDataStatus(null);
      return;
    }

    let isMounted = true;
    setIsLoading(true);

    apiService.getLocationData(location).then((res) => {
      if (isMounted) {
        setDataStatus({
          hasData: res.hasData,
          isSynthetic: res.isSynthetic,
          statusMessage: res.statusMessage,
        });
        setIsLoading(false);
      }
    });

    return () => {
      isMounted = false;
    };
  }, [location]);

  return (
    <AnimatePresence>
      {location && (
        <motion.aside
          initial={{ x: '100%', opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: '100%', opacity: 0 }}
          transition={{ type: 'spring', damping: 26, stiffness: 220 }}
          className="fixed top-0 right-0 z-40 h-full w-full max-w-md lg:max-w-lg glass-panel flex flex-col shadow-2xl overflow-hidden border-l border-cyan-500/30"
        >
          {/* Top Panel Bar */}
          <div className="flex items-center justify-between p-5 border-b border-cyan-500/20 bg-space-950/60">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-nasa-cyan animate-pulse" />
              <span className="text-xs font-mono font-bold tracking-widest text-nasa-cyan uppercase">
                TARGET TELEMETRY LOG
              </span>
            </div>
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-space-800 transition-colors"
              title="Close panel (Esc)"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Scrollable Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6 text-sm text-slate-300">
            {/* Location Title & Geo Coordinates */}
            <div>
              <div className="text-[11px] font-mono tracking-wider text-slate-400 uppercase">
                {location.country || 'GLOBAL SURFACE POINT'}
              </div>
              <h2 className="text-xl font-bold font-mono text-white tracking-wide mt-0.5">
                {location.name}
              </h2>
              {location.description && (
                <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                  {location.description}
                </p>
              )}
            </div>

            {/* Geographic Coordinates Card */}
            <div className="p-4 rounded-xl bg-space-900/80 border border-cyan-500/25 space-y-3">
              <div className="flex items-center gap-2 text-xs font-mono text-slate-400 uppercase">
                <Compass className="w-4 h-4 text-nasa-cyan" />
                <span>Geographic Precision Coordinates</span>
              </div>
              <div className="flex items-baseline justify-between font-mono">
                <span className="text-lg font-bold text-nasa-cyan">
                  {formatCoordinates(location.lat, location.lng)}
                </span>
                <span className="text-[10px] text-slate-400">WGS 84</span>
              </div>
              <div className="grid grid-cols-2 gap-2 pt-2 border-t border-slate-800 text-xs font-mono">
                <div>
                  <span className="text-slate-400">LATITUDE:</span>{' '}
                  <span className="text-slate-200">{location.lat.toFixed(4)}°</span>
                </div>
                <div>
                  <span className="text-slate-400">LONGITUDE:</span>{' '}
                  <span className="text-slate-200">{location.lng.toFixed(4)}°</span>
                </div>
              </div>
            </div>

            {/* Scientific Data Availability Status */}
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs font-mono text-slate-400 uppercase">
                <Database className="w-4 h-4 text-nasa-cyan" />
                <span>Observational Data Readiness</span>
              </div>

              {isLoading ? (
                <div className="p-4 rounded-xl bg-space-900/50 border border-slate-800 animate-pulse text-xs font-mono text-cyan-300">
                  Querying regional telemetry index...
                </div>
              ) : dataStatus?.hasData && dataStatus.isSynthetic ? (
                /* Synthetic Demo Active */
                <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200 space-y-3">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                    <span className="font-mono font-bold text-xs uppercase tracking-wider text-amber-300">
                      Synthetic Demonstration Record
                    </span>
                  </div>
                  <p className="text-xs text-amber-200/90 leading-relaxed">
                    This region carries 10-year illustrative data (2015–2024) for interface testing. <strong>These are synthetic values, not NASA satellite observations.</strong>
                  </p>
                  <div className="pt-2 border-t border-amber-500/20 flex items-center justify-between text-xs font-mono">
                    <span className="text-amber-300">Signal Status:</span>
                    <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 font-semibold">
                      Candidate Green Mirage
                    </span>
                  </div>
                </div>
              ) : dataStatus?.hasData ? (
                /* Real Data Available */
                <div className="p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-200 space-y-2">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                    <span className="font-mono font-bold text-xs uppercase">
                      Observational Series Loaded
                    </span>
                  </div>
                  <p className="text-xs">{dataStatus.statusMessage}</p>
                </div>
              ) : (
                /* Arbitrary clicked point with No Data */
                <div className="p-4 rounded-xl bg-space-900/70 border border-slate-700/60 space-y-3">
                  <div className="flex items-start gap-2.5">
                    <HelpCircle className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                    <div className="space-y-1">
                      <p className="text-xs font-mono font-semibold text-slate-200">
                        No Observations for Arbitrary Point
                      </p>
                      <p className="text-xs text-slate-400 leading-relaxed">
                        {dataStatus?.statusMessage}
                      </p>
                    </div>
                  </div>
                  <div className="pt-2 border-t border-slate-800">
                    <button
                      onClick={() =>
                        onSelectPreset({
                          id: 'demo-region',
                          name: 'Synthetic Demo Region',
                          lat: 36.7783,
                          lng: -119.4179,
                          hasObservationalData: true,
                          isSyntheticDemo: true,
                          regionId: 'demo-region',
                          country: 'Global / Fictitious',
                          description: 'Scaffold demonstration dataset for testing the opposing NDVI/soil-moisture trend interface.',
                        })
                      }
                      className="w-full py-2 px-3 rounded-lg bg-nasa-blue/30 hover:bg-nasa-blue/50 border border-cyan-500/40 text-xs font-mono text-cyan-200 flex items-center justify-center gap-2 transition-colors"
                    >
                      <Sparkles className="w-3.5 h-3.5 text-nasa-cyan" />
                      <span>Jump to Demo Region (Test Data)</span>
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Milestone 2 Preview Placeholder */}
            <div className="p-4 rounded-xl bg-space-900/50 border border-slate-800 space-y-2">
              <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
                <TrendingUp className="w-4 h-4 text-nasa-cyan" />
                <span>Next Milestone: Interactive Visualizations</span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Full dual-axis Apache ECharts (NDVI greenness trajectory vs. soil moisture water table decline) and Member A's Theil–Sen / Mann–Kendall audit cards will activate in Milestone 2.
              </p>
            </div>
          </div>

          {/* Bottom Actions Bar */}
          <div className="p-4 border-t border-cyan-500/20 bg-space-950/80 flex items-center justify-between">
            <button
              onClick={onClose}
              className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-space-850 hover:bg-space-800 border border-slate-700 text-xs font-mono text-slate-300 hover:text-white transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Center Globe</span>
            </button>
            <div className="text-[10px] font-mono text-slate-400">
              PRESS ESC TO CLOSE
            </div>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
};
