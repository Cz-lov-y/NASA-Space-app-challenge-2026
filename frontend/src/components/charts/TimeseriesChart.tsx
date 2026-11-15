import React, { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import { TimeSeriesObservation } from '../../types/contracts';
import { calculateOLSTrend } from '../../utils/statistics';
import { ndviGapEstimates } from '../../utils/ndviEstimates';

interface TimeseriesChartProps {
  observations: TimeSeriesObservation[];
  selectedIndicators: string[];
  yearRange: [number, number];
  showTrendline: boolean;
}

const INDICATOR_CONFIG: Record<
  string,
  { label: string; color: string; unit: string; yAxisIndex: number }
> = {
  ndvi: {
    label: 'Vegetation (NDVI)',
    color: '#047857', // Emerald
    unit: 'index',
    yAxisIndex: 0,
  },
  soil_water_0_100cm: {
    label: 'Soil Water (0–100 cm)', color: '#1675b9', unit: 'kg m-2', yAxisIndex: 1,
  },
  soil_water_0_10cm: {
    label: 'Soil Water (0–10 cm)', color: '#a855f7', unit: 'kg m-2', yAxisIndex: 1,
  },
  soil_moisture: {
    label: 'Soil Moisture',
    color: '#1675b9', // Electric Cyan
    unit: 'kg/m²',
    yAxisIndex: 1,
  },
  temperature: {
    label: 'Temperature',
    color: '#f59e0b', // Amber
    unit: '°C',
    yAxisIndex: 1,
  },
  precipitation: {
    label: 'Precipitation',
    color: '#3b82f6', // Blue
    unit: 'mm/mo',
    yAxisIndex: 1,
  },
};

export const TimeseriesChart: React.FC<TimeseriesChartProps> = ({
  observations,
  selectedIndicators,
  yearRange,
  showTrendline,
}) => {
  // Filter by indicator and year range
  const filtered = useMemo(() => {
    return observations.filter((obs) => {
      const year = new Date(obs.date).getUTCFullYear();
      return (
        selectedIndicators.includes(obs.variable) &&
        year >= yearRange[0] &&
        year <= yearRange[1]
      );
    });
  }, [observations, selectedIndicators, yearRange]);

  const option = useMemo(() => {
    // Unique sorted dates
    const dates = Array.from(
      new Set(filtered.map((d) => d.date))
    ).sort();

    // Determine if dual y-axis is needed
    const hasNDVI = selectedIndicators.includes('ndvi');
    const hasOther = selectedIndicators.some((ind) => ind !== 'ndvi');
    const useDualAxis = hasNDVI && hasOther;

    // Build series
    const seriesList: any[] = [];

    selectedIndicators.forEach((variable) => {
      const config = INDICATOR_CONFIG[variable] || {
        label: variable.toUpperCase(),
        color: '#a855f7',
        unit: '',
        yAxisIndex: 0,
      };

      const varObs = filtered.filter((d) => d.variable === variable);
      if (varObs.length === 0) return;

      const dataMap = new Map(varObs.map((d) => [d.date, d.value]));
      const seriesData = dates.map((date) => dataMap.get(date) ?? null);

      const yAxisIdx = useDualAxis
        ? variable === 'ndvi'
          ? 0
          : 1
        : 0;

      // 1. Observed time-series line
      seriesList.push({
        name: config.label,
        type: 'line',
        yAxisIndex: yAxisIdx,
        data: seriesData,
        smooth: 0.25,
        symbol: 'circle',
        symbolSize: 6,
        showSymbol: true,
        lineStyle: {
          width: 2.5,
          color: config.color,
        },
        itemStyle: {
          color: config.color,
          borderColor: '#ffffff',
          borderWidth: 2,
        },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: `${config.color}33` }, // 20% opacity
              { offset: 1, color: `${config.color}00` }, // transparent
            ],
          },
        },
      });

      if (variable === 'ndvi') {
        const estimated = ndviGapEstimates(dates, varObs);
        if (estimated.some(point => point?.estimated)) seriesList.push({
          name: 'Vegetation estimate', type: 'line', yAxisIndex: yAxisIdx,
          data: estimated, smooth: 0.2, symbol: 'none', connectNulls: false,
          lineStyle: { width: 2, type: 'dashed', color: config.color },
          itemStyle: { color: config.color },
        });
      }

      // 2. Trendline (if enabled and sufficient observations)
      if (showTrendline && varObs.length >= 3 && varObs.every((obs) => obs.source.toUpperCase().includes('SYNTHETIC'))) {
        const trend = calculateOLSTrend(varObs);
        if (trend) {
          const trendMap = new Map(trend.trendline.map((t) => [t.date, t.value]));
          const trendData = dates.map((date) => trendMap.get(date) ?? null);

          seriesList.push({
            name: `${config.label} Exploratory Demo Fit`,
            type: 'line',
            yAxisIndex: yAxisIdx,
            data: trendData,
            smooth: false,
            symbol: 'none',
            lineStyle: {
              width: 1.8,
              type: 'dashed',
              color: config.color,
              opacity: 0.75,
            },
          });
        }
      }
    });

    const primaryUnit = hasNDVI
      ? 'NDVI Index'
      : (filtered.find((obs) => obs.variable === selectedIndicators[0])?.unit || INDICATOR_CONFIG[selectedIndicators[0]]?.unit || '');
    const secondaryUnit = useDualAxis
      ? (filtered.find((obs) => obs.variable !== 'ndvi')?.unit || INDICATOR_CONFIG[selectedIndicators.find((i) => i !== 'ndvi') || '']?.unit || '')
      : '';

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
            if (item.value === null || item.value === undefined || (item.seriesName === 'Vegetation estimate' && !item.data?.estimated)) return;
            tip += `<div style="display:flex;align-items:center;justify-content:space-between;gap:16px;margin:3px 0;">
              <span style="display:inline-flex;align-items:center;gap:6px;">
                <span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${item.color};"></span>
                <span style="color:#355469">${item.seriesName}</span>
              </span>
              <strong style="color:#17334a">${item.value}</strong>
            </div>`;
          });
          return tip;
        },
      },
      legend: {
        top: 2,
        data: seriesList.map(series => series.name),
        textStyle: {
          color: '#475f70',
          fontSize: 11,
          fontFamily: 'ui-monospace, monospace',
        },
        icon: 'roundRect',
      },
      grid: {
        top: 60,
        left: 48,
        right: useDualAxis ? 48 : 20,
        bottom: 50,
        containLabel: false,
      },
      xAxis: {
        type: 'category',
        data: dates,
        axisLine: { lineStyle: { color: 'rgba(0, 229, 255, 0.2)' } },
        axisLabel: {
          color: '#475f70',
          fontSize: 10,
          fontFamily: 'ui-monospace, monospace',
          formatter: (val: string) => val.slice(0, 4), // show year
        },
        splitLine: { show: false },
      },
      yAxis: [
        {
          type: 'value',
          name: primaryUnit,
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
          },
          splitLine: {
            lineStyle: {
              color: 'rgba(0, 229, 255, 0.08)',
              type: 'dashed',
            },
          },
        },
        ...(useDualAxis
          ? [
              {
                type: 'value',
                name: secondaryUnit,
                nameTextStyle: {
                  color: '#526c7c',
                  fontSize: 10,
                  fontFamily: 'ui-monospace, monospace',
                },
                position: 'right',
                axisLine: { show: false },
                axisLabel: {
                  color: '#475f70',
                  fontSize: 10,
                  fontFamily: 'ui-monospace, monospace',
                },
                splitLine: { show: false },
              },
            ]
          : []),
      ],
      dataZoom: [
        {
          type: 'slider',
          show: true,
          bottom: 4,
          height: 18,
          borderColor: 'rgba(0, 229, 255, 0.2)',
          fillerColor: 'rgba(0, 229, 255, 0.15)',
          handleStyle: {
            color: '#1675b9',
            borderColor: '#ffffff',
          },
          textStyle: { color: '#526c7c', fontSize: 9 },
        },
        {
          type: 'inside',
        },
      ],
      series: seriesList,
    };
  }, [filtered, selectedIndicators, showTrendline]);

  if (filtered.length === 0) {
    return (
      <div className="p-8 rounded-xl bg-space-900/50 border border-slate-800 text-center text-xs text-slate-400 font-mono">
        No observation records available for the selected indicators in this time range.
      </div>
    );
  }

  return (
    <div className="w-full">
      <ReactECharts
        option={option}
        style={{ width: '100%', height: 320 }}
        notMerge
        lazyUpdate
      />
      {option.series.some((series: any) => series.name === 'Vegetation estimate') &&
        <p className="mt-2 text-xs text-slate-500">Dashed green lines show estimated vegetation; solid lines show observations.</p>}
    </div>
  );
};
