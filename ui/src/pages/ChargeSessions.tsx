import React, { useState, useEffect, useCallback } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
  IonList,
  IonItem,
  IonLabel,
  IonModal,
  IonButton,
  IonButtons,
  IonSpinner,
} from '@ionic/react';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from 'recharts';
import {
  api,
  ChargingSession,
  ChargeCurve,
  ChargeCurveStats,
  ChargeEnrichment,
} from '../api/client';

// ── Shared chart palette (matches Analytics.tsx) ──────────────────────────────
const C = {
  green: '#10b981',
  blue: '#0FBCF9',
  orange: '#F99716',
  red: '#FF6B6B',
  text: '#e5e5e5',
  sub: '#86888f',
  grid: '#333',
  tooltipBg: '#1a1a1a',
  tooltipBorder: '#333',
};

const tooltipStyle = {
  contentStyle: {
    background: C.tooltipBg,
    border: `1px solid ${C.tooltipBorder}`,
    borderRadius: 6,
    fontSize: 12,
  },
  labelStyle: { color: C.text },
  itemStyle: { color: C.green },
};

// ── Small spinner matching Analytics.tsx ─────────────────────────────────────
function Spin() {
  return (
    <svg width={28} height={28} viewBox="0 0 24 24" fill="none">
      <circle cx={12} cy={12} r={9} stroke="rgba(255,255,255,0.08)" strokeWidth={3} />
      <path d="M12 3a9 9 0 019 9" stroke="#05C46B" strokeWidth={3} strokeLinecap="round">
        <animateTransform
          attributeName="transform"
          type="rotate"
          from="0 12 12"
          to="360 12 12"
          dur="0.8s"
          repeatCount="indefinite"
        />
      </path>
    </svg>
  );
}

// ── Bolt icon ────────────────────────────────────────────────────────────────
const BoltIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <path d="M7 2v11h3v9l7-12h-4l4-8z" />
  </svg>
);

// ── Formatters ────────────────────────────────────────────────────────────────

function formatRelative(dateStr: string): string {
  try {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    const hrs = Math.floor(mins / 60);
    const days = Math.floor(hrs / 24);
    if (days > 0) return `hace ${days}d`;
    if (hrs > 0) return `hace ${hrs}h`;
    return `hace ${mins}m`;
  } catch {
    return dateStr;
  }
}

function formatDurationMin(mins?: number | null): string {
  if (mins == null) return '--';
  const h = Math.floor(mins / 60);
  const m = Math.round(mins % 60);
  return h === 0 ? `${m} min` : `${h}h ${m}m`;
}

function formatDurationSec(secs: number): string {
  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = Math.floor(secs % 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}:${String(s).padStart(2, '0')}`;
}

function formatMmSs(secs: number): string {
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

function formatCost(cost: number | null, estimated: boolean): string {
  if (cost == null) return '--';
  return `$${cost.toFixed(2)}${estimated ? ' est.' : ''}`;
}

// ── Stat card ─────────────────────────────────────────────────────────────────
interface StatCardProps {
  label: string;
  value: string;
  color?: string;
}

function StatCard({ label, value, color = '#0BE881' }: StatCardProps) {
  return (
    <div
      className="tesla-card"
      style={{ padding: '14px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}
    >
      <span style={{ color: C.sub, fontSize: 11, fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        {label}
      </span>
      <span style={{ color, fontWeight: 700, fontSize: 18, lineHeight: 1, letterSpacing: '-0.4px' }}>
        {value}
      </span>
    </div>
  );
}

// ── Empty / error states ──────────────────────────────────────────────────────
function EmptyState() {
  return (
    <div className="empty-state" style={{ padding: '48px 24px', textAlign: 'center' }}>
      <div style={{ marginBottom: 16 }}>
        <svg width={48} height={48} viewBox="0 0 24 24" fill="rgba(255,255,255,0.15)">
          <path d="M7 2v11h3v9l7-12h-4l4-8z" />
        </svg>
      </div>
      <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 18, marginBottom: 8 }}>
        Sin sesiones de carga
      </div>
      <div style={{ color: C.sub, fontSize: 14, lineHeight: 1.5 }}>
        Conecta TeslaMate para ver tus sesiones
      </div>
    </div>
  );
}

function TeslaMateUnavailable() {
  return (
    <div className="empty-state" style={{ padding: '48px 24px', textAlign: 'center' }}>
      <div style={{ marginBottom: 16 }}>
        <svg width={48} height={48} viewBox="0 0 24 24" fill="rgba(249,151,22,0.4)">
          <path d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0zm-4-4l2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z" />
        </svg>
      </div>
      <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 18, marginBottom: 8 }}>
        TeslaMate no está disponible
      </div>
      <div style={{ color: C.sub, fontSize: 14, lineHeight: 1.5 }}>
        Verifica la configuración en Ajustes o que el servidor TeslaMate esté activo.
      </div>
    </div>
  );
}

// ── Curiosidades helpers ──────────────────────────────────────────────────────

function confidenceEs(c: 'high' | 'medium' | 'low' | null): string {
  if (c === 'high') return 'alta';
  if (c === 'medium') return 'media';
  if (c === 'low') return 'baja';
  return '';
}

function formatHHmm(iso: string | null): string {
  if (!iso) return '--';
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  } catch {
    return '--';
  }
}

interface CurioCardProps {
  label: string;
  subtext: string;
  accent: string;
}

function CurioCard({ label, subtext, accent }: CurioCardProps) {
  return (
    <div
      className="tesla-card"
      style={{
        padding: '14px 12px',
        display: 'flex',
        flexDirection: 'column',
        gap: 6,
        borderLeft: `3px solid ${accent}`,
      }}
    >
      <span style={{ color: '#e5e5e5', fontSize: 13, fontWeight: 600, lineHeight: 1.3 }}>
        {label}
      </span>
      <span style={{ color: C.sub, fontSize: 11, lineHeight: 1.4 }}>
        {subtext}
      </span>
    </div>
  );
}

interface CuriosidadesSectionProps {
  enrichment: ChargeEnrichment;
}

function CuriosidadesSection({ enrichment }: CuriosidadesSectionProps) {
  const cards: React.ReactNode[] = [];

  // Card 1 — Ranking
  if (enrichment.rank.fastest_20_to_80_position !== null) {
    if (enrichment.rank.is_personal_best) {
      cards.push(
        <CurioCard
          key="rank"
          label="🏆 Récord personal"
          subtext="Tu carga 20→80% más rápida en 90 días"
          accent="#10b981"
        />
      );
    } else {
      const pos = enrichment.rank.fastest_20_to_80_position;
      const total = enrichment.rank.fastest_20_to_80_total;
      cards.push(
        <CurioCard
          key="rank"
          label={`#${pos}${total !== null ? ` de ${total}` : ''}`}
          subtext="Posición en cargas 20→80% (90 días)"
          accent={C.blue}
        />
      );
    }
  }

  // Card 2 — Preconditioning
  if (enrichment.preconditioning.detected) {
    const dur = enrichment.preconditioning.duration_minutes;
    const conf = confidenceEs(enrichment.preconditioning.confidence);
    const sub = [
      dur !== null ? `${dur} min antes de cargar` : null,
      conf ? `confianza ${conf}` : null,
    ]
      .filter(Boolean)
      .join(' · ');
    cards.push(
      <CurioCard
        key="precond"
        label="Preacondicionamiento detectado"
        subtext={sub || 'Batería precondicionada antes de la sesión'}
        accent="#0FBCF9"
      />
    );
  }

  // Card 3 — Shared stall
  if (enrichment.shared_stall.detected) {
    const drop = enrichment.shared_stall.power_drop_kw;
    const ts = formatHHmm(enrichment.shared_stall.timestamp);
    const sub = [
      drop !== null ? `Caída de ${drop.toFixed(0)} kW` : null,
      enrichment.shared_stall.timestamp ? `a las ${ts}` : null,
    ]
      .filter(Boolean)
      .join(' ');
    cards.push(
      <CurioCard
        key="stall"
        label="Stall compartido detectado"
        subtext={sub || 'Se detectó una caída de potencia inesperada'}
        accent={C.orange}
      />
    );
  }

  // Card 4 — ABRP cost
  if (enrichment.abrp_cost.available && enrichment.abrp_cost.estimated_cost !== null) {
    const { delta_pct, estimated_cost, actual_cost, currency } = enrichment.abrp_cost;
    let label: string;
    let accent: string;
    let sub: string;

    const absDelta = delta_pct !== null ? Math.abs(delta_pct) : null;
    const estFmt = `${currency} ${estimated_cost.toFixed(2)}`;
    const actFmt = actual_cost !== null ? `${currency} ${actual_cost.toFixed(2)}` : null;
    const costLine = actFmt ? `${actFmt} (estimado ${estFmt})` : `Estimado ${estFmt}`;

    if (delta_pct !== null && delta_pct < -5) {
      label = '💰 Bajo el estimado ABRP';
      accent = '#10b981';
      sub = `Pagaste ${absDelta!.toFixed(1)}% menos que la predicción · ${costLine}`;
    } else if (delta_pct !== null && delta_pct > 5) {
      label = '📈 Sobre el estimado ABRP';
      accent = C.orange;
      sub = `Pagaste ${delta_pct.toFixed(1)}% más que la predicción · ${costLine}`;
    } else {
      label = '≈ Igual al estimado ABRP';
      accent = C.sub;
      sub = delta_pct !== null
        ? `Diferencia ${delta_pct.toFixed(1)}% (dentro del rango esperado) · ${costLine}`
        : costLine;
    }

    cards.push(
      <CurioCard key="abrp" label={label} subtext={sub} accent={accent} />
    );
  }

  if (cards.length === 0) return null;

  return (
    <div style={{ marginTop: 16 }}>
      {/* Section header — matches the "Curva de carga" heading style */}
      <div
        style={{
          color: '#fff',
          fontSize: 13,
          fontWeight: 600,
          marginBottom: 8,
          paddingLeft: 4,
        }}
      >
        Curiosidades de esta sesión
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {cards}
      </div>
    </div>
  );
}

// ── Modal detail content ──────────────────────────────────────────────────────
interface DetailProps {
  session: ChargingSession;
  onClose: () => void;
}

function ChargeSessionDetail({ session, onClose }: DetailProps) {
  const [curve, setCurve] = useState<ChargeCurve | null>(null);
  const [stats, setStats] = useState<ChargeCurveStats | null>(null);
  const [enrichment, setEnrichment] = useState<ChargeEnrichment | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!session.process_id) return;
    setLoading(true);
    setError(false);
    Promise.all([
      api.getChargingCurve(session.process_id),
      api.getChargingStats(session.process_id),
      api.getChargingEnrichment(session.process_id),
    ])
      .then(([c, s, e]) => {
        setCurve(c);
        setStats(s);
        setEnrichment(e);
      })
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  }, [session.process_id]);

  // Map samples for Recharts (X = soc)
  const chartData = React.useMemo(() => {
    if (!curve) return [];
    return curve.samples.map(s => ({
      soc: s.soc,
      power_kw: s.power_kw,
      range_km: s.ideal_range_km,
    }));
  }, [curve]);

  return (
    <div style={{ background: '#0d0e11', minHeight: '100%', paddingBottom: 32 }}>
      {/* Modal header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '16px 16px 8px',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
        }}
      >
        <div>
          <div style={{ color: '#fff', fontWeight: 700, fontSize: 16 }}>
            {session.location || 'Sesión de carga'}
          </div>
          <div style={{ color: C.sub, fontSize: 12, marginTop: 2 }}>
            {formatRelative(session.date)} · {session.kwh.toFixed(1)} kWh
          </div>
        </div>
        <button
          onClick={onClose}
          style={{
            background: 'rgba(255,255,255,0.07)',
            border: 'none',
            borderRadius: 8,
            color: '#fff',
            padding: '6px 14px',
            cursor: 'pointer',
            fontSize: 13,
          }}
        >
          Cerrar
        </button>
      </div>

      <div style={{ padding: '16px 12px' }}>
        {/* No process_id — basic summary only */}
        {!session.process_id && (
          <div
            className="tesla-card"
            style={{ padding: '14px 16px', marginBottom: 12, color: C.sub, fontSize: 13 }}
          >
            Detalle de curva no disponible para esta sesión (process_id ausente).
          </div>
        )}

        {/* Loading */}
        {session.process_id && loading && (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '40px 0' }}>
            <Spin />
          </div>
        )}

        {/* Error */}
        {session.process_id && !loading && error && (
          <div
            className="tesla-card"
            style={{ padding: '14px 16px', marginBottom: 12, color: C.orange, fontSize: 13 }}
          >
            No se pudo cargar la curva de carga. TeslaMate puede no estar disponible.
          </div>
        )}

        {/* Chart */}
        {!loading && !error && curve && chartData.length > 0 && (
          <div className="tesla-card" style={{ padding: '14px 8px 8px', marginBottom: 12 }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '0 8px',
                marginBottom: 10,
              }}
            >
              <span style={{ color: '#fff', fontSize: 13, fontWeight: 600 }}>
                Curva de carga
              </span>
              {curve.downsampled && (
                <span
                  style={{
                    fontSize: 10,
                    padding: '2px 8px',
                    borderRadius: 8,
                    background: 'rgba(249,151,22,0.15)',
                    color: C.orange,
                    border: '1px solid rgba(249,151,22,0.3)',
                  }}
                >
                  {curve.samples.length} de {curve.total_samples} muestras
                </span>
              )}
            </div>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData} margin={{ top: 4, right: 4, bottom: 4, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={C.grid} />
                <XAxis
                  dataKey="soc"
                  stroke={C.sub}
                  fontSize={11}
                  unit="%"
                  label={{ value: 'SoC %', position: 'insideBottomRight', offset: -4, fill: C.sub, fontSize: 10 }}
                />
                <YAxis
                  yAxisId="left"
                  stroke={C.sub}
                  fontSize={11}
                  unit=" kW"
                  width={52}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  stroke={C.blue}
                  fontSize={11}
                  unit=" km"
                  width={48}
                />
                <Tooltip
                  {...tooltipStyle}
                  formatter={(value: any, name: any) => {
                    if (name === 'power_kw') return [value != null ? `${Number(value).toFixed(1)} kW` : '--', 'Potencia'];
                    if (name === 'range_km') return [value != null ? `${Number(value).toFixed(0)} km` : '--', 'Rango ideal'];
                    return [value, name];
                  }}
                  labelFormatter={(soc: any) => `SoC: ${soc}%`}
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="power_kw"
                  stroke={C.green}
                  strokeWidth={2}
                  dot={false}
                  name="power_kw"
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="range_km"
                  stroke={C.blue}
                  strokeWidth={1.5}
                  dot={false}
                  strokeDasharray="4 2"
                  name="range_km"
                  connectNulls={false}
                />
              </LineChart>
            </ResponsiveContainer>
            {/* Legend */}
            <div style={{ display: 'flex', gap: 16, padding: '4px 8px', marginTop: 4 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <div style={{ width: 16, height: 2, background: C.green, borderRadius: 1 }} />
                <span style={{ color: C.sub, fontSize: 11 }}>Potencia (kW)</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <div style={{ width: 16, height: 2, borderRadius: 1, borderTop: `2px dashed ${C.blue}` }} />
                <span style={{ color: C.sub, fontSize: 11 }}>Rango ideal (km)</span>
              </div>
            </div>
          </div>
        )}

        {/* Stats 2×2 grid */}
        {!loading && !error && stats && (
          <>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
              <StatCard
                label="Potencia pico"
                value={`${stats.peak_kw.toFixed(1)} kW`}
                color="#0BE881"
              />
              <StatCard
                label="Promedio 20–80%"
                value={stats.avg_kw_20_80 != null ? `${stats.avg_kw_20_80.toFixed(1)} kW` : 'N/A'}
                color="#0FBCF9"
              />
              <StatCard
                label="Knee (taper)"
                value={stats.taper_knee_soc != null ? `${stats.taper_knee_soc}%` : 'N/A'}
                color="#F99716"
              />
              <StatCard
                label="Tiempo > 100 kW"
                value={formatMmSs(stats.time_above_100kw_s)}
                color="#05C46B"
              />
            </div>

            {/* Secondary row */}
            <div className="tesla-card" style={{ padding: '14px 16px' }}>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr 1fr',
                  gap: 12,
                }}
              >
                <div>
                  <div style={{ color: C.sub, fontSize: 11, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Duración
                  </div>
                  <div style={{ color: '#fff', fontSize: 14, fontWeight: 600 }}>
                    {formatDurationSec(stats.duration_s)}
                  </div>
                </div>
                <div>
                  <div style={{ color: C.sub, fontSize: 11, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    kWh añadidos
                  </div>
                  <div style={{ color: '#0BE881', fontSize: 14, fontWeight: 600 }}>
                    {stats.kwh_added.toFixed(2)} kWh
                  </div>
                </div>
                <div>
                  <div style={{ color: C.sub, fontSize: 11, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                    Fases
                  </div>
                  <div style={{ color: '#0FBCF9', fontSize: 14, fontWeight: 600 }}>
                    {stats.phases_used.length > 0 ? stats.phases_used.join(', ') : '--'}
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        {/* Curiosidades de esta sesión */}
        {!loading && !error && enrichment && (
          <CuriosidadesSection enrichment={enrichment} />
        )}

        {/* Basic session info when curve is unavailable */}
        {(!session.process_id || (!loading && !error && !curve)) && (
          <div className="tesla-card" style={{ padding: '14px 16px', marginTop: 12 }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <div style={{ color: C.sub, fontSize: 11, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Energía</div>
                <div style={{ color: '#0BE881', fontSize: 16, fontWeight: 700 }}>{session.kwh.toFixed(2)} kWh</div>
              </div>
              {session.duration_min != null && (
                <div>
                  <div style={{ color: C.sub, fontSize: 11, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Duración</div>
                  <div style={{ color: '#fff', fontSize: 16, fontWeight: 700 }}>{formatDurationMin(session.duration_min)}</div>
                </div>
              )}
              {session.battery_start != null && session.battery_end != null && (
                <div>
                  <div style={{ color: C.sub, fontSize: 11, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>SoC</div>
                  <div style={{ color: '#0FBCF9', fontSize: 16, fontWeight: 700 }}>
                    {session.battery_start}% → {session.battery_end}%
                  </div>
                </div>
              )}
              {session.cost != null && (
                <div>
                  <div style={{ color: C.sub, fontSize: 11, marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.04em' }}>Costo</div>
                  <div style={{ color: '#F99716', fontSize: 16, fontWeight: 700 }}>
                    {formatCost(session.cost, session.cost_estimated)}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
const ChargeSessions: React.FC = () => {
  const [sessions, setSessions] = useState<ChargingSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [selected, setSelected] = useState<ChargingSession | null>(null);

  const fetchSessions = useCallback(() => {
    setLoading(true);
    setUnavailable(false);
    api
      .getChargeSessions(50)
      .then(data => setSessions(Array.isArray(data) ? data : []))
      .catch((err: any) => {
        const status = err?.response?.status;
        if (status === 503 || status === 502) {
          setUnavailable(true);
        } else {
          // Any other error — treat as unavailable (TeslaMate not connected)
          setUnavailable(true);
        }
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700 }}>Sesiones de carga</IonTitle>
        </IonToolbar>
      </IonHeader>

      <IonContent>
        {loading ? (
          <div style={{ display: 'flex', justifyContent: 'center', padding: '60px 0' }}>
            <Spin />
          </div>
        ) : unavailable ? (
          <TeslaMateUnavailable />
        ) : sessions.length === 0 ? (
          <EmptyState />
        ) : (
          <div style={{ padding: '8px 0' }}>
            <IonList style={{ background: 'transparent' }}>
              {sessions.map((s, i) => (
                <IonItem
                  key={i}
                  button
                  detail={false}
                  onClick={() => setSelected(s)}
                  style={{
                    '--background': 'transparent',
                    '--background-hover': 'rgba(255,255,255,0.04)',
                    '--border-color': 'rgba(255,255,255,0.07)',
                    '--padding-start': '12px',
                    '--padding-end': '12px',
                    '--inner-padding-end': '0',
                  } as React.CSSProperties}
                >
                  {/* Left: bolt icon badge */}
                  <div
                    slot="start"
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: 10,
                      background: 'rgba(5,196,107,0.12)',
                      color: '#05C46B',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                      marginRight: 12,
                    }}
                  >
                    <BoltIcon />
                  </div>

                  <IonLabel>
                    {/* Row 1: location + kWh */}
                    <div
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'flex-start',
                        marginBottom: 4,
                      }}
                    >
                      <span
                        style={{
                          color: '#ffffff',
                          fontSize: 13,
                          fontWeight: 500,
                          flex: 1,
                          marginRight: 8,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {s.location || 'Ubicación desconocida'}
                      </span>
                      <span style={{ color: '#0BE881', fontWeight: 700, fontSize: 14, flexShrink: 0 }}>
                        +{s.kwh.toFixed(1)} kWh
                      </span>
                    </div>

                    {/* Row 2: meta */}
                    <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
                      <span style={{ color: C.sub, fontSize: 11 }}>{formatRelative(s.date)}</span>
                      {s.battery_start != null && s.battery_end != null && (
                        <span style={{ color: C.sub, fontSize: 11 }}>
                          {s.battery_start}% → {s.battery_end}%
                        </span>
                      )}
                      {s.duration_min != null && (
                        <span style={{ color: C.sub, fontSize: 11 }}>
                          {formatDurationMin(s.duration_min)}
                        </span>
                      )}
                      {s.cost != null && (
                        <span style={{ color: C.orange, fontSize: 11 }}>
                          {formatCost(s.cost, s.cost_estimated)}
                        </span>
                      )}
                    </div>
                  </IonLabel>

                  {/* Chevron */}
                  <div slot="end" style={{ display: 'flex', alignItems: 'center' }}>
                    <svg
                      width={16}
                      height={16}
                      viewBox="0 0 24 24"
                      fill="rgba(255,255,255,0.25)"
                    >
                      <path d="M10 6L8.59 7.41 13.17 12l-4.58 4.59L10 18l6-6z" />
                    </svg>
                  </div>
                </IonItem>
              ))}
            </IonList>
          </div>
        )}

        {/* Detail modal */}
        <IonModal
          isOpen={selected !== null}
          onDidDismiss={() => setSelected(null)}
          breakpoints={[0, 0.5, 0.92]}
          initialBreakpoint={0.92}
          style={{ '--border-radius': '20px 20px 0 0' } as React.CSSProperties}
        >
          {selected && (
            <IonContent style={{ '--background': '#0d0e11' } as React.CSSProperties}>
              <ChargeSessionDetail session={selected} onClose={() => setSelected(null)} />
            </IonContent>
          )}
        </IonModal>
      </IonContent>
    </IonPage>
  );
};

export default ChargeSessions;
