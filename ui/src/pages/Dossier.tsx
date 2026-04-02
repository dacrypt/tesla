import React, { useState, useEffect } from 'react';
import { IonContent, IonHeader, IonPage, IonToolbar, IonTitle, IonRefresher, IonRefresherContent } from '@ionic/react';
import { api } from '../api/client';
import { useHistory } from 'react-router-dom';
import Analytics from './Analytics';

/* ── Icons ── */
const RefreshIcon = () => <svg width={14} height={14} viewBox="0 0 24 24" fill="currentColor"><path d="M17.65 6.35A7.958 7.958 0 0012 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08A5.99 5.99 0 0112 18c-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>;
const AlertIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z"/></svg>;

function Spin() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none">
      <path d="M12 3a9 9 0 019 9" stroke="#05C46B" strokeWidth={3} strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

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

/* ── Source data renderer ── */
function SourceData({ data }: { data: any }) {
  if (!data) return <div style={{ color: '#86888f', fontSize: 12, textAlign: 'center', padding: 8 }}>Sin datos</div>;
  if (typeof data === 'string') return <div style={{ color: '#fff', fontSize: 12 }}>{data}</div>;

  // Render key-value pairs for objects
  const entries = Object.entries(data).filter(([k, v]) => v != null && v !== '' && k !== 'audit' && !k.startsWith('_'));

  // Special: if it has 'recalls' array
  if (Array.isArray(data.recalls)) {
    return (
      <>
        <div style={{ fontSize: 12, color: '#86888f', marginBottom: 6 }}>{data.recalls.length} recalls found</div>
        {data.recalls.slice(0, 5).map((r: any, i: number) => (
          <div key={i} style={{ marginBottom: 8, paddingBottom: 8, borderBottom: i < Math.min(data.recalls.length, 5) - 1 ? '1px solid rgba(255,255,255,0.05)' : 'none' }}>
            <div style={{ fontSize: 12, fontWeight: 500, color: '#fff' }}>{r.component || r.summary?.slice(0, 60)}</div>
            <div style={{ fontSize: 10, color: '#86888f', marginTop: 2 }}>{typeof r.summary === 'string' ? r.summary.slice(0, 100) : ''}</div>
          </div>
        ))}
      </>
    );
  }

  // Special: if it has 'estaciones' array
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
  return (
    <>
      {entries.slice(0, 20).map(([k, v]) => {
        if (typeof v === 'object' && v !== null) return null; // Skip nested objects
        const display = typeof v === 'boolean' ? (v ? '✓ Sí' : '✗ No') : String(v);
        return (
          <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: 11 }}>
            <span style={{ color: '#86888f' }}>{k.replace(/_/g, ' ')}</span>
            <span style={{ color: '#fff', fontWeight: 500, maxWidth: '55%', textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{display}</span>
          </div>
        );
      })}
    </>
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
  const history = useHistory();

  const fetchAll = async () => {
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
  };

  useEffect(() => { fetchAll(); }, []);

  const refreshSource = async (sourceId: string) => {
    setRefreshing(sourceId);
    try {
      const result = await api.refreshSource(sourceId);
      // Update the cached data
      const fresh = await api.getSource(sourceId);
      setSourceData(prev => ({ ...prev, [sourceId]: fresh }));
      // Update source list
      const newList = await api.getSources();
      setSources(newList);
    } catch { /* */ }
    finally { setRefreshing(null); }
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
                    <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'rgba(255,255,255,0.25)' }}>
                      {CATEGORIES[cat] || cat}
                    </span>
                    <div style={{ height: 1, flex: 1, background: 'rgba(255,255,255,0.06)' }} />
                  </div>

                  {/* Source cards */}
                  {grouped[cat].map((src: any) => {
                    const sd = sourceData[src.id];
                    const hasError = sd?.error || src.error;
                    const isRefreshing = refreshing === src.id;

                    return (
                      <div key={src.id} className="tesla-card" style={{ padding: '12px 14px', marginBottom: 8 }}>
                        {/* Header */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: sd?.data ? 8 : 0 }}>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 600, color: '#fff' }}>{src.name}</div>
                            <div style={{ fontSize: 10, color: hasError ? '#FF6B6B' : src.stale ? '#F99716' : '#86888f', marginTop: 1 }}>
                              {hasError ? (typeof hasError === 'string' ? hasError.slice(0, 60) : 'Error')
                                : sd?.refreshed_at ? timeAgo(sd.refreshed_at) : 'Not loaded'}
                            </div>
                          </div>
                          <button
                            onClick={() => refreshSource(src.id)}
                            disabled={isRefreshing}
                            style={{
                              background: 'none', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6,
                              padding: '4px 8px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4,
                              color: '#86888f', fontSize: 10,
                            }}
                          >
                            {isRefreshing ? <Spin /> : <RefreshIcon />}
                          </button>
                        </div>

                        {/* Data */}
                        {sd?.data && <SourceData data={sd.data} />}
                      </div>
                    );
                  })}
                </div>
              ))}

              {/* ── Analytics (embedded) ── */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '18px 0 8px' }}>
                <div style={{ height: 1, flex: 1, background: 'rgba(255,255,255,0.06)' }} />
                <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'rgba(255,255,255,0.25)' }}>
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
      </IonContent>
    </IonPage>
  );
};

export default Dossier;
