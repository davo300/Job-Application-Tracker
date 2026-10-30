import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ApiError, request } from './api/client';
import { AuthForm, type User } from './features/auth/AuthForm';
import './style.css';
import { Workspace } from './features/tracking/Workspace';

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [signingOut, setSigningOut] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const expired = () => {
      setUser(null);
      setError('');
    };
    window.addEventListener('session-expired', expired);
    return () => window.removeEventListener('session-expired', expired);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError('');
    request<User>('/auth/me', { signal: controller.signal })
      .then(setUser)
      .catch((cause) => {
        if (controller.signal.aborted) return;
        if (cause instanceof ApiError && cause.status === 401) setUser(null);
        else
          setError(
            'Unable to connect to your workspace. Check that the API and database are running.',
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [retry]);

  async function logout() {
    setSigningOut(true);
    setError('');
    try {
      await request<void>('/auth/logout', { method: 'POST' });
      setUser(null);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) setUser(null);
      else
        setError(cause instanceof Error ? cause.message : 'Unable to sign out. Please try again.');
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header>
        <a className="brand" href="/">
          ◈ <span>Job Application Tracker</span>
        </a>
        <span className="badge">Your next opportunity starts here</span>
      </header>
      <main id="main-content" tabIndex={-1}>
        {loading ? (
          <p role="status">Opening your workspace…</p>
        ) : user ? (
          <Workspace
            user={user}
            onLogout={() => void logout()}
            signingOut={signingOut}
            authError={error}
          />
        ) : error ? (
          <section>
            <p role="alert" className="error">
              {error}
            </p>
            <button onClick={() => setRetry((value) => value + 1)}>Try again</button>
          </section>
        ) : (
          <div className="welcome">
            <div className="intro">
              <p className="eyebrow">MAKE YOUR NEXT MOVE</p>
              <h1>A clearer view of your next opportunity.</h1>
              <p>
                A personal workspace for the applications, conversations, and opportunities that
                shape your career.
              </p>
              <p className="help">
                Save opportunities, record applications, and keep your notes together.
              </p>
            </div>
            <AuthForm onAuthenticated={setUser} />
          </div>
        )}
      </main>
      <footer>Built for a more thoughtful job search.</footer>
    </>
  );
}
createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
