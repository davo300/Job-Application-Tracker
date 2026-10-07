import { useState, type FormEvent } from 'react';
import { request } from '../../api/client';

export interface User {
  id: string;
  email: string;
  created_at: string;
}

export function AuthForm({ onAuthenticated }: { onAuthenticated: (user: User) => void }) {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const user = await request<User>(`/auth/${mode}`, {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      setPassword('');
      onAuthenticated(user);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Unable to connect. Please try again.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="auth-card" aria-labelledby="auth-title">
      <p className="eyebrow">YOUR JOB SEARCH, ORGANIZED</p>
      <h2 id="auth-title">{mode === 'login' ? 'Welcome back' : 'Create your account'}</h2>
      <p>
        {mode === 'login'
          ? 'Sign in to your personal workspace.'
          : 'Start with a secure home for your job search.'}
      </p>
      <form onSubmit={submit} aria-busy={busy}>
        <label htmlFor="email">Email address</label>
        <input
          id="email"
          type="email"
          autoComplete="email"
          required
          maxLength={320}
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          disabled={busy}
        />
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          required
          minLength={mode === 'register' ? 12 : 1}
          maxLength={128}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={busy}
          aria-describedby={mode === 'register' ? 'password-help' : undefined}
        />
        {mode === 'register' && (
          <p id="password-help" className="help">
            Use 12–128 characters. A long, unique passphrase works well.
          </p>
        )}
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy}>
          {busy ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
        </button>
      </form>
      <button
        type="button"
        className="text-button"
        disabled={busy}
        onClick={() => {
          setMode(mode === 'login' ? 'register' : 'login');
          setError('');
          setPassword('');
        }}
      >
        {mode === 'login' ? 'New here? Create an account' : 'Already have an account? Sign in'}
      </button>
    </section>
  );
}
