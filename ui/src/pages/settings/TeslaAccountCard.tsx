import React, { useState } from 'react';
import { api, AuthStatus, describeError } from '../../api/client';
import Spinner from '../../components/icons/Spinner';
import type { Notify } from './types';

interface Props {
  authStatus: AuthStatus | null;
  notify: Notify;
  /** Called after the account is connected, to reload everything. */
  onConnected: () => void;
}

/** Tesla account connection via the OAuth2 PKCE callback-URL flow. */
const TeslaAccountCard: React.FC<Props> = ({ authStatus, notify, onConnected }) => {
  const [authLoading, setAuthLoading] = useState(false);
  const [, setAuthUrl] = useState('');
  const [authState, setAuthState] = useState('');
  const [showAuthInput, setShowAuthInput] = useState(false);
  const [callbackUrl, setCallbackUrl] = useState('');

  const startTeslaLogin = async () => {
    setAuthLoading(true);
    try {
      const data = await api.getAuthLogin();
      setAuthUrl(data.auth_url);
      setAuthState(data.state);
      setShowAuthInput(true);
      window.open(data.auth_url, 'tesla-auth', 'width=600,height=700');
    } catch (e: unknown) {
      notify('Login failed: ' + describeError(e), 'danger');
    } finally {
      setAuthLoading(false);
    }
  };

  const submitCallback = async () => {
    if (!callbackUrl.trim()) return;
    setAuthLoading(true);
    try {
      // Extract code and state from URL
      const url = new URL(callbackUrl.trim());
      const code = url.searchParams.get('code');
      const state = url.searchParams.get('state') || authState;
      if (!code) {
        notify('No code found in URL', 'danger');
        return;
      }
      await api.postAuthCallback(code, state);
      notify('Tesla account connected!', 'success');
      setShowAuthInput(false);
      setCallbackUrl('');
      onConnected();
    } catch (e: unknown) {
      notify('Auth failed: ' + describeError(e), 'danger');
    } finally {
      setAuthLoading(false);
    }
  };

  return (
    <div className="tesla-card">
      <div className="flex-center gap-sm" style={{ marginBottom: 14 }}>
        <div style={{ width: 34, height: 34, borderRadius: '50%', background: authStatus?.authenticated ? 'rgba(11,232,129,0.15)' : 'rgba(255,107,107,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: authStatus?.authenticated ? '#0BE881' : '#FF6B6B' }}>
          <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/></svg>
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Tesla Account</div>
          <div style={{ color: '#86888f', fontSize: 12 }}>
            {authStatus?.authenticated ? `Connected via ${authStatus.backend}` : 'Not connected'}
          </div>
        </div>
        {authStatus?.authenticated && (
          <div className="flex-center gap-xs">
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#0BE881', boxShadow: '0 0 6px #0BE881' }} />
            <span style={{ color: '#0BE881', fontSize: 12, fontWeight: 600 }}>Connected</span>
          </div>
        )}
      </div>

      {!authStatus?.authenticated && !showAuthInput && (
        <button
          onClick={startTeslaLogin}
          disabled={authLoading}
          className="tesla-btn"
          style={{ width: '100%', fontSize: 14, padding: '12px 16px' }}
        >
          {authLoading ? <Spinner /> : 'Login with Tesla'}
        </button>
      )}

      {showAuthInput && (
        <div>
          <div style={{ color: '#86888f', fontSize: 12, marginBottom: 8, lineHeight: 1.5 }}>
            A Tesla login window opened. After signing in, you'll see a blank page.
            <br /><strong style={{ color: '#fff' }}>Copy the full URL</strong> from that blank page and paste it below.
          </div>
          <input
            type="url"
            value={callbackUrl}
            onChange={(e) => setCallbackUrl(e.target.value)}
            placeholder="https://auth.tesla.com/void/callback?code=..."
            className="tesla-input mono"
            style={{ marginBottom: 8, fontSize: 12 }}
          />
          <button
            onClick={submitCallback}
            disabled={authLoading || !callbackUrl.trim()}
            className="tesla-btn"
            style={{ width: '100%', fontSize: 13 }}
          >
            {authLoading ? <Spinner /> : 'Connect'}
          </button>
        </div>
      )}

      {authStatus?.authenticated && (
        <div className="flex-center gap-sm" style={{ fontSize: 12 }}>
          {authStatus.has_fleet && <span style={{ color: '#0BE881' }}>Fleet API</span>}
          {authStatus.has_tessie && <span style={{ color: '#0FBCF9' }}>Tessie</span>}
        </div>
      )}
    </div>
  );
};

export default TeslaAccountCard;
