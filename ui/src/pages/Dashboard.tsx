import React, { useState } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
  IonRefresher,
  IonRefresherContent,
  IonSpinner,
  IonToast,
} from '@ionic/react';
import { useHistory } from 'react-router-dom';
import ModelYSilhouette from '../components/ModelYSilhouette';
import RecentCharges from '../components/RecentCharges';
import StatusBadge from '../components/StatusBadge';
import OrderProcessTracker from '../components/OrderProcessTracker';
import { useVehicleData } from '../hooks/useVehicleData';
import { useDossierData } from '../hooks/useDossierData';
import { useDashboardTiles } from '../hooks/useDashboardTiles';
import { api, FleetVehicle, OrderTask } from '../api/client';

// ---- SVG Icons ----
const LockIcon = () => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor">
    <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zM12 17c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1s3.1 1.39 3.1 3.1v2z"/>
  </svg>
);
const UnlockIcon = () => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor">
    <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6h2c0-1.65 1.35-3 3-3s3 1.35 3 3v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm0 12H6V10h12v10zm-6-3c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2z"/>
  </svg>
);
const AcIcon = () => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor">
    <path d="M22 11h-4.17l3.24-3.24-1.41-1.42L15 11h-2V9l4.66-4.66-1.42-1.41L13 6.17V2h-2v4.17L7.76 2.93 6.34 4.34 11 9v2H9L4.34 6.34 2.93 7.76 6.17 11H2v2h4.17l-3.24 3.24 1.41 1.42L9 13h2v2l-4.66 4.66 1.42 1.41L11 17.83V22h2v-4.17l3.24 3.24 1.42-1.41L13 15v-2h2l4.66 4.66 1.41-1.42L17.83 13H22z"/>
  </svg>
);
const FlashLightsIcon = () => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor">
    <path d="M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9v1zm3-19C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7z"/>
  </svg>
);
const HornIcon = () => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor">
    <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/>
  </svg>
);
const WakeIcon = () => (
  <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor">
    <path d="M6.76 4.84l-1.8-1.79-1.41 1.41 1.79 1.79 1.42-1.41zM4 10.5H1v2h3v-2zm9-9.95h-2V3.5h2V.55zm7.45 3.91l-1.41-1.41-1.79 1.79 1.41 1.41 1.79-1.79zm-3.21 13.7l1.79 1.8 1.41-1.41-1.8-1.79-1.4 1.4zM20 10.5v2h3v-2h-3zm-8-5c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm-1 16.95h2V19.5h-2v2.95zm-7.45-3.91l1.41 1.41 1.79-1.8-1.41-1.41-1.79 1.8z"/>
  </svg>
);
const BoltIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <path d="M7 2v11h3v9l7-12h-4l4-8z"/>
  </svg>
);

// Inline spinner
function Spin({ color = '#05C46B' }: { color?: string }) {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none">
      <circle cx={12} cy={12} r={9} stroke="rgba(255,255,255,0.15)" strokeWidth={3} />
      <path d="M12 3a9 9 0 019 9" stroke={color} strokeWidth={3} strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

function DeliveryCountdown({ deliveryDate }: { deliveryDate?: Date | null }) {
  const [, setTick] = React.useState(0);
  React.useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 60000);
    return () => clearInterval(id);
  }, []);

  if (!deliveryDate) {
    return <div style={{ color: '#86888f', fontSize: 14, fontWeight: 500, marginTop: 4 }}>Delivery date pending</div>;
  }

  const now = new Date();
  const diff = deliveryDate.getTime() - now.getTime();
  const days = Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
  const hours = Math.max(0, Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60)));
  const isPast = diff <= 0;
  if (isPast) {
    return <div style={{ color: '#0BE881', fontWeight: 700, fontSize: 18 }}>Delivery Day! 🎉</div>;
  }
  return (
    <div style={{ display: 'flex', gap: 20, justifyContent: 'center' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ color: '#05C46B', fontWeight: 700, fontSize: 36, lineHeight: 1, letterSpacing: '-1px' }}>{days}</div>
        <div style={{ color: '#86888f', fontSize: 11, marginTop: 3 }}>days</div>
      </div>
      <div style={{ color: '#86888f', fontSize: 28, lineHeight: 1.3, alignSelf: 'flex-start', marginTop: 4 }}>:</div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ color: '#05C46B', fontWeight: 700, fontSize: 36, lineHeight: 1, letterSpacing: '-1px' }}>{String(hours).padStart(2, '0')}</div>
        <div style={{ color: '#86888f', fontSize: 11, marginTop: 3 }}>hours</div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* PRE-DELIVERY MISSION CONTROL                                               */
/* For the anxious customer obsessing over every detail of their order         */
/* ═══════════════════════════════════════════════════════════════════════════ */

function PreDeliveryDashboard() {
  const { dossier } = useDossierData();
  const history = useHistory();
  const [picoYPlaca, setPicoYPlaca] = React.useState<any>(null);
  const [orderTasks, setOrderTasks] = React.useState<OrderTask[]>([]);
  const [orderFinancing, setOrderFinancing] = React.useState<Record<string, unknown> | null>(null);
  const [orderStatus, setOrderStatus] = React.useState<Record<string, unknown> | null>(null);
  const [orderLoading, setOrderLoading] = React.useState(false);

  React.useEffect(() => {
    const placa = dossier?.runt?.placa;
    if (placa) {
      api.getPicoYPlaca(placa).then(setPicoYPlaca).catch(() => {});
    }
  }, [dossier?.runt?.placa]);

  React.useEffect(() => {
    setOrderLoading(true);
    api.getOrderDetails()
      .then(details => {
        setOrderTasks(details.tasks || []);
        setOrderFinancing(details.financing || null);
        setOrderStatus(details.status as unknown as Record<string, unknown> || null);
      })
      .catch(() => {
        // Fallback: try basic order status
        api.getOrderStatus().then(s => {
          setOrderStatus(s as unknown as Record<string, unknown>);
        }).catch(() => {});
      })
      .finally(() => setOrderLoading(false));
  }, []);

  const status = dossier?.real_status;
  const order = dossier?.order;
  const specs = dossier?.specs;
  const phase = status?.phase || 'ordered';
  const phaseLabels: Record<string, string> = {
    ordered: 'Ordenado', produced: 'Producido', shipped: 'En Tránsito',
    in_country: 'En País', registered: 'Registrado', delivery_scheduled: 'Cita Programada', delivered: 'Entregado',
  };
  const phaseColors: Record<string, string> = {
    ordered: '#0FBCF9', produced: '#F99716', shipped: '#F99716',
    in_country: '#0BE881', registered: '#0BE881', delivery_scheduled: '#05C46B', delivered: '#05C46B',
  };
  const phaseColor = phaseColors[phase] || '#0FBCF9';

  // Build summary line from current state
  const summaryParts: string[] = [];
  if (status?.is_in_country && !status?.in_runt) summaryParts.push('Registro RUNT pendiente');
  else if (status?.in_runt && !status?.has_placa) summaryParts.push('Asignación de placa pendiente');
  else if (status?.has_placa && !status?.has_soat) summaryParts.push('SOAT pendiente');
  else if (status?.is_shipped && !status?.is_in_country) summaryParts.push('Vehículo en tránsito marítimo');
  else if (status?.is_produced && !status?.is_shipped) summaryParts.push('Listo para envío');
  else if (order?.current?.order_substatus) summaryParts.push(order.current.order_substatus);
  const summaryLine = summaryParts.join(' · ') || order?.current?.order_status || 'Procesando orden';

  return (
    <div className="page-pad" style={{ paddingTop: 8 }}>
      {/* ── Hero: Car + Countdown ── */}
      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        <div style={{ maxWidth: 240, margin: '0 auto', filter: 'drop-shadow(0 0 30px rgba(5,196,107,0.1))' }}>
          <ModelYSilhouette locked={true} />
        </div>
        <DeliveryCountdown deliveryDate={status?.delivery_date ? new Date(status.delivery_date) : null} />
        <div style={{ color: '#86888f', fontSize: 11, marginTop: 6 }}>
          {order?.reservation_number ? `RN ${order.reservation_number}` : ''}
          {specs?.exterior_color ? ` · ${specs.exterior_color}` : ''}
          {specs?.variant ? ` · ${specs.variant}` : ''}
        </div>
      </div>

      {/* ── Status Card ── */}
      <div className="tesla-card" style={{ padding: 16, marginBottom: 12 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: phaseColor, background: `${phaseColor}18`, padding: '4px 12px', borderRadius: 100 }}>
            {phaseLabels[phase] || phase}
          </span>
          {order?.current?.order_status && order.current.order_status !== phaseLabels[phase] && (
            <span style={{ fontSize: 11, color: '#86888f' }}>{order.current.order_status}</span>
          )}
        </div>
        <div style={{ color: '#fff', fontSize: 14, fontWeight: 500, marginBottom: 4 }}>{summaryLine}</div>
        {order?.current?.delivery_window_start && (
          <div style={{ color: '#86888f', fontSize: 12, marginTop: 6 }}>
            Entrega estimada: <span style={{ color: '#05C46B', fontWeight: 600 }}>{order.current.delivery_window_start} — {order.current.delivery_window_end}</span>
          </div>
        )}
        {status?.delivery_date && (
          <div style={{ color: '#05C46B', fontSize: 14, fontWeight: 700, marginTop: 8 }}>
            Cita: {status.delivery_date}
            {status.delivery_location && <span style={{ fontWeight: 400, fontSize: 12, color: '#86888f' }}> · {status.delivery_location}</span>}
          </div>
        )}
      </div>

      {/* ── Pico y Placa ── */}
      {picoYPlaca && picoYPlaca.placa && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', marginBottom: 10,
          borderRadius: 10, border: `1px solid ${picoYPlaca.restringido ? 'rgba(255,107,107,0.2)' : 'rgba(11,232,129,0.15)'}`,
          background: picoYPlaca.restringido ? 'rgba(255,107,107,0.06)' : 'rgba(11,232,129,0.04)',
        }}>
          <span style={{ fontSize: 18 }}>{picoYPlaca.restringido ? '🚫' : '✅'}</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: picoYPlaca.restringido ? '#FF6B6B' : '#0BE881' }}>
              {picoYPlaca.restringido ? 'Pico y Placa hoy — No puedes circular' : 'Sin restricción hoy'}
            </div>
            <div style={{ fontSize: 10, color: '#86888f' }}>
              {picoYPlaca.motivo || `Placa ${picoYPlaca.placa} · ${picoYPlaca.ciudad || ''}`}
            </div>
          </div>
        </div>
      )}

      {/* ── Checklist summary ── */}
      {status && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 12, justifyContent: 'center' }}>
          {[
            { flag: status.vin_assigned, label: 'VIN' },
            { flag: status.is_produced, label: 'Producido' },
            { flag: status.is_shipped, label: 'Enviado' },
            { flag: status.is_in_country, label: 'En País' },
            { flag: status.is_customs_cleared, label: 'Aduana' },
            { flag: status.in_runt, label: 'RUNT' },
            { flag: status.has_placa, label: 'Placa' },
            { flag: status.has_soat, label: 'SOAT' },
            { flag: status.is_delivery_scheduled, label: 'Cita' },
          ].filter(f => f.flag != null).map(f => (
            <span key={f.label} style={{
              fontSize: 9, fontWeight: 600, padding: '2px 7px', borderRadius: 100,
              background: f.flag ? 'rgba(11,232,129,0.1)' : 'rgba(255,255,255,0.03)',
              color: f.flag ? '#0BE881' : 'rgba(255,255,255,0.2)',
              border: `1px solid ${f.flag ? 'rgba(11,232,129,0.15)' : 'rgba(255,255,255,0.05)'}`,
            }}>{f.flag ? '✓' : '○'} {f.label}</span>
          ))}
        </div>
      )}

      {/* ── Order Process Tracker ── */}
      <OrderProcessTracker
        orderStatus={orderStatus}
        tasks={orderTasks}
        financing={orderFinancing}
        realStatus={status}
        logistics={dossier?.logistics}
        runt={dossier?.runt}
        financial={dossier?.financial}
        loading={orderLoading}
      />

      {/* ── CTA: View full detail ── */}
      <button
        onClick={() => history.push('/info')}
        className="tesla-btn"
        style={{ width: '100%', fontSize: 14, padding: '14px 20px', borderRadius: 12, marginBottom: 8 }}
      >
        Ver detalle completo →
      </button>

      {/* Last updated */}
      {dossier?.last_updated && (
        <div style={{ textAlign: 'center', fontSize: 10, color: 'rgba(255,255,255,0.2)', paddingBottom: 8 }}>
          Actualizado: {new Date(dossier.last_updated).toLocaleString()}
        </div>
      )}
    </div>
  );
}

const TeslaIcon = () => (
  <svg width={48} height={48} viewBox="0 0 24 24" fill="#05C46B">
    <path d="M12 3l-4 5h3v5H7l5 8 5-8h-4V8h3z"/>
  </svg>
);

const Dashboard: React.FC = () => {
  const { state, charge, climate, loading, error, refresh, lastUpdated, connected } = useVehicleData();
  // Post-delivery: vehicle data is available (charge_state present)
  const isPostDelivery = charge !== null || state !== null;
  const { tiles: enabledTiles } = useDashboardTiles();
  const isTileEnabled = (id: string) => enabledTiles.some((t) => t.id === id);
  const [cmdLoading, setCmdLoading] = useState<string | null>(null);
  const [cmdError, setCmdError] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [authenticated, setAuthenticated] = useState(true); // Assume true initially
  const [authLoading, setAuthLoading] = useState(false);
  const [fleetData, setFleetData] = useState<FleetVehicle[]>([]);
  const [fleetLoading, setFleetLoading] = useState(false);
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginMfa, setLoginMfa] = useState('');
  const [mfaRequired, setMfaRequired] = useState(false);
  const [loginError, setLoginError] = useState('');
  const history = useHistory();

  // Check auth status on mount
  React.useEffect(() => {
    api.getAuthStatus().then(s => {
      setAuthenticated(s.authenticated);
      setAuthChecked(true);
    }).catch(() => setAuthChecked(true));
  }, []);

  // Fetch fleet summary when fleet tile is enabled
  React.useEffect(() => {
    if (!isTileEnabled('fleet')) return;
    setFleetLoading(true);
    api.getFleetSummary().then(data => {
      setFleetData(data);
    }).catch(() => {
      setFleetData([]);
    }).finally(() => setFleetLoading(false));
  }, [enabledTiles]);

  const doLogin = async () => {
    if (!loginEmail.trim() || !loginPassword.trim()) return;
    setAuthLoading(true);
    setLoginError('');
    try {
      const result = await api.browserLogin(loginEmail.trim(), loginPassword.trim(), loginMfa || undefined);
      if (result.ok) {
        setAuthenticated(true);
        setMfaRequired(false);
        refresh();
      } else if (result.mfa_required) {
        setMfaRequired(true);
      } else {
        setLoginError(result.error || 'Login failed');
      }
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || 'Login failed';
      if (msg.includes('MFA') || msg.includes('mfa')) {
        setMfaRequired(true);
      } else {
        setLoginError(msg);
      }
    } finally {
      setAuthLoading(false);
    }
  };

  const handleCommand = async (command: string, params?: Record<string, unknown>, label?: string) => {
    const k = label || command;
    setCmdLoading(k);
    setCmdError(null);
    try {
      await api.sendCommand({ command, params });
      setTimeout(refresh, 1500);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Command failed';
      setCmdError(msg);
    } finally {
      setCmdLoading(null);
    }
  };

  const handleWake = async () => {
    setCmdLoading('wake');
    try {
      await api.wakeVehicle();
      setTimeout(refresh, 3000);
    } catch {
      // silently fail
    } finally {
      setCmdLoading(null);
    }
  };

  const doRefresh = async (event: CustomEvent) => {
    refresh();
    await new Promise<void>((r) => setTimeout(r, 1000));
    (event.target as HTMLIonRefresherElement).complete();
  };

  const batteryPct = state?.battery_level ?? charge?.battery_level;
  const isLocked = state?.locked ?? true;
  const sentryOn = state?.sentry_mode ?? false;
  const vehicleState = state?.state;
  const isCharging = state?.charging_state === 'Charging' || charge?.charging_state === 'Charging';
  const climateOn = state?.is_climate_on ?? climate?.is_climate_on ?? false;
  const displayName = state?.display_name || 'Model Y';
  const range = state?.battery_range;
  const insideTemp = state?.inside_temp ?? climate?.inside_temp;
  const outsideTemp = state?.outside_temp ?? climate?.outside_temp;
  const isAsleep = vehicleState === 'asleep' || vehicleState === 'sleeping';

  // Ready-to-drive assessment (mirrors tesla vehicle ready logic)
  const readyIssues: string[] = [];
  if (batteryPct != null && batteryPct < 20) readyIssues.push('Low battery');
  if (isCharging) readyIssues.push('Still charging');
  if (!isLocked) readyIssues.push('Unlocked');
  if (outsideTemp != null && outsideTemp < 5 && !climateOn) readyIssues.push('Cold outside');
  const isReady = !isAsleep && readyIssues.length === 0 && batteryPct != null;

  const batteryColor =
    batteryPct == null ? '#86888f'
    : batteryPct > 50 ? '#0BE881'
    : batteryPct > 20 ? '#F99716'
    : '#FF6B6B';

  const actions = [
    {
      key: 'lock',
      icon: isLocked ? <LockIcon /> : <UnlockIcon />,
      label: isLocked ? 'Unlock' : 'Lock',
      cmd: isLocked ? 'door_unlock' : 'door_lock',
      iconBg: isLocked ? 'rgba(255,255,255,0.1)' : '#05C46B',
    },
    {
      key: 'climate',
      icon: <AcIcon />,
      label: climateOn ? 'AC Off' : 'AC On',
      cmd: climateOn ? 'auto_conditioning_stop' : 'auto_conditioning_start',
      iconBg: climateOn ? 'rgba(15,188,249,0.85)' : 'rgba(255,255,255,0.1)',
    },
    {
      key: 'flash',
      icon: <FlashLightsIcon />,
      label: 'Flash',
      cmd: 'flash_lights',
      iconBg: 'rgba(249,151,22,0.7)',
    },
    {
      key: 'sentry',
      icon: <span style={{ fontSize: 18 }}>{sentryOn ? '🛡' : '🛡'}</span>,
      label: sentryOn ? 'Sentry Off' : 'Sentry On',
      cmd: 'set_sentry_mode',
      cmdParams: { on: !sentryOn },
      iconBg: sentryOn ? 'rgba(5,196,107,0.7)' : 'rgba(255,255,255,0.1)',
    },
    {
      key: 'trunk',
      icon: <span style={{ fontSize: 18 }}>🚗</span>,
      label: 'Trunk',
      cmd: 'actuate_trunk',
      cmdParams: { which_trunk: 'rear' },
      iconBg: 'rgba(255,255,255,0.1)',
    },
  ];

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700, letterSpacing: '-0.3px' }}>
            {displayName}
          </IonTitle>
          <div slot="end" style={{ paddingRight: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span
              title={connected ? 'SSE connected' : 'SSE disconnected'}
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: connected ? '#0BE881' : '#86888f',
                display: 'inline-block',
                flexShrink: 0,
              }}
            />
            {!loading && state && !isAsleep && (
              <span style={{
                fontSize: 10,
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: 10,
                background: isReady ? 'rgba(11,232,129,0.15)' : 'rgba(249,151,22,0.15)',
                color: isReady ? '#0BE881' : '#F99716',
              }}>
                {isReady ? '✓ Ready' : `⚠ ${readyIssues.length}`}
              </span>
            )}
            {loading && !state ? (
              <IonSpinner name="dots" style={{ '--color': '#86888f', width: 20, height: 20 } as React.CSSProperties} />
            ) : (
              <StatusBadge state={vehicleState} />
            )}
          </div>
        </IonToolbar>
      </IonHeader>

      <IonContent>
        <IonRefresher slot="fixed" onIonRefresh={doRefresh}>
          <IonRefresherContent />
        </IonRefresher>

        {/* ---- Onboarding: not authenticated ---- */}
        {authChecked && !authenticated ? (
          <div className="empty-state" style={{ minHeight: 'calc(100vh - 56px)', justifyContent: 'center' }}>
            <div style={{ width: 80, height: 80, borderRadius: '50%', background: 'rgba(5,196,107,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 20 }}>
              <TeslaIcon />
            </div>
            <div style={{ color: '#ffffff', fontWeight: 700, fontSize: 22, letterSpacing: '-0.5px' }}>Welcome to Tesla Control</div>
            <div style={{ color: '#86888f', fontSize: 14, lineHeight: 1.6, maxWidth: 280, textAlign: 'center', margin: '8px 0 24px' }}>
              Connect your Tesla account to monitor your vehicle, track deliveries, and access all features.
            </div>

            <div style={{ width: '100%', maxWidth: 320 }}>
              <input
                type="email"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                placeholder="Tesla email"
                className="tesla-input"
                style={{ marginBottom: 8, fontSize: 14 }}
                disabled={authLoading}
              />
              <input
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                placeholder="Password"
                className="tesla-input"
                style={{ marginBottom: 8, fontSize: 14 }}
                disabled={authLoading}
                onKeyDown={(e) => e.key === 'Enter' && doLogin()}
              />
              {mfaRequired && (
                <input
                  type="text"
                  value={loginMfa}
                  onChange={(e) => setLoginMfa(e.target.value)}
                  placeholder="MFA code"
                  className="tesla-input"
                  style={{ marginBottom: 8, fontSize: 14, textAlign: 'center', letterSpacing: '0.2em' }}
                  autoFocus
                  onKeyDown={(e) => e.key === 'Enter' && doLogin()}
                />
              )}
              {loginError && (
                <div style={{ color: '#FF6B6B', fontSize: 12, marginBottom: 8, textAlign: 'center' }}>{loginError}</div>
              )}
              <button
                onClick={doLogin}
                disabled={authLoading || !loginEmail.trim() || !loginPassword.trim()}
                className="tesla-btn"
                style={{ width: '100%', fontSize: 16, padding: '14px 24px', borderRadius: 12 }}
              >
                {authLoading ? 'Connecting...' : mfaRequired ? 'Verify MFA' : 'Login with Tesla'}
              </button>
            </div>

            <div style={{ color: '#86888f', fontSize: 11, marginTop: 24, opacity: 0.5 }}>
              Your credentials are sent directly to Tesla — we never see your password.
            </div>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        ) : !isPostDelivery && error ? (
          /* ---- PRE-DELIVERY DASHBOARD ---- */
          <PreDeliveryDashboard />
        ) : (
          <div className="page-pad">
            {/* ---- Car silhouette card (always visible) ---- */}
            <div className="tesla-card" style={{ padding: '8px 4px 4px' }}>
              <ModelYSilhouette
                locked={isLocked}
                chargingState={state?.charging_state || charge?.charging_state}
                batteryPercent={batteryPct}
                climateOn={climateOn}
              />
            </div>

            {/* ---- Hero stats row (battery tile) ---- */}
            {isTileEnabled('battery') && <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 10 }}>
              {/* Battery */}
              <div className="tesla-card" style={{ textAlign: 'center', padding: '16px 4px' }}>
                <div style={{ fontSize: 44, fontWeight: 700, color: batteryColor, lineHeight: 1, letterSpacing: '-2px', fontVariantNumeric: 'tabular-nums' }}>
                  {batteryPct ?? '--'}
                </div>
                <div style={{ color: '#f5f5f7', fontSize: 11, fontWeight: 600, marginTop: 2 }}>%</div>
                <div style={{ color: '#86888f', fontSize: 10, marginTop: 3 }}>
                  {range ? `${Math.round(range)} mi` : 'Battery'}
                </div>
              </div>

              {/* Inside temp */}
              <div className="tesla-card" style={{ textAlign: 'center', padding: '16px 4px' }}>
                <div style={{ fontSize: 44, fontWeight: 700, color: climateOn ? '#0FBCF9' : '#86888f', lineHeight: 1, letterSpacing: '-2px', fontVariantNumeric: 'tabular-nums' }}>
                  {insideTemp != null ? Math.round(insideTemp) : '--'}
                </div>
                <div style={{ color: climateOn ? '#0FBCF9' : '#f5f5f7', fontSize: 11, fontWeight: 600, marginTop: 2 }}>°C</div>
                <div style={{ color: '#86888f', fontSize: 10, marginTop: 3 }}>
                  {outsideTemp != null ? `Out ${Math.round(outsideTemp)}°` : 'Interior'}
                </div>
              </div>

              {/* Charge power */}
              <div className="tesla-card" style={{ textAlign: 'center', padding: '16px 4px' }}>
                <div style={{ fontSize: 44, fontWeight: 700, color: isCharging ? '#0BE881' : '#86888f', lineHeight: 1, letterSpacing: '-2px', fontVariantNumeric: 'tabular-nums' }}>
                  {isCharging ? (state?.charger_power ?? charge?.charger_power ?? 0) : '--'}
                </div>
                <div style={{ color: isCharging ? '#0BE881' : '#f5f5f7', fontSize: 11, fontWeight: 600, marginTop: 2 }}>
                  {isCharging ? 'kW' : '···'}
                </div>
                <div style={{ color: '#86888f', fontSize: 10, marginTop: 3 }}>
                  {isCharging ? `${state?.minutes_to_full_charge ?? charge?.minutes_to_full_charge ?? 0}m left` : 'Charging'}
                </div>
              </div>
            </div>}

            {/* ---- Quick actions ---- */}
            {isTileEnabled('quickActions') && (
              <>
                <p className="section-title">Quick Actions</p>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(3, 1fr)',
                    gap: 8,
                    marginBottom: 10,
                  }}
                >
                  {actions.map((a) => (
                    <button
                      key={a.key}
                      onClick={() => handleCommand(a.cmd, (a as any).cmdParams, a.key)}
                      disabled={!!cmdLoading}
                      style={{
                        background: 'rgba(255,255,255,0.04)',
                        border: `1px solid rgba(255,255,255,0.07)`,
                        borderRadius: 14,
                        padding: '14px 4px',
                        cursor: cmdLoading === a.key ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        flexDirection: 'column' as const,
                        alignItems: 'center',
                        gap: 7,
                        opacity: cmdLoading && cmdLoading !== a.key ? 0.4 : 1,
                        transition: 'all 0.15s',
                        fontFamily: 'inherit',
                      }}
                    >
                      <div
                        style={{
                          width: 40,
                          height: 40,
                          borderRadius: '50%',
                          background: a.iconBg,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#ffffff',
                          boxShadow: a.key === 'climate' && climateOn ? '0 0 14px rgba(15,188,249,0.5)' : a.key === 'lock' && !isLocked ? '0 0 14px rgba(5,196,107,0.5)' : 'none',
                        }}
                      >
                        {cmdLoading === a.key ? <Spin color="#fff" /> : a.icon}
                      </div>
                      <span style={{ color: '#f5f5f7', fontSize: 10, fontWeight: 600, textAlign: 'center' }}>
                        {a.label}
                      </span>
                    </button>
                  ))}
                </div>
              </>
            )}

            {/* ---- Wake button if asleep (always visible) ---- */}
            {isAsleep && (
              <button
                onClick={handleWake}
                disabled={cmdLoading === 'wake'}
                className="tesla-btn"
                style={{ marginBottom: 10 }}
              >
                {cmdLoading === 'wake' ? <Spin color="#fff" /> : <WakeIcon />}
                {cmdLoading === 'wake' ? 'Waking...' : 'Wake Vehicle'}
              </button>
            )}

            {/* ---- Charging progress card (schedule tile) ---- */}
            {isTileEnabled('schedule') && isCharging && (
              <div className="tesla-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#0BE881', fontWeight: 600, fontSize: 14 }}>
                    <BoltIcon />
                    Charging
                  </div>
                  <span style={{ color: '#86888f', fontSize: 12 }}>
                    Limit: {state?.charge_limit_soc ?? charge?.charge_limit_soc ?? '--'}%
                  </span>
                </div>
                {/* Progress bar */}
                <div className="progress-track" style={{ marginBottom: 8 }}>
                  <div
                    className="progress-fill charging"
                    style={{ width: `${batteryPct ?? 0}%` }}
                  />
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12 }}>
                  <span style={{ color: '#86888f' }}>
                    {state?.charger_power ?? charge?.charger_power ?? 0} kW
                  </span>
                  <span style={{ color: '#86888f' }}>
                    +{(state?.charge_energy_added ?? charge?.charge_energy_added ?? 0).toFixed(1)} kWh added
                  </span>
                  <span style={{ color: '#0BE881' }}>
                    {state?.minutes_to_full_charge ?? charge?.minutes_to_full_charge ?? 0}m left
                  </span>
                </div>
              </div>
            )}

            {/* ---- Recent Charges ---- */}
            {isTileEnabled('recentCharges') && <RecentCharges />}

            {/* ---- Vehicle info footer (vehicle tile) ---- */}
            {isTileEnabled('vehicle') && state && !isAsleep && (
              <div style={{
                display: 'flex',
                justifyContent: 'center',
                gap: 16,
                padding: '8px 0',
                fontSize: 11,
                color: '#86888f',
              }}>
                {state.car_version && (
                  <span>🚗 {state.car_version}</span>
                )}
                <span>{sentryOn ? '🛡 Sentry' : ''}</span>
                {state.odometer && (
                  <span>📏 {Math.round((state.odometer as number) * 1.60934).toLocaleString()} km</span>
                )}
              </div>
            )}

            {/* ---- Fleet health tile (only shown when >1 vehicle) ---- */}
            {isTileEnabled('fleet') && fleetData.length > 1 && (
              <>
                <p className="section-title">Fleet Health</p>
                <div className="tesla-card" style={{ padding: 12, marginBottom: 10 }}>
                  {fleetLoading ? (
                    <div style={{ textAlign: 'center', padding: 12 }}>
                      <IonSpinner name="dots" style={{ '--color': '#86888f' } as React.CSSProperties} />
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {fleetData.map(v => {
                        const battColor = v.battery_level == null ? '#86888f'
                          : v.battery_level > 50 ? '#0BE881'
                          : v.battery_level > 20 ? '#F99716'
                          : '#FF6B6B';
                        return (
                          <div key={v.vin} style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '8px 10px',
                            borderRadius: 8,
                            background: 'rgba(255,255,255,0.03)',
                            border: '1px solid rgba(255,255,255,0.06)',
                          }}>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                              <span style={{ fontSize: 13, fontWeight: 600, color: '#f5f5f7' }}>
                                {v.alias}
                              </span>
                              <span style={{ fontSize: 10, color: '#86888f' }}>
                                ...{v.vin.slice(-6)}
                              </span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                              {v.battery_level != null && (
                                <span style={{ fontSize: 13, fontWeight: 700, color: battColor }}>
                                  {v.battery_level}%
                                </span>
                              )}
                              {v.charging_state === 'Charging' && (
                                <span style={{ fontSize: 10, color: '#0BE881' }}>⚡</span>
                              )}
                              <span style={{ fontSize: 11, color: v.locked ? '#86888f' : '#F99716' }}>
                                {v.locked == null ? '—' : v.locked ? '🔒' : '🔓'}
                              </span>
                              {v.sentry && (
                                <span style={{ fontSize: 11, color: '#0FBCF9' }}>🛡</span>
                              )}
                              {v.error && (
                                <span style={{ fontSize: 10, color: '#FF6B6B' }} title={v.error}>⚠</span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </>
            )}

            {/* ---- Last updated ---- */}
            {lastUpdated && (
              <div style={{ textAlign: 'center', paddingTop: 8 }}>
                <span style={{ color: '#86888f', fontSize: 11, opacity: 0.7 }}>
                  Updated {lastUpdated.toLocaleTimeString()}
                </span>
              </div>
            )}
          </div>
        )}
      </IonContent>

      <IonToast
        isOpen={!!cmdError}
        message={cmdError ?? ''}
        duration={3000}
        color="danger"
        onDidDismiss={() => setCmdError(null)}
        position="bottom"
      />
    </IonPage>
  );
};

export default Dashboard;
