import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { TimeSeriesObservation } from '../../types/contracts';
import { calculateZScores } from '../../utils/statistics';

interface ZScoreChartProps {
  observations: TimeSeriesObservation[];
  yearRange: [number, number];
}

export const ZScoreChart: React.FC<ZScoreChartProps> = ({
  observations,
  yearRange,
}) => {
  const filtered = useMemo(() => {
    return observations.filter((obs) => {
      const year = new Date(obs.date).getFullYear();
      return (
        ['ndvi', 'soil_moisture'].includes(obs.variable) &&
        year >= yearRange[0] &&
        year <= yearRange[1]
      );
    });
  }, [observations, yearRange]);

  const ndviSeries = useMemo(() => {
    const ndviObs = filtered.filter((d) => d.variable === 'ndvi');
    return calculateZScores(ndviObs);
  }, [filtered]);

  const moistureSeries = useMemo(() => {
    const moistObs = filtered.filter((d) => d.variable === 'soil_moisture');
    return calculateZScores(moistObs);
  }, [filtered]);

  const option = useMemo(() => {
    const allDates = Array.from(
      new Set([
        ...ndviSeries.map((d) => d.date),
        ...moistureSeries.map((d) => d.date),
      ])
    ).sort();

    const ndviMap = new Map(ndviSeries.map((d) => [d.date, d.zScore]));
    const moistureMap = new Map(moistureSeries.map((d) => [d.date, d.zScore]));

    const ndviData = allDates.map((d) => ndviMap.get(d) ?? null);
    const moistureData = allDates.map((d) => moistureMap.get(d) ?? null);

    return {
      backgroundColor: 'transparent',
      animationDuration: 750,
      tooltip: {
        trigger: 'axis',
        backgroundColor: 'rgba(2, 6, 23, 0.92)',
        borderColor: 'rgba(0, 229, 255, 0.3)',
        borderWidth: 1,
        padding: [10, 14],
        textStyle: {
          color: '#f8fafc',
          fontFamily: 'ui-monospace, monospace',
          fontSize: 12,
        },
        formatter: (params: any[]) => {
          if (!params || params.length === 0) return '';
          let tip = `<div style="font-weight:bold;margin-bottom:6px;border-bottom:1px solid rgba(255,255,255,0.1);padding-bottom:4px;color:#00e5ff">${params[0].axisValue}</div>`;
          params.forEach((item) => {
            if (item.value === null || item.value === undefined) return;
            const sign = item.value >= 0 ? '+' : '';
            tip += `<div style="display:flex;align-items:center;justify-content:space-between;gap:16px;margin:3px 0;">
              <span style="display:inline-flex;align-items:center;gap:6px;">
                <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${item.color};"></span>
                <span style="color:#cbd5e1">${item.seriesName}</span>
              </span>
              <strong style="color:#ffffff">${sign}${item.value} σ</strong>
            </div>`;
          });
          return tip;
        },
      },
      legend: {
        top: 2,
        textStyle: {
          color: '#94a3b8',
          fontSize: 11,
          fontFamily: 'ui-monospace, monospace',
        },
        icon: 'roundRect',
      },
      grid: {
        top: 55,
        left: 52,
        right: 20,
        bottom: 25,
      },
      xAxis: {
        type: 'category',
        data: allDates,
        axisLine: { lineStyle: { color: 'rgba(0, 229, 255, 0.2)' } },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 10,
          fontFamily: 'ui-monospace, monospace',
          formatter: (val: string) => val.slice(0, 4),
        },
        splitLine: { show: false },
      },
      yAxis: {
        type: 'value',
        name: 'Anomaly (σ)',
        nameTextStyle: {
          color: '#64748b',
          fontSize: 10,
          fontFamily: 'ui-monospace, monospace',
        },
        axisLine: { show: false },
        axisLabel: {
          color: '#94a3b8',
          fontSize: 10,
          fontFamily: 'ui-monospace, monospace',
          formatter: '{value} σ',
        },
        splitLine: {
          lineStyle: {
            color: 'rgba(0, 229, 255, 0.08)',
            type: 'dashed',
          },
        },
      },
      series: [
        {
          name: 'NDVI (Greenness Trajectory)',
          type: 'line',
          data: ndviData,
          smooth: 0.3,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { width: 2.8, color: '#10b981' },
          itemStyle: { color: '#10b981', borderColor: '#020617', borderWidth: 2 },
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { color: 'rgba(255, 255, 255, 0.2)', type: 'dashed' },
            data: [{ yAxis: 0 }],
          },
        },
        {
          name: 'Soil Moisture (Water Content)',
          type: 'line',
          data: moistureData,
          smooth: 0.3,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { width: 2.8, color: '#00e5ff' },
          itemStyle: { color: '#00e5ff', borderColor: '#020617', borderWidth: 2 },
        },
      ],
    };
  }, [ndviSeries, moistureSeries]);

  if (ndviSeries.length === 0 || moistureSeries.length === 0) {
    return (
      <div className="p-6 rounded-xl bg-space-900/50 border border-slate-800 text-center text-xs text-slate-400 font-mono">
        Both NDVI and Soil Moisture indicators are required for standardized comparative screening.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="w-full h-64 sm:h-72">
        <ReactECharts
          option={option}
          style={{ width: '100%', height: '100%' }}
          notMerge
          lazyUpdate
        />
      </div>
      <p className="text-[11px] text-slate-400 leading-relaxed font-mono px-1">
        * Trajectories are centered on indicator means and scaled by sample standard deviation (z-score). This compares relative trajectory slopes across disparate physical units; it is <strong>not</strong> an environmental hazard score.
      </p>
    </div>
  );
};
