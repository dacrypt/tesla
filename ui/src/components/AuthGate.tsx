import React from 'react';
import { IonSpinner } from '@ionic/react';
import { api, onAuthRequired } from '../api/client';

/**
 * Blocks the dashboard until the browser holds a valid session.
 *
 * When the server has an API key configured, the user pastes it once;
 * POST /api/session exchanges it for an HttpOnly cookie (the key itself is
 * never stored in JS-readable storage). Any later 401 re-opens this screen.
 */
type GateState = 'checking' | 'ok' | 'login';

const card: React.CSSProperties = {
  width: '100%',
  maxWidth: 380,
  background: 'var(--tesla-card, #181b21)',
  border: '1px solid var(--tesla-card-border, rgba(255,255,255,0.07))',
  borderRadius: 16,
  padding: 24,
  color: '#fff',
};

const input: React.CSSProperties = {
  width: '100%',
  boxSizing: 'border-box',
  padding: '12px 14px',
  marginTop: 16,
  borderRadius: 10,
  border: '1px solid rgba(255,255,255,0.15)',
  background: 'rgba(255,255,255,0.05)',
  color: '#fff',
  fontSize: 15,
};

const button: React.CSSProperties = {
  width: '100%',
  marginTop: 14,
  padding: '12px 14px',
  borderRadius: 10,
  border: 'none',
  background: '#05C46B',
  color: '#000',
  fontWeight: 600,
  fontSize: 15,
  cursor: 'pointer',
};

export default function AuthGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = React.useState<GateState>('checking');
  const [key, setKey] = React.useState('');
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    let alive = true;
    api
      .getSession()
      .then(s => alive && setState(s.authenticated ? 'ok' : 'login'))
      // Older servers have no /api/session: let the app render as before.
      .catch(() => alive && setState('ok'));
    const off = onAuthRequired(() => setState('login'));
    return () => {
      alive = false;
      off();
    };
  }, []);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!key.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await api.login(key.trim());
      setKey('');
      // Reload so every query and the SSE stream restart with the cookie.
      window.location.reload();
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      setError(status === 401 ? 'Invalid API key.' : 'Could not reach the server.');
    } finally {
      setBusy(false);
    }
  };

  if (state === 'ok') return <>{children}</>;

  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 16,
        background: 'var(--tesla-bg, #0d0e11)',
      }}
    >
      {state === 'checking' ? (
        <IonSpinner name="dots" style={{ '--color': '#05C46B' } as React.CSSProperties} />
      ) : (
        <form style={card} onSubmit={submit}>
          <h2 style={{ margin: 0, fontSize: 20 }}>Sign in</h2>
          <p style={{ margin: '8px 0 0', opacity: 0.7, fontSize: 14, lineHeight: 1.4 }}>
            This server requires an API key. Find it on the server with{' '}
            <code>tesla serve api-key</code>.
          </p>
          <input
            style={input}
            type="password"
            autoComplete="current-password"
            placeholder="API key"
            value={key}
            onChange={e => setKey(e.target.value)}
            autoFocus
            aria-label="API key"
          />
          {error && (
            <div role="alert" style={{ color: '#ff6b6b', fontSize: 13, marginTop: 10 }}>
              {error}
            </div>
          )}
          <button style={{ ...button, opacity: busy ? 0.6 : 1 }} type="submit" disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      )}
    </div>
  );
}
