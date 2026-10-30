import {
  cloneElement,
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type ReactElement,
  type ReactNode,
} from 'react';
import { request } from '../../api/client';
import { type Application, type Company, type Job, localDate } from './types';

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const previousFocus = document.activeElement;
    const dialog = ref.current;
    dialog?.showModal();
    return () => {
      dialog?.close();
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      aria-labelledby="modal-title"
    >
      <div className="modal-header">
        <h2 id="modal-title">{title}</h2>
        <button type="button" className="text-button" onClick={onClose} aria-label="Close form">
          ✕
        </button>
      </div>
      {children}
    </dialog>
  );
}

function Field({ label, children }: { label: string; children: ReactElement<{ id?: string }> }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      {cloneElement(children, { id })}
    </div>
  );
}

function useSave(onSaved: () => void) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState('');
  async function save(event: FormEvent, path: string, method: string, data: unknown) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await request(path, { method, body: JSON.stringify(data) });
      onSaved();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to save.');
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, save };
}

export function CompanyForm({ company, onSaved }: { company?: Company; onSaved: () => void }) {
  const [name, setName] = useState(company?.name ?? ''),
    [website, setWebsite] = useState(company?.website ?? '');
  const [location, setLocation] = useState(company?.location ?? ''),
    [notes, setNotes] = useState(company?.notes ?? '');
  const { busy, error, save } = useSave(onSaved);
  return (
    <form
      onSubmit={(event) =>
        save(
          event,
          company ? `/companies/${company.id}` : '/companies',
          company ? 'PATCH' : 'POST',
          { name, website: website || null, location: location || null, notes: notes || null },
        )
      }
    >
      <fieldset disabled={busy}>
        <Field label="Company name">
          <input required maxLength={250} value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <Field label="Website">
          <input
            type="url"
            placeholder="https://example.com"
            value={website}
            onChange={(e) => setWebsite(e.target.value)}
          />
        </Field>
        <Field label="Company location">
          <input maxLength={250} value={location} onChange={(e) => setLocation(e.target.value)} />
        </Field>
        <Field label="Company notes">
          <textarea maxLength={20000} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </Field>
      </fieldset>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <button disabled={busy} type="submit">
        {busy ? 'Saving…' : 'Save company'}
      </button>
    </form>
  );
}

export function JobForm({
  job,
  description,
  companies,
  onSaved,
}: {
  job?: Job;
  description?: string;
  companies: Company[];
  onSaved: () => void;
}) {
  const initial = {
    company_id: job?.company_id ?? companies[0]?.id ?? '',
    title: job?.title ?? '',
    url: job?.url ?? '',
    location: job?.location ?? '',
    work_arrangement: job?.work_arrangement ?? '',
    employment_type: job?.employment_type ?? '',
    salary_min: job?.salary_min ?? '',
    salary_max: job?.salary_max ?? '',
    salary_currency: job?.salary_currency ?? '',
    salary_period: job?.salary_period ?? '',
    posted_on: job?.posted_on ?? '',
    deadline_on: job?.deadline_on ?? '',
    raw_description: description ?? '',
  };
  const [form, setForm] = useState(initial);
  const { busy, error, save } = useSave(onSaved);
  function change(key: keyof typeof initial, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
  }
  const text = (
    key: keyof typeof initial,
    title: string,
    type = 'text',
    required = false,
    maxLength?: number,
  ) => (
    <Field label={title}>
      <input
        type={type}
        required={required}
        maxLength={maxLength}
        value={form[key]}
        onChange={(e) => change(key, e.target.value)}
        {...(type === 'number' ? { min: '0', step: '0.01' } : {})}
      />
    </Field>
  );
  function submit(event: FormEvent) {
    const payload: Record<string, string | null> = { ...form };
    for (const key of Object.keys(payload)) if (payload[key] === '') payload[key] = null;
    if (job && form.raw_description === (description ?? '')) delete payload.raw_description;
    void save(event, job ? `/jobs/${job.id}` : '/jobs', job ? 'PATCH' : 'POST', payload);
  }
  return (
    <form onSubmit={submit}>
      <fieldset disabled={busy}>
        <Field label="Company">
          <select
            required
            value={form.company_id}
            onChange={(e) => change('company_id', e.target.value)}
          >
            <option value="">Select a company</option>
            {companies.map((company) => (
              <option key={company.id} value={company.id}>
                {company.name}
              </option>
            ))}
          </select>
        </Field>
        {text('title', 'Job title', 'text', true, 300)}
        {text('url', 'Job URL', 'url')}
        {text('location', 'Job location', 'text', false, 250)}
        <div className="form-grid">
          <Field label="Work arrangement">
            <select
              value={form.work_arrangement}
              onChange={(e) => change('work_arrangement', e.target.value)}
            >
              <option value="">Not specified</option>
              <option value="remote">Remote</option>
              <option value="hybrid">Hybrid</option>
              <option value="on_site">On-site</option>
            </select>
          </Field>
          <Field label="Employment type">
            <select
              value={form.employment_type}
              onChange={(e) => change('employment_type', e.target.value)}
            >
              <option value="">Not specified</option>
              {['full_time', 'part_time', 'internship', 'contract', 'temporary', 'other'].map(
                (value) => (
                  <option key={value} value={value}>
                    {value.replaceAll('_', ' ')}
                  </option>
                ),
              )}
            </select>
          </Field>
        </div>
        <div className="form-grid">
          {text('salary_min', 'Minimum salary', 'number')}
          {text('salary_max', 'Maximum salary', 'number')}
          <Field label="Currency">
            <input
              maxLength={3}
              pattern="[A-Z]{3}"
              placeholder="USD"
              value={form.salary_currency}
              onChange={(e) => change('salary_currency', e.target.value.toUpperCase())}
              required={!!(form.salary_min || form.salary_max)}
            />
          </Field>
          <Field label="Salary period">
            <select
              value={form.salary_period}
              onChange={(e) => change('salary_period', e.target.value)}
              required={!!(form.salary_min || form.salary_max)}
            >
              <option value="">Not specified</option>
              <option value="year">Per year</option>
              <option value="month">Per month</option>
              <option value="hour">Per hour</option>
            </select>
          </Field>
          {text('posted_on', 'Date posted', 'date')}
          {text('deadline_on', 'Application deadline', 'date')}
        </div>
        <Field label="Job description">
          <textarea
            rows={8}
            maxLength={100000}
            value={form.raw_description}
            onChange={(e) => change('raw_description', e.target.value)}
          />
        </Field>
        {job && <p className="help">Changes to the description are saved as a new version.</p>}
      </fieldset>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <button disabled={busy || !companies.length} type="submit">
        {busy ? 'Saving…' : 'Save job'}
      </button>
    </form>
  );
}

export function ApplicationForm({
  application,
  jobs,
  jobId,
  onSaved,
}: {
  application?: Application;
  jobs: Job[];
  jobId?: string;
  onSaved: () => void;
}) {
  const [selected, setSelected] = useState(jobId ?? jobs[0]?.id ?? '');
  const [appliedOn, setAppliedOn] = useState(localDate()),
    [notes, setNotes] = useState(application?.notes ?? '');
  const { busy, error, save } = useSave(onSaved);
  return (
    <form
      onSubmit={(event) =>
        save(
          event,
          application ? `/applications/${application.id}` : '/applications',
          application ? 'PATCH' : 'POST',
          application
            ? { notes: notes || null }
            : { job_id: selected, applied_on: appliedOn, notes: notes || null },
        )
      }
    >
      <fieldset disabled={busy}>
        {application ? (
          <p>
            {application.job.title} · {application.job.company.name}
          </p>
        ) : (
          <>
            <Field label="Job">
              <select required value={selected} onChange={(e) => setSelected(e.target.value)}>
                <option value="">Select a job</option>
                {jobs.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title} · {job.company.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Application date">
              <input
                type="date"
                required
                value={appliedOn}
                onChange={(e) => setAppliedOn(e.target.value)}
              />
            </Field>
            <p className="help">
              This creates a new application attempt and records its applied event.
            </p>
          </>
        )}
        <Field label="Application notes">
          <textarea
            rows={5}
            maxLength={20000}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </Field>
      </fieldset>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <button disabled={busy || (!application && !jobs.length)} type="submit">
        {busy ? 'Saving…' : application ? 'Save notes' : 'Record application'}
      </button>
    </form>
  );
}
