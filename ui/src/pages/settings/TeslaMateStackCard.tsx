import React, { useState } from 'react';
import { api, describeError, StackStatus } from '../../api/client';
import Spinner from '../../components/icons/Spinner';
import { DockerIcon, LogIcon } from './icons';
import type { Notify } from './types';

interface Props {
  stack: StackStatus | null;
  onStackChange: (stack: StackStatus) => void;
  notify: Notify;
}

/** Docker Compose managed TeslaMate stack: services, start/stop/update, logs. */
const TeslaMateStackCard: React.FC<Props> = ({ stack, onStackChange, notify }) => {
  const [stackCmd, setStackCmd] = useState<string | null>(null);
  const [stackLogs, setStackLogs] = useState<string>('');
  const [logsService, setLogsService] = useState('');
  const [showLogs, setShowLogs] = useState(false);

  const runStackAction = async (action: 'start' | 'stop' | 'restart' | 'update') => {
    setStackCmd(action);
    try {
      if (action === 'start') await api.stackStart();
      else if (action === 'stop') await api.stackStop();
      else if (action === 'restart') await api.stackRestart();
      else if (action === 'update') await api.stackUpdate();
      notify(`Stack ${action} OK`, 'success');
      setTimeout(async () => {
        try {
          const st = await api.getStackStatus();
          onStackChange(st);
        } catch { /* ignore */ }
      }, 2500);
    } catch (e: unknown) {
      notify(`Stack ${action} failed: ${describeError(e)}`, 'danger');
    } finally {
      setStackCmd(null);
    }
  };

  const fetchLogs = async () => {
    try {
      const data = await api.getStackLogs(logsService || undefined);
      setStackLogs(data.logs || '(no output)');
      setShowLogs(true);
    } catch (e: unknown) {
      setStackLogs(`Error: ${describeError(e)}`);
      setShowLogs(true);
    }
  };

  return (
    <div className="tesla-card">
      <div className="flex-center gap-sm" style={{ marginBottom: 14 }}>
        <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(5,196,107,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#05C46B' }}>
          <DockerIcon />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>TeslaMate Stack</div>
          <div style={{ color: '#86888f', fontSize: 12 }}>Docker Compose managed services</div>
        </div>
        {stack?.managed && (
          <div className="flex-center gap-xs">
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
                  {stackCmd === action ? <Spinner /> : label}
                </button>
              );
            })}
          </div>

          {/* Quick links */}
          {stack.ports && (
            <div className="flex-center gap-md" style={{ marginBottom: 12 }}>
              <a href={`${window.location.protocol}//${window.location.hostname}:${stack.ports.teslamate}`} target="_blank" rel="noreferrer"
                style={{ color: '#0FBCF9', fontSize: 13, textDecoration: 'none' }}>
                TeslaMate UI ↗
              </a>
              <a href={`${window.location.protocol}//${window.location.hostname}:${stack.ports.grafana}`} target="_blank" rel="noreferrer"
                style={{ color: '#0FBCF9', fontSize: 13, textDecoration: 'none' }}>
                Grafana ↗
              </a>
            </div>
          )}

          {/* Logs */}
          <div className="flex-center gap-xs">
            <LogIcon />
            <span className="text-secondary text-base">Logs</span>
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
  );
};

export default TeslaMateStackCard;
