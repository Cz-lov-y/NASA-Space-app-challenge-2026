import { useEffect, useState } from 'react';
import { RegionalDetail } from '../../types/contracts';
import { apiJson } from '../../services/api';

function safeUrl(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  try { const u = new URL(value); return ['https:', 'http:'].includes(u.protocol) ? u.href : undefined; }
  catch { return undefined; }
}
export function ResearchPanel({ detail }: { detail: RegionalDetail }) {
  const [status, setStatus] = useState('Waiting for regional context…');
  const [report, setReport] = useState<any>(null);
  useEffect(() => {
    let active = true;
    let pollTimer: ReturnType<typeof setTimeout>;
    setReport(null); setStatus('Preparing regional research…');
    const base = `/api/v1/regions/${encodeURIComponent(detail.region_id)}/research`;
    const poll = async (job: any) => {
      try {
        const data = await apiJson(`/api/v1/jobs/${job.request_id}?region_id=${encodeURIComponent(detail.region_id)}&context_key=${encodeURIComponent(job.context_key)}`);
        if (!active) return;
        if (data.state === 'complete') { setReport(data.report); setStatus('Research report available'); }
        else if (['queued','loading'].includes(data.state)) { setStatus('Researching policies and articles…'); pollTimer = setTimeout(() => poll(job), 1500); }
        else setStatus(`Research ${data.state}; no regional finding inferred.`);
      } catch { if (active) setStatus('Research service unavailable. No policy absence inferred.'); }
    };
    const start = async () => {
      try { const saved = await apiJson(base + '/cached');
        if (active) { setReport(saved); setStatus('Cached research available'); } return;
      } catch { /* A missing exact-context cache permits the configured live path. */ }
      if (!active) return;
      try { const job = await apiJson(base, {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
        if (active) await poll(job);
      } catch { if (active) setStatus('Live research unavailable or disabled; source review remains pending.'); }
    };
    const delay = setTimeout(start, 700);
    return () => { active = false; clearTimeout(delay); clearTimeout(pollTimer); };
  }, [detail.region_id, detail.dataset_version]);
  return <section className="rounded-xl border border-cyan-500/25 bg-space-950/70 p-4 space-y-3 font-mono text-xs">
    <h3 className="text-cyan-200 font-bold">Policy &amp; scientific context · AI narrative</h3>
    <p className="text-slate-400">{status}</p>
    {report && <>
      <p className="text-amber-200">{report.verification_status} · source applicability and current legal status require review</p>
      {report.qualitative ? <>
        <p>{report.qualitative.summary?.text}</p>
        {['policies','scientific_studies','conservation_options'].map(key => <div key={key} className="space-y-2">
          <h4 className="text-cyan-300">{key.replace(/_/g,' ')}</h4>
          {(report.qualitative[key] || []).map((claim: any, index: number) => <p key={index}>{claim.text} [{claim.source_ids?.join(', ')}]</p>)}
        </div>)}
      </> : <p>No validated AI narrative available.</p>}
      <div className="space-y-1">{(report.citations || []).map((source: any) => {
        const url = safeUrl(source.url);
        return url ? <a key={source.id} className="block text-cyan-300 underline" href={url} target="_blank" rel="noreferrer">[{source.id}] {source.title}</a> : null;
      })}</div>
      {(report.limitations || []).map((text: string, i: number) => <p key={i} className="text-slate-400">{text}</p>)}
    </>}
  </section>;
}
