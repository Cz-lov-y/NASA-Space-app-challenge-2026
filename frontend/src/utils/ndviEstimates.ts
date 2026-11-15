import type { TimeSeriesObservation } from '../types/contracts';

type Monthly = TimeSeriesObservation & { quality_flag?: string };
export type ChartPoint = { value: number; estimated: boolean } | null;
const REJECTED = new Set(['low_coverage', 'missing', 'invalid', 'qa_rejected', 'no_valid_data', 'no_valid_pixels', 'negative_value', 'pending_export']);
const monthIndex = (date: string) => {
  const match = /^(\d{4})-(\d{2})/.exec(date);
  return match ? Number(match[1]) * 12 + Number(match[2]) - 1 : NaN;
};

// Least-squares annual harmonic plus linear trend, fitted to observed months.
function seasonalModel(rows: Monthly[]): ((month: number) => number) | null {
  const observed = rows.filter(r => typeof r.value === 'number' && Number.isFinite(r.value) &&
    Number.isFinite(monthIndex(r.date)) && !REJECTED.has(r.quality_flag || ''));
  const months = observed.map(r => monthIndex(r.date));
  if (observed.length < 18 || new Set(months.map(m => Math.floor(m / 12))).size < 3 ||
      new Set(months.map(m => ((m % 12) + 12) % 12)).size < 4) return null;
  const origin = months.reduce((a,b) => a+b, 0) / months.length;
  const features = (m: number) => [1, (m-origin)/120, Math.sin(2*Math.PI*m/12), Math.cos(2*Math.PI*m/12)];
  const matrix = Array.from({length: 4}, () => Array(5).fill(0));
  observed.forEach((row, index) => {
    const x = features(months[index]);
    for (let i=0;i<4;i++) { for(let j=0;j<4;j++) matrix[i][j] += x[i]*x[j]; matrix[i][4] += x[i]*row.value!; }
  });
  for (let i=0;i<4;i++) {
    let pivot=i; for(let j=i+1;j<4;j++) if(Math.abs(matrix[j][i])>Math.abs(matrix[pivot][i]))pivot=j;
    if(Math.abs(matrix[pivot][i])<1e-10)return null;
    [matrix[i],matrix[pivot]]=[matrix[pivot],matrix[i]];
    const scale=matrix[i][i]; for(let k=i;k<5;k++)matrix[i][k]/=scale;
    for(let j=0;j<4;j++)if(j!==i){const factor=matrix[j][i];for(let k=i;k<5;k++)matrix[j][k]-=factor*matrix[i][k];}
  }
  const beta=matrix.map(row=>row[4]);
  return m=>features(m).reduce((sum,x,i)=>sum+x*beta[i],0);
}

/** Bounded winter/other no-pixel gaps: seasonal fit with observed endpoint adjustment. */
export function ndviGapEstimates(dates: string[], observations: Monthly[], maxGap = 6): ChartPoint[] {
  const byDate = new Map(observations.map(row => [row.date, row]));
  const result: ChartPoint[] = dates.map(() => null);
  const model=seasonalModel(observations);
  if(!model)return result;
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
    const av = a!.value!, bv = b!.value!, residualA=av-model(startMonth), residualB=bv-model(monthIndex(dates[right]));
    result[left] = {value: av, estimated: false};
    for (let k = start; k <= end; k++) {
      const fraction=(k-left)/(right-left);
      const predicted=model(monthIndex(dates[k]))+(1-fraction)*residualA+fraction*residualB;
      result[k] = {value: Math.max(-0.2,Math.min(1,predicted)), estimated: true};
    }
    result[right] = {value: bv, estimated: false};
  }
  return result;
}
