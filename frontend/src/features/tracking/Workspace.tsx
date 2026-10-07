import { useEffect, useState } from 'react';
import { ApiError, request } from '../../api/client';
import { type User } from '../auth/AuthForm';
import { ApplicationForm, CompanyForm, JobForm, Modal } from './Forms';
import { ApplicationHistory, DocumentsView } from './History';
import {
  type Application,
  type Company,
  type Description,
  type Job,
  type Page,
  label,
} from './types';

type Tab = 'applications' | 'jobs' | 'companies' | 'documents';
type Editor =
  | { kind: 'company'; company?: Company }
  | { kind: 'job'; job?: Job; description?: string }
  | { kind: 'application'; application?: Application; jobId?: string }
  | { kind: 'history'; identifier: string }
  | { kind: 'description'; job: Job; versions: Description[] };

async function catalog<T>(path: string, signal: AbortSignal): Promise<T[]> {
  let page = 1;
  const items: T[] = [];
  while (true) {
    const result = await request<Page<T>>(`${path}?page=${page}&page_size=100`, { signal });
    items.push(...result.items);
    if (items.length >= result.total || result.items.length === 0) return items;
    page++;
  }
}

function DescriptionView({ versions }: { versions: Description[] }) {
  const [selected, setSelected] = useState(versions[0]?.id ?? '');
  const version = versions.find((item) => item.id === selected);
  return versions.length ? (
    <>
      <label className="field">
        Description version
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          {versions.map((item) => (
            <option key={item.id} value={item.id}>
              Version {item.version} · {new Date(item.created_at).toLocaleDateString()}
            </option>
          ))}
        </select>
      </label>
      <pre className="description-text">{version?.raw_text}</pre>
    </>
  ) : (
    <p>No description has been stored. Edit this job to add one.</p>
  );
}

export function Workspace({
  user,
  onLogout,
  signingOut,
  authError,
}: {
  user: User;
  onLogout: () => void;
  signingOut: boolean;
  authError: string;
}) {
  const [tab, setTab] = useState<Tab>('applications');
  const [q, setQ] = useState(''),
    [company, setCompany] = useState(''),
    [status, setStatus] = useState('');
  const [location, setLocation] = useState(''),
    [from, setFrom] = useState(''),
    [to, setTo] = useState('');
  const [sort, setSort] = useState('newest'),
    [archived, setArchived] = useState(false),
    [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0),
    [loading, setLoading] = useState(true),
    [error, setError] = useState('');
  const [result, setResult] = useState<{ tab: Tab; items: unknown[]; total: number }>();
  const [companies, setCompanies] = useState<Company[]>([]),
    [jobs, setJobs] = useState<Job[]>([]);
  const [catalogReady, setCatalogReady] = useState(false);
  const [editor, setEditor] = useState<Editor>();
  const [actionBusy, setActionBusy] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    setCatalogReady(false);
    Promise.all([
      catalog<Company>('/companies', controller.signal),
      catalog<Job>('/jobs', controller.signal),
    ])
      .then(([companies, jobs]) => {
        setCompanies(companies);
        setJobs(jobs);
        setCatalogReady(true);
      })
      .catch((cause) => {
        if (!controller.signal.aborted)
          setError(cause instanceof Error ? cause.message : 'Unable to load choices.');
      });
    return () => controller.abort();
  }, [refresh]);

  useEffect(() => {
    if (tab === 'documents') return;
    const controller = new AbortController();
    setLoading(true);
    setError('');
    const timer = setTimeout(() => {
      const params = new URLSearchParams({ page: String(page), page_size: '12' });
      if (q) params.set('q', q);
      if (company && tab !== 'companies') params.set('company_id', company);
      if (tab === 'jobs') params.set('archived', String(archived));
      if (tab === 'applications') {
        if (status) params.set('status', status);
        if (location) params.set('location', location);
        if (from) params.set('date_from', from);
        if (to) params.set('date_to', to);
        params.set('sort', sort);
      }
      request<Page<unknown>>(`/${tab}?${params}`, { signal: controller.signal })
        .then((data) => {
          if (page > 1 && !data.items.length && data.total > 0) {
            setPage(Math.max(1, Math.ceil(data.total / 12)));
            return;
          }
          setResult({ tab, items: data.items, total: data.total });
        })
        .catch((cause) => {
          if (!controller.signal.aborted)
            setError(cause instanceof ApiError ? cause.message : 'Unable to load your records.');
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [tab, q, company, status, location, from, to, sort, archived, page, refresh]);

  function saved() {
    setEditor(undefined);
    setRefresh((value) => value + 1);
  }
  function switchTab(next: Tab) {
    setTab(next);
    setPage(1);
    setQ('');
    setCompany('');
  }
  function filter(action: () => void) {
    action();
    setPage(1);
  }
  async function editJob(job: Job, view = false) {
    setActionBusy(true);
    setError('');
    try {
      const versions = await request<Description[]>(`/jobs/${job.id}/descriptions`);
      setEditor(
        view
          ? { kind: 'description', job, versions }
          : { kind: 'job', job, description: versions[0]?.raw_text },
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to open job.');
    } finally {
      setActionBusy(false);
    }
  }
  async function archive(job: Job) {
    setActionBusy(true);
    setError('');
    try {
      await request(`/jobs/${job.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ archived: !job.archived_at }),
      });
      setRefresh((value) => value + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to update job.');
    } finally {
      setActionBusy(false);
    }
  }
  const current = result?.tab === tab ? result : undefined;
  const filtered = !!(
    q ||
    company ||
    (tab === 'applications' && (status || location || from || to))
  );
  const name = tab[0].toUpperCase() + tab.slice(1);
  const primaryAction =
    tab === 'companies' || !companies.length
      ? '+ Add company'
      : tab === 'jobs' || !jobs.length
        ? '+ Add job'
        : '+ Record application';

  return (
    <div className="tracker-layout">
      <aside className="sidebar">
        <p className="eyebrow">YOUR WORKSPACE</p>
        <nav aria-label="Workspace">
          {(['applications', 'jobs', 'companies', 'documents'] as Tab[]).map((item) => (
            <button
              key={item}
              className={tab === item ? 'nav-item selected' : 'nav-item'}
              aria-current={tab === item ? 'page' : undefined}
              onClick={() => switchTab(item)}
            >
              {item[0].toUpperCase() + item.slice(1)}
            </button>
          ))}
        </nav>
        <div className="account">
          <p>{user.email}</p>
          <button className="text-button" onClick={onLogout} disabled={signingOut}>
            {signingOut ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      </aside>
      <div className="tracker-content">
        {tab === 'documents' ? (
          <DocumentsView />
        ) : (
          <>
            <div className="page-heading">
              <div>
                <p className="eyebrow">KEEP YOUR NEXT MOVE IN SIGHT</p>
                <h1>{name}</h1>
                <p>
                  {tab === 'applications'
                    ? 'Every application, in one place.'
                    : tab === 'jobs'
                      ? 'Save opportunities before you take the next step.'
                      : 'The organizations behind your opportunities.'}
                </p>
              </div>
              <button
                disabled={!catalogReady}
                onClick={() =>
                  setEditor(
                    tab === 'companies'
                      ? { kind: 'company' }
                      : tab === 'jobs'
                        ? companies.length
                          ? { kind: 'job' }
                          : { kind: 'company' }
                        : jobs.length
                          ? { kind: 'application' }
                          : companies.length
                            ? { kind: 'job' }
                            : { kind: 'company' },
                  )
                }
              >
                {primaryAction}
              </button>
            </div>
            {(error || authError) && (
              <p role="alert" className="error">
                {error || authError}{' '}
                <button className="text-button" onClick={() => setRefresh((value) => value + 1)}>
                  Retry
                </button>
              </p>
            )}
            <section className="filters" aria-label="Search and filters">
              <label>
                Search
                <input
                  type="search"
                  placeholder={tab === 'companies' ? 'Company name' : 'Role or company'}
                  maxLength={200}
                  value={q}
                  onChange={(e) => filter(() => setQ(e.target.value))}
                />
              </label>
              {tab !== 'companies' && (
                <label>
                  Company
                  <select
                    value={company}
                    onChange={(e) => filter(() => setCompany(e.target.value))}
                  >
                    <option value="">All companies</option>
                    {companies.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {tab === 'jobs' && (
                <label>
                  Show
                  <select
                    value={String(archived)}
                    onChange={(e) => filter(() => setArchived(e.target.value === 'true'))}
                  >
                    <option value="false">Saved jobs</option>
                    <option value="true">Archived jobs</option>
                  </select>
                </label>
              )}
              {tab === 'applications' && (
                <>
                  <label>
                    Status
                    <select
                      value={status}
                      onChange={(e) => filter(() => setStatus(e.target.value))}
                    >
                      <option value="">All statuses</option>
                      {['active', 'offer', 'rejected', 'withdrawn'].map((item) => (
                        <option key={item} value={item}>
                          {label(item)}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Location
                    <input
                      maxLength={200}
                      value={location}
                      placeholder="Any location"
                      onChange={(e) => filter(() => setLocation(e.target.value))}
                    />
                  </label>
                  <label>
                    Applied from
                    <input
                      type="date"
                      value={from}
                      onChange={(e) => filter(() => setFrom(e.target.value))}
                    />
                  </label>
                  <label>
                    Applied to
                    <input
                      type="date"
                      value={to}
                      onChange={(e) => filter(() => setTo(e.target.value))}
                    />
                  </label>
                  <label>
                    Sort
                    <select value={sort} onChange={(e) => filter(() => setSort(e.target.value))}>
                      <option value="newest">Newest first</option>
                      <option value="oldest">Oldest first</option>
                      <option value="company">Company name</option>
                      <option value="title">Job title</option>
                    </select>
                  </label>
                </>
              )}
              {filtered && (
                <button
                  className="text-button"
                  onClick={() =>
                    filter(() => {
                      setQ('');
                      setCompany('');
                      setStatus('');
                      setLocation('');
                      setFrom('');
                      setTo('');
                    })
                  }
                >
                  Clear filters
                </button>
              )}
            </section>
            {loading ? (
              <p role="status">Loading {tab}…</p>
            ) : (
              !error &&
              current && (
                <>
                  <p className="result-count">
                    {current.total} {filtered ? 'matching ' : ''}
                    {current.total === 1
                      ? {
                          applications: 'application',
                          jobs: 'job',
                          companies: 'company',
                          documents: 'document',
                        }[tab]
                      : tab}
                  </p>
                  {!current.items.length ? (
                    <section className="empty-state">
                      <h2>{filtered ? 'No matches found' : `Your ${tab} start here`}</h2>
                      <p>
                        {filtered
                          ? 'Try a different search or clear the filters.'
                          : tab === 'applications'
                            ? 'Save a company and job, then record your first application.'
                            : tab === 'jobs'
                              ? archived
                                ? 'Archived jobs will appear here. You can restore them at any time.'
                                : 'Add a job and preserve the details of the opportunity.'
                              : 'Add a company to get started.'}
                      </p>
                    </section>
                  ) : (
                    <div className="record-list">
                      {current.items.map((raw) => {
                        if (tab === 'companies') {
                          const item = raw as Company;
                          return (
                            <article className="record" key={item.id}>
                              <div>
                                <h2>{item.name}</h2>
                                <p>{item.location || 'Location not specified'}</p>
                                {item.website && (
                                  <a href={item.website} target="_blank" rel="noopener noreferrer">
                                    Company website ↗
                                  </a>
                                )}
                                {item.notes && <p className="notes">{item.notes}</p>}
                              </div>
                              <button
                                className="secondary"
                                onClick={() => setEditor({ kind: 'company', company: item })}
                              >
                                Edit company
                              </button>
                            </article>
                          );
                        }
                        if (tab === 'jobs') {
                          const item = raw as Job;
                          return (
                            <article className="record" key={item.id}>
                              <div>
                                <p className="company-name">{item.company.name}</p>
                                <h2>{item.title}</h2>
                                <p>
                                  {item.location || 'Location not specified'} ·{' '}
                                  {label(item.work_arrangement)} · {label(item.employment_type)}
                                </p>
                                {(item.salary_min || item.salary_max) && (
                                  <p>
                                    {item.salary_currency} {item.salary_min ?? '—'}–
                                    {item.salary_max ?? '—'} / {item.salary_period}
                                  </p>
                                )}
                                {item.deadline_on && <p>Deadline: {item.deadline_on}</p>}
                                {item.url && (
                                  <a href={item.url} target="_blank" rel="noopener noreferrer">
                                    View posting ↗
                                  </a>
                                )}
                              </div>
                              <div className="record-actions">
                                <button
                                  className="secondary"
                                  disabled={actionBusy}
                                  onClick={() => void editJob(item)}
                                >
                                  Edit job
                                </button>
                                <button
                                  className="text-button"
                                  disabled={actionBusy}
                                  onClick={() => void editJob(item, true)}
                                >
                                  Descriptions
                                </button>
                                {!item.archived_at && (
                                  <button
                                    disabled={!catalogReady}
                                    onClick={() =>
                                      setEditor({ kind: 'application', jobId: item.id })
                                    }
                                  >
                                    Record application
                                  </button>
                                )}
                                <button
                                  className="text-button"
                                  disabled={actionBusy}
                                  onClick={() => void archive(item)}
                                >
                                  {item.archived_at ? 'Restore job' : 'Archive job'}
                                </button>
                              </div>
                            </article>
                          );
                        }
                        const item = raw as Application;
                        return (
                          <article className="record" key={item.id}>
                            <div>
                              <p className="company-name">{item.job.company.name}</p>
                              <h2>{item.job.title}</h2>
                              <p>
                                {item.job.location || 'Location not specified'} · Applied{' '}
                                {item.applied_on}
                                {item.attempt_number > 1 ? ` · Attempt ${item.attempt_number}` : ''}
                              </p>
                              <span className="badge">
                                {label(item.status)} · {label(item.current_stage)}
                              </span>
                              {item.job.archived_at && (
                                <p className="help">Job archived · application retained</p>
                              )}
                              {item.notes && <p className="notes">{item.notes}</p>}
                            </div>
                            <div className="record-actions">
                              <button
                                onClick={() => setEditor({ kind: 'history', identifier: item.id })}
                              >
                                Timeline &amp; documents
                              </button>
                              <button
                                className="secondary"
                                onClick={() =>
                                  setEditor({ kind: 'application', application: item })
                                }
                              >
                                Edit notes
                              </button>
                              <button
                                className="text-button"
                                disabled={actionBusy}
                                onClick={() => void editJob(item.job, true)}
                              >
                                Job description
                              </button>
                            </div>
                          </article>
                        );
                      })}
                    </div>
                  )}
                  {current.total > 12 && (
                    <nav className="pagination" aria-label="Results pages">
                      <button disabled={page === 1} onClick={() => setPage(page - 1)}>
                        Previous
                      </button>
                      <span>
                        Page {page} of {Math.ceil(current.total / 12)}
                      </span>
                      <button
                        disabled={page >= Math.ceil(current.total / 12)}
                        onClick={() => setPage(page + 1)}
                      >
                        Next
                      </button>
                    </nav>
                  )}
                </>
              )
            )}
          </>
        )}
      </div>
      {editor && (
        <Modal
          title={
            editor.kind === 'company'
              ? editor.company
                ? 'Edit company'
                : 'Add company'
              : editor.kind === 'job'
                ? editor.job
                  ? 'Edit job'
                  : 'Add job'
                : editor.kind === 'application'
                  ? editor.application
                    ? 'Application notes'
                    : 'Record application'
                  : editor.kind === 'history'
                    ? 'Application history'
                    : `${editor.job.title} · Descriptions`
          }
          onClose={() => setEditor(undefined)}
        >
          {editor.kind === 'company' ? (
            <CompanyForm company={editor.company} onSaved={saved} />
          ) : editor.kind === 'job' ? (
            <JobForm
              job={editor.job}
              description={editor.description}
              companies={companies}
              onSaved={saved}
            />
          ) : editor.kind === 'application' ? (
            <ApplicationForm
              application={editor.application}
              jobId={editor.jobId}
              jobs={jobs}
              onSaved={saved}
            />
          ) : editor.kind === 'history' ? (
            <ApplicationHistory
              identifier={editor.identifier}
              onChanged={() => setRefresh((value) => value + 1)}
            />
          ) : (
            <DescriptionView versions={editor.versions} />
          )}
        </Modal>
      )}
    </div>
  );
}
