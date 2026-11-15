import { useEffect, useState } from 'react';
import { BookOpen, ExternalLink, FileText, Leaf, Sparkles } from 'lucide-react';
import { RegionalDetail } from '../../types/contracts';
import { apiJson } from '../../services/api';

function safeUrl(value: unknown): string | undefined {
  if (typeof value !== 'string') return undefined;
  try { const u = new URL(value); return ['https:', 'http:'].includes(u.protocol) ? u.href : undefined; }
  catch { return undefined; }
}

const sections = [
  { key: 'policies', title: 'Policies & initiatives', icon: FileText },
  { key: 'scientific_studies', title: 'Research & evidence', icon: BookOpen },
  { key: 'conservation_options', title: 'Conservation approaches', icon: Leaf },
];

export function ResearchPanel({ detail }: { detail: RegionalDetail }) {
  const selection = `${detail.region_id}:${detail.dataset_version}`;
  const [requested, setRequested] = useState<string | null>(null);
  const [status, setStatus] = useState('');
  const [report, setReport] = useState<any>(null);
  useEffect(() => {
    let active = true;
    let pollTimer: ReturnType<typeof setTimeout>;
    setReport(null);
    if (requested !== selection) { setRequested(null); setStatus(''); return; }
    setStatus('Finding relevant information…');
    const base = `/api/v1/regions/${encodeURIComponent(detail.region_id)}/research`;
    const poll = async (job: any) => {
      try {
        const data = await apiJson(`/api/v1/jobs/${job.request_id}?region_id=${encodeURIComponent(detail.region_id)}&context_key=${encodeURIComponent(job.context_key)}`);
        if (!active) return;
        if (data.state === 'complete') { setReport(data.report); setStatus(''); }
        else if (['queued','loading'].includes(data.state)) { setStatus('Finding relevant information…'); pollTimer = setTimeout(() => poll(job), 1500); }
        else setStatus('Context is unavailable right now. Please try again later.');
      } catch { if (active) setStatus('Context is unavailable right now. Please try again later.'); }
    };
    const start = async () => {
      try { const saved = await apiJson(base + '/cached'); if (active) { setReport(saved); setStatus(''); } return; }
      catch { /* A matching saved report was unavailable. */ }
      if (!active) return;
      try { const job = await apiJson(base, {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}); if (active) await poll(job); }
      catch { if (active) setStatus('Context is unavailable right now. Please try again later.'); }
    };
    void start();
    return () => { active = false; clearTimeout(pollTimer); };
  }, [detail.region_id, detail.dataset_version, requested, selection]);

  const citations: any[] = Array.isArray(report?.citations) ? report.citations : [];
  const sourceLink = (id: string) => {
    const source = citations.find(item => item.id === id);
    const url = safeUrl(source?.url);
    return url ? <a key={id} href={url} target="_blank" rel="noreferrer" className="font-medium text-cyan-700 underline underline-offset-2">{id}</a> : <span key={id}>{id}</span>;
  };
  return <section className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-700">
    <div className="flex items-start gap-3">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-cyan-50 text-cyan-700"><Sparkles size={18} /></span>
      <div>
        <h3 className="text-base font-semibold text-slate-900">Policy &amp; scientific context</h3>
        <p className="mt-1 text-xs text-slate-500">Explore information related to this location.</p>
      </div>
    </div>
    {requested !== selection && <button type="button" onClick={() => setRequested(selection)}
      className="mt-4 rounded-lg border border-cyan-600 bg-cyan-700 px-4 py-2 text-xs font-semibold text-white hover:bg-cyan-800">
      Get policy &amp; scientific context
    </button>}
    {status && <p role="status" className="mt-4 text-xs text-slate-500">{status}</p>}
    {report && <div className="mt-5 space-y-5">
      <p className="text-xs text-slate-500">AI-generated context{report.retrieved_at ? ` · Retrieved ${new Date(report.retrieved_at).toLocaleDateString()}` : ''}{report.cache_stale ? ' · Saved copy may be outdated' : ''}</p>
      {report.qualitative ? <>
        <div>
          <h4 className="text-sm font-semibold text-slate-900">Overview</h4>
          <p className="mt-2 leading-relaxed">{report.qualitative.summary?.text}{' '}{(report.qualitative.summary?.source_ids || []).map(sourceLink)}</p>
        </div>
        {sections.map(({ key, title, icon: Icon }) => {
          const claims = Array.isArray(report.qualitative[key]) ? report.qualitative[key] : [];
          if (!claims.length) return null;
          return <div key={key}>
            <h4 className="flex items-center gap-2 text-sm font-semibold text-slate-900"><Icon size={15} className="text-cyan-700" />{title}</h4>
            <ul className="mt-2 list-disc space-y-2 pl-5 leading-relaxed">
              {claims.map((claim: any, index: number) => <li key={index}>{claim.text}{' '}{(claim.source_ids || []).map(sourceLink)}</li>)}
            </ul>
          </div>;
        })}
      </> : <p className="text-slate-500">No summary is available for this location.</p>}
      {citations.length > 0 && <div className="border-t border-slate-200 pt-4">
        <h4 className="text-sm font-semibold text-slate-900">Sources</h4>
        <ul className="mt-2 space-y-2">
          {citations.map(source => { const url = safeUrl(source.url); return url ? <li key={source.id}>
            <a href={url} target="_blank" rel="noreferrer" className="inline-flex items-start gap-1.5 text-xs leading-relaxed text-cyan-700 underline underline-offset-2"><span>{source.title}</span><ExternalLink size={12} className="mt-0.5 shrink-0" /></a>
          </li> : null; })}
        </ul>
      </div>}
    </div>}
  </section>;
}
