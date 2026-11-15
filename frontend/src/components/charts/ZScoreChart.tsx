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
      const year = new Date(obs.date).getUTCFullYear();
      return (
        ['ndvi', 'soil_water_0_100cm', 'soil_water_0_10cm', 'soil_moisture'].includes(obs.variable) &&
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
    const soil = ['soil_water_0_100cm', 'soil_moisture', 'soil_water_0_10cm'].find((name) => filtered.some((d) => d.variable === name));
    const moistObs = filtered.filter((d) => d.variable === soil);
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
        backgroundColor: 'rgba(255, 255, 255, 0.97)',
        borderColor: 'rgba(0, 229, 255, 0.3)',
        borderWidth: 1,
        padding: [10, 14],
        textStyle: {
          color: '#17334a',
          fontFamily: 'ui-monospace, monospace',
          fontSize: 12,
        },
        formatter: (params: any[]) => {
          if (!params || params.length === 0) return '';
          let tip = `<div style="font-weight:bold;margin-bottom:6px;border-bottom:1px solid rgba(30,75,100,0.15);padding-bottom:4px;color:#08758f">${params[0].axisValue}</div>`;
          params.forEach((item) => {
            if (item.value === null || item.value === undefined) return;
            const sign = item.value >= 0 ? '+' : '';
            tip += `<div style="display:flex;align-items:center;justify-content:space-between;gap:16px;margin:3px 0;">
              <span style="display:inline-flex;align-items:center;gap:6px;">
                <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${item.color};"></span>
                <span style="color:#355469">${item.seriesName}</span>
              </span>
              <strong style="color:#17334a">${sign}${item.value} σ</strong>
            </div>`;
          });
          return tip;
        },
      },
      legend: {
        top: 2,
        textStyle: {
          color: '#475f70',
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
          color: '#475f70',
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
          color: '#526c7c',
          fontSize: 10,
          fontFamily: 'ui-monospace, monospace',
        },
        axisLine: { show: false },
        axisLabel: {
          color: '#475f70',
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
          lineStyle: { width: 2.8, color: '#047857' },
          itemStyle: { color: '#047857', borderColor: '#ffffff', borderWidth: 2 },
          markLine: {
            silent: true,
            symbol: 'none',
            lineStyle: { color: 'rgba(255, 255, 255, 0.2)', type: 'dashed' },
            data: [{ yAxis: 0 }],
          },
        },
        {
          name: `Soil Water (${filtered.some((d) => d.variable === 'soil_water_0_100cm') ? '0–100 cm' : filtered.some((d) => d.variable === 'soil_water_0_10cm') ? '0–10 cm' : 'demo'})`,
          type: 'line',
          data: moistureData,
          smooth: 0.3,
          symbol: 'circle',
          symbolSize: 6,
          lineStyle: { width: 2.8, color: '#1675b9' },
          itemStyle: { color: '#1675b9', borderColor: '#ffffff', borderWidth: 2 },
        },
      ],
    };
  }, [ndviSeries, moistureSeries, filtered]);

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
