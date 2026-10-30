import { useEffect, useState } from 'react';
import { MatchView } from './Matching';
import { request } from '../../api/client';
import { type Page, label } from './types';
type Evidence = { value: string; quote: string; start: number; end: number };
type Analysis = {
  id: string;
  provider: string;
  provider_version: string;
  schema_version: number;
  created_at: string;
  structured_data: Record<string, Evidence | Evidence[] | null>;
};
export function DescriptionAnalysis({ identifier }: { identifier: string }) {
  const [analyses, setAnalyses] = useState<Analysis[]>([]),
    [selected, setSelected] = useState('');
  const [error, setError] = useState(''),
    [busy, setBusy] = useState(true);
  useEffect(() => {
    const controller = new AbortController();
    setBusy(true);
    setError('');
    setAnalyses([]);
    setSelected('');
    (async () => {
      let page = 1;
      const items: Analysis[] = [];
      while (true) {
        const result = await request<Page<Analysis>>(
          `/descriptions/${identifier}/analyses?page=${page}&page_size=100`,
          { signal: controller.signal },
        );
        items.push(...result.items);
        if (items.length >= result.total || !result.items.length) break;
        page++;
      }
      if (!controller.signal.aborted) {
        setAnalyses(items);
        setSelected(items[0]?.id ?? '');
      }
    })()
      .catch((cause) => {
        if (!controller.signal.aborted)
          setError(cause instanceof Error ? cause.message : 'Unable to load analyses.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, [identifier]);
  async function analyze() {
    setBusy(true);
    setError('');
    try {
      const result = await request<Analysis>(`/descriptions/${identifier}/analyses`, {
        method: 'POST',
      });
      setAnalyses((previous) => [result, ...previous.filter((a) => a.id !== result.id)]);
      setSelected(result.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to analyze description.');
    } finally {
      setBusy(false);
    }
  }
  const current = analyses.find((a) => a.id === selected);
  return (
    <section className="analysis-panel">
      <h3>Structured analysis</h3>
      <p className="help">
        Rule-based extraction recognizes a limited skill vocabulary and explicit fields. Missing
        items mean unknown, not absent. Review source evidence before using these results.
      </p>
      <button onClick={() => void analyze()} disabled={busy}>
        {busy ? 'Loading…' : 'Analyze this description'}
      </button>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {!busy && !analyses.length && <p>No analysis yet for this description version.</p>}
      {!!analyses.length && (
        <label className="field">
          Analysis version
          <select value={selected} onChange={(e) => setSelected(e.target.value)}>
            {analyses.map((a) => (
              <option key={a.id} value={a.id}>
                {a.provider} {a.provider_version} · {new Date(a.created_at).toLocaleString()}
              </option>
            ))}
          </select>
        </label>
      )}
      {current && (
        <>
          <MatchView key={current.id} identifier={current.id} />
          <p className="help">
            Provider: {current.provider} {current.provider_version} · Schema{' '}
            {current.schema_version}
          </p>
          {Object.entries(current.structured_data).map(([field, value]) => {
            const items = Array.isArray(value) ? value : value ? [value] : [];
            return (
              <div key={field}>
                <h4>{label(field)}</h4>
                {items.length ? (
                  <ul>
                    {items.map((item, index) => (
                      <li key={index}>
                        <strong>{item.value}</strong>
                        <blockquote>{item.quote}</blockquote>
                        <small>
                          Source characters {item.start}–{item.end} (end exclusive)
                        </small>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="help">Not identified</p>
                )}
              </div>
            );
          })}
        </>
      )}
    </section>
  );
}
