import { TimeSeriesObservation } from '../types/contracts';

export interface LinearRegressionResult {
  slope: number;
  intercept: number;
  r2: number;
  stdError: number;
  trendline: Array<{ date: string; value: number }>;
}

/**
 * Exploratory demo-only OLS; scientific inference comes from backend annual fits.
 */
export function calculateOLSTrend(observations: TimeSeriesObservation[]): LinearRegressionResult | null {
  const valid = observations
    .filter((obs) => typeof obs.value === 'number' && Number.isFinite(obs.value) && Number.isFinite(Date.parse(obs.date)))
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());

  if (valid.length < 3) return null;

  const n = valid.length;
  const dates = valid.map((obs) => new Date(obs.date).getTime());
  const minDate = dates[0];
  const msInYear = 365.25 * 24 * 3600 * 1000;

  // Convert time to years relative to first observation
  const x = dates.map((d) => (d - minDate) / msInYear);
  const y = valid.map((obs) => obs.value as number);

  const sumX = x.reduce((a, b) => a + b, 0);
  const sumY = y.reduce((a, b) => a + b, 0);
  const meanX = sumX / n;
  const meanY = sumY / n;

  let numerator = 0;
  let denominator = 0;
  for (let i = 0; i < n; i++) {
    numerator += (x[i] - meanX) * (y[i] - meanY);
    denominator += (x[i] - meanX) ** 2;
  }

  if (denominator === 0) return null;

  const slope = numerator / denominator;
  const intercept = meanY - slope * meanX;

  // Compute R2
  let ssTot = 0;
  let ssRes = 0;
  for (let i = 0; i < n; i++) {
    const yPred = intercept + slope * x[i];
    ssTot += (y[i] - meanY) ** 2;
    ssRes += (y[i] - yPred) ** 2;
  }

  const r2 = ssTot === 0 ? 0 : Math.max(0, 1 - ssRes / ssTot);
  const stdError = Math.sqrt(ssRes / Math.max(1, n - 2)) / Math.sqrt(denominator);

  // Generate trendline points
  const trendline = valid.map((obs, idx) => ({
    date: obs.date,
    value: Number((intercept + slope * x[idx]).toFixed(4)),
  }));

  return {
    slope: Number(slope.toFixed(4)),
    intercept: Number(intercept.toFixed(4)),
    r2: Number(r2.toFixed(4)),
    stdError: Number(stdError.toFixed(4)),
    trendline,
  };
}

/**
 * Normalizes time-series values to Z-scores: z = (x - mean) / stdDev
 */
export function calculateZScores(
  observations: TimeSeriesObservation[]
): Array<{ date: string; zScore: number | null; rawValue: number | null }> {
  const ordered = [...observations].filter((obs) => Number.isFinite(Date.parse(obs.date)))
    .sort((a, b) => Date.parse(a.date) - Date.parse(b.date));
  const values = ordered.map((obs) => obs.value)
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value));
  const mean = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0;
  const variance = values.length ? values.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(1, values.length - 1) : 0;
  const stdDev = Math.sqrt(variance);
  // Retain every supplied monthly slot; missing observations remain null.
  return ordered.map((obs) => {
    const valid = typeof obs.value === 'number' && Number.isFinite(obs.value);
    const value = valid ? obs.value as number : null;
    return { date: obs.date, rawValue: value,
      zScore: value === null ? null : stdDev === 0 ? 0 : (value - mean) / stdDev };
  });
}
