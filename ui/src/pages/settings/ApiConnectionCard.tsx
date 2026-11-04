import React, { useState } from 'react';
import { api, getBaseUrl, ServerStatus, setBaseUrl } from '../../api/client';
import Spinner from '../../components/icons/Spinner';
import { ServerIcon } from './icons';
import type { Notify } from './types';

interface Props {
  status: ServerStatus | null;
  notify: Notify;
  /** Called (after a short delay) once a new URL is saved, to reload everything. */
  onUrlSaved: () => void;
}

/** API base URL editor + connection test. */
const ApiConnectionCard: React.FC<Props> = ({ status, notify, onUrlSaved }) => {
  const [apiUrl, setApiUrl] = useState(getBaseUrl());
  const [urlDirty, setUrlDirty] = useState(false);
  const [testing, setTesting] = useState(false);

  const testConnection = async () => {
    setTesting(true);
    try {
      await api.getStatus();
      notify('Connection successful', 'success');
    } catch {
      notify('Connection failed — check URL', 'danger');
    } finally {
      setTesting(false);
    }
  };

  const saveUrl = () => {
    setBaseUrl(apiUrl);
    setUrlDirty(false);
    notify('URL saved — reconnecting...', 'success');
    setTimeout(onUrlSaved, 500);
  };

  return (
    <div className="tesla-card">
      <div className="flex-center gap-sm" style={{ marginBottom: 14 }}>
        <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(15,188,249,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0FBCF9' }}>
          <ServerIcon />
        </div>
        <div>
          <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>API Connection</div>
          <div style={{ color: '#86888f', fontSize: 12 }}>Backend server URL</div>
        </div>
        {/* Connection status dot */}
        <div className="flex-center gap-xs" style={{ marginLeft: 'auto' }}>
          <div style={{ width: 8, height: 8, borderRadius: '50%', background: status ? '#0BE881' : '#FF6B6B', boxShadow: `0 0 6px ${status ? '#0BE881' : '#FF6B6B'}` }} />
          <span style={{ color: status ? '#0BE881' : '#FF6B6B', fontSize: 12, fontWeight: 600 }}>
            {status ? 'Connected' : 'Offline'}
          </span>
        </div>
      </div>

      <input
        type="url"
        value={apiUrl}
        onChange={(e) => { setApiUrl(e.target.value); setUrlDirty(true); }}
        placeholder={typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8080'}
        className="tesla-input mono"
        style={{
          borderColor: urlDirty ? 'rgba(5,196,107,0.5)' : 'rgba(255,255,255,0.1)',
          marginBottom: 10,
        }}
      />

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <button
          onClick={saveUrl}
          disabled={!urlDirty}
          className={`tesla-btn${urlDirty ? '' : ' secondary'}`}
          style={{ fontSize: 13 }}
        >
          {urlDirty ? 'Save URL' : 'Saved'}
        </button>
        <button
          onClick={testConnection}
          disabled={testing}
          className="tesla-btn blue"
          style={{ fontSize: 13 }}
        >
          {testing ? <Spinner /> : null}
          Test
        </button>
      </div>
    </div>
  );
};

export default ApiConnectionCard;
