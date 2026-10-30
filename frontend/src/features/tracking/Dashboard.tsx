import { useEffect, useState } from 'react';
import { request } from '../../api/client';
import { label } from './types';

type Ratio = { numerator: number; denominator: number; value: number | null };
type Metrics = {
  total: number;
  timezone: string;
  statuses: Record<string, number>;
  active_stages: Record<string, number>;
  response_rate: Ratio;
  assessment_rate: Ratio;
  interview_rate: Ratio;
  offer_rate: Ratio;
  interview_to_offer: Ratio;
  unanswered: number;
  mean_response_days: number | null;
  stage_durations: { stage: string; completed_intervals: number; mean_days: number }[];
  weekly_activity: { week: string; applications: number; events: number }[];
};
export function Dashboard() {
  const [from, setFrom] = useState(''),
    [to, setTo] = useState('');
  const [data, setData] = useState<Metrics>(),
    [error, setError] = useState('');
  const [loading, setLoading] = useState(true),
    [retry, setRetry] = useState(0);
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    const params = new URLSearchParams({ timezone });
    if (from) params.set('date_from', from);
    if (to) params.set('date_to', to);
    request<Metrics>(`/analytics/dashboard?${params}`, { signal: controller.signal })
      .then(setData)
      .catch((cause) => {
        if (!controller.signal.aborted)
          setError(cause instanceof Error ? cause.message : 'Unable to load dashboard.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [from, to, timezone, retry]);
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">YOUR SEARCH AT A GLANCE</p>
          <h1>Dashboard</h1>
          <p>See progress across your applications.</p>
        </div>
      </div>
      <section className="filters" aria-label="Dashboard date filters">
        <label>
          From
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </label>
        <label>
          To
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </label>
        <button
          className="text-button"
          onClick={() => {
            setFrom('');
            setTo('');
          }}
        >
          All dates
        </button>
      </section>
      <p className="help">
        Conversions include applications submitted in this date range and their full history.
        Activity includes events occurring in this range. Weeks start Monday · {timezone}.
      </p>
      {error ? (
        <p className="error" role="alert">
          {error} <button onClick={() => setRetry(retry + 1)}>Retry</button>
        </p>
      ) : loading ? (
        <p role="status">Loading dashboard…</p>
      ) : (
        data && (
          <>
            {!data.total && (
              <section className="empty-state">
                <h2>No applications in this cohort</h2>
                <p>Record an application or widen the date range to see conversion metrics.</p>
              </section>
            )}
            <div className="metric-grid">
              {[
                ['Applications', data.total],
                ...Object.entries(data.statuses).map(([key, value]) => [label(key), value]),
              ].map(([name, value]) => (
                <article className="metric-card" key={name}>
                  <p>{name}</p>
                  <strong>{value}</strong>
                </article>
              ))}
            </div>
            <section className="dashboard-panel">
              <h2>Historical conversions</h2>
              <div className="metric-grid">
                {(
                  [
                    ['Response', data.response_rate],
                    ['Assessment', data.assessment_rate],
                    ['Interview', data.interview_rate],
                    ['Offer', data.offer_rate],
                    ['Interview to offer', data.interview_to_offer],
                  ] as [string, Ratio][]
                ).map(([name, ratio]) => (
                  <article className="metric-card" key={name}>
                    <p>{name}</p>
                    <strong>
                      {ratio.value === null ? 'Unavailable' : `${(ratio.value * 100).toFixed(1)}%`}
                    </strong>
                    <p>
                      {ratio.numerator} / {ratio.denominator} applications
                    </p>
                  </article>
                ))}
              </div>
              <p className="help">
                Response means an assessment, interview, offer, or rejection. Notes and withdrawal
                are excluded. Interview to offer excludes direct offers without interviews.
              </p>
              <p>
                Mean time to first response:{' '}
                <strong>
                  {data.mean_response_days === null
                    ? 'Unavailable'
                    : `${data.mean_response_days.toFixed(1)} days`}
                </strong>{' '}
                among respondents · {data.unanswered} unanswered.
              </p>
              <p className="help">
                Application dates use UTC midnight; response times are approximate to the
                application day.
              </p>
            </section>
            <section className="dashboard-panel">
              <h2>Active applications by stage</h2>
              {Object.entries(data.active_stages).map(([stage, count]) => (
                <div className="stage-bar" key={stage}>
                  <span>{label(stage)}</span>
                  <meter
                    min={0}
                    max={Math.max(1, data.statuses.active)}
                    value={count}
                    aria-label={`${label(stage)}: ${count}`}
                  />
                  <strong>{count}</strong>
                </div>
              ))}
            </section>
            <section className="dashboard-panel">
              <h2>Weekly activity</h2>
              <p className="help">
                Applications use their submitted calendar date. Events use local occurrence dates,
                exclude initial applied events, and include notes and repeated transitions.
              </p>
              {data.weekly_activity.length ? (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Week starting</th>
                        <th>Applications</th>
                        <th>Events</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.weekly_activity.map((row) => (
                        <tr key={row.week}>
                          <td>{row.week}</td>
                          <td>{row.applications}</td>
                          <td>{row.events}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p>No activity in this range.</p>
              )}
            </section>
            <section className="dashboard-panel">
              <h2>Completed stage intervals</h2>
              <p className="help">
                Mean time until the next stage or outcome. Repeated stages form separate intervals;
                skipped stages are absent. Open intervals are excluded.
              </p>
              {data.stage_durations.length ? (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>Stage</th>
                        <th>Intervals</th>
                        <th>Mean days</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.stage_durations.map((row) => (
                        <tr key={row.stage}>
                          <td>{label(row.stage)}</td>
                          <td>{row.completed_intervals}</td>
                          <td>{row.mean_days.toFixed(1)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p>No completed intervals yet.</p>
              )}
            </section>
          </>
        )
      )}
    </>
  );
}
