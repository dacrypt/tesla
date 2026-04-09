import React, { useState, useEffect, useCallback } from 'react';
import {
  IonContent, IonHeader, IonPage, IonToolbar, IonTitle,
  IonRefresher, IonRefresherContent,
} from '@ionic/react';
import { api } from '../api/client';
import { useHistory, useLocation } from 'react-router-dom';
import Analytics from './Analytics';
import VinDecoder from '../components/dossier/VinDecoder';

/* ── Icons ── */
const RefreshIcon = () => (
  <svg width={13} height={13} viewBox="0 0 24 24" fill="currentColor">
    <path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z" />
  </svg>
);
const AlertIcon = () => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor">
    <path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z" />
  </svg>
);
const HistoryIcon = () => (
  <svg width={13} height={13} viewBox="0 0 24 24" fill="currentColor">
    <path d="M13 3a9 9 0 00-9 9H1l3.89 3.89.07.14L9 12H6c0-3.87 3.13-7 7-7s7 3.13 7 7-3.13 7-7 7c-1.93 0-3.68-.79-4.94-2.06l-1.42 1.42A8.954 8.954 0 0013 21a9 9 0 000-18zm-1 5v5l4.28 2.54.72-1.21-3.5-2.08V8H12z" />
  </svg>
);
const QueryIcon = () => (
  <svg width={13} height={13} viewBox="0 0 24 24" fill="currentColor">
    <path d="M9.5 3a6.5 6.5 0 014.98 10.68l4.42 4.42-1.4 1.4-4.42-4.42A6.5 6.5 0 119.5 3zm0 2a4.5 4.5 0 100 9 4.5 4.5 0 000-9z"/>
  </svg>
);
const InfoIcon = () => (
  <svg width={13} height={13} viewBox="0 0 24 24" fill="currentColor">
    <path d="M11 17h2v-6h-2v6zm0-8h2V7h-2v2zm1 13C6.48 22 2 17.52 2 12S6.48 2 12 2s10 4.48 10 10-4.48 10-10 10z"/>
  </svg>
);
const CloseIcon = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor">
    <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z" />
  </svg>
);

function Spin() {
  return (
    <svg width={14} height={14} viewBox="0 0 24 24" fill="none">
      <path d="M12 3a9 9 0 019 9" stroke="#05C46B" strokeWidth={3} strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

/* ── Time formatting ── */
function timeAgo(iso?: string): string {
  if (!iso) return 'never';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

function formatDateTime(iso?: string): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit', hour12: true,
    });
  } catch {
    return iso;
  }
}

/* ── Category labels and order ── */
const CATEGORIES: Record<string, string> = {
  vehiculo: 'Vehículo',
  registro: 'Registro',
  infracciones: 'Infracciones',
  financiero: 'Financiero',
  seguridad: 'Seguridad',
  servicios: 'Servicios',
};

const CAT_ORDER = ['vehiculo', 'registro', 'infracciones', 'seguridad', 'financiero', 'servicios'];

/* ── History Modal ── */
interface HistoryEntry {
  timestamp?: string;
  data_hash?: string;
  changes?: { field: string; old?: string; new?: string }[];
}

interface QueryEntry {
  queried_at?: string;
  status?: string;
  request?: {
    mode?: string;
    source_name?: string;
    url?: string;
    method?: string;
    status_code?: number | null;
    openquery_source?: string;
  };
  response?: {
    error?: string | null;
    normalized_data?: any;
    response_text_excerpt?: string;
    raw_output_excerpt?: string;
    raw_error_excerpt?: string;
  };
}

type SourceDetailTab = 'current' | 'history' | 'queries';

/* ── Shared modal overlay + sheet styles ── */
const modalOverlayStyle: React.CSSProperties = {
  position: 'fixed', inset: 0, zIndex: 999,
  background: 'rgba(0,0,0,0.7)',
};
const modalSheetStyle: React.CSSProperties = {
  width: '100%', maxHeight: '75vh', overflowY: 'auto',
  background: '#18191f', borderRadius: '16px 16px 0 0',
  padding: '20px 16px 32px',
};

/* ── Shared history timeline renderer ── */
function HistoryTimeline({ entries }: { entries: HistoryEntry[] }) {
  return (
    <>
      {entries.map((entry, i) => {
        const hasChanges = entry.changes && entry.changes.length > 0;
        return (
          <div key={i} className="flex-start gap-md" style={{ marginBottom: 14 }}>
            {/* Dot + line */}
            <div className="flex-col" style={{ alignItems: 'center', flexShrink: 0 }}>
              <div style={{
                width: 8, height: 8, borderRadius: '50%', marginTop: 3,
                background: hasChanges ? '#F99716' : '#86888f',
                flexShrink: 0,
              }} />
              {i < entries.length - 1 && (
                <div style={{ width: 1, flex: 1, background: 'rgba(255,255,255,0.06)', marginTop: 4 }} />
              )}
            </div>
            {/* Content */}
            <div className="flex-1" style={{ paddingBottom: 4 }}>
              <div className="text-sm text-secondary mb-xs">{formatDateTime(entry.timestamp)}</div>
              {hasChanges ? (
                <div>
                  <div className="text-sm fw-semi mb-xs" style={{ color: '#F99716' }}>
                    {entry.changes!.length} change{entry.changes!.length !== 1 ? 's' : ''}
                  </div>
                  {entry.changes!.map((ch, ci) => (
                    <div key={ci} className="text-sm text-secondary" style={{ marginBottom: 2 }}>
                      <span style={{ color: '#fff' }}>{ch.field.replace(/_/g, ' ')}</span>
                      {': '}
                      <span style={{ color: 'rgba(255,255,255,0.35)' }}>{ch.old || '—'}</span>
                      {' → '}
                      <span style={{ color: '#0BE881' }}>{ch.new || '—'}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-secondary" style={{ fontStyle: 'italic' }}>No changes</div>
              )}
            </div>
          </div>
        );
      })}
    </>
  );
}

/* ── Shared query list renderer ── */
function QueryList({ entries }: { entries: QueryEntry[] }) {
  return (
    <>
      {entries.map((entry, i) => (
        <div key={i} className="tesla-card" style={{ padding: 12, marginBottom: 10 }}>
          <div className="text-sm text-secondary" style={{ marginBottom: 8 }}>{formatDateTime(entry.queried_at)}</div>
          <div className="text-base fw-semi" style={{ color: '#fff', marginBottom: 6 }}>
            {(entry.request?.method || entry.request?.mode || 'query')} {entry.request?.url || entry.request?.openquery_source || ''}
          </div>
          <div className="text-sm" style={{ color: entry.status === 'ok' ? '#0BE881' : '#FF6B6B', marginBottom: 6 }}>
            {entry.status?.toUpperCase()} {entry.request?.status_code != null ? `· HTTP ${entry.request.status_code}` : ''}
          </div>
          {entry.response?.error && (
            <div className="text-sm" style={{ color: '#FF6B6B', marginBottom: 6, wordBreak: 'break-word' }}>
              {entry.response.error}
            </div>
          )}
          {entry.response?.response_text_excerpt && (
            <pre className="text-xs text-secondary" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0 }}>
              {entry.response.response_text_excerpt.slice(0, 500)}
            </pre>
          )}
          {!entry.response?.response_text_excerpt && entry.response?.raw_output_excerpt && (
            <pre className="text-xs text-secondary" style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0 }}>
              {entry.response.raw_output_excerpt.slice(0, 500)}
            </pre>
          )}
        </div>
      ))}
    </>
  );
}

/* ── Modal header ── */
function ModalHeader({ title, subtitle, onClose }: { title: string; subtitle: string; onClose: () => void }) {
  return (
    <div className="flex-between" style={{ alignItems: 'center', marginBottom: 16 }}>
      <div>
        <div className="text-lg fw-bold" style={{ color: '#fff' }}>{title}</div>
        <div className="text-sm text-secondary" style={{ marginTop: 2 }}>{subtitle}</div>
      </div>
      <button
        onClick={onClose}
        className="icon-btn"
      >
        <CloseIcon />
      </button>
    </div>
  );
}

function HistoryModal({ sourceId, sourceName, onClose }: {
  sourceId: string;
  sourceName: string;
  onClose: () => void;
}) {
  const [entries, setEntries] = useState<HistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getSourceHistory(sourceId, 10)
      .then(data => setEntries([...data].reverse()))
      .catch(e => setError(e?.message || 'Failed to load history'))
      .finally(() => setLoading(false));
  }, [sourceId]);

  return (
    <div className="flex-center" style={{ ...modalOverlayStyle, alignItems: 'flex-end' }} onClick={onClose}>
      <div style={modalSheetStyle} onClick={e => e.stopPropagation()}>
        <ModalHeader title="History" subtitle={sourceName} onClose={onClose} />

        {loading && <div className="flex-center" style={{ padding: 24 }}><Spin /></div>}
        {error && <div className="text-base" style={{ color: '#FF6B6B', textAlign: 'center', padding: 16 }}>{error}</div>}
        {!loading && !error && entries.length === 0 && (
          <div className="text-base text-secondary" style={{ textAlign: 'center', padding: 16 }}>No history yet</div>
        )}
        <HistoryTimeline entries={entries} />
      </div>
    </div>
  );
}

function QueriesModal({ sourceId, sourceName, onClose }: {
  sourceId: string;
  sourceName: string;
  onClose: () => void;
}) {
  const [entries, setEntries] = useState<QueryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getSourceQueries(sourceId, 10)
      .then(data => setEntries([...data].reverse()))
      .catch(e => setError(e?.message || 'Failed to load query audit'))
      .finally(() => setLoading(false));
  }, [sourceId]);

  return (
    <div className="flex-center" style={{ ...modalOverlayStyle, alignItems: 'flex-end' }} onClick={onClose}>
      <div style={modalSheetStyle} onClick={e => e.stopPropagation()}>
        <ModalHeader title="Query Audit" subtitle={sourceName} onClose={onClose} />

        {loading && <div className="flex-center" style={{ padding: 24 }}><Spin /></div>}
        {error && <div className="text-base" style={{ color: '#FF6B6B', textAlign: 'center', padding: 16 }}>{error}</div>}
        {!loading && !error && entries.length === 0 && (
          <div className="text-base text-secondary" style={{ textAlign: 'center', padding: 16 }}>No query audit yet</div>
        )}
        <QueryList entries={entries} />
      </div>
    </div>
  );
}

function SourceDetailModal({
  sourceId,
  sourceName,
  sourceData,
  initialTab,
  onClose,
}: {
  sourceId: string;
  sourceName: string;
  sourceData: any;
  initialTab: SourceDetailTab;
  onClose: () => void;
}) {
  const [tab, setTab] = useState<SourceDetailTab>(initialTab);
  const [historyEntries, setHistoryEntries] = useState<HistoryEntry[]>([]);
  const [queryEntries, setQueryEntries] = useState<QueryEntry[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [loadingQueries, setLoadingQueries] = useState(true);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [queryError, setQueryError] = useState<string | null>(null);

  useEffect(() => {
    api.getSourceHistory(sourceId, 10)
      .then(data => setHistoryEntries([...data].reverse()))
      .catch(e => setHistoryError(e?.message || 'Failed to load history'))
      .finally(() => setLoadingHistory(false));
    api.getSourceQueries(sourceId, 10)
      .then(data => setQueryEntries([...data].reverse()))
      .catch(e => setQueryError(e?.message || 'Failed to load query audit'))
      .finally(() => setLoadingQueries(false));
  }, [sourceId]);

  const tabButton = (key: SourceDetailTab, label: string) => (
    <button
      type="button"
      onClick={() => setTab(key)}
      style={{
        flex: 1,
        background: tab === key ? 'rgba(5,196,107,0.18)' : 'rgba(255,255,255,0.06)',
        border: `1px solid ${tab === key ? 'rgba(5,196,107,0.45)' : 'rgba(255,255,255,0.12)'}`,
        borderRadius: 10,
        padding: '12px 14px',
        color: tab === key ? '#05C46B' : '#86888f',
        fontSize: 13,
        fontWeight: 700,
        cursor: 'pointer',
      }}
    >
      {label}
    </button>
  );

  return (
    <div
      className="flex-center"
      style={{ ...modalOverlayStyle, alignItems: 'flex-end' }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%', maxHeight: '80vh', overflowY: 'auto',
          background: '#20242d', borderRadius: '18px 18px 0 0',
          borderTop: '1px solid rgba(255,255,255,0.08)',
          boxShadow: '0 -20px 60px rgba(0,0,0,0.45)',
          padding: '20px 16px 32px',
        }}
        onClick={e => e.stopPropagation()}
      >
        <div style={{ position: 'sticky', top: 0, zIndex: 2, background: '#20242d', paddingBottom: 12 }}>
          <ModalHeader title={sourceName} subtitle={sourceId} onClose={onClose} />
          <div className="flex-start gap-sm" style={{ marginBottom: 16 }}>
            {tabButton('current', 'Current')}
            {tabButton('history', 'History')}
            {tabButton('queries', 'Query Audit')}
          </div>
        </div>

        {tab === 'current' && (
          <div className="tesla-card" style={{ padding: 16, background: 'rgba(255,255,255,0.04)' }}>
            {sourceData?.error ? (
              <div className="text-base" style={{ color: '#FF6B6B', wordBreak: 'break-word' }}>{sourceData.error}</div>
            ) : sourceData?.data ? (
              <SourceData data={sourceData.data} />
            ) : (
              <div className="text-base text-secondary" style={{ textAlign: 'center', padding: 16 }}>No current data</div>
            )}
          </div>
        )}

        {tab === 'history' && (
          <>
            {loadingHistory && <div className="flex-center" style={{ padding: 24 }}><Spin /></div>}
            {historyError && <div className="text-base" style={{ color: '#FF6B6B', textAlign: 'center', padding: 16 }}>{historyError}</div>}
            {!loadingHistory && !historyError && historyEntries.length === 0 && (
              <div className="text-base text-secondary" style={{ textAlign: 'center', padding: 16 }}>No history yet</div>
            )}
            <HistoryTimeline entries={historyEntries} />
          </>
        )}

        {tab === 'queries' && (
          <>
            {loadingQueries && <div className="flex-center" style={{ padding: 24 }}><Spin /></div>}
            {queryError && <div className="text-base" style={{ color: '#FF6B6B', textAlign: 'center', padding: 16 }}>{queryError}</div>}
            {!loadingQueries && !queryError && queryEntries.length === 0 && (
              <div className="text-base text-secondary" style={{ textAlign: 'center', padding: 16 }}>No query audit yet</div>
            )}
            <QueryList entries={queryEntries} />
          </>
        )}
      </div>
    </div>
  );
}

/* ── Source data renderer ── */
function SourceData({ data }: { data: any }) {
  if (!data) return (
    <div className="text-base text-secondary" style={{ textAlign: 'center', padding: 8 }}>No data</div>
  );
  if (typeof data === 'string') return <div className="text-base" style={{ color: '#fff' }}>{data}</div>;

  // Special: recalls array
  if (Array.isArray(data.recalls)) {
    return (
      <>
        <div className="text-base text-secondary" style={{ marginBottom: 6 }}>{data.recalls.length} recalls found</div>
        {data.recalls.slice(0, 5).map((r: any, i: number) => (
          <div key={i} style={{
            marginBottom: 8, paddingBottom: 8,
            borderBottom: i < Math.min(data.recalls.length, 5) - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none',
          }}>
            <div className="text-base fw-medium" style={{ color: '#fff' }}>{r.component || r.summary?.slice(0, 60)}</div>
            <div className="text-xs text-secondary" style={{ marginTop: 2 }}>
              {typeof r.summary === 'string' ? r.summary.slice(0, 100) : ''}
            </div>
          </div>
        ))}
      </>
    );
  }

  // Special: estaciones array
  if (Array.isArray(data.estaciones)) {
    return (
      <>
        <div className="text-base text-secondary" style={{ marginBottom: 6 }}>{data.total || data.estaciones.length} estaciones</div>
        {data.estaciones.slice(0, 8).map((s: any, i: number) => (
          <div key={i} style={{ marginBottom: 6, fontSize: 11 }}>
            <div className="fw-medium" style={{ color: '#fff' }}>{s.estaci_n || s.nombre || s.tipo_de_estacion}</div>
            <div className="text-secondary">{s.ciudad} · {s.tipo || ''} · {s.horario || ''}</div>
          </div>
        ))}
      </>
    );
  }

  // Generic key-value
  const entries = Object.entries(data).filter(([k, v]) => v != null && v !== '' && k !== 'audit' && !k.startsWith('_'));
  return (
    <>
      {entries.slice(0, 20).map(([k, v]) => {
        if (typeof v === 'object' && v !== null) return null;
        const display = typeof v === 'boolean' ? (v ? '✓ Sí' : '✗ No') : String(v);
        return (
          <div key={k} className="flex-between text-sm" style={{ padding: '3px 0' }}>
            <span className="text-secondary">{k.replace(/_/g, ' ')}</span>
            <span className="fw-medium" style={{
              color: '#fff', maxWidth: '55%',
              textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>{display}</span>
          </div>
        );
      })}
    </>
  );
}

/* ── Source Card ── */
function SourceCard({ src, sd, isRefreshing, onRefresh, onHistory, onQueries, onCurrent }: {
  src: any;
  sd: any;
  isRefreshing: boolean;
  onRefresh: () => void;
  onHistory: () => void;
  onQueries: () => void;
  onCurrent: () => void;
}) {
  const hasError = sd?.error || src.error;
  const errorMsg = typeof hasError === 'string' ? hasError : 'Error';
  const changeCount = sd?.changes?.length || 0;
  const queriedAt = sd?.refreshed_at;

  return (
    <div className="tesla-card" style={{ padding: '12px 14px', marginBottom: 8 }}>
      {/* Header row */}
      <div className="flex-between" style={{ alignItems: 'flex-start', marginBottom: 6 }}>
        {/* Title + timestamp */}
        <div className="flex-1" style={{ minWidth: 0 }}>
          <div className="flex-start gap-sm" style={{ flexWrap: 'wrap' }}>
            <span className="text-lg fw-semi" style={{ color: '#fff' }}>{src.name}</span>
            {/* Change badge */}
            {changeCount > 0 && (
              <span className="badge badge-orange">
                {changeCount} change{changeCount !== 1 ? 's' : ''}
              </span>
            )}
          </div>
          {/* Timestamp */}
          {queriedAt ? (
            <div style={{ marginTop: 3 }}>
              <div className="text-sm" style={{ color: hasError ? '#FF6B6B' : src.stale ? '#F99716' : '#86888f' }}>
                {hasError ? errorMsg.slice(0, 80) : (
                  <>
                    <span className="fw-medium" style={{ color: '#fff' }}>{formatDateTime(queriedAt)}</span>
                    <span className="text-secondary"> &middot; {timeAgo(queriedAt)}</span>
                  </>
                )}
              </div>
            </div>
          ) : (
            <div className="text-sm" style={{ color: hasError ? '#FF6B6B' : '#86888f', marginTop: 3 }}>
              {hasError ? errorMsg.slice(0, 80) : 'Not loaded yet'}
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div className="flex-start gap-sm" style={{ flexShrink: 0, marginLeft: 8, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
          <button type="button" onClick={onCurrent} title="View current data" className="source-action-btn">
            <InfoIcon /> Current
          </button>
          <button type="button" onClick={onQueries} title="View query audit" className="source-action-btn">
            <QueryIcon /> Audit
          </button>
          <button type="button" onClick={onHistory} title="View history" className="source-action-btn">
            <HistoryIcon /> History
          </button>
          <button type="button" onClick={onRefresh} disabled={isRefreshing} title="Refresh source" className="source-action-btn">
            {isRefreshing ? <Spin /> : <RefreshIcon />} Refresh
          </button>
        </div>
      </div>

      {/* Error display */}
      {hasError && (
        <div style={{
          marginTop: 4, padding: '8px 10px',
          background: 'rgba(255,107,107,0.08)', border: '1px solid rgba(255,107,107,0.2)',
          borderRadius: 8,
        }}>
          <div className="text-sm" style={{ color: '#FF6B6B', wordBreak: 'break-word' }}>
            {errorMsg.length > 200 ? errorMsg.slice(0, 200) + '…' : errorMsg}
          </div>
        </div>
      )}

      {/* Data */}
      {!hasError && sd?.data && (
        <div style={{ marginTop: 4 }}>
          <SourceData data={sd.data} />
        </div>
      )}

      {/* Changes detected */}
      {changeCount > 0 && sd?.changes && (
        <div style={{
          marginTop: 8, padding: '8px 10px',
          background: 'rgba(249,151,22,0.08)', border: '1px solid rgba(249,151,22,0.15)', borderRadius: 8,
        }}>
          <div className="text-xs fw-semi" style={{ color: '#F99716', marginBottom: 4 }}>Cambios detectados</div>
          {sd.changes.map((ch: any, ci: number) => (
            <div key={ci} className="text-xs text-secondary" style={{ marginBottom: 2 }}>
              <span style={{ color: '#fff' }}>{ch.field}</span>
              {': '}
              <span style={{ color: 'rgba(255,255,255,0.35)' }}>{ch.old || '—'}</span>
              {' → '}
              <span style={{ color: '#0BE881' }}>{ch.new || '—'}</span>
            </div>
          ))}
        </div>
      )}

      {/* Audit PDF link */}
      {src.uses_playwright && sd?.data && (
        <button
          onClick={async () => {
            try {
              const audits = await api.getSourceAudits(src.id);
              if (audits.length > 0) {
                const baseUrl = (api as any).getBaseUrl?.() || '';
                window.open(`${baseUrl}/api/sources/${src.id}/audit/${audits[0].filename}`, '_blank');
              }
            } catch { /* */ }
          }}
          style={{
            marginTop: 6, background: 'none', border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: 6, padding: '4px 10px', cursor: 'pointer',
            color: '#86888f', fontSize: 10, display: 'flex', alignItems: 'center', gap: 4,
          }}
        >
          Ver evidencia PDF
        </button>
      )}
    </div>
  );
}

/* ── Main Page ── */
const Dossier: React.FC = () => {
  const [sources, setSources] = useState<any[]>([]);
  const [sourceData, setSourceData] = useState<Record<string, any>>({});
  const [missingAuth, setMissingAuth] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState<string | null>(null);
  const [sourceConfig, setSourceConfig] = useState<any>({});
  const [cedula, setCedula] = useState('');
  const [cedulaDirty, setCedulaDirty] = useState(false);
  const [sourceModal, setSourceModal] = useState<{ id: string; name: string; tab: SourceDetailTab } | null>(null);
  const history = useHistory();
  const location = useLocation();

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const [srcList, authMissing, cfgData] = await Promise.allSettled([
        api.getSources(),
        api.getMissingAuth(),
        api.getSourceConfig(),
      ]);
      const list = srcList.status === 'fulfilled' ? srcList.value : [];
      setSources(list);
      if (authMissing.status === 'fulfilled') setMissingAuth(authMissing.value);
      if (cfgData.status === 'fulfilled') {
        setSourceConfig(cfgData.value);
        setCedula(cfgData.value.cedula || '');
      }

      // Fetch cached data for all sources that have data
      const dataPromises = list
        .filter((s: any) => s.has_data)
        .map((s: any) => api.getSource(s.id).then(d => ({ id: s.id, ...d })).catch(() => null));
      const results = await Promise.all(dataPromises);
      const dataMap: Record<string, any> = {};
      for (const r of results) {
        if (r) dataMap[r.id] = r;
      }
      setSourceData(dataMap);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  useEffect(() => {
    if (!sources.length) return;
    const params = new URLSearchParams(location.search);
    const sourceId = params.get('source');
    const wantsHistory = params.get('history') === '1';
    const wantsQueries = params.get('queries') === '1';
    if (!sourceId) return;
    const source = sources.find((item: any) => item.id === sourceId);
    if (source && wantsHistory && !sourceModal) {
      setSourceModal({ id: source.id, name: source.name, tab: 'history' });
    }
    if (source && wantsQueries && !sourceModal) {
      setSourceModal({ id: source.id, name: source.name, tab: 'queries' });
    }
  }, [sources, sourceModal, location.search]);

  const refreshSource = async (sourceId: string) => {
    setRefreshing(sourceId);
    try {
      await api.refreshSource(sourceId);
      const [fresh, newList] = await Promise.all([
        api.getSource(sourceId),
        api.getSources(),
      ]);
      setSourceData(prev => ({ ...prev, [sourceId]: { id: sourceId, ...fresh } }));
      setSources(newList);
    } catch { /* */ } finally {
      setRefreshing(null);
    }
  };

  const doRefresh = async (event: CustomEvent) => {
    await fetchAll();
    (event.target as HTMLIonRefresherElement).complete();
  };

  // Group sources by category
  const grouped: Record<string, any[]> = {};
  for (const src of sources) {
    const cat = src.category || 'other';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(src);
  }

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700 }}>Info</IonTitle>
        </IonToolbar>
      </IonHeader>

      <IonContent>
        <IonRefresher slot="fixed" onIonRefresh={doRefresh}>
          <IonRefresherContent />
        </IonRefresher>

        <div className="page-pad">
          {/* ── Missing Auth Banner ── */}
          {missingAuth.length > 0 && (
            <div style={{
              background: 'rgba(249,151,22,0.08)', border: '1px solid rgba(249,151,22,0.2)',
              borderRadius: 12, padding: '12px 16px', marginBottom: 14,
            }}>
              <div className="flex-start gap-sm mb-sm">
                <div style={{ color: '#F99716' }}><AlertIcon /></div>
                <span className="text-lg fw-semi" style={{ color: '#F99716' }}>Authentication needed</span>
              </div>
              {missingAuth.map((m, i) => (
                <div key={i} className="text-base text-secondary" style={{ marginBottom: 4 }}>
                  {m.message} <span style={{ color: 'rgba(255,255,255,0.3)' }}>({m.name})</span>
                </div>
              ))}
              <button
                onClick={() => history.push('/settings')}
                className="tesla-btn"
                style={{ marginTop: 8, fontSize: 12, padding: '8px 16px', width: '100%' }}
              >
                Connect accounts →
              </button>
            </div>
          )}

          {/* ── Owner Config (cedula) ── */}
          {!loading && !sourceConfig.cedula && (
            <div className="tesla-card" style={{ padding: '12px 14px', marginBottom: 14 }}>
              <div className="text-lg fw-semi mb-sm" style={{ color: '#fff' }}>Datos del propietario</div>
              <div className="text-sm text-secondary mb-sm">
                Tu cédula es necesaria para consultar multas (SIMIT), antecedentes, y otros servicios.
              </div>
              <div className="flex-start gap-sm">
                <input
                  type="text"
                  value={cedula}
                  onChange={(e) => { setCedula(e.target.value); setCedulaDirty(true); }}
                  placeholder="Número de cédula"
                  className="tesla-input flex-1"
                  style={{ fontSize: 13 }}
                />
                <button
                  onClick={async () => {
                    if (!cedula.trim()) return;
                    await api.updateSourceConfig({ cedula: cedula.trim() });
                    setCedulaDirty(false);
                    fetchAll();
                  }}
                  disabled={!cedulaDirty || !cedula.trim()}
                  className="tesla-btn"
                  style={{ fontSize: 12, padding: '8px 16px', flexShrink: 0 }}
                >
                  Guardar
                </button>
              </div>
            </div>
          )}

          {loading ? (
            <div className="loading-center"><Spin /></div>
          ) : (
            <>
              {/* ── VIN Decoder (visual) ── */}
              {sourceData['vin.decode']?.data && (
                <VinDecoder data={sourceData['vin.decode'].data} />
              )}

              {/* ── Sources by category ── */}
              {CAT_ORDER.filter(cat => grouped[cat]).map(cat => (
                <div key={cat}>
                  {/* Category header */}
                  <div className="flex-center gap-md" style={{ margin: '18px 0 8px', padding: '0 2px' }}>
                    <div style={{ height: 1, flex: 1, background: 'rgba(255,255,255,0.06)' }} />
                    <span className="section-label">
                      {CATEGORIES[cat] || cat}
                    </span>
                    <div style={{ height: 1, flex: 1, background: 'rgba(255,255,255,0.06)' }} />
                  </div>

                  {/* Source cards */}
                  {grouped[cat].map((src: any) => (
                    <SourceCard
                      key={src.id}
                      src={src}
                      sd={sourceData[src.id]}
                      isRefreshing={refreshing === src.id}
                      onRefresh={() => refreshSource(src.id)}
                      onCurrent={() => setSourceModal({ id: src.id, name: src.name, tab: 'current' })}
                      onHistory={() => setSourceModal({ id: src.id, name: src.name, tab: 'history' })}
                      onQueries={() => setSourceModal({ id: src.id, name: src.name, tab: 'queries' })}
                    />
                  ))}
                </div>
              ))}

              {/* ── Analytics (embedded) ── */}
              <div className="flex-center gap-md" style={{ margin: '18px 0 8px' }}>
                <div style={{ height: 1, flex: 1, background: 'rgba(255,255,255,0.06)' }} />
                <span className="section-label">Analytics</span>
                <div style={{ height: 1, flex: 1, background: 'rgba(255,255,255,0.06)' }} />
              </div>
              <div style={{ margin: '0 -16px' }}>
                <Analytics embedded />
              </div>
            </>
          )}
        </div>

        {/* ── Source Detail Modal ── */}
        {sourceModal && (
          <SourceDetailModal
            sourceId={sourceModal.id}
            sourceName={sourceModal.name}
            sourceData={sourceData[sourceModal.id]}
            initialTab={sourceModal.tab}
            onClose={() => setSourceModal(null)}
          />
        )}
      </IonContent>
    </IonPage>
  );
};

export default Dossier;
