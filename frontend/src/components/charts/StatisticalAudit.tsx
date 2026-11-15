import React from 'react';
import { ShieldAlert, CheckCircle2, AlertCircle, Scale, Activity, Layers } from 'lucide-react';
import { RegionalAnalysis, RegionalDetail, TimeSeriesObservation } from '../../types/contracts';

interface StatisticalAuditProps {
  analysis?: RegionalAnalysis;
  detail?: RegionalDetail;
  observations: TimeSeriesObservation[];
  selectedIndicators: string[];
  yearRange: [number, number];
}

const INDICATOR_NAMES: Record<string, string> = {
  ndvi: 'Vegetation Greenness (NDVI)',
  soil_water_0_100cm: 'Soil Water Storage (0–100 cm)',
  soil_water_0_10cm: 'Soil Water Storage (0–10 cm)',
  soil_moisture: 'Soil Moisture (Synthetic Demo)',
  temperature: 'Surface Temperature',
  precipitation: 'Monthly Precipitation',
};
const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);
const numeric = (value: unknown, signed = false) => finite(value)
  ? `${signed && value > 0 ? '+' : ''}${value === 0 ? '0' : Math.abs(value) < .001 ? value.toExponential(3) : Number(value.toPrecision(5))}`
  : 'N/A';
const percent = (value: unknown) => finite(value) ? `${(value * 100).toFixed(1)}%` : 'Unavailable';

export const StatisticalAudit: React.FC<StatisticalAuditProps> = ({
  analysis, detail, observations, selectedIndicators, yearRange,
}) => {
  // Stored backend annual inference is authoritative. Chart filters never refit it.
  const activeStats = selectedIndicators.map((indicator) => {
    const varObs = observations.filter((obs) => {
      const yr = new Date(obs.date).getUTCFullYear();
      return obs.variable === indicator && yr >= yearRange[0] && yr <= yearRange[1];
    });
    const trend = analysis?.trends?.[indicator];
    const full = analysis?.analysis?.[indicator];
    const ols = full?.linear_regression;
    return {
      variable: indicator, name: INDICATOR_NAMES[indicator] || indicator,
      unit: trend?.unit || varObs[0]?.unit || 'unit',
      rawCount: varObs.length, finiteCount: varObs.filter((o) => finite(o.value)).length,
      annualCount: full?.data_quality?.n_years ?? trend?.n_observations,
      slope: ols?.slope ?? trend?.slope_per_year,
      ci: ols?.confidence_interval ?? trend?.slope_95ci,
      confidence: ols?.confidence_level ?? .95,
      pValue: ols?.p_value ?? trend?.p_value,
      theilSen: full?.theil_sen?.slope ?? trend?.theil_sen_slope_per_year,
      missingFraction: full?.data_quality?.missing_fraction,
      rawMissingFraction: full?.data_quality?.raw_missing_fraction,
      reliable: full?.reliable,
    };
  });
  const category = detail ? detail.screening?.category : analysis?.divergence?.category ?? analysis?.divergence_category;
  const classification = detail?.screening?.classification ?? (category ? analysis?.divergence_status : 'unavailable');
  const isSupported = category === 'Supported Signal';
  const isAbsent = category === 'No Detected Divergence';
  const headline = category || ({ pending: 'Paired Screening Pending', unsupported: 'Outside Product Coverage',
    insufficient: 'Insufficient Common Annual Data', unavailable: 'Screening Unavailable' }[classification || 'unavailable'] || 'Screening Unavailable');
  const period = analysis?.observation_period;
  const periodLabel = !period ? 'Unavailable' : Array.isArray(period) ? `${period[0]} to ${period[1]}` : `${period.start ?? 'N/A'} to ${period.end ?? 'N/A'}`;
  const sources = analysis?.data_quality.sources ?? [...new Set(observations.map((o) => o.source))];

  return (
    <div className="space-y-4 font-mono text-xs text-slate-300">
      <div className={`p-4 rounded-xl border ${isSupported ? 'bg-red-500/10 border-red-500/30 text-red-700' : isAbsent ? 'bg-green-500/10 border-green-500/30 text-green-800' : category ? 'bg-yellow-500/10 border-yellow-500/30 text-yellow-800' : 'bg-space-900/50 border-slate-800 text-slate-400'}`}>
        <div className="flex items-center gap-2 mb-1.5">
          {isSupported ? <ShieldAlert className="w-4 h-4 text-red-600 shrink-0" /> : isAbsent ? <CheckCircle2 className="w-4 h-4 text-green-600 shrink-0" /> : <AlertCircle className="w-4 h-4 text-yellow-600 shrink-0" />}
          <span className="font-bold text-sm tracking-wide">{headline}</span>
        </div>
        <p className="text-[11px] leading-relaxed opacity-90">
          {detail?.screening?.classification === 'pending'
            ? 'Regional NDVI or another primary series is pending. Available soil statistics are standalone diagnostics; paired divergence has not been classified.'
            : detail?.available_indicator_analysis && detail.screening?.classification === 'insufficient'
            ? 'There are too few common complete years for paired screening. The soil statistics below use their separate available record and do not establish paired divergence.'
            : 'Classification comes from stored backend annual analysis and its quality, robustness and significance checks. Opposing signs alone do not establish a Supported Signal or ecological damage.'}
        </p>
        {detail?.screening?.reasons?.length ? <p className="text-[10px] mt-2">{detail.screening.reasons.join(' · ')}</p> : null}
      </div>

      <div>
        <div className="flex items-center gap-2 text-slate-400 uppercase text-[10px] tracking-wider mb-2">
          <Scale className="w-3.5 h-3.5 text-nasa-cyan" /><span>Stored Annual Trend Inference</span>
        </div>
        <p className="text-[10px] text-slate-400 mb-2">Analyzed period: {periodLabel}. Chart window: {yearRange[0]}–{yearRange[1]}. {detail?.screening_status === 'current_browser_computation' ? 'Statistics update in your browser when the chart window changes.' : 'Changing the chart window does not recompute these statistics.'}</p>
        <div className="space-y-2.5">
          {activeStats.map((stat) => (
            <div key={stat.variable} className="p-3 rounded-lg bg-space-950/70 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between border-b border-slate-800/80 pb-1.5 gap-2">
                <span className="font-bold text-white text-xs">{stat.name}</span>
                <span className="text-[10px] text-slate-400">{finite(stat.annualCount) ? stat.annualCount : 'N/A'} annual values · chart: {stat.rawCount} rows ({stat.finiteCount} finite)</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <span className="text-slate-400 block text-[10px]">OLS Annual Slope:</span>
                  <span className={`font-bold ${finite(stat.slope) && stat.slope > 0 ? 'text-emerald-400' : finite(stat.slope) && stat.slope < 0 ? 'text-cyan-400' : 'text-slate-300'}`}>{numeric(stat.slope, true)} {stat.unit}/yr</span>
                </div>
                <div>
                  <span className="text-slate-400 block text-[10px]">{(stat.confidence * 100).toFixed(0)}% Slope CI:</span>
                  <span className="text-slate-200">{Array.isArray(stat.ci) && stat.ci.length === 2 && stat.ci.every(finite) ? `[${numeric(stat.ci[0], true)}, ${numeric(stat.ci[1], true)}] ${stat.unit}/yr` : 'N/A'}</span>
                </div>
                <div><span className="text-slate-400 block text-[10px]">Raw OLS p-value:</span><span className="text-nasa-cyan font-medium">{numeric(stat.pValue)}</span></div>
                <div><span className="text-slate-400 block text-[10px]">Theil–Sen Robust Slope:</span><span className="text-slate-300">{numeric(stat.theilSen, true)} {stat.unit}/yr</span></div>
                <div><span className="text-slate-400 block text-[10px]">Analyzed Missing Fraction:</span><span className="text-slate-300">{percent(stat.missingFraction)}</span></div>
                <div><span className="text-slate-400 block text-[10px]">Raw Missing Fraction:</span><span className="text-slate-300">{percent(stat.rawMissingFraction)}</span></div>
                <div className="col-span-2"><span className="text-slate-400 block text-[10px]">Statistical Reliability Checks:</span><span className="text-slate-300">{stat.reliable === true ? 'Passed statistical checks; source QA remains separate' : stat.reliable === false ? 'Not all checks passed; inspect limitations' : 'Unavailable for this indicator'}</span></div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="p-3.5 rounded-lg bg-space-900/60 border border-slate-800 space-y-2.5">
        <div className="flex items-center gap-2 text-slate-400 uppercase text-[10px] tracking-wider"><Activity className="w-3.5 h-3.5 text-nasa-cyan" /><span>Data Quality & Provenance Attribution</span></div>
        <div className="grid grid-cols-2 gap-2 text-[11px]">
          <div><span className="text-slate-400 block text-[10px]">Source QA Reviewed:</span><span className="text-slate-300">{analysis?.data_quality.qa_reviewed === true ? 'Marked reviewed by source pipeline' : 'Review pending'}</span></div>
          <div><span className="text-slate-400 block text-[10px]">Synthetic Data:</span><span className="text-slate-300">{analysis?.data_quality.synthetic_demo ? 'Yes — demonstration only' : 'No synthetic input declared'}</span></div>
          <div className="col-span-2">
            <span className="text-slate-400 block text-[10px]">Attributed Sources:</span>
            <div className="flex flex-wrap gap-1.5 mt-1">{sources.length ? sources.map((src) => <span key={src} className="px-2 py-0.5 rounded bg-space-950 border border-cyan-800/40 text-[10px] text-cyan-300">{src}</span>) : <span>Unavailable</span>}</div>
          </div>
        </div>
      </div>
      <div className="p-3.5 rounded-lg bg-space-950/60 border border-slate-800 space-y-2">
        <div className="flex items-center gap-2 text-slate-400 uppercase text-[10px] tracking-wider"><Layers className="w-3.5 h-3.5 text-nasa-cyan" /><span>Scientific Caveats & Limitations</span></div>
        <ul className="space-y-1.5 list-disc list-inside text-[11px] text-slate-400 leading-relaxed">
          {(analysis?.limitations || ['Paired analysis is unavailable. Source coverage and quality review remain necessary.']).map((limitation, idx) => <li key={idx} className="text-slate-400"><span className="text-slate-300">{limitation}</span></li>)}
        </ul>
      </div>
    </div>
  );
};
