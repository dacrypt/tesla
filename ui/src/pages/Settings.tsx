import React, { useState, useEffect } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
  IonToast,
} from '@ionic/react';
import { api, ProviderStatus, TeslaConfig, ServerStatus, StackStatus } from '../api/client';
import { getBaseUrl, setBaseUrl } from '../api/client';

// ---- Icons ----
const ServerIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M20 3H4v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V3zm-2 9H6V5h12v7zM4 19c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2v-2H4v2zm6-1h4v1h-4v-1z"/></svg>;
const GearIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>;
const PlugIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M16.01 7L16 3h-2v4h-4V3H8v4h-.01C7 6.99 6 7.99 6 8.99v5.49L9.5 18v3h5v-3l3.5-3.51V9c0-1.1-.99-2-1.99-2zm-7.5 9.5V9h7l.01 7.5L12 20l-3.49-3.5z"/></svg>;
const InfoIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>;
const DockerIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M13 3h2v2h-2V3zm-2 0h2v2h-2V3zM9 3h2v2H9V3zM5 7h2v2H5V7zm4 0h2v2H9V7zm4 0h2v2h-2V7zm-8 4h2v2H5v-2zm4 0h2v2H9v-2zm4 0h2v2h-2v-2zm4 0h2v2h-2v-2zm1-4h2v2h-2V7zm4 3c-.55 0-1.22.15-1.72.42-.22-1.3-1.38-2.42-2.78-2.42h-.5V3h-2v2h-2V3H9v2H7V3H5v4H3v2H1v2h2.05c-.03.17-.05.33-.05.5C3 14.53 5.47 17 8.5 17c1.7 0 3.2-.76 4.2-1.96C13.61 16.29 14.97 17 16.5 17c2.48 0 4.5-2.02 4.5-4.5 0-.66-.16-1.28-.43-1.83.58-.31 1.43-.67 1.43-1.67 0-.72-.67-1-1-1z"/></svg>;
const LogIcon = () => <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor"><path d="M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z"/></svg>;

function Spin() {
  return (
    <svg width={24} height={24} viewBox="0 0 24 24" fill="none">
      <circle cx={12} cy={12} r={9} stroke="rgba(255,255,255,0.08)" strokeWidth={3} />
      <path d="M12 3a9 9 0 019 9" stroke="#05C46B" strokeWidth={3} strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

function providerColor(s: string): string {
  if (['ok', 'connected', 'active'].includes(s)) return '#0BE881';
  if (['error', 'failed'].includes(s)) return '#05C46B';
  return '#86888f';
}

const Settings: React.FC = () => {
  const [apiUrl, setApiUrl] = useState(getBaseUrl());
  const [urlDirty, setUrlDirty] = useState(false);
  const [status, setStatus] = useState<ServerStatus | null>(null);
  const [config, setConfig] = useState<TeslaConfig | null>(null);
  const [providers, setProviders] = useState<ProviderStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [toast, setToast] = useState<{ message: string; color: string } | null>(null);

  // TeslaMate stack
  const [stack, setStack] = useState<StackStatus | null>(null);
  const [stackCmd, setStackCmd] = useState<string | null>(null);
  const [stackLogs, setStackLogs] = useState<string>('');
  const [logsService, setLogsService] = useState('');
  const [showLogs, setShowLogs] = useState(false);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [s, c, p, st] = await Promise.allSettled([
        api.getStatus(), api.getConfig(), api.getProviders(), api.getStackStatus(),
      ]);
      if (s.status === 'fulfilled') setStatus(s.value);
      if (c.status === 'fulfilled') setConfig(c.value);
      if (p.status === 'fulfilled') setProviders(Array.isArray(p.value) ? p.value : []);
      if (st.status === 'fulfilled') setStack(st.value);
    } finally {
      setLoading(false);
    }
  };

  const runStackAction = async (action: 'start' | 'stop' | 'restart' | 'update') => {
    setStackCmd(action);
    try {
      if (action === 'start') await api.stackStart();
      else if (action === 'stop') await api.stackStop();
      else if (action === 'restart') await api.stackRestart();
      else if (action === 'update') await api.stackUpdate();
      setToast({ message: `Stack ${action} OK`, color: 'success' });
      setTimeout(async () => {
        try {
          const st = await api.getStackStatus();
          setStack(st);
        } catch { /* ignore */ }
      }, 2500);
    } catch (e: any) {
      setToast({ message: `Stack ${action} failed: ${e.message || e}`, color: 'danger' });
    } finally {
      setStackCmd(null);
    }
  };

  const fetchLogs = async () => {
    try {
      const data = await api.getStackLogs(logsService || undefined);
      setStackLogs(data.logs || '(no output)');
      setShowLogs(true);
    } catch (e: any) {
      setStackLogs(`Error: ${e.message || e}`);
      setShowLogs(true);
    }
  };

  const testConnection = async () => {
    setTesting(true);
    try {
      await api.getStatus();
      setToast({ message: 'Connection successful', color: 'success' });
    } catch {
      setToast({ message: 'Connection failed — check URL', color: 'danger' });
    } finally {
      setTesting(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const saveUrl = () => {
    setBaseUrl(apiUrl);
    setUrlDirty(false);
    setToast({ message: 'URL saved — reconnecting...', color: 'success' });
    setTimeout(fetchAll, 500);
  };

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700 }}>Settings</IonTitle>
        </IonToolbar>
      </IonHeader>

      <IonContent>
        <div className="page-pad">
          {/* ---- API URL ---- */}
          <div className="tesla-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(15,188,249,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0FBCF9' }}>
                <ServerIcon />
              </div>
              <div>
                <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>API Connection</div>
                <div style={{ color: '#86888f', fontSize: 12 }}>Backend server URL</div>
              </div>
              {/* Connection status dot */}
              <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: status ? '#0BE881' : '#05C46B', boxShadow: `0 0 6px ${status ? '#0BE881' : '#05C46B'}` }} />
                <span style={{ color: status ? '#0BE881' : '#05C46B', fontSize: 12, fontWeight: 600 }}>
                  {status ? 'Connected' : 'Offline'}
                </span>
              </div>
            </div>

            <input
              type="url"
              value={apiUrl}
              onChange={(e) => { setApiUrl(e.target.value); setUrlDirty(true); }}
              placeholder="http://localhost:8080"
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
                {testing ? <Spin /> : null}
                Test
              </button>
            </div>
          </div>

          {loading ? (
            <div className="loading-center"><Spin /></div>
          ) : (
            <>
              {/* ---- Server info ---- */}
              {status && (
                <div className="tesla-card">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                    <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(11,232,129,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0BE881' }}>
                      <InfoIcon />
                    </div>
                    <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Server Info</div>
                  </div>
                  {[
                    { label: 'Version', value: status.version },
                    { label: 'Backend', value: status.backend },
                    { label: 'VIN', value: status.vin || 'Not configured', mono: true },
                  ].map((item) => (
                    <div key={item.label} className="stat-row">
                      <span className="label-sm">{item.label}</span>
                      <span style={{ color: '#ffffff', fontSize: 13, fontFamily: item.mono ? 'SF Mono, Menlo, monospace' : 'inherit', fontWeight: item.mono ? 600 : 400, letterSpacing: item.mono ? '0.05em' : 'normal' }}>
                        {item.value || '--'}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* ---- Configuration ---- */}
              {config && (
                <div className="tesla-card">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                    <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(249,151,22,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#F99716' }}>
                      <GearIcon />
                    </div>
                    <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Configuration</div>
                  </div>
                  {[
                    { label: 'Backend', value: config.backend },
                    { label: 'VIN', value: config.vin, mono: true },
                    { label: 'Tessie Token', value: config.tessie_token ? '••••' + config.tessie_token.slice(-4) : 'Not set' },
                    { label: 'TeslaMate URL', value: config.teslaMate_url || 'Not configured' },
                  ].map((item) => (
                    <div key={item.label} className="stat-row">
                      <span className="label-sm">{item.label}</span>
                      <span style={{ color: item.value ? '#ffffff' : '#86888f', fontSize: 12, fontFamily: (item as { mono?: boolean }).mono ? 'SF Mono, Menlo, monospace' : 'inherit', maxWidth: '55%', textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {item.value || '--'}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* ---- TeslaMate Stack ---- */}
              {(stack || !loading) && (
                <div className="tesla-card">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                    <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(5,196,107,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#05C46B' }}>
                      <DockerIcon />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>TeslaMate Stack</div>
                      <div style={{ color: '#86888f', fontSize: 12 }}>Docker Compose managed services</div>
                    </div>
                    {stack?.managed && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div style={{ width: 8, height: 8, borderRadius: '50%', background: stack.running ? '#0BE881' : '#FF6B6B', boxShadow: `0 0 6px ${stack.running ? '#0BE881' : '#FF6B6B'}` }} />
                        <span style={{ color: stack.running ? '#0BE881' : '#FF6B6B', fontSize: 12, fontWeight: 600 }}>
                          {stack.running ? 'Running' : 'Stopped'}
                        </span>
                      </div>
                    )}
                  </div>

                  {!stack ? (
                    <div style={{ textAlign: 'center', padding: '16px 0' }}>
                      <div style={{ color: '#86888f', fontSize: 13 }}>Connect to API first to manage TeslaMate stack</div>
                    </div>
                  ) : !stack.managed ? (
                    <div style={{ textAlign: 'center', padding: '16px 0' }}>
                      <div style={{ color: '#86888f', fontSize: 13, marginBottom: 6 }}>Not installed</div>
                      <div style={{ color: 'rgba(255,255,255,0.35)', fontSize: 12 }}>
                        Run <code style={{ background: 'rgba(255,255,255,0.06)', padding: '2px 6px', borderRadius: 4 }}>tesla teslaMate install</code> from CLI
                      </div>
                    </div>
                  ) : (
                    <>
                      {/* Service cards */}
                      {stack.services.length > 0 && (
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
                          {stack.services.map((svc) => (
                            <div key={svc.name} style={{
                              background: 'rgba(255,255,255,0.03)',
                              border: '1px solid rgba(255,255,255,0.07)',
                              borderRadius: 8, padding: '10px 12px',
                            }}>
                              <div style={{ fontSize: 13, fontWeight: 600, color: '#fff', marginBottom: 2 }}>{svc.name}</div>
                              <div style={{ fontSize: 10, color: '#86888f', marginBottom: 4 }}>{svc.image || ''}</div>
                              <div style={{ fontSize: 12, fontWeight: 500, color: svc.state === 'running' ? '#0BE881' : '#FF6B6B' }}>
                                {svc.state}{svc.status ? ` — ${svc.status}` : ''}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Action buttons */}
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 6, marginBottom: 12 }}>
                        {(['start', 'stop', 'restart', 'update'] as const).map((action) => {
                          const disabled = stackCmd !== null || (action === 'start' && stack.running) || (action === 'stop' && !stack.running);
                          const label = action === 'update' ? 'Update' : action.charAt(0).toUpperCase() + action.slice(1);
                          return (
                            <button
                              key={action}
                              onClick={() => runStackAction(action)}
                              disabled={disabled}
                              className={`tesla-btn${action === 'start' ? '' : ' secondary'}`}
                              style={{ fontSize: 12, padding: '8px 4px' }}
                            >
                              {stackCmd === action ? <Spin /> : label}
                            </button>
                          );
                        })}
                      </div>

                      {/* Quick links */}
                      {stack.ports && (
                        <div style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
                          <a href={`http://localhost:${stack.ports.teslamate}`} target="_blank" rel="noreferrer"
                            style={{ color: '#0FBCF9', fontSize: 13, textDecoration: 'none' }}>
                            TeslaMate UI ↗
                          </a>
                          <a href={`http://localhost:${stack.ports.grafana}`} target="_blank" rel="noreferrer"
                            style={{ color: '#0FBCF9', fontSize: 13, textDecoration: 'none' }}>
                            Grafana ↗
                          </a>
                        </div>
                      )}

                      {/* Logs */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <LogIcon />
                        <span style={{ fontSize: 12, color: '#86888f' }}>Logs</span>
                        <select
                          value={logsService}
                          onChange={(e) => setLogsService(e.target.value)}
                          style={{
                            background: 'rgba(255,255,255,0.05)', color: '#fff',
                            border: '1px solid rgba(255,255,255,0.1)', borderRadius: 4,
                            padding: '3px 6px', fontSize: 11, marginLeft: 4,
                          }}
                        >
                          <option value="">All</option>
                          <option value="teslamate">teslamate</option>
                          <option value="postgres">postgres</option>
                          <option value="grafana">grafana</option>
                          <option value="mosquitto">mosquitto</option>
                        </select>
                        <button onClick={fetchLogs} className="tesla-btn secondary" style={{ fontSize: 11, padding: '4px 10px', marginLeft: 'auto' }}>
                          {showLogs ? 'Refresh' : 'View'}
                        </button>
                      </div>
                      {showLogs && (
                        <pre style={{
                          background: '#0a0b0e', color: '#aaa',
                          fontFamily: 'SF Mono, Menlo, monospace', fontSize: 10,
                          lineHeight: 1.5, borderRadius: 8, padding: 10,
                          maxHeight: 200, overflowY: 'auto', marginTop: 8,
                          whiteSpace: 'pre-wrap', wordBreak: 'break-all',
                        }}>
                          {stackLogs}
                        </pre>
                      )}
                    </>
                  )}
                </div>
              )}

              {/* ---- Providers ---- */}
              {providers.length > 0 && (
                <div className="tesla-card">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
                    <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(15,188,249,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0FBCF9' }}>
                      <PlugIcon />
                    </div>
                    <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Provider Status</div>
                  </div>
                  {providers.map((p, i) => {
                    const color = providerColor(p.status);
                    return (
                      <div key={i} className="stat-row" style={{ borderBottom: i < providers.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none' }}>
                        <div>
                          <div style={{ color: '#ffffff', fontSize: 14 }}>{p.name}</div>
                          {p.message && <div style={{ color: '#86888f', fontSize: 11, marginTop: 2 }}>{p.message}</div>}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <div style={{ width: 7, height: 7, borderRadius: '50%', background: color, boxShadow: `0 0 5px ${color}` }} />
                          <span style={{ color, fontWeight: 600, fontSize: 13, textTransform: 'capitalize' }}>{p.status}</span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* ---- About ---- */}
              <div className="tesla-card" style={{ textAlign: 'center', padding: '24px 16px' }}>
                <div style={{ width: 52, height: 52, borderRadius: '50%', background: '#05C46B', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 14px', boxShadow: '0 4px 16px rgba(5,196,107,0.35)' }}>
                  <svg width={28} height={28} viewBox="0 0 24 24" fill="white">
                    <path d="M12 3l-4 5h3v5H7l5 8 5-8h-4V8h3z"/>
                  </svg>
                </div>
                <div style={{ color: '#ffffff', fontWeight: 700, fontSize: 18, letterSpacing: '-0.3px' }}>Tesla Control</div>
                <div style={{ color: '#86888f', fontSize: 13, marginTop: 4 }}>Companion app for tesla-cli</div>
                <div style={{ color: '#86888f', fontSize: 12, marginTop: 6, opacity: 0.5 }}>v1.0.0</div>
              </div>
            </>
          )}
        </div>

        <IonToast
          isOpen={!!toast}
          message={toast?.message}
          duration={3000}
          color={toast?.color}
          onDidDismiss={() => setToast(null)}
          position="bottom"
        />
      </IonContent>
    </IonPage>
  );
};

export default Settings;
