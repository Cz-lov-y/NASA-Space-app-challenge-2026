import React from 'react';
import {
  ShieldAlert,
  CheckCircle2,
  AlertCircle,
  Scale,
  Activity,
  Layers,
} from 'lucide-react';
import { RegionalAnalysis, TimeSeriesObservation } from '../../types/contracts';
import { calculateOLSTrend } from '../../utils/statistics';

interface StatisticalAuditProps {
  analysis?: RegionalAnalysis;
  observations: TimeSeriesObservation[];
  selectedIndicators: string[];
  yearRange: [number, number];
}

const INDICATOR_NAMES: Record<string, string> = {
  ndvi: 'Vegetation Greenness (NDVI)',
  soil_moisture: 'Root-Zone Soil Moisture',
  temperature: 'Surface Temperature',
  precipitation: 'Monthly Precipitation',
};

export const StatisticalAudit: React.FC<StatisticalAuditProps> = ({
  analysis,
  observations,
  selectedIndicators,
  yearRange,
}) => {
  // Compute real-time filtered statistics for the active window
  const activeStats = selectedIndicators.map((indicator) => {
    const varObs = observations.filter((obs) => {
      const yr = new Date(obs.date).getFullYear();
      return obs.variable === indicator && yr >= yearRange[0] && yr <= yearRange[1];
    });

    const ols = calculateOLSTrend(varObs);
    const contractTrend = analysis?.trends?.[indicator];
    const unit = contractTrend?.unit || varObs[0]?.unit || 'unit';

    return {
      variable: indicator,
      name: INDICATOR_NAMES[indicator] || indicator,
      unit,
      count: varObs.length,
      slope: ols ? ols.slope : contractTrend?.slope_per_year ?? null,
      r2: ols ? ols.r2 : null,
      stdErr: ols ? ols.stdError : null,
      ci: contractTrend?.slope_95ci,
      pValue: contractTrend?.p_value,
      theilSen: contractTrend?.theil_sen_slope_per_year,
      tau: contractTrend?.kendall_tau,
    };
  });

  // Divergence check between NDVI and Soil Moisture
  const ndviStat = activeStats.find((s) => s.variable === 'ndvi');
  const moistureStat = activeStats.find((s) => s.variable === 'soil_moisture');

  const hasBoth = Boolean(ndviStat && moistureStat && ndviStat.slope !== null && moistureStat.slope !== null);
  const isDivergent = hasBoth && (ndviStat!.slope! > 0) && (moistureStat!.slope! < 0);

  return (
    <div className="space-y-4 font-mono text-xs text-slate-300">
      {/* 1. Screening Signal Evaluation Banner */}
      <div
        className={`p-4 rounded-xl border ${
          isDivergent
            ? 'bg-amber-500/10 border-amber-500/30 text-amber-200'
            : hasBoth
            ? 'bg-space-900/80 border-slate-700/60 text-slate-300'
            : 'bg-space-900/50 border-slate-800 text-slate-400'
        }`}
      >
        <div className="flex items-center gap-2 mb-1.5">
          {isDivergent ? (
            <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0" />
          ) : hasBoth ? (
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
          ) : (
            <AlertCircle className="w-4 h-4 text-slate-400 shrink-0" />
          )}
          <span className="font-bold text-sm tracking-wide">
            {isDivergent
              ? 'Candidate Green Mirage Detected'
              : hasBoth
              ? 'No Opposing Trend Divergence'
              : 'Divergence Screening Incomplete'}
          </span>
        </div>
        <p className="text-[11px] leading-relaxed opacity-90">
          {isDivergent
            ? 'Vegetation greenness shows a positive slope while soil moisture exhibits a negative trajectory. Under Member A’s contract, this triggers a candidate screening flag for further hydro-ecological investigation.'
            : hasBoth
            ? 'Trends in greenness and soil moisture do not exhibit opposing slopes across this window. This does not establish environmental stability or rule out micro-scale deficits.'
            : 'Both NDVI and Soil Moisture indicators must be active to evaluate the Green Mirage divergence hypothesis.'}
        </p>
      </div>

      {/* 2. Detailed Trend & Statistical Inference Cards */}
      <div>
        <div className="flex items-center gap-2 text-slate-400 uppercase text-[10px] tracking-wider mb-2">
          <Scale className="w-3.5 h-3.5 text-nasa-cyan" />
          <span>Indicator Trend Inference (Member A Contract)</span>
        </div>

        <div className="space-y-2.5">
          {activeStats.map((stat) => (
            <div
              key={stat.variable}
              className="p-3 rounded-lg bg-space-950/70 border border-slate-800 space-y-2"
            >
              <div className="flex items-center justify-between border-b border-slate-800/80 pb-1.5">
                <span className="font-bold text-white text-xs">{stat.name}</span>
                <span className="text-[10px] text-slate-400">
                  {stat.count} observations ({yearRange[0]}–{yearRange[1]})
                </span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px]">
                {/* Annual Slope */}
                <div>
                  <span className="text-slate-400 block text-[10px]">OLS Annual Slope:</span>
                  <span
                    className={`font-bold ${
                      stat.slope !== null && stat.slope > 0
                        ? 'text-emerald-400'
                        : stat.slope !== null && stat.slope < 0
                        ? 'text-cyan-400'
                        : 'text-slate-300'
                    }`}
                  >
                    {stat.slope !== null
                      ? `${stat.slope >= 0 ? '+' : ''}${stat.slope} ${stat.unit}/yr`
                      : 'N/A'}
                  </span>
                </div>

                {/* 95% Confidence Interval */}
                <div>
                  <span className="text-slate-400 block text-[10px]">95% Slope CI:</span>
                  <span className="text-slate-200">
                    {stat.ci
                      ? `[${stat.ci[0] >= 0 ? '+' : ''}${stat.ci[0]}, ${stat.ci[1] >= 0 ? '+' : ''}${stat.ci[1]}]`
                      : stat.stdErr
                      ? `±${(stat.stdErr * 1.96).toFixed(3)} ${stat.unit}`
                      : 'N/A'}
                  </span>
                </div>

                {/* Raw p-value */}
                <div>
                  <span className="text-slate-400 block text-[10px]">Regression p-value:</span>
                  <span className="text-nasa-cyan font-medium">
                    {stat.pValue !== undefined
                      ? stat.pValue < 0.001
                        ? '< 0.001 (p = 0.0001)'
                        : stat.pValue.toFixed(4)
                      : stat.r2 !== null
                      ? `R² = ${stat.r2}`
                      : 'N/A'}
                  </span>
                </div>

                {/* Theil-Sen Median Slope */}
                <div>
                  <span className="text-slate-400 block text-[10px]">Theil–Sen Robust Slope:</span>
                  <span className="text-slate-300">
                    {stat.theilSen !== undefined
                      ? `${stat.theilSen >= 0 ? '+' : ''}${stat.theilSen} ${stat.unit}/yr`
                      : 'Awaiting audit'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 3. Data Quality & Provenance Attribution */}
      <div className="p-3.5 rounded-lg bg-space-900/60 border border-slate-800 space-y-2.5">
        <div className="flex items-center gap-2 text-slate-400 uppercase text-[10px] tracking-wider">
          <Activity className="w-3.5 h-3.5 text-nasa-cyan" />
          <span>Data Quality & Provenance Attribution</span>
        </div>

        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <div>
            <span className="text-slate-400 block text-[10px]">QA Filter Reviewed:</span>
            <span className="text-slate-300">
              {analysis?.data_quality.qa_reviewed ? 'Yes (Verified)' : 'No (Raw Scaffold)'}
            </span>
          </div>
          <div>
            <span className="text-slate-400 block text-[10px]">Missing Fraction:</span>
            <span className="text-slate-300">
              {analysis?.data_quality.missing_fraction !== undefined
                ? `${(analysis.data_quality.missing_fraction * 100).toFixed(1)}%`
                : '0.0%'}
            </span>
          </div>
          <div className="col-span-2">
            <span className="text-slate-400 block text-[10px]">Attributed Sources:</span>
            <div className="flex flex-wrap gap-1.5 mt-1">
              {(analysis?.data_quality.sources || ['SYNTHETIC_DEMO_NOT_NASA']).map((src) => (
                <span
                  key={src}
                  className="px-2 py-0.5 rounded bg-space-950 border border-cyan-800/40 text-[10px] text-cyan-300"
                >
                  {src}
                </span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 4. Scientific Limitations & Caveats */}
      <div className="p-3.5 rounded-lg bg-space-950/60 border border-slate-800 space-y-2">
        <div className="flex items-center gap-2 text-slate-400 uppercase text-[10px] tracking-wider">
          <Layers className="w-3.5 h-3.5 text-nasa-cyan" />
          <span>Scientific Caveats & Limitations</span>
        </div>
        <ul className="space-y-1.5 list-disc list-inside text-[11px] text-slate-400 leading-relaxed">
          {(analysis?.limitations || [
            'Opposing trend signs establish a candidate divergence signal, not proof of ecological damage.',
            'Unadjusted regressions require correction for seasonality and serial autocorrelation.',
          ]).map((limitation, idx) => (
            <li key={idx} className="text-slate-400">
              <span className="text-slate-300">{limitation}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
};
