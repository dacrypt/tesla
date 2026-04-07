import React, { useState, useEffect, useCallback } from 'react';
import {
  IonContent, IonHeader, IonPage, IonToolbar, IonTitle,
  IonRefresher, IonRefresherContent,
} from '@ionic/react';
import { api } from '../api/client';
import { useHistory } from 'react-router-dom';
import Analytics from './Analytics';

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
    <div
      style={{
        position: 'fixed', inset: 0, zIndex: 999,
        background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'flex-end',
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%', maxHeight: '75vh', overflowY: 'auto',
          background: '#18191f', borderRadius: '16px 16px 0 0',
          padding: '20px 16px 32px',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: '#fff' }}>History</div>
            <div style={{ fontSize: 11, color: '#86888f', marginTop: 2 }}>{sourceName}</div>
          </div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', color: '#86888f', cursor: 'pointer', padding: 4 }}
          >
            <CloseIcon />
          </button>
        </div>

        {loading && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}><Spin /></div>
        )}
        {error && (
          <div style={{ color: '#FF6B6B', fontSize: 12, textAlign: 'center', padding: 16 }}>{error}</div>
        )}
        {!loading && !error && entries.length === 0 && (
          <div style={{ color: '#86888f', fontSize: 12, textAlign: 'center', padding: 16 }}>No history yet</div>
        )}

        {/* Timeline */}
        {entries.map((entry, i) => {
          const hasChanges = entry.changes && entry.changes.length > 0;
          return (
            <div key={i} style={{ display: 'flex', gap: 12, marginBottom: 14 }}>
              {/* Dot + line */}
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
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
              <div style={{ flex: 1, paddingBottom: 4 }}>
                <div style={{ fontSize: 11, color: '#86888f', marginBottom: 4 }}>
                  {formatDateTime(entry.timestamp)}
                </div>
                {hasChanges ? (
                  <div>
                    <div style={{ fontSize: 11, color: '#F99716', fontWeight: 600, marginBottom: 4 }}>
                      {entry.changes!.length} change{entry.changes!.length !== 1 ? 's' : ''}
                    </div>
                    {entry.changes!.map((ch, ci) => (
                      <div key={ci} style={{ fontSize: 11, color: '#86888f', marginBottom: 2 }}>
                        <span style={{ color: '#fff' }}>{ch.field.replace(/_/g, ' ')}</span>
                        {': '}
                        <span style={{ color: 'rgba(255,255,255,0.35)' }}>{ch.old || '—'}</span>
                        {' → '}
                        <span style={{ color: '#0BE881' }}>{ch.new || '—'}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: 11, color: '#86888f', fontStyle: 'italic' }}>No changes</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Source data renderer ── */
function SourceData({ data }: { data: any }) {
  if (!data) return (
    <div style={{ color: '#86888f', fontSize: 12, textAlign: 'center', padding: 8 }}>Sin datos</div>
  );
  if (typeof data === 'string') return <div style={{ color: '#fff', fontSize: 12 }}>{data}</div>;

  // Special: recalls array
  if (Array.isArray(data.recalls)) {
    return (
      <>
        <div style={{ fontSize: 12, color: '#86888f', marginBottom: 6 }}>{data.recalls.length} recalls found</div>
        {data.recalls.slice(0, 5).map((r: any, i: number) => (
          <div key={i} style={{
            marginBottom: 8, paddingBottom: 8,
            borderBottom: i < Math.min(data.recalls.length, 5) - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none',
          }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: '#fff' }}>{r.component || r.summary?.slice(0, 60)}</div>
            <div style={{ fontSize: 10, color: '#86888f', marginTop: 2 }}>
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
        <div style={{ fontSize: 12, color: '#86888f', marginBottom: 6 }}>{data.total || data.estaciones.length} estaciones</div>
        {data.estaciones.slice(0, 8).map((s: any, i: number) => (
          <div key={i} style={{ marginBottom: 6, fontSize: 11 }}>
            <div style={{ color: '#fff', fontWeight: 500 }}>{s.estaci_n || s.nombre || s.tipo_de_estacion}</div>
            <div style={{ color: '#86888f' }}>{s.ciudad} · {s.tipo || ''} · {s.horario || ''}</div>
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
          <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: 11 }}>
            <span style={{ color: '#86888f' }}>{k.replace(/_/g, ' ')}</span>
            <span style={{
              color: '#fff', fontWeight: 500, maxWidth: '55%',
              textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            }}>{display}</span>
          </div>
        );
      })}
    </>
  );
}

/* ── Source Card ── */
function SourceCard({ src, sd, isRefreshing, onRefresh, onHistory }: {
  src: any;
  sd: any;
  isRefreshing: boolean;
  onRefresh: () => void;
  onHistory: () => void;
}) {
  const hasError = sd?.error || src.error;
  const errorMsg = typeof hasError === 'string' ? hasError : 'Error';
  const changeCount = sd?.changes?.length || 0;
  const queriedAt = sd?.refreshed_at;

  return (
    <div className="tesla-card" style={{ padding: '12px 14px', marginBottom: 8 }}>
      {/* Header row */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 6 }}>
        {/* Title + timestamp */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13, fontWeight: 600, color: '#fff' }}>{src.name}</span>
            {/* Change badge */}
            {changeCount > 0 && (
              <span style={{
                background: 'rgba(249,151,22,0.15)', border: '1px solid rgba(249,151,22,0.3)',
                borderRadius: 10, padding: '1px 7px', fontSize: 10, color: '#F99716', fontWeight: 600,
              }}>
                {changeCount} change{changeCount !== 1 ? 's' : ''}
              </span>
            )}
          </div>
          {/* Timestamp — prominently shown */}
          {queriedAt ? (
            <div style={{ marginTop: 3 }}>
              <div style={{ fontSize: 11, color: hasError ? '#FF6B6B' : src.stale ? '#F99716' : '#86888f' }}>
                {hasError ? errorMsg.slice(0, 80) : (
                  <>
                    <span style={{ color: '#fff', fontWeight: 500 }}>{formatDateTime(queriedAt)}</span>
                    <span style={{ color: '#86888f' }}> &middot; {timeAgo(queriedAt)}</span>
                  </>
                )}
              </div>
            </div>
          ) : (
            <div style={{ fontSize: 11, color: hasError ? '#FF6B6B' : '#86888f', marginTop: 3 }}>
              {hasError ? errorMsg.slice(0, 80) : 'Not loaded yet'}
            </div>
          )}
        </div>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 6, flexShrink: 0, marginLeft: 8 }}>
          {/* History button */}
          <button
            onClick={onHistory}
            title="View history"
            style={{
              background: 'none', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6,
              padding: '4px 8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
              color: '#86888f', fontSize: 10,
            }}
          >
            <HistoryIcon />
          </button>
          {/* Refresh button */}
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            title="Refresh source"
            style={{
              background: 'none', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6,
              padding: '4px 8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
              color: '#86888f', fontSize: 10,
            }}
          >
            {isRefreshing ? <Spin /> : <RefreshIcon />}
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
          <div style={{ fontSize: 11, color: '#FF6B6B', wordBreak: 'break-word' }}>
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
          <div style={{ fontSize: 10, fontWeight: 600, color: '#F99716', marginBottom: 4 }}>Cambios detectados</div>
          {sd.changes.map((ch: any, ci: number) => (
            <div key={ci} style={{ fontSize: 10, color: '#86888f', marginBottom: 2 }}>
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
  const [historyModal, setHistoryModal] = useState<{ id: string; name: string } | null>(null);
  const history = useHistory();

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
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                <div style={{ color: '#F99716' }}><AlertIcon /></div>
                <span style={{ color: '#F99716', fontWeight: 600, fontSize: 13 }}>Authentication needed</span>
              </div>
              {missingAuth.map((m, i) => (
                <div key={i} style={{ color: '#86888f', fontSize: 12, marginBottom: 4 }}>
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
              <div style={{ fontSize: 13, fontWeight: 600, color: '#fff', marginBottom: 8 }}>Datos del propietario</div>
              <div style={{ color: '#86888f', fontSize: 11, marginBottom: 8 }}>
                Tu cédula es necesaria para consultar multas (SIMIT), antecedentes, y otros servicios.
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  type="text"
                  value={cedula}
                  onChange={(e) => { setCedula(e.target.value); setCedulaDirty(true); }}
                  placeholder="Número de cédula"
                  className="tesla-input"
                  style={{ flex: 1, fontSize: 13 }}
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
              {/* ── Sources by category ── */}
              {CAT_ORDER.filter(cat => grouped[cat]).map(cat => (
                <div key={cat}>
                  {/* Category header */}
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '18px 0 8px', padding: '0 2px' }}>
                    <div style={{ height: 1, flex: 1, background: 'rgba(255,255,255,0.06)' }} />
                    <span style={{
                      fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
                      letterSpacing: '0.12em', color: 'rgba(255,255,255,0.25)',
                    }}>
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
                      onHistory={() => setHistoryModal({ id: src.id, name: src.name })}
                    />
                  ))}
                </div>
              ))}

              {/* ── Analytics (embedded) ── */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '18px 0 8px' }}>
                <div style={{ height: 1, flex: 1, background: 'rgba(255,255,255,0.06)' }} />
                <span style={{
                  fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
                  letterSpacing: '0.12em', color: 'rgba(255,255,255,0.25)',
                }}>
                  Analytics
                </span>
                <div style={{ height: 1, flex: 1, background: 'rgba(255,255,255,0.06)' }} />
              </div>
              <div style={{ margin: '0 -16px' }}>
                <Analytics embedded />
              </div>
            </>
          )}
        </div>

        {/* ── History Modal ── */}
        {historyModal && (
          <HistoryModal
            sourceId={historyModal.id}
            sourceName={historyModal.name}
            onClose={() => setHistoryModal(null)}
          />
        )}
      </IonContent>
    </IonPage>
  );
};

export default Dossier;
