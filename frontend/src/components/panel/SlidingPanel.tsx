import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Compass,
  CheckCircle2,
  HelpCircle,
  RotateCcw,
  BarChart3,
  FileSpreadsheet,
  Copy, Printer, Share2, Download,
} from 'lucide-react';
import { SelectedLocation } from '../../types/globe';
import { LocationData, RegionalDetail } from '../../types/contracts';
import { ResearchPanel } from './ResearchPanel';
import { formatCoordinates } from '../../utils/coordinates';
import { apiService, apiJson, locationDataFromDetail } from '../../services/api';
import { computeLiveScreening } from '../../services/liveScreening';
import { TimeseriesChart } from '../charts/TimeseriesChart';
import { ZScoreChart } from '../charts/ZScoreChart';
import { IndicatorFilter } from '../charts/IndicatorFilter';
import { StatisticalAudit } from '../charts/StatisticalAudit';

interface SlidingPanelProps {
  location: SelectedLocation | null;
  onClose: () => void;
  onSelectPreset: (location: SelectedLocation) => void;
  onDetail?: (detail: RegionalDetail) => void;
}

export const SlidingPanel: React.FC<SlidingPanelProps> = ({
  location,
  onClose,
  onSelectPreset,
  onDetail,
}) => {
  const [dataStatus, setDataStatus] = useState<LocationData | null>(null);
  const [dataYears, setDataYears] = useState<[number, number]>([2003,2024]);

  const [isLoading, setIsLoading] = useState(false);
  const [actionStatus, setActionStatus] = useState('');
  const [nearest, setNearest] = useState<{region_id: string; bbox: [number, number, number, number]; distance_km: number} | null>(null);
  const [nearestLoading, setNearestLoading] = useState(false);
  const reportRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState<'visualize' | 'audit'>('visualize');

  // Visualization interactive states
  const [selectedIndicators, setSelectedIndicators] = useState<string[]>([
    'ndvi',
    'soil_water_0_100cm',
  ]);
  const [chartMode, setChartMode] = useState<'timeseries' | 'zscore'>('timeseries');
  const [showTrendline, setShowTrendline] = useState(true);
  const [yearRange, setYearRange] = useState<[number, number]>([2015, 2024]);

  useEffect(() => {
    setActionStatus('');
    if (!location) {
      setDataStatus(null);
      return;
    }

    let isMounted = true;
    setIsLoading(true);
    setDataStatus(null);

    apiService.getLocationData(location).then((res) => {
      if (isMounted) {
        setDataStatus(res);
        setIsLoading(false);
        if (res.observations && res.observations.length > 0) {
          const years = res.observations.map((o) => Number(o.date.slice(0,4)));
          const minY = Math.min(...years);
          const maxY = Math.max(...years);
          setYearRange([minY, maxY]); setDataYears([minY, maxY]);
          const names = [...new Set(res.observations.filter(o => o.value !== null).map(o => o.variable))];
          const preferred = names.filter(n => ['ndvi','soil_water_0_100cm','soil_moisture'].includes(n));
          setSelectedIndicators(preferred.length ? preferred : names.slice(0,2));
        }
      }
    });

    return () => {
      isMounted = false;
    };
  }, [location]);

  useEffect(() => {
    setNearest(null);
    if (!location || isLoading || !dataStatus || dataStatus.hasData ||
        dataStatus.statusMessage?.startsWith('Another cell') ||
        dataStatus.statusMessage?.startsWith('Location data are temporarily unavailable')) {
      setNearestLoading(false);
      return;
    }
    let active = true;
    setNearestLoading(true);
    apiJson(`/api/v1/cell/nearest?lat=${encodeURIComponent(location.lat)}&lon=${encodeURIComponent(location.lng)}`)
      .then(result => { if (active) setNearest(result); })
      .catch(() => { if (active) setNearest(null); })
      .finally(() => { if (active) setNearestLoading(false); });
    return () => { active = false; };
  }, [location, dataStatus, isLoading]);

  const retrieval = dataStatus?.detail?.ndvi_retrieval;
  useEffect(() => {
    if (!retrieval?.poll_url || !['queued', 'loading'].includes(retrieval.state)) return;
    let active = true; let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const job = await apiJson(retrieval.poll_url!);
        if (!active) return;
        if (job.state === 'complete' && (job.observations_response || job.detail)) {
          const raw = job.observations_response;
          const next = raw ? { ...locationDataFromDetail(computeLiveScreening(raw, { startYear: yearRange[0], endYear: yearRange[1] })), rawObservations: raw } : locationDataFromDetail(job.detail);
          setDataStatus(next);
          if (next.observations?.some(o => o.variable === 'ndvi' && o.value !== null))
            setSelectedIndicators(current => current.includes('ndvi') ? current : ['ndvi', ...current]);
        } else if (['queued', 'loading'].includes(job.state)) {
          setDataStatus(current => current?.detail ? { ...current, detail: { ...current.detail, ndvi_retrieval: { ...retrieval, ...job } } } : current);
          timer = setTimeout(poll, 2000);
        } else {
          setDataStatus(current => current?.detail ? { ...current, detail: { ...current.detail, ndvi_retrieval: { ...retrieval, ...job } } } : current);
        }
      } catch {
        if (active) setDataStatus(current => current?.detail ? { ...current, detail: { ...current.detail, ndvi_retrieval: { ...retrieval, state: 'failed' } } } : current);
      }
    };
    timer = setTimeout(poll, 1000);
    return () => { active = false; clearTimeout(timer); };
  }, [location?.regionId, retrieval?.poll_url, yearRange]);

  useEffect(() => { if (dataStatus?.detail && onDetail) onDetail(dataStatus.detail); }, [dataStatus?.detail, onDetail]);

  const retryVegetation = async () => {
    if (!retrieval?.retry_url) return;
    try {
      const state = await apiJson(retrieval.retry_url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      setDataStatus(current => current?.detail ? { ...current, detail: { ...current.detail, ndvi_retrieval: state } } : current);
    } catch {
      setDataStatus(current => current?.detail ? { ...current, detail: { ...current.detail, ndvi_retrieval: { ...retrieval, state: 'failed' } } } : current);
    }
  };

  useEffect(() => {
    setDataStatus(current => {
      if (!current?.rawObservations) return current;
      const detail = computeLiveScreening(current.rawObservations, { startYear: yearRange[0], endYear: yearRange[1] });
      return { ...locationDataFromDetail(detail), rawObservations: current.rawObservations };
    });
  }, [yearRange]);

  const handleToggleIndicator = (variable: string) => {
    setSelectedIndicators((prev) => {
      if (prev.includes(variable)) {
        if (prev.length === 1) return prev;
        return prev.filter((v) => v !== variable);
      }
      return [...prev, variable];
    });
  };

  const availableIndicators = [...new Set((dataStatus?.observations || []).map(o => o.variable))];

  const reportText = () => {
    const rows = (dataStatus?.observations || []).map(o => [o.date.slice(0,10), o.variable, o.value ?? '', o.unit, o.source].join(','));
    return `EarthRisk — ${location?.name || 'Location'}\nCoordinates: ${location ? formatCoordinates(location.lat, location.lng) : ''}\n\n${reportRef.current?.innerText || ''}\n\nMonthly observations (date,variable,value,unit,source)\n${rows.join('\n')}`;
  };
  const copyReport = async () => {
    try { await navigator.clipboard.writeText(reportText()); setActionStatus('Results copied.'); }
    catch { setActionStatus('Could not copy. Please check clipboard permissions.'); }
  };
  const shareReport = async () => {
    try {
      if (navigator.share) { await navigator.share({ title: `EarthRisk — ${location?.name || 'Location'}`, text: reportText() }); setActionStatus('Share menu opened.'); }
      else { await navigator.clipboard.writeText(reportText()); setActionStatus('Sharing is unavailable here. Results copied instead.'); }
    } catch (error) { if (!(error instanceof Error && error.name === 'AbortError')) setActionStatus('Unable to share results.'); }
  };
  const printReport = () => {
    const popup = window.open('', '_blank');
    if (!popup) { setActionStatus('Allow pop-ups to save a PDF.'); return; }
    const safe = reportText().replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c] || c));
    popup.document.write(`<!doctype html><html><head><title>EarthRisk results</title><style>body{font:14px system-ui;color:#17334a;margin:2cm}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px system-ui;line-height:1.5}h1{font-size:22px}</style></head><body><h1>EarthRisk results</h1><pre>${safe}</pre></body></html>`);
    popup.document.close(); popup.focus(); popup.print();
    setActionStatus('Print dialog opened. Choose “Save as PDF” to save the report.');
  };
  const downloadData = () => {
    const csv = ['date,variable,value,unit,source,region_id', ...(dataStatus?.observations || []).map(o => [o.date.slice(0,10), o.variable, o.value ?? '', o.unit, o.source, o.region_id].map(v => `"${String(v).replace(/"/g,'""')}"`).join(','))].join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a'); a.href = url; a.download = `earthrisk-${location?.regionId || 'results'}.csv`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000); setActionStatus('Data downloaded.');
  };

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
                Location overview
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
          <div ref={reportRef} className="flex-1 overflow-y-auto p-5 space-y-4 text-sm text-slate-300">
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

            </div>

            {/* Scientific Data Availability / Provenance Warning */}
            {isLoading ? (
              <div className="p-3 rounded-lg bg-space-900/50 border border-slate-800 animate-pulse text-xs font-mono text-cyan-300">
                Loading location data…
              </div>
            ) : dataStatus?.hasData ? (
              <div className={`p-3 rounded-lg border flex items-center gap-2 text-xs font-mono ${dataStatus.detail?.screening?.classification === 'supported_signal' ? 'bg-red-50 border-red-200 text-red-700' : dataStatus.detail?.screening?.classification === 'no_detected_divergence' ? 'bg-green-50 border-green-200 text-green-800' : dataStatus.detail?.screening?.classification === 'uncertain_signal' ? 'bg-yellow-50 border-yellow-200 text-yellow-800' : 'bg-slate-50 border-slate-200 text-slate-700'}`}>
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>{dataStatus.detail?.screening?.classification === 'supported_signal' ? 'A potential concern was detected.' : dataStatus.detail?.screening?.classification === 'no_detected_divergence' ? 'No concerning pattern detected.' : dataStatus.detail?.screening?.classification === 'uncertain_signal' ? 'The pattern here is uncertain.' : dataStatus.detail?.screening?.classification === 'insufficient' ? 'Not enough data for a clear result.' : 'Analysis is in progress.'} <span className="block mt-1 text-slate-400">Results are preliminary.</span></span>
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-space-900/70 border border-slate-700/60 space-y-3">
                <div className="flex items-start gap-2.5">
                  <HelpCircle className="w-4 h-4 text-slate-400 shrink-0 mt-0.5" />
                  <div className="space-y-1">
                    <p className="text-xs font-mono font-semibold text-slate-200">
                      {dataStatus?.statusMessage?.startsWith('Another cell') || dataStatus?.statusMessage?.startsWith('Location data are temporarily unavailable')
                        ? 'Cell data temporarily unavailable' : 'No Data Available for Selected Point'}
                    </p>
                    <p className="text-xs text-slate-400 leading-relaxed font-mono">
                      {dataStatus?.statusMessage}
                    </p>
                  </div>
                </div>
                {nearestLoading && <p className="text-xs text-slate-500">Finding the nearest location with soil data…</p>}
                {nearest && <div className="pt-2 border-t border-slate-200">
                  <button
                    type="button"
                    onClick={() => onSelectPreset({
                      id: nearest.region_id,
                      name: 'Nearby location',
                      lat: (nearest.bbox[1] + nearest.bbox[3]) / 2,
                      lng: (nearest.bbox[0] + nearest.bbox[2]) / 2,
                      bbox: nearest.bbox,
                      hasObservationalData: true,
                      isSyntheticDemo: false,
                      regionId: nearest.region_id,
                    })}
                    className="w-full py-2.5 px-3 rounded-lg bg-cyan-700 hover:bg-cyan-800 text-white text-xs font-semibold flex items-center justify-center gap-2 transition-colors"
                  >
                    <Compass className="w-4 h-4" />
                    Explore nearest location with soil data · {Math.round(nearest.distance_km).toLocaleString()} km away
                  </button>
                  <p className="mt-2 text-xs text-slate-500">Vegetation data may still need to load for this location.</p>
                </div>}
              </div>
            )}

            {retrieval && ['queued', 'loading'].includes(retrieval.state) && <p className="text-xs text-slate-400">Loading vegetation history…</p>}
            {retrieval && ['failed', 'busy', 'unavailable'].includes(retrieval.state) && <p className="text-xs text-amber-200">Vegetation data are temporarily unavailable. Soil data can still be viewed.</p>}
            {retrieval?.retryable && retrieval.retry_url && <button type="button" onClick={retryVegetation} className="border border-cyan-700 rounded px-2 py-1 text-cyan-200 text-xs">Try again</button>}
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
                    <span>Trends</span>
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
                    <span>Details</span>
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
                      minYear={dataYears[0]}
                      allowTrendline={false}
                      maxYear={dataYears[1]}
                      onChangeYearRange={setYearRange}
                      showTrendline={false}
                      onToggleTrendline={() => setShowTrendline(!showTrendline)}
                      chartMode={chartMode}
                      onChangeChartMode={setChartMode}
                    />

                    <div className="p-3.5 rounded-xl bg-space-950/80 border border-cyan-500/20 space-y-2">
                      <div className="flex items-center justify-between text-xs font-mono text-slate-400 border-b border-slate-800/80 pb-1.5">
                        <span className="font-bold text-white uppercase">
                          {chartMode === 'timeseries'
                            ? 'Changes over time'
                            : 'Comparing changes'}
                        </span>
                        <span className="text-[10px] text-cyan-300">
                          {chartMode === 'timeseries' ? '' : 'STANDARDIZED'}
                        </span>
                      </div>

                      {chartMode === 'timeseries' ? (
                        <TimeseriesChart
                          observations={dataStatus.observations}
                          selectedIndicators={selectedIndicators}
                          yearRange={yearRange}
                          showTrendline={false}
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
                    detail={dataStatus.detail}
                    analysis={dataStatus.analysis}
                    observations={dataStatus.observations}
                    selectedIndicators={selectedIndicators}
                    yearRange={yearRange}
                  />
                )}
              </div>
            )}
            {dataStatus?.hasData && dataStatus.detail && <ResearchPanel detail={dataStatus.detail} />}
            {dataStatus?.hasData && <section className="rounded-xl border border-slate-200 bg-white p-4">
              <h3 className="text-sm font-semibold text-slate-800">Take these results with you</h3>
              <p className="mt-1 text-xs text-slate-500">Copy, share, or save this location’s results and data.</p>
              <div className="mt-3 grid grid-cols-2 gap-2">
                <button type="button" onClick={copyReport} className="flex items-center justify-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"><Copy size={15}/> Copy all</button>
                <button type="button" onClick={printReport} className="flex items-center justify-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"><Printer size={15}/> Save as PDF</button>
                <button type="button" onClick={shareReport} className="flex items-center justify-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"><Share2 size={15}/> Share results</button>
                <button type="button" onClick={downloadData} className="flex items-center justify-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100"><Download size={15}/> Download data</button>
              </div>
              <p role="status" className="mt-2 text-xs text-slate-500">{actionStatus}</p>
            </section>}
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
