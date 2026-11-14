import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Compass,
  AlertTriangle,
  CheckCircle2,
  HelpCircle,
  RotateCcw,
  Sparkles,
  BarChart3,
  FileSpreadsheet,
} from 'lucide-react';
import { SelectedLocation } from '../../types/globe';
import { TimeSeriesObservation, RegionalAnalysis } from '../../types/contracts';
import { formatCoordinates } from '../../utils/coordinates';
import { apiService } from '../../services/api';
import { TimeseriesChart } from '../charts/TimeseriesChart';
import { ZScoreChart } from '../charts/ZScoreChart';
import { IndicatorFilter } from '../charts/IndicatorFilter';
import { StatisticalAudit } from '../charts/StatisticalAudit';

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
    observations?: TimeSeriesObservation[];
    analysis?: RegionalAnalysis;
    statusMessage: string;
  } | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'visualize' | 'audit'>('visualize');

  // Visualization interactive states
  const [selectedIndicators, setSelectedIndicators] = useState<string[]>([
    'ndvi',
    'soil_moisture',
  ]);
  const [chartMode, setChartMode] = useState<'timeseries' | 'zscore'>('timeseries');
  const [showTrendline, setShowTrendline] = useState(true);
  const [yearRange, setYearRange] = useState<[number, number]>([2015, 2024]);

  useEffect(() => {
    if (!location) {
      setDataStatus(null);
      return;
    }

    let isMounted = true;
    setIsLoading(true);

    apiService.getLocationData(location).then((res) => {
      if (isMounted) {
        setDataStatus(res);
        setIsLoading(false);
        if (res.observations && res.observations.length > 0) {
          const years = res.observations.map((o) => new Date(o.date).getFullYear());
          const minY = Math.min(...years);
          const maxY = Math.max(...years);
          setYearRange([minY, maxY]);
        }
      }
    });

    return () => {
      isMounted = false;
    };
  }, [location]);

  const handleToggleIndicator = (variable: string) => {
    setSelectedIndicators((prev) => {
      if (prev.includes(variable)) {
        if (prev.length === 1) return prev;
        return prev.filter((v) => v !== variable);
      }
      return [...prev, variable];
    });
  };

  const availableIndicators = ['ndvi', 'soil_moisture', 'temperature', 'precipitation'];

  return (
    <AnimatePresence>
      {location && (
        <motion.aside
          initial={{ x: '100%', opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          exit={{ x: '100%', opacity: 0 }}
          transition={{ type: 'spring', damping: 26, stiffness: 220 }}
          className="fixed top-0 right-0 z-40 h-full w-full max-w-md md:max-w-xl lg:max-w-2xl glass-panel flex flex-col shadow-2xl overflow-hidden border-l border-cyan-500/30 font-sans"
        >
          {/* Top Panel Bar */}
          <div className="flex items-center justify-between p-3.5 px-5 border-b border-cyan-500/20 bg-space-950/80">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-nasa-cyan animate-pulse" />
              <span className="text-xs font-mono font-bold tracking-widest text-nasa-cyan uppercase">
                TARGET TELEMETRY LOG
              </span>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-space-800 transition-colors"
              title="Close panel (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Scrollable Content */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4 text-sm text-slate-300">
            {/* Unified Region Header & Coordinates Card */}
            <div className="p-3.5 rounded-xl bg-space-900/80 border border-cyan-500/25 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono tracking-wider text-slate-400 uppercase">
                  {location.country || 'GLOBAL SURFACE POINT'}
                </span>
                <span className="text-xs font-mono font-bold text-nasa-cyan flex items-center gap-1.5">
                  <Compass className="w-3.5 h-3.5" />
                  {formatCoordinates(location.lat, location.lng)}
                </span>
              </div>
              <h2 className="text-lg font-bold font-mono text-white tracking-wide">
                {location.name}
              </h2>
              {location.description && (
                <p className="text-xs text-slate-400 leading-relaxed font-mono">
                  {location.description}
                </p>
              )}
            </div>

            {/* Scientific Data Availability / Provenance Warning */}
            {isLoading ? (
              <div className="p-3 rounded-lg bg-space-900/50 border border-slate-800 animate-pulse text-xs font-mono text-cyan-300">
                Querying regional telemetry index...
              </div>
            ) : dataStatus?.hasData && dataStatus.isSynthetic ? (
              <div className="px-3.5 py-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-200 flex items-center justify-between text-xs font-mono">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
                  <div>
                    <span className="font-bold text-amber-300 uppercase">Synthetic Demonstration Record</span>
                    <span className="block text-[10px] text-amber-200/80">
                      10-year illustrative test series (2015–2024) · Not NASA observations
                    </span>
                  </div>
                </div>
                <span className="px-2 py-0.5 rounded bg-amber-500/20 text-[10px] font-semibold text-amber-300 shrink-0">
                  Candidate Green Mirage
                </span>
              </div>
            ) : dataStatus?.hasData ? (
              <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-200 flex items-center gap-2 text-xs font-mono">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>{dataStatus.statusMessage}</span>
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-space-900/70 border border-slate-700/60 space-y-3">
                <div className="flex items-start gap-2.5">
                  <HelpCircle className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="text-xs font-mono font-semibold text-slate-200">
                      No Observational Records for Selected Point
                    </p>
                    <p className="text-xs text-slate-400 leading-relaxed font-mono">
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
                    <span>Load Demo Region with Test Observations</span>
                  </button>
                </div>
              </div>
            )}

            {/* MILESTONE 2: Environmental Data Visualization & Statistical Dashboard */}
            {dataStatus?.hasData && dataStatus.observations && (
              <div className="space-y-3 pt-1">
                {/* Tab Navigation: Visualization vs Statistical Audit */}
                <div className="flex items-center gap-2 p-1 rounded-xl bg-space-950 border border-slate-800 font-mono text-xs">
                  <button
                    onClick={() => setActiveTab('visualize')}
                    className={`flex-1 flex items-center justify-center gap-2 py-1.5 rounded-lg transition-colors ${
                      activeTab === 'visualize'
                        ? 'bg-nasa-blue text-white font-bold shadow-md'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    <BarChart3 className="w-4 h-4 text-nasa-cyan" />
                    <span>Environmental Trends</span>
                  </button>
                  <button
                    onClick={() => setActiveTab('audit')}
                    className={`flex-1 flex items-center justify-center gap-2 py-1.5 rounded-lg transition-colors ${
                      activeTab === 'audit'
                        ? 'bg-nasa-blue text-white font-bold shadow-md'
                        : 'text-slate-400 hover:text-white'
                    }`}
                  >
                    <FileSpreadsheet className="w-4 h-4 text-nasa-cyan" />
                    <span>Scientific Audit</span>
                  </button>
                </div>

                {/* Tab 1: Interactive Charts & Filters */}
                {activeTab === 'visualize' && (
                  <div className="space-y-3">
                    <IndicatorFilter
                      availableIndicators={availableIndicators}
                      selectedIndicators={selectedIndicators}
                      onToggleIndicator={handleToggleIndicator}
                      yearRange={yearRange}
                      minYear={2015}
                      maxYear={2024}
                      onChangeYearRange={setYearRange}
                      showTrendline={showTrendline}
                      onToggleTrendline={() => setShowTrendline(!showTrendline)}
                      chartMode={chartMode}
                      onChangeChartMode={setChartMode}
                    />

                    <div className="p-3.5 rounded-xl bg-space-950/80 border border-cyan-500/20 space-y-2">
                      <div className="flex items-center justify-between text-xs font-mono text-slate-400 border-b border-slate-800/80 pb-1.5">
                        <span className="font-bold text-white uppercase">
                          {chartMode === 'timeseries'
                            ? 'Interactive Multi-Indicator Trends'
                            : 'Standardized Z-Score Comparison'}
                        </span>
                        <span className="text-[10px] text-cyan-300">
                          {chartMode === 'timeseries' ? 'DUAL-AXIS SCALING' : 'DIMENSIONLESS (σ)'}
                        </span>
                      </div>

                      {chartMode === 'timeseries' ? (
                        <TimeseriesChart
                          observations={dataStatus.observations}
                          selectedIndicators={selectedIndicators}
                          yearRange={yearRange}
                          showTrendline={showTrendline}
                        />
                      ) : (
                        <ZScoreChart
                          observations={dataStatus.observations}
                          yearRange={yearRange}
                        />
                      )}
                    </div>
                  </div>
                )}

                {/* Tab 2: Statistical Audit & Safeguards */}
                {activeTab === 'audit' && (
                  <StatisticalAudit
                    analysis={dataStatus.analysis}
                    observations={dataStatus.observations}
                    selectedIndicators={selectedIndicators}
                    yearRange={yearRange}
                  />
                )}
              </div>
            )}
          </div>

          {/* Bottom Actions Bar */}
          <div className="p-3.5 px-6 border-t border-cyan-500/20 bg-space-950/90 flex items-center justify-between">
            <button
              onClick={onClose}
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-space-850 hover:bg-space-800 border border-slate-700 text-xs font-mono text-slate-300 hover:text-white transition-colors"
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
