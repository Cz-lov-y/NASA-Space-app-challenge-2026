import { RegionalDetail } from '../../types/contracts';

function trendText(value: unknown, subject: string): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return `${subject}: not enough data to show a trend.`;
  if (Math.abs(value)<1e-10) return `${subject}: stayed about the same.`;
  return `${subject}: generally ${value>0?'increased':'decreased'} over the selected years.`;
}

export function PlainLanguageSummary({detail}: {detail: RegionalDetail}) {
  const paired=detail.paired_analysis;
  const green=paired?.trends?.ndvi?.theil_sen_slope_per_year;
  const soil=paired?.trends?.soil_water_0_100cm?.theil_sen_slope_per_year ??
    detail.available_indicator_analysis?.trends?.soil_water_0_100cm?.theil_sen_slope_per_year;
  const classification=detail.screening?.classification;
  let conclusion: string;
  if(classification==='supported_signal') conclusion='Together: vegetation increased while soil water declined, a pattern worth attention.';
  else if(classification==='no_detected_divergence') conclusion='Together: the trends do not show the increasing-greenness and declining-soil-water pattern.';
  else if(classification==='uncertain_signal') conclusion='Together: the available trends do not give a clear answer.';
  else if(classification==='pending') conclusion='Together: the result will update when vegetation and soil records are available.';
  else conclusion='Together: there are not enough paired years to determine a pattern.';
  return <section aria-label="What this means" className="rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700">
    <h3 className="font-semibold text-slate-900">What this means</h3>
    <ul className="mt-2 list-disc space-y-1.5 pl-5 text-xs leading-relaxed">
      <li>{trendText(green,'Vegetation')}</li>
      <li>{trendText(soil,'Soil water')}</li>
      <li>{conclusion}</li>
    </ul>
  </section>;
}
