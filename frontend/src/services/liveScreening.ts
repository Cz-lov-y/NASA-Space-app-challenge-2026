/** Live annual inference from monthly observations and optional seasonal NDVI estimates.
 * Uses complete-year, Sen/MK/OLS and reliability rules; model uncertainty is not propagated.
 * Scope is the selected cell and window; no global or stored collection q-values are reused.
 */
import { RegionalDetail, TimeSeriesObservation } from '../types/contracts';
import { ndviGapEstimates } from '../utils/ndviEstimates';

type Observation = TimeSeriesObservation & { quality_flag?: string };
type Raw = { region_id: string; feature: any; dataset_version: string; observations: Observation[];
  provenance: any; availability?: any; ndvi_retrieval?: RegionalDetail['ndvi_retrieval'] };
export interface LiveOptions { startYear: number; endYear: number; alpha?: number; estimateMissing?: boolean }
const REJECT = new Set(['low_coverage','missing','invalid','qa_rejected','no_valid_data','no_valid_pixels','negative_value']);
const VARIABLES = ['ndvi','soil_water_0_100cm'];
const SCOPE = 'live browser single-cell/window exploratory; not adjusted across regions or repeated windows';
const LIMITATIONS = [
  'Computed in the browser from supplied monthly source observations; source QA remains unreviewed.',
  'NDVI may include model-estimated months in short no-pixel gaps; annual means require12 observed or estimated months.',
  'Uncertainty from estimated NDVI is not propagated into statistical significance or trend intervals.',
  'BH covers only the primary indicators in this selected cell/window; no adjustment across regions or repeated windows.',
  'P-values and marginal slope intervals assume independent annual observations; lag1is a diagnostic, not a correction.',
  'Evidence categories are not calibrated environmental-risk probabilities. Divergence does not establish damage or causation.',
  'Matching cell boundaries do not establish identical MODIS/GLDAS valid footprints.',
];
const finite = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);
const sum = (x: number[]) => x.reduce((a,b)=>a+b,0);
const mean = (x: number[]) => sum(x)/x.length;
const sorted = (x: number[]) => [...x].sort((a,b)=>a-b);
const median = (x: number[]) => { const s=sorted(x),n=s.length; return n%2 ? s[(n-1)/2] : (s[n/2-1]+s[n/2])/2; };
const tolerance = (x: number[]) => 100*Number.EPSILON*Math.max(Number.MIN_VALUE,...x.map(Math.abs));
const constant = (x: number[]) => Math.max(...x)-Math.min(...x)<=tolerance(x);
const ties = (x: number[]) => { const m=new Map<number,number>();x.forEach(v=>m.set(v,(m.get(v)||0)+1));return [...m.values()]; };
const roundEven = (x: number) => { const f=Math.floor(x);return x-f===.5 ? (f%2===0?f:f+1) : Math.round(x); };

// Lanczos log-gamma and convergent incomplete-beta/gamma routines avoid a new runtime dependency.
function logGamma(z: number): number {
  const p=[676.5203681218851,-1259.1392167224028,771.32342877765313,-176.61502916214059,12.507343278686905,-.13857109526572012,9.9843695780195716e-6,1.5056327351493116e-7];
  if(z<.5)return Math.log(Math.PI)-Math.log(Math.sin(Math.PI*z))-logGamma(1-z);
  z-=1;let x=.99999999999980993; p.forEach((v,i)=>x+=v/(z+i+1));const t=z+7.5;
  return .5*Math.log(2*Math.PI)+(z+.5)*Math.log(t)-t+Math.log(x);
}
function betaFraction(a:number,b:number,x:number) {
  const tiny=1e-300;let c=1,d=1-(a+b)*x/(a+1);if(Math.abs(d)<tiny)d=tiny;d=1/d;let h=d;
  for(let m=1;m<300;m++) { const m2=2*m;
    let aa=m*(b-m)*x/((a+m2-1)*(a+m2));d=1+aa*d;if(Math.abs(d)<tiny)d=tiny;c=1+aa/c;if(Math.abs(c)<tiny)c=tiny;d=1/d;h*=d*c;
    aa=-(a+m)*(a+b+m)*x/((a+m2)*(a+m2+1));d=1+aa*d;if(Math.abs(d)<tiny)d=tiny;c=1+aa/c;if(Math.abs(c)<tiny)c=tiny;d=1/d;const delta=d*c;h*=delta;if(Math.abs(delta-1)<3e-14)break;
  } return h;
}
function betaI(x:number,a:number,b:number) {
  if(x<=0)return 0;if(x>=1)return 1;
  const bt=Math.exp(logGamma(a+b)-logGamma(a)-logGamma(b)+a*Math.log(x)+b*Math.log1p(-x));
  return x<(a+1)/(a+b+2) ? bt*betaFraction(a,b,x)/a : 1-bt*betaFraction(b,a,1-x)/b;
}
function normalSF(z:number):number {
  if(z<0)return 1-normalSF(-z);if(z===0)return .5;
  const a=.5,x=z*z/2, factor=Math.exp(-x+a*Math.log(x)-logGamma(a));let q:number;
  if(x<a+1){let term=1/a,s=term;for(let n=1;n<400;n++){term*=x/(a+n);s+=term;if(Math.abs(term)<Math.abs(s)*1e-15)break;}q=1-s*factor;}
  else {let b=x+1-a,c=1e300,d=1/b,h=d;for(let n=1;n<400;n++){const an=-n*(n-a);b+=2;d=an*d+b;if(Math.abs(d)<1e-300)d=1e-300;c=b+an/c;if(Math.abs(c)<1e-300)c=1e-300;d=1/d;const delta=d*c;h*=delta;if(Math.abs(delta-1)<1e-15)break;}q=factor*h;}
  return Math.max(0,Math.min(1,q))*.5;
}
function normalCritical(alpha:number){let lo=0,hi=12;for(let i=0;i<70;i++){const mid=(lo+hi)/2;if(normalSF(mid)>alpha/2)lo=mid;else hi=mid;}return (lo+hi)/2;}
function tTwoTail(t:number,df:number){return betaI(df/(df+t*t),df/2,.5);}
function tCritical(alpha:number,df:number){let lo=0,hi=1;while(tTwoTail(hi,df)>alpha)hi*=2;for(let i=0;i<80;i++){const mid=(lo+hi)/2;if(tTwoTail(mid,df)>alpha)lo=mid;else hi=mid;}return (lo+hi)/2;}

function ols(x:number[],y:number[],alpha:number) {
  const origin=x[0],xx=x.map(v=>v-origin),mx=mean(xx),my=mean(y),n=x.length;
  if(constant(y))return {slope:0,intercept:y[0],time_origin:origin,p_value:1,r_squared:0,standard_error:0,confidence_interval:[0,0],confidence_level:1-alpha};
  const ssx=sum(xx.map(v=>(v-mx)**2)),ssy=sum(y.map(v=>(v-my)**2)),cov=sum(xx.map((v,i)=>(v-mx)*(y[i]-my)));
  const slope=cov/ssx,r=Math.max(-1,Math.min(1,cov/Math.sqrt(ssx*ssy))),se=Math.sqrt(Math.max(0,(1-r*r)*ssy/ssx/(n-2)));
  const p=tTwoTail(Math.abs(r)*Math.sqrt((n-2)/((1-r+1e-20)*(1+r+1e-20))),n-2),margin=tCritical(alpha,n-2)*se;
  return {slope,intercept:my-slope*mx,time_origin:origin,p_value:p,r_squared:r*r,standard_error:se,confidence_interval:[slope-margin,slope+margin],confidence_level:1-alpha};
}
function sen(x:number[],y:number[],alpha:number) {
  if(constant(y))return {slope:0,intercept:y[0],time_origin:x[0],confidence_level:1-alpha,confidence_interval:[0,0]};
  const slopes:number[]=[];for(let i=0;i<x.length;i++)for(let j=i+1;j<x.length;j++)slopes.push((y[j]-y[i])/(x[j]-x[i]));slopes.sort((a,b)=>a-b);
  const n=y.length,variance=(n*(n-1)*(2*n+5)-sum(ties(y).map(k=>k*(k-1)*(2*k+5))))/18;
  const width=normalCritical(alpha)*Math.sqrt(Math.max(0,variance)),m=slopes.length;
  const low=Math.max(roundEven((m-width)/2)-1,0),high=Math.min(roundEven((m+width)/2),m-1),slope=median(slopes);
  return {slope,intercept:median(y)-slope*median(x.map(v=>v-x[0])),time_origin:x[0],confidence_level:1-alpha,confidence_interval:[slopes[low],slopes[high]]};
}
function mk(values:number[],alpha:number) {
  const y=constant(values)?values.map(()=>values[0]):values;let s=0;for(let i=0;i<y.length;i++)for(let j=i+1;j<y.length;j++)s+=Math.sign(y[j]-y[i]);
  const n=y.length,variance=(n*(n-1)*(2*n+5)-sum(ties(y).map(k=>k*(k-1)*(2*k+5))))/18,z=variance?(s-Math.sign(s))/Math.sqrt(variance):0,p=2*normalSF(Math.abs(z));
  return {s,variance,z,p_value:p,tau_a:s/(n*(n-1)/2),significant:p<alpha,direction:p<alpha?(s>0?'increasing':'decreasing'):'no_significant_trend',method:'asymptotic_mann_kendall_ties_continuity_corrected'};
}
export function adjustLivePValues(p:(number|null)[]) {
  const ranked=p.map((v,i)=>({v:v??1,i})).sort((a,b)=>a.v-b.v),q:(number|null)[]=p.map(()=>null);let minimum=1;
  for(let j=ranked.length-1;j>=0;j--){minimum=Math.min(minimum,ranked[j].v*p.length/(j+1));q[ranked[j].i]=p[ranked[j].i]===null?null:minimum;}return q;
}
function prepare(rows:Observation[]) {
  const yearRows=new Map<number,number[]>(),observedYears=new Map<number,number>(),seen=new Set<string>();let valid=0,estimated=0;
  rows.forEach(row=>{const date=new Date(row.date),year=date.getUTCFullYear(),month=`${year}-${date.getUTCMonth()}`;
    if(seen.has(month))throw new Error('Duplicate monthly source observations');seen.add(month);
    const values=yearRows.get(year)||[];if(finite(row.value)&&!REJECT.has(row.quality_flag||'')){values.push(row.value);valid++;if(row.quality_flag==='model_estimated')estimated++;else observedYears.set(year,(observedYears.get(year)||0)+1);}yearRows.set(year,values);
  });
  const years=sorted([...yearRows.keys()]),first=years[0],last=years[years.length-1],annual=new Map<number,number>();
  yearRows.forEach((values,year)=>{if(values.length===12)annual.set(year,mean(values));});
  const excluded:number[]=[];for(let y=first;y<=last;y++)if((observedYears.get(y)||0)<12)excluded.push(y);
  return {annual,yearRows,quality:{input_rows:rows.length,valid_observations:valid-estimated,model_estimated_observations:estimated,raw_expected_observations:(last-first+1)*12,raw_missing_fraction:1-(valid-estimated)/((last-first+1)*12),raw_excluded_years:excluded,available_years:sorted([...annual.keys()]),raw_incomplete_retained_years:excluded.filter(y=>annual.has(y)),input_period:{start:rows.map(r=>r.date.slice(0,10)).sort()[0],end:rows.map(r=>r.date.slice(0,10)).sort().slice(-1)[0]}}};
}
function analyzeVariable(prepared:ReturnType<typeof prepare>,years:number[],unit:string,source:string,alpha:number):any {
  const x=years,y=years.map(year=>prepared.annual.get(year)!),n=years.length,expected=n?(years[n-1]-years[0]+1)*12:0;
  const q={...prepared.quality,analyzed_years:years,n_years:n,analysis_period:n?{start:`${years[0]}-01-01`,end:`${years[n-1]}-12-31`}:null,
    expected_observations:expected,analyzed_valid_observations:n*12,missing_fraction:expected?1-n*12/expected:null,
    excluded_years:n?prepared.quality.raw_excluded_years.filter(v=>v>=years[0]&&v<=years[n-1]):[],incomplete_retained_years:[],
    missing_analysis_years:n?Array.from({length:years[n-1]-years[0]+1},(_,i)=>years[0]+i).filter(v=>!years.includes(v)):[],alignment_excluded_years:prepared.quality.available_years.filter(v=>!years.includes(v))};
  const reasons:string[]=[];if(q.missing_fraction!==null&&q.missing_fraction>.2)reasons.push('excess_missing_observations');if(n<8)reasons.push('insufficient_years');
  const base={status:'insufficient_data',data_quality:q,linear_regression:null,theil_sen:null,mann_kendall:null,sensitivity:null,autocorrelation:null,reliable:false,reliability_reasons:reasons,unit,slope_unit:`${unit}/year`,adjusted_p_value:null};
  if(n<8)return {...base,source};
  const linear=ols(x,y,alpha),robust=sen(x,y,alpha),kendall=mk(y,alpha);
  const slopes=x.map((_,i)=>sen(x.filter((_,j)=>i!==j),y.filter((_,j)=>i!==j),alpha).slope);
  const sensitivity={leave_one_year_out_slope_range:[Math.min(...slopes),Math.max(...slopes)],direction_stable:slopes.every(s=>Math.sign(s)===Math.sign(robust.slope)),ols_sen_direction_agree:Math.sign(linear.slope)===Math.sign(robust.slope)};
  const residual=y.map((v,i)=>v-(linear.intercept+linear.slope*(x[i]-x[0]))),pairs=x.slice(1).map((v,i)=>v-x[i]===1?i:-1).filter(i=>i>=0),tol=tolerance(y);
  let autocorrelation:any={lag1:null,adjacent_pairs:pairs.length,threshold:pairs.length?1.96/Math.sqrt(pairs.length):null,flagged:true,status:'not_assessable'};
  if(Math.max(...residual.map(Math.abs))<=tol)autocorrelation={...autocorrelation,lag1:0,flagged:false,status:'zero_residual_variance'};
  else if(pairs.length>=5){const left=pairs.map(i=>residual[i]),right=pairs.map(i=>residual[i+1]),a=mean(left),b=mean(right),sx=sum(left.map(v=>(v-a)**2)),sy=sum(right.map(v=>(v-b)**2));
    if(Math.sqrt(sx/left.length)>tol&&Math.sqrt(sy/right.length)>tol){const rho=sum(left.map((v,i)=>(v-a)*(right[i]-b)))/Math.sqrt(sx*sy);autocorrelation={...autocorrelation,lag1:rho,flagged:Math.abs(rho)>autocorrelation.threshold,status:'screen_only'};}}
  if(!sensitivity.direction_stable)reasons.push('leave_one_year_out_direction_unstable');if(!sensitivity.ols_sen_direction_agree)reasons.push('trend_methods_disagree');if(autocorrelation.flagged)reasons.push('autocorrelation_flagged_or_not_assessable');
  return {...base,status:'ok',source,linear_regression:linear,theil_sen:robust,mann_kendall:kendall,sensitivity,autocorrelation,reliable:reasons.length===0,reliability_reasons:reasons};
}
function analyze(rows:Observation[],variables:string[],region:string,alpha:number):any {
  const prepared=Object.fromEntries(variables.map(v=>[v,prepare(rows.filter(r=>r.variable===v))]));
  const years=prepared[variables[0]].quality.available_years.filter(y=>variables.every(v=>prepared[v].annual.has(y)));
  const results:any={};variables.forEach(v=>{const source=rows.find(r=>r.variable===v)!;results[v]=analyzeVariable(prepared[v],years,source.unit,source.source,alpha);});
  const adjusted=adjustLivePValues(variables.map(v=>results[v].mann_kendall?.p_value??null));variables.forEach((v,i)=>results[v].adjusted_p_value=adjusted[i]);
  const green=results.ndvi,water=results.soil_water_0_100cm;let category='Uncertain Signal';const reasons:string[]=[];let detected:boolean|null=null;
  if(green&&water){if(green.status!=='ok'||water.status!=='ok')reasons.push('insufficient_data');else{
    const directional=green.theil_sen.slope>0&&water.theil_sen.slope<0,significant=[green,water].every(r=>r.adjusted_p_value!==null&&r.adjusted_p_value<alpha),intervals=green.theil_sen.confidence_interval[0]>0&&water.theil_sen.confidence_interval[1]<0,reliable=green.reliable&&water.reliable;
    if(!reliable)reasons.push('quality_or_robustness_checks_failed');
    if(directional&&significant&&intervals&&reliable)category='Supported Signal';else if(directional||!reliable){if(!significant)reasons.push('adjusted_significance_not_established');if(!intervals)reasons.push('directional_confidence_intervals_not_established');}else{category='No Detected Divergence';reasons.push('required_opposing_directions_absent');}detected=category==='Supported Signal';
  }}else reasons.push('required_vegetation_or_soil_moisture_missing');
  const trends:any={};variables.forEach(v=>{const r=results[v],o=r.linear_regression,s=r.theil_sen,m=r.mann_kendall;trends[v]={variable:v,unit:r.unit,n_observations:years.length,slope_per_year:o?.slope??null,slope_95ci:o?.confidence_interval??null,p_value:o?.p_value??null,theil_sen_slope_per_year:s?.slope??null,theil_sen_95ci:s?.confidence_interval??null,kendall_tau:m?.tau_a??null,kendall_p_value:m?.p_value??null};});
  return {schema_version:'0.3',region,observation_period:{start:years.length?`${years[0]}-01-01`:null,end:years.length?`${years[years.length-1]}-12-31`:null,years,aggregation:'annual_mean'},variables,analysis:results,trends,
    trend_slopes:Object.fromEntries(variables.map(v=>[v,trends[v].slope_per_year])),confidence_intervals:Object.fromEntries(variables.map(v=>[v,trends[v].slope_95ci])),p_values:Object.fromEntries(variables.map(v=>[v,trends[v].p_value])),adjusted_p_values:Object.fromEntries(variables.map(v=>[v,results[v].adjusted_p_value])),
    data_quality:{n_raw_rows:rows.length,sources:[...new Set(rows.map(r=>r.source))].sort(),synthetic_demo:rows.some(r=>r.source.toUpperCase().includes('SYNTHETIC')),qa_reviewed:false,by_variable:Object.fromEntries(variables.map(v=>[v,results[v].data_quality]))},
    divergence_detected:detected,divergence_status:category==='Supported Signal'?'supported_signal':category==='No Detected Divergence'?'no_detected_divergence':'uncertain_signal',divergence:{category,reasons,pairs:green&&water?[{vegetation:'ndvi',soil_moisture:'soil_water_0_100cm',category,reasons}]:[]},
    limitations:LIMITATIONS,settings:{frequency:'monthly',alpha,min_years:8,min_months_per_year:12,max_missing_fraction:.2},inference_scope:SCOPE};
}

export function computeLiveScreening(raw:Raw,options:LiveOptions):RegionalDetail {
  const alpha=options.alpha??.05;if(!(alpha>0&&alpha<.5)||!Number.isInteger(options.startYear)||!Number.isInteger(options.endYear)||options.startYear>options.endYear||options.endYear-options.startYear>499)throw new Error('Invalid live analysis window or alpha');
  const rows=raw.observations.filter(row=>{if(!Number.isFinite(Date.parse(row.date)))throw new Error('Invalid source date');const year=new Date(row.date).getUTCFullYear();return year>=options.startYear&&year<=options.endYear;});
  rows.forEach(row=>{if(row.region_id!==raw.region_id||row.value!==null&&!finite(row.value)||!row.source||!row.unit)throw new Error('Invalid source observation or metadata');});
  const selected=rows.filter(r=>VARIABLES.includes(r.variable));
  const ndviRows=selected.filter(r=>r.variable==='ndvi').sort((a,b)=>a.date.localeCompare(b.date));
  const estimates=options.estimateMissing===false?[]:ndviGapEstimates(ndviRows.map(r=>r.date),ndviRows);
  const estimatedByDate=new Map<string,number>();
  ndviRows.forEach((row,i)=>{const point=estimates[i];if(point?.estimated)estimatedByDate.set(row.date,point.value);});
  const analysisRows=selected.map(row=>row.variable==='ndvi' && estimatedByDate.has(row.date)
    ? {...row,value:estimatedByDate.get(row.date)!,quality_flag:'model_estimated'} : row);
  VARIABLES.forEach(v=>{const values=selected.filter(r=>r.variable===v);if(new Set(values.map(r=>r.unit)).size>1||new Set(values.map(r=>r.source)).size>1)throw new Error('Mixed units or sources');if(values.length&&values[0].unit!==(v==='ndvi'?'1':'kg m-2'))throw new Error('Unexpected physical units');});
  const usable=(v:string)=>selected.some(r=>r.variable===v&&finite(r.value)&&!REJECT.has(r.quality_flag||''));
  const supplied=(v:string)=>selected.some(r=>r.variable===v&&r.quality_flag!=='pending_export');
  const supported=usable('soil_water_0_100cm'),paired=supplied('ndvi')&&supplied('soil_water_0_100cm')?analyze(analysisRows,VARIABLES,raw.region_id,alpha):null;
  const eligible=paired&&VARIABLES.every(v=>paired.analysis[v].status==='ok');
  const diagnostic=!eligible&&supported?analyze(selected.filter(r=>r.variable==='soil_water_0_100cm'),['soil_water_0_100cm'],raw.region_id,alpha):null;
  const classification=!supported?'unsupported':!paired?'pending':!eligible?'insufficient':paired.divergence_status;
  const screening:any={classification,category:eligible?paired.divergence.category:null,reasons:eligible?paired.divergence.pairs.flatMap((p:any)=>p.reasons):[classification],qa_reviewed:false,provisional:true,probability:null,probability_status:'not_calibrated',family_scope:SCOPE,computed_in:'browser',multiple_testing:{method:'benjamini_hochberg',family_size:eligible?2:0,globally_adjusted:false},adjusted_p_values:eligible?paired.adjusted_p_values:{}};
  const displayed=diagnostic||paired,annualFits:any={};
  Object.entries(displayed?.analysis||{}).forEach(([v,value])=>{const r:any=value,o=r.linear_regression;annualFits[v]=o?{kind:'annual_ols_fitted',unit:r.unit,slope_unit:r.slope_unit,...o,points:r.data_quality.analyzed_years.map((year:number)=>({year,date:`${year}-01-01`,value:o.intercept+o.slope*(year-o.time_origin)}))}:null;});
  const result:any={schema_version:'regional-detail-1',region_id:raw.region_id,feature:raw.feature,dataset_version:raw.dataset_version,screening_status:'current_browser_computation',observations:rows,provenance:{...raw.provenance,live_analysis:{engine:'browser-typescript-v1',window:[options.startYear,options.endYear],scope:SCOPE,source_dataset_version:raw.dataset_version,ndvi_model:'seasonal_harmonic_bounded_gaps_v1',ndvi_estimated_months:estimatedByDate.size}},paired_analysis:paired,available_indicator_analysis:diagnostic,screening,annual_fits:annualFits,ndvi_retrieval:raw.ndvi_retrieval,scientific_display:{analysis_kind:diagnostic?'available_indicator':paired?'paired':'none',analysis_period:displayed?.observation_period??null,category:screening.category,classification,qa_reviewed:false,limitations:LIMITATIONS}};
  return result;
}
