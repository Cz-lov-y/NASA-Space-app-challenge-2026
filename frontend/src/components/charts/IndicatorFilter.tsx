import React from 'react';
import { SlidersHorizontal, Eye, EyeOff } from 'lucide-react';

interface IndicatorFilterProps {
  availableIndicators: string[];
  selectedIndicators: string[];
  onToggleIndicator: (variable: string) => void;
  yearRange: [number, number];
  minYear: number;
  maxYear: number;
  onChangeYearRange: (range: [number, number]) => void;
  showTrendline: boolean;
  allowTrendline?: boolean;
  onToggleTrendline: () => void;
  chartMode: 'timeseries' | 'zscore';
  onChangeChartMode: (mode: 'timeseries' | 'zscore') => void;
}

const INDICATOR_LABELS: Record<string, { label: string; color: string; badge: string }> = {
  ndvi: { label: 'NDVI (Greenness)', color: 'text-emerald-700 border-emerald-500/40 bg-emerald-500/10', badge: 'bg-emerald-500' },
  soil_water_0_100cm: { label: 'Soil Water (0–100 cm)', color: 'text-cyan-400 border-cyan-500/40 bg-cyan-500/10', badge: 'bg-cyan-500' },
  soil_water_0_10cm: { label: 'Soil Water (0–10 cm)', color: 'text-purple-700 border-purple-500/40 bg-purple-500/10', badge: 'bg-purple-500' },
  soil_moisture: { label: 'Soil Moisture', color: 'text-cyan-400 border-cyan-500/40 bg-cyan-500/10', badge: 'bg-cyan-500' },
  temperature: { label: 'Surface Temp', color: 'text-amber-800 border-amber-500/40 bg-amber-500/10', badge: 'bg-amber-500' },
  precipitation: { label: 'Precipitation', color: 'text-blue-700 border-blue-500/40 bg-blue-500/10', badge: 'bg-blue-500' },
};

export const IndicatorFilter: React.FC<IndicatorFilterProps> = ({
  availableIndicators,
  selectedIndicators,
  onToggleIndicator,
  yearRange,
  minYear,
  maxYear,
  onChangeYearRange,
  showTrendline,
  allowTrendline = true,
  onToggleTrendline,
  chartMode,
  onChangeChartMode,
}) => {
  return (
    <div className="p-4 rounded-xl bg-space-900/80 border border-cyan-500/20 space-y-3.5">
      {/* Top Filter Controls: Chart Mode Switcher & Trendline Toggle */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-2.5">
        <div className="flex items-center gap-1.5 p-0.5 rounded-lg bg-space-950 border border-slate-800 text-[11px] font-mono">
          <button
            onClick={() => onChangeChartMode('timeseries')}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              chartMode === 'timeseries'
                ? 'bg-nasa-blue text-white font-semibold'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Over time
          </button>
          <button
            onClick={() => onChangeChartMode('zscore')}
            className={`px-2.5 py-1 rounded-md transition-colors ${
              chartMode === 'zscore'
                ? 'bg-nasa-blue text-white font-semibold'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Compare changes
          </button>
        </div>

        {chartMode === 'timeseries' && (
          <button
            onClick={onToggleTrendline}
            disabled={!allowTrendline}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-[11px] font-mono transition-colors ${
              showTrendline
                ? 'border-cyan-500/40 bg-cyan-500/10 text-cyan-300'
                : 'border-slate-800 bg-space-950 text-slate-400 hover:text-slate-200'
            }`}
            title="Trend information is available in Details"
          >
            {showTrendline ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            <span>{!allowTrendline ? 'Trend details in Details' : showTrendline ? 'Trendlines On' : 'Trendlines Off'}</span>
          </button>
        )}
      </div>

      {/* Indicator Selection Toggles */}
      <div>
        <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 uppercase mb-2">
          <span>Choose what to show</span>
          <span className="text-[10px] text-slate-400">SELECT AVAILABLE</span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          {availableIndicators.map((variable) => {
            const isSelected = selectedIndicators.includes(variable);
            const meta = INDICATOR_LABELS[variable] || {
              label: variable,
              color: 'text-slate-300 border-slate-700 bg-slate-800',
              badge: 'bg-slate-400',
            };

            return (
              <button
                key={variable}
                onClick={() => onToggleIndicator(variable)}
                className={`flex items-center gap-2 p-2 rounded-lg border text-xs font-mono transition-all text-left ${
                  isSelected
                    ? `${meta.color} font-semibold shadow-sm`
                    : 'border-slate-800 bg-space-950/60 text-slate-400 hover:border-slate-700 hover:text-slate-200'
                }`}
              >
                <span
                  className={`w-2 h-2 rounded-full shrink-0 ${
                    isSelected ? meta.badge : 'bg-slate-600'
                  }`}
                />
                <span className="truncate">{meta.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Observation Window / Time-Range Filter */}
      <div>
        <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 mb-1.5">
          <div className="flex items-center gap-1.5">
            <SlidersHorizontal className="w-3 h-3 text-nasa-cyan" />
            <span className="uppercase">Time period</span>
          </div>
          <span className="text-nasa-cyan font-bold">
            {yearRange[0]} — {yearRange[1]} ({yearRange[1] - yearRange[0] + 1} yrs)
          </span>
        </div>

        {/* Range Slider Controls */}
        <div className="flex items-center gap-3 pt-1">
          <span className="text-[10px] font-mono text-slate-400">{minYear}</span>
          <input
            type="range"
            min={minYear}
            max={yearRange[1] - 1}
            value={yearRange[0]}
            onChange={(e) =>
              onChangeYearRange([Number(e.target.value), yearRange[1]])
            }
            className="w-full h-1.5 bg-space-950 rounded-lg appearance-none cursor-pointer accent-nasa-cyan"
          />
          <input
            type="range"
            min={yearRange[0] + 1}
            max={maxYear}
            value={yearRange[1]}
            onChange={(e) =>
              onChangeYearRange([yearRange[0], Number(e.target.value)])
            }
            className="w-full h-1.5 bg-space-950 rounded-lg appearance-none cursor-pointer accent-nasa-cyan"
          />
          <span className="text-[10px] font-mono text-slate-400">{maxYear}</span>
        </div>
      </div>
    </div>
  );
};
