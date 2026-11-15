import type { TimeSeriesObservation } from '../types/contracts';

type Monthly = TimeSeriesObservation & { quality_flag?: string };
type ChartPoint = { value: number; estimated: boolean } | null;
const REJECTED = new Set(['low_coverage', 'missing', 'invalid', 'qa_rejected', 'no_valid_data', 'no_valid_pixels', 'negative_value', 'pending_export']);
const monthIndex = (date: string) => {
  const match = /^(\d{4})-(\d{2})/.exec(date);
  return match ? Number(match[1]) * 12 + Number(match[2]) - 1 : NaN;
};

/** Display-only linear interpolation for short, bounded no-pixel NDVI gaps. */
export function ndviGapEstimates(dates: string[], observations: Monthly[], maxGap = 6): ChartPoint[] {
  const byDate = new Map(observations.map(row => [row.date, row]));
  const result: ChartPoint[] = dates.map(() => null);
  const isObserved = (row: Monthly | undefined) => row && typeof row.value === 'number' && Number.isFinite(row.value) && !REJECTED.has(row.quality_flag || '');
  let i = 0;
  while (i < dates.length) {
    const row = byDate.get(dates[i]);
    if (!row || row.value !== null || row.quality_flag !== 'no_valid_pixels') { i++; continue; }
    const start = i;
    while (i < dates.length) {
      const candidate = byDate.get(dates[i]);
      if (!candidate || candidate.value !== null || candidate.quality_flag !== 'no_valid_pixels') break;
      i++;
    }
    const end = i - 1, left = start - 1, right = i;
    if (end - start + 1 > maxGap || left < 0 || right >= dates.length) continue;
    const a = byDate.get(dates[left]), b = byDate.get(dates[right]);
    if (!isObserved(a) || !isObserved(b)) continue;
    const startMonth = monthIndex(dates[left]);
    if (!Number.isFinite(startMonth) || dates.slice(left, right + 1).some((d, k) => monthIndex(d) !== startMonth + k)) continue;
    const av = a!.value!, bv = b!.value!;
    result[left] = {value: av, estimated: false};
    for (let k = start; k <= end; k++)
      result[k] = {value: av + (bv - av) * (k - left) / (right - left), estimated: true};
    result[right] = {value: bv, estimated: false};
  }
  return result;
}
