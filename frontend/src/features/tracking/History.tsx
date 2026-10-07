import { useEffect, useState, type FormEvent } from 'react';
import { request } from '../../api/client';
import { Modal } from './Forms';
import {
  type Application,
  type ApplicationEvent,
  type DocumentVersion,
  type Page,
  label,
} from './types';

export async function allPages<T>(path: string, signal: AbortSignal): Promise<T[]> {
  const items: T[] = [];
  let page = 1;
  while (true) {
    const data = await request<Page<T>>(
      `${path}${path.includes('?') ? '&' : '?'}page=${page}&page_size=100`,
      { signal },
    );
    items.push(...data.items);
    if (items.length >= data.total || !data.items.length) return items;
    page++;
  }
}

export function DocumentForm({ onSaved }: { onSaved: () => void }) {
  const [kind, setKind] = useState('resume'),
    [name, setName] = useState('');
  const [version, setVersion] = useState(''),
    [reference, setReference] = useState('');
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await request('/documents', {
        method: 'POST',
        body: JSON.stringify({
          kind,
          label: name,
          version_label: version || null,
          storage_reference: reference || null,
        }),
      });
      onSaved();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to save document.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <form onSubmit={submit}>
      <fieldset disabled={busy}>
        <label htmlFor="document-kind">Document type</label>
        <select id="document-kind" value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="resume">Resume</option>
          <option value="cover_letter">Cover letter</option>
        </select>
        <label htmlFor="document-label">Document label</label>
        <input
          id="document-label"
          required
          maxLength={250}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Backend-focused resume"
        />
        <label htmlFor="document-version">Version label</label>
        <input
          id="document-version"
          maxLength={100}
          value={version}
          onChange={(e) => setVersion(e.target.value)}
          placeholder="October 2026"
        />
        <label htmlFor="document-reference">File or storage reference</label>
        <input
          id="document-reference"
          maxLength={2000}
          value={reference}
          onChange={(e) => setReference(e.target.value)}
          placeholder="resumes/backend-october.pdf"
        />
        <p className="help">
          This saves a reference, not an uploaded file. Create a new record for each document
          version; existing versions remain unchanged.
        </p>
      </fieldset>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <button disabled={busy}>{busy ? 'Saving…' : 'Save document reference'}</button>
    </form>
  );
}

const localTimestamp = () => {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 19);
};

export function ApplicationHistory({
  identifier,
  onChanged,
}: {
  identifier: string;
  onChanged: () => void;
}) {
  const [application, setApplication] = useState<Application>();
  const [events, setEvents] = useState<ApplicationEvent[]>([]),
    [documents, setDocuments] = useState<DocumentVersion[]>([]);
  const [loading, setLoading] = useState(true),
    [refresh, setRefresh] = useState(0),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  const [type, setType] = useState('recruiter_screen'),
    [occurred, setOccurred] = useState(localTimestamp),
    [notes, setNotes] = useState('');
  const [resume, setResume] = useState(''),
    [cover, setCover] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    Promise.all([
      request<Application>(`/applications/${identifier}`, { signal: controller.signal }),
      allPages<ApplicationEvent>(`/applications/${identifier}/events`, controller.signal),
      allPages<DocumentVersion>('/documents', controller.signal),
      allPages<DocumentVersion>('/documents?archived=true', controller.signal),
    ])
      .then(([application, events, active, archived]) => {
        setApplication(application);
        setEvents(events);
        setDocuments([...active, ...archived]);
        setResume(application.resume_id ?? '');
        setCover(application.cover_letter_id ?? '');
      })
      .catch((cause) => {
        if (!controller.signal.aborted)
          setError(cause instanceof Error ? cause.message : 'Unable to load application.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [identifier, refresh]);
  async function save(event: FormEvent, mode: 'event' | 'documents') {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await request(`/applications/${identifier}${mode === 'event' ? '/events' : ''}`, {
        method: mode === 'event' ? 'POST' : 'PATCH',
        body: JSON.stringify(
          mode === 'event'
            ? {
                event_type: application?.status === 'active' ? type : 'note',
                occurred_at: new Date(occurred).toISOString(),
                notes: notes || null,
              }
            : { resume_id: resume || null, cover_letter_id: cover || null },
        ),
      });
      setNotes('');
      setOccurred(localTimestamp());
      setRefresh((value) => value + 1);
      onChanged();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to save.');
    } finally {
      setBusy(false);
    }
  }
  const options = (kind: string, selected: string) =>
    documents
      .filter((item) => item.kind === kind && (!item.archived_at || item.id === selected))
      .map((item) => (
        <option key={item.id} value={item.id}>
          {item.label}
          {item.version_label ? ` · ${item.version_label}` : ''}
          {item.archived_at ? ' (archived)' : ''}
        </option>
      ));
  return (
    <div>
      {error && (
        <p className="error" role="alert">
          {error}{' '}
          <button className="text-button" onClick={() => setRefresh((value) => value + 1)}>
            Reload
          </button>
        </p>
      )}
      {loading ? (
        <p role="status">Loading application history…</p>
      ) : (
        application && (
          <>
            <p className="company-name">{application.job.company.name}</p>
            <h3>{application.job.title}</h3>
            <span className="badge">
              {label(application.status)} · {label(application.current_stage)}
            </span>
            <h3>Documents used</h3>
            <form onSubmit={(event) => void save(event, 'documents')}>
              <fieldset disabled={busy}>
                <label htmlFor="resume-reference">Resume version</label>
                <select
                  id="resume-reference"
                  value={resume}
                  onChange={(e) => setResume(e.target.value)}
                >
                  <option value="">No resume reference</option>
                  {options('resume', resume)}
                </select>
                <label htmlFor="cover-reference">Cover letter version</label>
                <select
                  id="cover-reference"
                  value={cover}
                  onChange={(e) => setCover(e.target.value)}
                >
                  <option value="">No cover letter reference</option>
                  {options('cover_letter', cover)}
                </select>
                {!documents.length && (
                  <p className="help">
                    Add resume or cover-letter references from the Documents view first.
                  </p>
                )}
              </fieldset>
              <button className="secondary" disabled={busy}>
                Save document references
              </button>
            </form>
            <h3>Application timeline</h3>
            <ol className="timeline">
              {events.map((item) => (
                <li key={item.id}>
                  <strong>{label(item.event_type)}</strong>
                  <time dateTime={item.occurred_at}>
                    {item.event_type === 'applied'
                      ? `Application date: ${application.applied_on}`
                      : new Date(item.occurred_at).toLocaleString()}
                  </time>
                  {item.notes && <p className="notes">{item.notes}</p>}
                  <small>Recorded {new Date(item.recorded_at).toLocaleString()}</small>
                </li>
              ))}
            </ol>
            <h3>{application.status === 'active' ? 'Record a stage or outcome' : 'Add a note'}</h3>
            {application.status !== 'active' && (
              <p className="help">
                This application is closed. Its history is preserved, and you can still add notes.
              </p>
            )}
            <form onSubmit={(event) => void save(event, 'event')}>
              <fieldset disabled={busy}>
                {application.status === 'active' && (
                  <>
                    <label htmlFor="event-type">Event type</label>
                    <select id="event-type" value={type} onChange={(e) => setType(e.target.value)}>
                      {[
                        'assessment',
                        'recruiter_screen',
                        'technical_interview',
                        'behavioral_interview',
                        'final_interview',
                        'offer',
                        'rejected',
                        'withdrawn',
                        'note',
                      ].map((value) => (
                        <option key={value} value={value}>
                          {label(value)}
                        </option>
                      ))}
                    </select>
                  </>
                )}
                <label htmlFor="event-time">Occurred at (your local time)</label>
                <input
                  id="event-time"
                  type="datetime-local"
                  step="1"
                  required
                  value={occurred}
                  onChange={(e) => setOccurred(e.target.value)}
                />
                <label htmlFor="event-notes">Event notes</label>
                <textarea
                  id="event-notes"
                  maxLength={20000}
                  rows={3}
                  required={application.status !== 'active' || type === 'note'}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />
                <p className="help">
                  Record completed events. Stage and outcome times must be later than the latest
                  transition; future appointments are not supported here.
                </p>
              </fieldset>
              <button disabled={busy}>{busy ? 'Saving…' : 'Record event'}</button>
            </form>
          </>
        )
      )}
    </div>
  );
}

export function DocumentsView() {
  const [archived, setArchived] = useState(false),
    [page, setPage] = useState(1),
    [refresh, setRefresh] = useState(0);
  const [data, setData] = useState<Page<DocumentVersion>>(),
    [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [creating, setCreating] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    request<Page<DocumentVersion>>(`/documents?archived=${archived}&page=${page}&page_size=12`, {
      signal: controller.signal,
    })
      .then((result) => {
        if (page > 1 && !result.items.length) setPage(page - 1);
        else setData(result);
      })
      .catch((cause) => {
        if (!controller.signal.aborted)
          setError(cause instanceof Error ? cause.message : 'Unable to load documents.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [archived, page, refresh]);
  async function toggle(item: DocumentVersion) {
    setBusy(true);
    setError('');
    try {
      await request(`/documents/${item.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ archived: !item.archived_at }),
      });
      setRefresh((value) => value + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to update document.');
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">KEEP YOUR MATERIALS ORGANIZED</p>
          <h1>Documents</h1>
          <p>Track the resume and cover-letter versions you use.</p>
        </div>
        <button onClick={() => setCreating(true)}>+ Add document reference</button>
      </div>
      <section className="filters">
        <label htmlFor="document-visibility">
          Show
          <select
            id="document-visibility"
            value={String(archived)}
            onChange={(e) => {
              setArchived(e.target.value === 'true');
              setPage(1);
            }}
          >
            <option value="false">Active document references</option>
            <option value="true">Archived document references</option>
          </select>
        </label>
      </section>
      {error && (
        <p role="alert" className="error">
          {error}{' '}
          <button className="text-button" onClick={() => setRefresh((value) => value + 1)}>
            Retry
          </button>
        </p>
      )}
      {loading ? (
        <p role="status">Loading documents…</p>
      ) : (
        data && (
          <>
            <p className="result-count">
              {data.total} document {data.total === 1 ? 'reference' : 'references'}
            </p>
            <div className="record-list">
              {data.items.map((item) => (
                <article className="record" key={item.id}>
                  <div>
                    <p className="company-name">{label(item.kind)}</p>
                    <h2>{item.label}</h2>
                    <p>{item.version_label || 'Version label not specified'}</p>
                    {item.storage_reference && (
                      <p className="notes">Reference: {item.storage_reference}</p>
                    )}
                  </div>
                  <button className="secondary" disabled={busy} onClick={() => void toggle(item)}>
                    {item.archived_at ? 'Restore reference' : 'Archive reference'}
                  </button>
                </article>
              ))}
            </div>
            {!data.items.length && (
              <section className="empty-state">
                <h2>{archived ? 'No archived references' : 'Keep track of what you sent'}</h2>
                <p>
                  Add a reference for each resume or cover-letter version. Files are not uploaded.
                </p>
              </section>
            )}
            {data.total > 12 && (
              <nav className="pagination" aria-label="Document pages">
                <button disabled={page === 1} onClick={() => setPage(page - 1)}>
                  Previous
                </button>
                <span>
                  Page {page} of {Math.ceil(data.total / 12)}
                </span>
                <button
                  disabled={page >= Math.ceil(data.total / 12)}
                  onClick={() => setPage(page + 1)}
                >
                  Next
                </button>
              </nav>
            )}
          </>
        )
      )}
      {creating && (
        <Modal title="Add document reference" onClose={() => setCreating(false)}>
          <DocumentForm
            onSaved={() => {
              setCreating(false);
              setRefresh((value) => value + 1);
            }}
          />
        </Modal>
      )}
    </>
  );
}
