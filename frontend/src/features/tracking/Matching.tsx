import { useEffect, useState, type FormEvent } from 'react';
import { request } from '../../api/client';
import { type Page, label } from './types';
type Entry = { name: string; skills: string[]; summary: string };
type Data = { skills: string[]; education: string; projects: Entry[]; experience: Entry[] };
type Profile = { id: string; revision: number; data: Data };
const empty: Data = { skills: [], education: '', projects: [], experience: [] };
export function ProfileView() {
  const [data, setData] = useState<Data>(empty),
    [revision, setRevision] = useState(0);
  const [skills, setSkills] = useState(''),
    [error, setError] = useState(''),
    [message, setMessage] = useState('');
  const [busy, setBusy] = useState(true),
    [ready, setReady] = useState(false);
  async function load() {
    setBusy(true);
    setError('');
    try {
      const profile = await request<Profile | null>('/profile');
      setData(profile?.data ?? empty);
      setSkills(profile?.data.skills.join(', ') ?? '');
      setRevision(profile?.revision ?? 0);
      setReady(true);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to load profile.');
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  async function save(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const profile = await request<Profile>('/profile', {
        method: 'PUT',
        body: JSON.stringify({
          revision,
          data: {
            ...data,
            projects: data.projects.map((e) => ({
              ...e,
              skills: e.skills.map((s) => s.trim()).filter(Boolean),
            })),
            experience: data.experience.map((e) => ({
              ...e,
              skills: e.skills.map((s) => s.trim()).filter(Boolean),
            })),
            skills: skills
              .split(',')
              .map((s) => s.trim())
              .filter(Boolean),
          },
        }),
      });
      setRevision(profile.revision);
      setMessage(`Saved profile revision ${profile.revision}.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to save profile.');
    } finally {
      setBusy(false);
    }
  }
  function entries(kind: 'projects' | 'experience') {
    return (
      <section>
        <h2>{label(kind)}</h2>
        {data[kind].map((entry, index) => (
          <fieldset key={index}>
            <legend>
              {label(kind)} {index + 1}
            </legend>
            <label className="field">
              Name
              <input
                required
                maxLength={200}
                value={entry.name}
                onChange={(e) => change(index, { name: e.target.value })}
              />
            </label>
            <label className="field">
              Skills (comma separated)
              <input
                value={entry.skills.join(',')}
                onChange={(e) => change(index, { skills: e.target.value.split(',') })}
              />
            </label>
            <label className="field">
              Summary
              <textarea
                maxLength={2000}
                value={entry.summary}
                onChange={(e) => change(index, { summary: e.target.value })}
              />
            </label>
            <button
              type="button"
              className="text-button"
              onClick={() => setData({ ...data, [kind]: data[kind].filter((_, i) => i !== index) })}
            >
              Remove entry
            </button>
          </fieldset>
        ))}
        <button
          type="button"
          className="secondary"
          disabled={data[kind].length >= 50}
          onClick={() =>
            setData({ ...data, [kind]: [...data[kind], { name: '', skills: [], summary: '' }] })
          }
        >
          Add {kind === 'projects' ? 'project' : 'experience'}
        </button>
      </section>
    );
    function change(activeIndex: number, patch: Partial<Entry>) {
      setData({
        ...data,
        [kind]: data[kind].map((entry, index) =>
          index === activeIndex ? { ...entry, ...patch } : entry,
        ),
      });
    }
  }
  return (
    <>
      <h1>Your profile</h1>
      <p>Use skills and tagged projects or experience as evidence for job matching.</p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <button className="text-button" disabled={busy} onClick={() => void load()}>
        Reload saved profile
      </button>
      {message && <p role="status">{message}</p>}
      {ready && (
        <form onSubmit={save}>
          <fieldset disabled={busy}>
            <label className="field">
              Skills (comma separated)
              <input value={skills} onChange={(e) => setSkills(e.target.value)} />
            </label>
            <label className="field">
              Education
              <textarea
                value={data.education}
                maxLength={2000}
                onChange={(e) => setData({ ...data, education: e.target.value })}
              />
            </label>
            {entries('projects')}
            {entries('experience')}
            <button type="submit">{busy ? 'Saving…' : 'Save profile'}</button>
          </fieldset>
        </form>
      )}
    </>
  );
}

type Match = {
  id: string;
  profile_revision: number;
  scorer_version: string;
  created_at: string;
  breakdown: {
    score: number | null;
    scored_weight: number;
    components: {
      name: string;
      weight: number;
      value: number | null;
      matched: string[];
      missing: string[];
    }[];
    relevant_projects: { name: string; matched_skills: string[] }[];
    relevant_experience: { name: string; matched_skills: string[] }[];
    emphasize: string[];
    limitations: string[];
    education: { status: string; profile: string; requirements: { quote: string }[] };
  };
};
export function MatchView({ identifier }: { identifier: string }) {
  const [history, setHistory] = useState<Match[]>([]),
    [selected, setSelected] = useState('');
  const [busy, setBusy] = useState(true),
    [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setBusy(true);
    setError('');
    setHistory([]);
    (async () => {
      let page = 1;
      const items: Match[] = [];
      while (true) {
        const result = await request<Page<Match>>(
          `/analyses/${identifier}/matches?page=${page}&page_size=100`,
          { signal: controller.signal },
        );
        items.push(...result.items);
        if (items.length >= result.total || !result.items.length) break;
        page++;
      }
      if (!controller.signal.aborted) {
        setHistory(items);
        setSelected(items[0]?.id ?? '');
      }
    })()
      .catch((cause) => {
        if (!controller.signal.aborted)
          setError(cause instanceof Error ? cause.message : 'Unable to load matches.');
      })
      .finally(() => {
        if (!controller.signal.aborted) setBusy(false);
      });
    return () => controller.abort();
  }, [identifier]);
  async function match() {
    setBusy(true);
    setError('');
    try {
      const result = await request<Match>(`/analyses/${identifier}/matches`, { method: 'POST' });
      setHistory([result, ...history]);
      setSelected(result.id);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to match.');
    } finally {
      setBusy(false);
    }
  }
  const current = history.find((item) => item.id === selected);
  return (
    <section>
      <h3>Profile match</h3>
      <p className="help">
        Save your profile first. Score measures classified skill evidence, not hiring probability.
        Review extraction before matching.
      </p>
      <button disabled={busy} onClick={() => void match()}>
        {busy ? 'Loading…' : 'Match against saved profile'}
      </button>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {!!history.length && (
        <label className="field">
          Saved match
          <select value={selected} onChange={(e) => setSelected(e.target.value)}>
            {history.map((item) => (
              <option key={item.id} value={item.id}>
                Profile revision {item.profile_revision} ·{' '}
                {new Date(item.created_at).toLocaleString()}
              </option>
            ))}
          </select>
        </label>
      )}
      {current && (
        <>
          <h4>
            {current.breakdown.score === null
              ? 'Score unavailable'
              : `${current.breakdown.score}/100 skill evidence score`}
          </h4>
          <p>
            Profile revision {current.profile_revision} · Scorer {current.scorer_version} ·
            Available scoring weight {(current.breakdown.scored_weight * 100).toFixed(0)}%
          </p>
          {current.breakdown.components.map((c) => (
            <article key={c.name}>
              <h4>
                {label(c.name)} ·{' '}
                {c.value === null ? 'Unavailable' : `${(c.value * 100).toFixed(0)}%`} · Weight{' '}
                {c.weight * 100}%
              </h4>
              <p>Matched: {c.matched.join(', ') || 'None'}</p>
              <p>Missing evidence: {c.missing.join(', ') || 'None'}</p>
            </article>
          ))}
          {(['relevant_projects', 'relevant_experience'] as const).map((kind) => (
            <div key={kind}>
              <h4>{label(kind)}</h4>
              {current.breakdown[kind].map((entry, i) => (
                <p key={i}>
                  {entry.name}: {entry.matched_skills.join(', ')}
                </p>
              ))}
            </div>
          ))}
          <p>
            Emphasize: {current.breakdown.emphasize.join(', ') || 'No classified skill overlap'}
          </p>
          <h4>Education: {label(current.breakdown.education.status)}</h4>
          <p>{current.breakdown.education.profile || 'No education entered'}</p>
          {current.breakdown.education.requirements.map((e, i) => (
            <blockquote key={i}>{e.quote}</blockquote>
          ))}
          <ul>
            {current.breakdown.limitations.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
