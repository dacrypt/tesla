import React, { useEffect, useState, useCallback } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
} from '@ionic/react';
import { useLocation } from 'react-router-dom';
import { getBaseUrl } from '../api/client';

interface ActionDef {
  method: 'GET' | 'POST';
  path: string;
  label: string;
  destructive?: boolean;
}

const ACTION_MAP: Record<string, ActionDef> = {
  'lock':          { method: 'POST', path: '/api/security/lock',    label: 'Lock Doors' },
  'unlock':        { method: 'POST', path: '/api/security/unlock',  label: 'Unlock Doors',   destructive: true },
  'climate-on':    { method: 'POST', path: '/api/climate/on',       label: 'Climate On' },
  'climate-off':   { method: 'POST', path: '/api/climate/off',      label: 'Climate Off',    destructive: true },
  'charge-status': { method: 'GET',  path: '/api/charge/status',    label: 'Charge Status' },
  'horn':          { method: 'POST', path: '/api/vehicle/horn',     label: 'Honk Horn' },
  'flash':         { method: 'POST', path: '/api/vehicle/flash',    label: 'Flash Lights' },
};

type ExecState = 'idle' | 'confirm' | 'running' | 'done' | 'error';

const CheckIcon = () => (
  <svg width={48} height={48} viewBox="0 0 24 24" fill="#10b981">
    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
  </svg>
);

const ErrorIcon = () => (
  <svg width={48} height={48} viewBox="0 0 24 24" fill="#FF6B6B">
    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/>
  </svg>
);

const BoltIcon = () => (
  <svg width={32} height={32} viewBox="0 0 24 24" fill="#10b981">
    <path d="M7 2v11h3v9l7-12h-4l4-8z"/>
  </svg>
);

const Action: React.FC = () => {
  const location = useLocation();
  const [cmd, setCmd] = useState<string | null>(null);
  const [actionDef, setActionDef] = useState<ActionDef | null>(null);
  const [execState, setExecState] = useState<ExecState>('idle');
  const [result, setResult] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState<string>('');

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const rawCmd = params.get('cmd');

    if (!rawCmd) {
      setCmd(null);
      setActionDef(null);
      return;
    }

    // The cmd param may be a full web+tesla:// URI or just the action name
    let actionKey = rawCmd;
    try {
      // Handle web+tesla://lock or web+tesla:lock
      const decoded = decodeURIComponent(rawCmd);
      const match = decoded.match(/^web\+tesla:\/?\/?(.+)$/i);
      if (match) {
        actionKey = match[1].split('?')[0]; // strip any query params in the URI
      }
    } catch {
      // use rawCmd as-is
    }

    setCmd(actionKey);
    const def = ACTION_MAP[actionKey] ?? null;
    setActionDef(def);

    if (def && !def.destructive) {
      // Auto-execute safe actions
      setExecState('running');
    } else if (def?.destructive) {
      setExecState('confirm');
    }
  }, [location.search]);

  const execute = useCallback(async () => {
    if (!actionDef) return;
    setExecState('running');
    setResult(null);
    setErrorMsg('');

    try {
      const opts: RequestInit = { method: actionDef.method };
      if (actionDef.method === 'POST') {
        opts.headers = { 'Content-Type': 'application/json' };
        opts.body = JSON.stringify({});
      }
      const res = await fetch(`${getBaseUrl()}${actionDef.path}`, opts);
      if (!res.ok) {
        const text = await res.text();
        throw new Error(`${res.status}: ${text}`);
      }
      const contentType = res.headers.get('content-type') ?? '';
      const data = contentType.includes('application/json') ? await res.json() : await res.text();
      setResult(data);
      setExecState('done');
    } catch (err: any) {
      setErrorMsg(err?.message ?? 'Unknown error');
      setExecState('error');
    }
  }, [actionDef]);

  // Trigger auto-execute after state transitions to 'running' without confirmation
  useEffect(() => {
    if (execState === 'running' && actionDef && !actionDef.destructive) {
      execute();
    }
  }, [execState, actionDef, execute]);

  const renderResult = (data: any): React.ReactNode => {
    if (data === null || data === undefined) return null;
    if (typeof data === 'string') return <pre style={preStyle}>{data}</pre>;
    return <pre style={preStyle}>{JSON.stringify(data, null, 2)}</pre>;
  };

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700 }}>Tesla Action</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent>
        <div style={containerStyle}>
          {/* Unknown command */}
          {!actionDef && cmd && (
            <div style={cardStyle}>
              <div style={{ color: '#FF6B6B', fontSize: 16, fontWeight: 600, marginBottom: 8 }}>Unknown action</div>
              <div style={{ color: '#86888f', fontSize: 13 }}>
                <code style={{ color: '#e5e5e5' }}>{cmd}</code> is not a recognized Tesla action.
              </div>
              <div style={{ marginTop: 16, color: '#86888f', fontSize: 12 }}>
                <div style={{ marginBottom: 4, fontWeight: 600, color: '#999' }}>Available actions:</div>
                {Object.entries(ACTION_MAP).map(([key, def]) => (
                  <div key={key} style={{ padding: '3px 0' }}>
                    <code style={{ color: '#10b981' }}>web+tesla://{key}</code>
                    <span style={{ color: '#666', marginLeft: 8 }}>{def.label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* No command */}
          {!cmd && (
            <div style={cardStyle}>
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 16 }}>
                <BoltIcon />
              </div>
              <div style={{ color: '#fff', fontSize: 16, fontWeight: 600, marginBottom: 8, textAlign: 'center' }}>
                Tesla URL Handler
              </div>
              <div style={{ color: '#86888f', fontSize: 13, textAlign: 'center', marginBottom: 20 }}>
                Open a <code style={{ color: '#10b981' }}>web+tesla://</code> link to trigger a vehicle action.
              </div>
              <div style={{ color: '#86888f', fontSize: 12 }}>
                <div style={{ marginBottom: 6, fontWeight: 600, color: '#999' }}>Available actions:</div>
                {Object.entries(ACTION_MAP).map(([key, def]) => (
                  <div key={key} style={{ padding: '4px 0', display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #222' }}>
                    <code style={{ color: '#10b981' }}>web+tesla://{key}</code>
                    <span style={{ color: '#666' }}>{def.label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Confirmation dialog for destructive actions */}
          {actionDef && execState === 'confirm' && (
            <div style={cardStyle}>
              <div style={{ color: '#fff', fontSize: 18, fontWeight: 700, marginBottom: 8 }}>{actionDef.label}</div>
              <div style={{ color: '#86888f', fontSize: 13, marginBottom: 24 }}>
                This action requires confirmation. Are you sure you want to proceed?
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <button
                  style={{ ...btnStyle, background: '#10b981', color: '#000', flex: 1 }}
                  onClick={execute}
                >
                  Confirm
                </button>
                <button
                  style={{ ...btnStyle, background: '#222', color: '#e5e5e5', flex: 1 }}
                  onClick={() => setExecState('idle')}
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Running */}
          {execState === 'running' && (
            <div style={{ ...cardStyle, textAlign: 'center' }}>
              <div style={{ marginBottom: 16 }}>
                <svg width={40} height={40} viewBox="0 0 24 24" fill="none">
                  <circle cx={12} cy={12} r={9} stroke="rgba(255,255,255,0.08)" strokeWidth={3} />
                  <path d="M12 3a9 9 0 019 9" stroke="#10b981" strokeWidth={3} strokeLinecap="round">
                    <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
                  </path>
                </svg>
              </div>
              <div style={{ color: '#e5e5e5', fontSize: 15, fontWeight: 600 }}>
                {actionDef?.label ?? 'Running'}...
              </div>
            </div>
          )}

          {/* Done */}
          {execState === 'done' && (
            <div style={{ ...cardStyle, textAlign: 'center' }}>
              <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'center' }}>
                <CheckIcon />
              </div>
              <div style={{ color: '#10b981', fontSize: 16, fontWeight: 700, marginBottom: 8 }}>
                {actionDef?.label} — Done
              </div>
              {result !== null && typeof result !== 'string' && (
                <div style={{ textAlign: 'left', marginTop: 12 }}>
                  {renderResult(result)}
                </div>
              )}
              {typeof result === 'string' && result && (
                <div style={{ color: '#86888f', fontSize: 13, marginTop: 8 }}>{result}</div>
              )}
            </div>
          )}

          {/* Error */}
          {execState === 'error' && (
            <div style={{ ...cardStyle, textAlign: 'center' }}>
              <div style={{ marginBottom: 12, display: 'flex', justifyContent: 'center' }}>
                <ErrorIcon />
              </div>
              <div style={{ color: '#FF6B6B', fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Action Failed</div>
              <div style={{ color: '#86888f', fontSize: 13 }}>{errorMsg}</div>
              <button
                style={{ ...btnStyle, background: '#222', color: '#e5e5e5', marginTop: 20, width: '100%' }}
                onClick={execute}
              >
                Retry
              </button>
            </div>
          )}
        </div>
      </IonContent>
    </IonPage>
  );
};

const containerStyle: React.CSSProperties = {
  padding: '24px 16px',
  maxWidth: 480,
  margin: '0 auto',
};

const cardStyle: React.CSSProperties = {
  background: '#111',
  border: '1px solid #222',
  borderRadius: 12,
  padding: 24,
};

const btnStyle: React.CSSProperties = {
  padding: '12px 24px',
  borderRadius: 8,
  border: 'none',
  fontSize: 15,
  fontWeight: 600,
  cursor: 'pointer',
};

const preStyle: React.CSSProperties = {
  background: '#0a0a0a',
  border: '1px solid #222',
  borderRadius: 6,
  padding: 12,
  fontSize: 11,
  color: '#e5e5e5',
  overflowX: 'auto',
  textAlign: 'left',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-all',
};

export default Action;
