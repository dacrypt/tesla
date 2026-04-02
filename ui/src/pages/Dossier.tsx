import React from 'react';
import { IonContent, IonHeader, IonPage, IonToolbar, IonTitle, IonRefresher, IonRefresherContent } from '@ionic/react';
import { useDossierData } from '../hooks/useDossierData';
import CollapsibleSection from '../components/dossier/CollapsibleSection';
import StatusPipeline from '../components/dossier/StatusPipeline';
import SpecsGrid from '../components/dossier/SpecsGrid';
import OptionCodesPills from '../components/dossier/OptionCodesPills';
import RuntCard from '../components/dossier/RuntCard';
import SimitCard from '../components/dossier/SimitCard';
import LogisticsCard from '../components/dossier/LogisticsCard';
import Analytics from './Analytics';
import { api } from '../api/client';
import type { RuntData } from '../api/client';

/* ── Colombian data sections ── */

function EVStationsSection() {
  const [stations, setStations] = React.useState<any[]>([]);
  const [loading, setLoading] = React.useState(true);
  React.useEffect(() => {
    api.getEstacionesEV('').then(d => setStations(d.estaciones || [])).catch(() => {}).finally(() => setLoading(false));
  }, []);
  if (loading) return <div style={{ fontSize: 12, color: 'var(--tesla-text-secondary)', textAlign: 'center', padding: 12 }}>Cargando...</div>;
  if (!stations.length) return <div style={{ fontSize: 12, color: 'var(--tesla-text-secondary)', textAlign: 'center', padding: 12 }}>No se encontraron estaciones</div>;
  return (
    <>
      <div style={{ fontSize: 11, color: 'var(--tesla-text-dim)', marginBottom: 8 }}>{stations.length} estaciones encontradas</div>
      {stations.slice(0, 10).map((s, i) => (
        <div key={i} style={{ marginBottom: 8, paddingBottom: 8, borderBottom: i < Math.min(stations.length, 10) - 1 ? '1px solid var(--tesla-card-border)' : 'none' }}>
          <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--tesla-text)' }}>{s.nombre}</div>
          <div style={{ fontSize: 10, color: 'var(--tesla-text-secondary)' }}>{s.direccion} · {s.ciudad}</div>
          <div style={{ display: 'flex', gap: 8, marginTop: 2 }}>
            <span style={{ fontSize: 10, color: s.tipo?.includes('pida') ? '#0BE881' : '#0FBCF9' }}>{s.tipo}</span>
            <span style={{ fontSize: 10, color: 'var(--tesla-text-dim)' }}>{s.horario}</span>
          </div>
        </div>
      ))}
    </>
  );
}

function FasecoldaSection() {
  const [data, setData] = React.useState<any>(null);
  const [loading, setLoading] = React.useState(true);
  React.useEffect(() => {
    api.getFasecolda().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);
  if (loading) return <div style={{ fontSize: 12, color: 'var(--tesla-text-secondary)', textAlign: 'center', padding: 12 }}>Consultando Fasecolda...</div>;
  if (!data || data.error) return (
    <div style={{ textAlign: 'center', padding: 12 }}>
      <div style={{ fontSize: 12, color: 'var(--tesla-text-secondary)' }}>No disponible actualmente</div>
      <a href="https://guiadevalores.fasecolda.com/ConsultaExplorador/" target="_blank" rel="noreferrer" style={{ fontSize: 11, color: '#0FBCF9', textDecoration: 'none' }}>Consultar manualmente en Fasecolda ↗</a>
    </div>
  );
  return (
    <>
      {data.valor && (
        <div style={{ textAlign: 'center', padding: '12px 0' }}>
          <div style={{ fontSize: 10, color: 'var(--tesla-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.1em' }}>Valor Comercial</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: '#05C46B', marginTop: 4 }}>${Number(data.valor).toLocaleString()}</div>
          <div style={{ fontSize: 11, color: 'var(--tesla-text-dim)' }}>COP · {data.ano || ''}</div>
        </div>
      )}
      {data.marca && <div className="stat-row"><span style={{ color: 'var(--tesla-text-secondary)', fontSize: 12 }}>Marca</span><span style={{ color: 'var(--tesla-text)', fontSize: 12 }}>{data.marca}</span></div>}
      {data.linea && <div className="stat-row"><span style={{ color: 'var(--tesla-text-secondary)', fontSize: 12 }}>Línea</span><span style={{ color: 'var(--tesla-text)', fontSize: 12 }}>{data.linea}</span></div>}
      {data.clase && <div className="stat-row"><span style={{ color: 'var(--tesla-text-secondary)', fontSize: 12 }}>Clase</span><span style={{ color: 'var(--tesla-text)', fontSize: 12 }}>{data.clase}</span></div>}
    </>
  );
}

function Spin() {
  return (
    <svg width={20} height={20} viewBox="0 0 24 24" style={{ animation: 'spin 1s linear infinite' }}>
      <path d="M12 3a9 9 0 019 9" stroke="#05C46B" strokeWidth={3} strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="1s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

/* ── Helpers ── */

function KV({ label, value, mono, color }: { label: string; value?: unknown; mono?: boolean; color?: string }) {
  if (value == null || value === '' || value === 0) return null;
  // Safely convert objects to string to avoid React "Objects are not valid as a React child" crash
  const display = typeof value === 'object' ? JSON.stringify(value) : String(value);
  return (
    <div className="stat-row">
      <span style={{ color: 'var(--tesla-text-secondary)', fontSize: 12 }}>{label}</span>
      <span style={{ color: color || 'var(--tesla-text)', fontSize: 12, fontWeight: 500, fontFamily: mono ? "'SF Mono', monospace" : undefined }}>{display}</span>
    </div>
  );
}

function StatusPill({ ok, trueText, falseText }: { ok?: boolean; trueText: string; falseText: string }) {
  return (
    <span style={{
      background: ok ? 'rgba(11,232,129,0.12)' : 'rgba(255,107,107,0.12)',
      color: ok ? '#0BE881' : '#FF6B6B',
      border: `1px solid ${ok ? 'rgba(11,232,129,0.25)' : 'rgba(255,107,107,0.25)'}`,
      borderRadius: 100, padding: '3px 9px', fontSize: 10, fontWeight: 600,
    }}>
      {ok ? trueText : falseText}
    </span>
  );
}

function SectionDivider({ label }: { label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, margin: '20px 0 8px', padding: '0 2px' }}>
      <div style={{ flex: 1, height: 1, background: 'var(--tesla-border)' }} />
      <span style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.15em', color: 'var(--tesla-text-dim)' }}>{label}</span>
      <div style={{ flex: 1, height: 1, background: 'var(--tesla-border)' }} />
    </div>
  );
}

/* ── Legal flags renderer ── */
function LegalFlags({ runt }: { runt: RuntData }) {
  const flags: [string, boolean | undefined][] = [
    ['Gravámenes', runt.gravamenes],
    ['Prendas', runt.prendas],
    ['Repotenciado', runt.repotenciado],
    ['Blindaje', runt.blindaje],
    ['Antiguo/Clásico', runt.antiguo_clasico],
    ['Enseñanza', runt.vehiculo_ensenanza],
    ['Seguridad Estado', runt.seguridad_estado],
    ['Regrab. Motor', runt.regrabacion_motor],
    ['Regrab. Chasis', runt.regrabacion_chasis],
    ['Regrab. Serie', runt.regrabacion_serie],
    ['Regrab. VIN', runt.regrabacion_vin],
  ];
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 12 }}>
      {flags.map(([label, val]) => (
        <span key={label} style={{
          background: val ? 'rgba(255,107,107,0.1)' : 'rgba(11,232,129,0.08)',
          color: val ? '#FF6B6B' : '#0BE881',
          border: `1px solid ${val ? 'rgba(255,107,107,0.2)' : 'rgba(11,232,129,0.15)'}`,
          borderRadius: 100, padding: '3px 8px', fontSize: 9, fontWeight: 600,
        }}>
          {val ? '!' : '✓'} {label}
        </span>
      ))}
    </div>
  );
}

/* ── Phase config ── */
const PHASE_LABELS: Record<string, string> = {
  ordered: 'Order Placed', produced: 'Produced', shipped: 'In Transit',
  in_country: 'In Country', registered: 'Registered',
  delivery_scheduled: 'Delivery Scheduled', delivered: 'Delivered',
};
const PHASE_COLORS: Record<string, string> = {
  ordered: '#F99716', produced: '#0FBCF9', shipped: '#00D8D6',
  in_country: '#0BE881', registered: '#05C46B',
  delivery_scheduled: '#05C46B', delivered: '#05C46B',
};

/* ══════════════════════════════════════════════════════════════════════════ */

export default function Dossier() {
  const {
    dossier, runtLive, simitLive,
    loading, runtLoading, simitLoading,
    error, runtError, simitError,
    refresh, refreshRunt, refreshSimit,
  } = useDossierData();

  const handleRefresh = async (e: CustomEvent) => { await refresh(); e.detail.complete(); };

  const runt = runtLive || dossier?.runt;
  const simit = simitLive || dossier?.simit;
  const status = dossier?.real_status;
  const phase = status?.phase || '';
  const phaseLabel = PHASE_LABELS[phase] || status?.phase_description || 'Unknown';
  const phaseColor = PHASE_COLORS[phase] || '#86888f';

  let daysToDelivery: number | null = null;
  if (status?.delivery_date) {
    const diff = new Date(status.delivery_date).getTime() - Date.now();
    daysToDelivery = Math.max(0, Math.ceil(diff / 86400000));
  }

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle>Info</IonTitle>
          {loading && <div slot="end" style={{ paddingRight: 16 }}><Spin /></div>}
        </IonToolbar>
      </IonHeader>
      <IonContent>
        <IonRefresher slot="fixed" onIonRefresh={handleRefresh}>
          <IonRefresherContent />
        </IonRefresher>

        <div className="page-pad">

          {/* ── Empty state ── */}
          {error === 'no_dossier' && !loading && (
            <div className="empty-state" style={{ minHeight: 400 }}>
              <div className="empty-icon">
                <svg width={32} height={32} viewBox="0 0 24 24" fill="none">
                  <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" stroke="#86888f" strokeWidth={1.5} />
                  <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" stroke="#86888f" strokeWidth={1.5} strokeLinecap="round" />
                </svg>
              </div>
              <div style={{ color: 'var(--tesla-text)', fontWeight: 600, fontSize: 16 }}>No Dossier Built</div>
              <div style={{ color: 'var(--tesla-text-secondary)', fontSize: 13, maxWidth: 260 }}>
                Build your vehicle dossier to see VIN decode, specs, RUNT status, shipping info, and more.
              </div>
              <button className="tesla-btn" style={{ width: 'auto', padding: '12px 28px', marginTop: 8 }} onClick={refresh}>
                Build Dossier
              </button>
            </div>
          )}

          {error && error !== 'no_dossier' && !loading && (
            <div className="empty-state">
              <div style={{ color: '#FF6B6B', fontSize: 13, marginBottom: 8 }}>{error}</div>
              <button className="tesla-btn secondary" style={{ width: 'auto', padding: '10px 24px' }} onClick={refresh}>Retry</button>
            </div>
          )}

          {dossier && (
            <>
              {/* ════════════════════════════════════════════════════════════ */}
              {/* 1. HERO HEADER                                             */}
              {/* ════════════════════════════════════════════════════════════ */}
              <div className="tesla-card" style={{ textAlign: 'center', padding: '24px 18px 20px', marginBottom: 10 }}>
                <div style={{
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                  background: `${phaseColor}18`, color: phaseColor,
                  border: `1px solid ${phaseColor}40`,
                  borderRadius: 100, padding: '5px 14px',
                  fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.08em',
                  marginBottom: 12,
                }}>
                  {phaseLabel}
                </div>
                <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.3px', marginBottom: 4 }}>
                  {dossier.specs?.model} {dossier.specs?.variant}
                </div>
                <div style={{ fontSize: 12, color: 'var(--tesla-text-secondary)' }}>
                  {dossier.specs?.generation} &middot; {dossier.specs?.model_year} &middot; {dossier.specs?.exterior_color}
                </div>
                {daysToDelivery !== null && daysToDelivery > 0 && (
                  <div style={{ marginTop: 16 }}>
                    <div className="hero-number-lg" style={{ color: phaseColor }}>{daysToDelivery}</div>
                    <div style={{ fontSize: 11, color: 'var(--tesla-text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em', marginTop: 2 }}>
                      days to delivery
                    </div>
                  </div>
                )}
                {dossier.last_updated && (
                  <div style={{ fontSize: 10, color: 'var(--tesla-text-dim)', marginTop: 12 }}>
                    Updated: {new Date(dossier.last_updated).toLocaleString()}
                  </div>
                )}
              </div>

              {/* ════════════════════════════════════════════════════════════ */}
              {/* 2. STATUS PIPELINE                                         */}
              {/* ════════════════════════════════════════════════════════════ */}
              <StatusPipeline status={status} />

              {/* Multi-source intelligence flags */}
              {status && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, margin: '10px 0 4px', padding: '0 4px' }}>
                  {[
                    { flag: status.vin_assigned, label: 'VIN Assigned' },
                    { flag: status.is_produced, label: 'Produced' },
                    { flag: status.is_shipped, label: 'Shipped' },
                    { flag: status.is_in_country, label: 'In Country' },
                    { flag: status.is_customs_cleared, label: 'Customs' },
                    { flag: status.in_runt, label: 'RUNT' },
                    { flag: status.has_placa, label: 'Placa' },
                    { flag: status.has_soat, label: 'SOAT' },
                    { flag: status.is_registered, label: 'Registered' },
                    { flag: status.is_delivery_scheduled, label: 'Delivery Sched.' },
                    { flag: status.is_delivered, label: 'Delivered' },
                  ].filter(f => f.flag != null).map(f => (
                    <span key={f.label} style={{
                      fontSize: 10, fontWeight: 600, padding: '3px 8px', borderRadius: 100,
                      background: f.flag ? 'rgba(11,232,129,0.1)' : 'rgba(255,255,255,0.04)',
                      color: f.flag ? '#0BE881' : 'rgba(255,255,255,0.25)',
                      border: `1px solid ${f.flag ? 'rgba(11,232,129,0.2)' : 'rgba(255,255,255,0.06)'}`,
                    }}>{f.flag ? '✓' : '○'} {f.label}</span>
                  ))}
                </div>
              )}

              {/* ── VEHÍCULO ─────────────────────────────────────────────── */}
              <SectionDivider label="Vehículo" />

              {/* ════════════════════════════════════════════════════════════ */}
              {/* 3. IDENTIDAD                                               */}
              {/* ════════════════════════════════════════════════════════════ */}
              <CollapsibleSection title="Identidad" defaultOpen>
                <div style={{ marginBottom: 12 }}>
                  <div className="label-xs" style={{ marginBottom: 4 }}>VIN</div>
                  <div style={{
                    fontFamily: "'SF Mono', 'Menlo', monospace", fontSize: 15, fontWeight: 600,
                    letterSpacing: '0.08em', color: 'var(--tesla-text)',
                    background: 'var(--tesla-card-secondary)', borderRadius: 8, padding: '10px 14px',
                    border: '1px solid var(--tesla-card-border)', wordBreak: 'break-all',
                  }}>
                    {dossier.vin || '--'}
                  </div>
                </div>

                {/* Placa + RN side by side */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
                  <div style={{ background: 'var(--tesla-card-secondary)', borderRadius: 10, padding: '10px 14px', border: '1px solid var(--tesla-card-border)', textAlign: 'center' }}>
                    <div className="label-xs" style={{ marginBottom: 3 }}>Placa</div>
                    <div style={{ fontSize: 18, fontWeight: 700, letterSpacing: '0.1em', color: runt?.placa ? 'var(--tesla-text)' : 'var(--tesla-text-dim)' }}>
                      {runt?.placa || 'Pendiente'}
                    </div>
                  </div>
                  <div style={{ background: 'var(--tesla-card-secondary)', borderRadius: 10, padding: '10px 14px', border: '1px solid var(--tesla-card-border)', textAlign: 'center' }}>
                    <div className="label-xs" style={{ marginBottom: 3 }}>RN</div>
                    <div style={{ fontSize: 14, fontWeight: 600, fontFamily: "'SF Mono', monospace", color: 'var(--tesla-text)' }}>
                      {dossier.reservation_number || '--'}
                    </div>
                  </div>
                </div>

                {/* VIN Decode */}
                {dossier.vin_decode && (
                  <>
                    <div className="label-xs" style={{ marginBottom: 6, marginTop: 12 }}>VIN Decode</div>
                    <KV label="Manufacturer" value={dossier.vin_decode.manufacturer} />
                    <KV label="Plant" value={dossier.vin_decode.plant ? `${dossier.vin_decode.plant} (${dossier.vin_decode.plant_country})` : undefined} />
                    <KV label="Model" value={dossier.vin_decode.model} />
                    <KV label="Body" value={dossier.vin_decode.body_type} />
                    <KV label="Energy" value={dossier.vin_decode.energy_type} />
                    <KV label="Motor/Battery" value={dossier.vin_decode.motor_battery} />
                    <KV label="Chemistry" value={dossier.vin_decode.battery_chemistry} />
                    <KV label="Restraint" value={dossier.vin_decode.restraint_system} />
                    <KV label="Year Code" value={dossier.vin_decode.model_year} />
                    <KV label="Check Digit" value={dossier.vin_decode.check_digit} mono />
                    <KV label="Serial" value={dossier.vin_decode.serial_number} mono />
                  </>
                )}

                {/* RUNT identifiers */}
                {runt?.licencia_transito && <KV label="Licencia Tránsito" value={runt.licencia_transito} mono />}
                {runt?.tarjeta_registro && <KV label="Tarjeta Registro" value={runt.tarjeta_registro} mono />}
                {runt?.id_automotor ? <KV label="ID RUNT" value={runt.id_automotor} mono /> : null}
              </CollapsibleSection>

              {/* ════════════════════════════════════════════════════════════ */}
              {/* 4. CONFIGURACIÓN                                           */}
              {/* ════════════════════════════════════════════════════════════ */}
              <CollapsibleSection title="Configuración & Specs" defaultOpen>
                <SpecsGrid specs={dossier.specs} />

                {dossier.option_codes?.codes && dossier.option_codes.codes.length > 0 && (
                  <>
                    <div className="label-xs" style={{ marginBottom: 6, marginTop: 14 }}>Option Codes</div>
                    <OptionCodesPills options={dossier.option_codes} />
                  </>
                )}
              </CollapsibleSection>

              {/* ── COMPRA & ENTREGA ──────────────────────────────────────── */}
              <SectionDivider label="Compra & Entrega" />

              {/* ════════════════════════════════════════════════════════════ */}
              {/* 5. ORDEN                                                   */}
              {/* ════════════════════════════════════════════════════════════ */}
              {dossier.order && (
                <CollapsibleSection title="Orden" defaultOpen
                  badge={dossier.order.current?.order_status ? (
                    <StatusPill ok={true} trueText={dossier.order.current.order_status} falseText="" />
                  ) : undefined}
                >
                  <KV label="Reservation" value={dossier.order.reservation_number} mono />
                  <KV label="Country" value={dossier.order.country_code} />
                  {dossier.order.current && (
                    <>
                      <KV label="Status" value={dossier.order.current.order_status} color="#05C46B" />
                      <KV label="Substatus" value={dossier.order.current.order_substatus} />
                      <KV label="Delivery Window" value={
                        dossier.order.current.delivery_window_start
                          ? `${dossier.order.current.delivery_window_start} — ${dossier.order.current.delivery_window_end}`
                          : undefined
                      } />
                    </>
                  )}

                  {/* Delivery appointment */}
                  {status?.delivery_date && (
                    <div style={{
                      background: 'rgba(5,196,107,0.07)', border: '1px solid rgba(5,196,107,0.18)',
                      borderRadius: 12, padding: '14px 16px', margin: '12px 0',
                    }}>
                      <div className="label-xs" style={{ marginBottom: 6, color: '#05C46B' }}>Delivery Appointment</div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: '#05C46B' }}>{status.delivery_date}</div>
                      {status.delivery_location && <div style={{ fontSize: 12, color: 'var(--tesla-text-secondary)', marginTop: 4 }}>{status.delivery_location}</div>}
                      {status.delivery_appointment && <div style={{ fontSize: 11, color: 'var(--tesla-text-dim)', marginTop: 2 }}>{status.delivery_appointment}</div>}
                    </div>
                  )}

                  {/* History */}
                  {dossier.order.history && dossier.order.history.length > 0 && (
                    <>
                      <div className="label-xs" style={{ marginBottom: 6, marginTop: 8 }}>Status History</div>
                      {dossier.order.history.slice().reverse().map((snap, i) => (
                        <div key={i} style={{ display: 'flex', gap: 10, marginBottom: 8, alignItems: 'flex-start' }}>
                          <div style={{ width: 8, height: 8, borderRadius: '50%', background: i === 0 ? 'var(--tesla-green)' : 'var(--tesla-border)', marginTop: 5, flexShrink: 0 }} />
                          <div>
                            <div style={{ fontSize: 12, fontWeight: 500, color: 'var(--tesla-text)' }}>{snap.order_status}</div>
                            {snap.order_substatus && <div style={{ fontSize: 10, color: 'var(--tesla-text-secondary)' }}>{snap.order_substatus}</div>}
                            <div style={{ fontSize: 10, color: 'var(--tesla-text-dim)' }}>
                              {snap.timestamp ? new Date(snap.timestamp).toLocaleString() : '--'}
                              {snap.delivery_window_start ? ` · ${snap.delivery_window_start}–${snap.delivery_window_end}` : ''}
                            </div>
                          </div>
                        </div>
                      ))}
                    </>
                  )}
                </CollapsibleSection>
              )}

              {/* ════════════════════════════════════════════════════════════ */}
              {/* 6. LOGÍSTICA                                               */}
              {/* ════════════════════════════════════════════════════════════ */}
              <CollapsibleSection title="Logística & Envío">
                <LogisticsCard logistics={dossier.logistics} />
              </CollapsibleSection>

              {/* ════════════════════════════════════════════════════════════ */}
              {/* 7. FINANCIERO                                              */}
              {/* ════════════════════════════════════════════════════════════ */}
              {dossier.financial && (
                <CollapsibleSection title="Financiero">
                  <KV label="Precio Base" value={dossier.financial.base_price ? `$${dossier.financial.base_price.toLocaleString()} ${dossier.financial.currency}` : undefined} />
                  <KV label="Opciones" value={dossier.financial.options_total ? `$${dossier.financial.options_total.toLocaleString()}` : undefined} />
                  <KV label="Impuestos" value={dossier.financial.taxes ? `$${dossier.financial.taxes.toLocaleString()}` : undefined} />
                  <KV label="Total" value={dossier.financial.total_price ? `$${dossier.financial.total_price.toLocaleString()} ${dossier.financial.currency}` : undefined} color="#05C46B" />
                  <KV label="Método" value={dossier.financial.payment_method} />
                  <KV label="Depósito" value={dossier.financial.deposit_paid ? `$${dossier.financial.deposit_paid.toLocaleString()}` : undefined} />
                  <KV label="Saldo" value={dossier.financial.balance_due ? `$${dossier.financial.balance_due.toLocaleString()}` : undefined} color="#FF6B6B" />
                  <KV label="Financiamiento" value={(dossier.financial as any).financing_details} />
                  <KV label="Trade-in" value={(dossier.financial as any).trade_in ? `$${(dossier.financial as any).trade_in.toLocaleString()}` : undefined} />
                </CollapsibleSection>
              )}

              {/* ── REGISTRO COLOMBIA ─────────────────────────────────────── */}
              <SectionDivider label="Registro Colombia" />

              {/* ════════════════════════════════════════════════════════════ */}
              {/* 8. RUNT — REGISTRO VEHICULAR                               */}
              {/* ════════════════════════════════════════════════════════════ */}
              <CollapsibleSection title="RUNT — Registro Vehicular"
                badge={runt?.estado ? (
                  <StatusPill ok={runt.estado === 'REGISTRADO' || runt.estado === 'MATRICULADO'} trueText={runt.estado} falseText={runt.estado || 'N/R'} />
                ) : undefined}
              >
                <RuntCard runt={runt} loading={runtLoading} error={runtError} onRetry={refreshRunt} />
                {!runtLoading && !runtError && runt?.estado && (
                  <button className="tesla-btn secondary" style={{ marginTop: 10, fontSize: 12, padding: '8px 16px' }} onClick={refreshRunt}>
                    Actualizar RUNT
                  </button>
                )}
              </CollapsibleSection>

              {/* ════════════════════════════════════════════════════════════ */}
              {/* 9. RUNT — LEGAL & IMPORTACIÓN                              */}
              {/* ════════════════════════════════════════════════════════════ */}
              {runt?.estado && (
                <CollapsibleSection title="Legal & Importación"
                  badge={
                    <div style={{ display: 'flex', gap: 4 }}>
                      <StatusPill ok={!runt.gravamenes} trueText="Sin Grav." falseText="Grav." />
                      <StatusPill ok={!runt.prendas} trueText="Sin Prend." falseText="Prend." />
                    </div>
                  }
                >
                  <LegalFlags runt={runt} />

                  <div className="label-xs" style={{ marginBottom: 6, marginTop: 8 }}>Importación</div>
                  <KV label="País Origen" value={runt.nombre_pais} />
                  <KV label="DIAN Validación" value={runt.validacion_dian} />
                  <KV label="DIAN Válida" value={runt.ver_valida_dian ? 'Sí' : 'No'} color={runt.ver_valida_dian ? '#0BE881' : '#FF6B6B'} />
                  <KV label="Subpartida" value={runt.subpartida} mono />
                  <KV label="Lic. Import. Expedición" value={runt.fecha_expedicion_lt_importacion} />
                  <KV label="Lic. Import. Vencimiento" value={runt.fecha_vencimiento_lt_importacion} />

                  <div className="label-xs" style={{ marginBottom: 6, marginTop: 12 }}>Registro</div>
                  <KV label="Autoridad Tránsito" value={runt.autoridad_transito} />
                  <KV label="Fecha Matrícula" value={runt.fecha_matricula} />
                  <KV label="Fecha Registro" value={runt.fecha_registro} />
                  <KV label="Días Matriculado" value={runt.dias_matriculado} />
                  <KV label="Clasificación" value={runt.clasificacion} />
                  <KV label="Tipo Servicio" value={runt.tipo_servicio} />
                </CollapsibleSection>
              )}

              {/* ════════════════════════════════════════════════════════════ */}
              {/* 10. SIMIT — MULTAS                                         */}
              {/* ════════════════════════════════════════════════════════════ */}
              <CollapsibleSection title="SIMIT — Multas"
                badge={simit ? (() => {
                  const totalFines = (simit.comparendos ?? 0) + (simit.multas ?? 0);
                  const clean = simit.paz_y_salvo || (totalFines === 0 && (simit.total_deuda ?? 0) === 0);
                  return <StatusPill ok={clean} trueText="Paz y Salvo" falseText="Con Deudas" />;
                })() : undefined}
              >
                <SimitCard simit={simit} loading={simitLoading} error={simitError} onRetry={refreshSimit} />
                {!simitLoading && !simitError && (
                  <button className="tesla-btn secondary" style={{ marginTop: 10, fontSize: 12, padding: '8px 16px' }} onClick={refreshSimit}>
                    Actualizar SIMIT
                  </button>
                )}
              </CollapsibleSection>

              {/* ── MANTENIMIENTO ─────────────────────────────────────────── */}
              <SectionDivider label="Mantenimiento" />

              {/* ════════════════════════════════════════════════════════════ */}
              {/* 11. SEGURIDAD & RECALLS                                    */}
              {/* ════════════════════════════════════════════════════════════ */}
              <CollapsibleSection title="Seguridad & Recalls"
                badge={dossier.recalls && dossier.recalls.length > 0 ? (
                  <span style={{ fontSize: 9, padding: '2px 7px', borderRadius: 100, fontWeight: 600, background: 'rgba(255,107,107,0.12)', color: '#FF6B6B' }}>{dossier.recalls.length}</span>
                ) : <StatusPill ok trueText="Clean" falseText="" />}
              >
                {(!dossier.recalls || dossier.recalls.length === 0) ? (
                  <div style={{ fontSize: 12, color: 'var(--tesla-text-secondary)', textAlign: 'center', padding: 12 }}>No recalls found for this vehicle</div>
                ) : (
                  dossier.recalls.map((r, i) => (
                    <div key={i} style={{ marginBottom: 12, paddingBottom: 12, borderBottom: i < dossier.recalls!.length - 1 ? '1px solid var(--tesla-card-border)' : 'none' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                        <span style={{ fontSize: 12, fontWeight: 600 }}>{r.component}</span>
                        <StatusPill ok={r.status === 'completed'} trueText="Fixed" falseText={r.status || 'Open'} />
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--tesla-text-secondary)', lineHeight: 1.4 }}>{r.description}</div>
                      {r.remedy && <div style={{ fontSize: 11, color: '#0FBCF9', lineHeight: 1.4, marginTop: 4 }}>Remedy: {r.remedy}</div>}
                      <div style={{ fontSize: 10, color: 'var(--tesla-text-dim)', marginTop: 4 }}>
                        {r.date}{r.source ? ` · ${r.source}` : ''}{r.nhtsa_id ? ` · NHTSA ${r.nhtsa_id}` : ''}
                      </div>
                    </div>
                  ))
                )}
              </CollapsibleSection>

              {/* ════════════════════════════════════════════════════════════ */}
              {/* 12. SOFTWARE                                               */}
              {/* ════════════════════════════════════════════════════════════ */}
              <CollapsibleSection title="Software"
                badge={dossier.software?.current_version ? (
                  <span style={{ fontSize: 10, color: 'var(--tesla-text-secondary)', fontFamily: "'SF Mono', monospace" }}>{dossier.software.current_version}</span>
                ) : undefined}
              >
                {dossier.software?.versions && dossier.software.versions.length > 0 ? (
                  dossier.software.versions.map((v: any, i: number) => (
                    <div key={i} style={{ marginBottom: 6, paddingBottom: 6, borderBottom: i < (dossier.software?.versions?.length ?? 0) - 1 ? '1px solid var(--tesla-card-border)' : 'none' }}>
                      <div className="stat-row">
                        <span style={{ fontFamily: "'SF Mono', monospace", fontSize: 12, color: i === 0 ? '#0BE881' : 'var(--tesla-text)' }}>{v.version}</span>
                        <span style={{ fontSize: 10, color: 'var(--tesla-text-secondary)' }}>{v.first_seen ? new Date(v.first_seen).toLocaleDateString() : ''}</span>
                      </div>
                      {v.release_notes && <div style={{ fontSize: 10, color: 'var(--tesla-text-dim)', marginTop: 2, lineHeight: 1.4 }}>{typeof v.release_notes === 'string' ? v.release_notes : JSON.stringify(v.release_notes)}</div>}
                    </div>
                  ))
                ) : (
                  <div style={{ fontSize: 12, color: 'var(--tesla-text-secondary)', textAlign: 'center', padding: 12 }}>No software history yet</div>
                )}
              </CollapsibleSection>

              {/* ════════════════════════════════════════════════════════════ */}
              {/* 13. SERVICIO & MANTENIMIENTO                               */}
              {/* ════════════════════════════════════════════════════════════ */}
              <CollapsibleSection title="Servicio & Mantenimiento">
                {dossier.service_history && dossier.service_history.length > 0 ? (
                  dossier.service_history.map((s, i) => (
                    <div key={i} style={{ marginBottom: 10, paddingBottom: 10, borderBottom: i < dossier.service_history!.length - 1 ? '1px solid var(--tesla-card-border)' : 'none' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                        <span style={{ fontSize: 12, fontWeight: 600 }}>{s.type}</span>
                        <span style={{ fontSize: 10, color: 'var(--tesla-text-secondary)' }}>{s.date}</span>
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--tesla-text-secondary)' }}>{s.description}</div>
                      {s.mileage_km ? <div style={{ fontSize: 10, color: 'var(--tesla-text-dim)', marginTop: 2 }}>{s.mileage_km.toLocaleString()} km &middot; {s.location}</div> : null}
                    </div>
                  ))
                ) : (
                  <div style={{ fontSize: 12, color: 'var(--tesla-text-secondary)', textAlign: 'center', padding: 12 }}>No service records yet</div>
                )}
              </CollapsibleSection>

              {/* ── CUENTA ────────────────────────────────────────────────── */}
              <SectionDivider label="Cuenta" />

              {/* ════════════════════════════════════════════════════════════ */}
              {/* 14. CUENTA TESLA                                           */}
              {/* ════════════════════════════════════════════════════════════ */}
              <CollapsibleSection title="Cuenta Tesla">
                {dossier.account ? (
                  <>
                    <KV label="Nombre" value={dossier.account.full_name} />
                    <KV label="Email" value={dossier.account.email} />
                    <KV label="Vault UUID" value={dossier.account.vault_uuid} mono />
                    <KV label="Service Scheduling" value={dossier.account.service_scheduling_enabled ? 'Enabled' : 'Disabled'} color={dossier.account.service_scheduling_enabled ? '#0BE881' : 'var(--tesla-text-secondary)'} />
                  </>
                ) : (
                  <div style={{ fontSize: 12, color: 'var(--tesla-text-secondary)', textAlign: 'center', padding: 12 }}>No account data available</div>
                )}
              </CollapsibleSection>

              {/* ════════════════════════════════════════════════════════════ */}
              {/* REGISTRO & TRÁMITES                                        */}
              {/* ════════════════════════════════════════════════════════════ */}
              {runt && (
                <CollapsibleSection title="Registro & Trámites">
                  {[
                    { label: 'Nacionalización (DIAN)', done: runt.ver_valida_dian || runt.validacion_dian === 'VALIDADO', detail: runt.subpartida ? `Subpartida: ${runt.subpartida}` : runt.validacion_dian, date: runt.fecha_expedicion_lt_importacion },
                    { label: 'Registro RUNT', done: !!runt.estado, detail: runt.estado ? `Estado: ${runt.estado}` : undefined, date: runt.fecha_registro },
                    { label: 'Matrícula', done: !!runt.fecha_matricula, detail: runt.autoridad_transito, date: runt.fecha_matricula },
                    { label: 'Placa', done: !!runt.placa, detail: runt.placa || 'Pendiente' },
                    { label: 'SOAT', done: runt.soat_vigente ?? false, detail: runt.soat_aseguradora, date: runt.soat_vencimiento ? `Vence: ${runt.soat_vencimiento}` : undefined },
                    { label: 'RTM', done: runt.tecnomecanica_vigente ?? false, date: runt.tecnomecanica_vencimiento ? `Vence: ${runt.tecnomecanica_vencimiento}` : undefined },
                    { label: 'Gravámenes', done: runt.gravamenes === false, detail: runt.gravamenes ? 'Con gravámenes' : 'Libre' },
                    { label: 'Prendas', done: runt.prendas === false, detail: runt.prendas ? 'Con prendas' : 'Libre' },
                  ].map((s, i) => (
                    <div key={i} style={{ display: 'flex', gap: 10, marginBottom: 8, alignItems: 'flex-start' }}>
                      <div style={{ width: 20, height: 20, borderRadius: '50%', flexShrink: 0, marginTop: 1, background: s.done ? 'rgba(11,232,129,0.15)' : 'rgba(255,255,255,0.04)', border: `1.5px solid ${s.done ? '#0BE881' : 'rgba(255,255,255,0.1)'}`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: s.done ? '#0BE881' : 'rgba(255,255,255,0.2)', fontSize: 10, fontWeight: 700 }}>
                        {s.done ? '✓' : '○'}
                      </div>
                      <div>
                        <div style={{ fontSize: 12, fontWeight: 500, color: s.done ? 'var(--tesla-text)' : 'var(--tesla-text-secondary)' }}>{s.label}</div>
                        {s.detail && <div style={{ fontSize: 10, color: s.done ? '#0BE881' : 'var(--tesla-text-secondary)' }}>{s.detail}</div>}
                        {s.date && <div style={{ fontSize: 9, color: 'var(--tesla-text-dim)' }}>{s.date}</div>}
                      </div>
                    </div>
                  ))}
                </CollapsibleSection>
              )}

              {/* ════════════════════════════════════════════════════════════ */}
              {/* ANALYTICS (embedded)                                       */}
              {/* ════════════════════════════════════════════════════════════ */}
              {/* ════════════════════════════════════════════════════════════ */}
              {/* COLOMBIA: EV Stations, Fasecolda, Peajes                   */}
              {/* ════════════════════════════════════════════════════════════ */}
              <SectionDivider label="Colombia" />

              <CollapsibleSection title="Electrolineras (Estaciones EV)">
                <EVStationsSection />
              </CollapsibleSection>

              <CollapsibleSection title="Valor Comercial (Fasecolda)">
                <FasecoldaSection />
              </CollapsibleSection>

              <SectionDivider label="Analytics" />
              <div style={{ margin: '0 -16px' }}>
                <Analytics embedded />
              </div>

              {/* ── Metadata ── */}
              <div style={{ textAlign: 'center', padding: '16px 0 8px', fontSize: 10, color: 'var(--tesla-text-dim)' }}>
                Dossier v{dossier.dossier_version} &middot; Updates: {dossier.update_count} &middot; Created: {dossier.created_at ? new Date(dossier.created_at).toLocaleDateString() : '--'}
              </div>
            </>
          )}
        </div>
      </IonContent>
    </IonPage>
  );
}
