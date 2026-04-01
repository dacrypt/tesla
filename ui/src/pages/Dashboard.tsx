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
} from '@ionic/react';
import { useHistory } from 'react-router-dom';
import ModelYSilhouette from '../components/ModelYSilhouette';
import StatusBadge from '../components/StatusBadge';
import { useVehicleData } from '../hooks/useVehicleData';
import { api } from '../api/client';

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

const DELIVERY_DATE = new Date('2026-04-10T10:00:00');

function DeliveryCountdown() {
  const [, setTick] = React.useState(0);
  React.useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 60000);
    return () => clearInterval(id);
  }, []);
  const now = new Date();
  const diff = DELIVERY_DATE.getTime() - now.getTime();
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

const TeslaIcon = () => (
  <svg width={48} height={48} viewBox="0 0 24 24" fill="#05C46B">
    <path d="M12 3l-4 5h3v5H7l5 8 5-8h-4V8h3z"/>
  </svg>
);

const Dashboard: React.FC = () => {
  const { state, charge, climate, loading, error, refresh, lastUpdated } = useVehicleData();
  const [cmdLoading, setCmdLoading] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [authenticated, setAuthenticated] = useState(true); // Assume true initially
  const [authLoading, setAuthLoading] = useState(false);
  const [showAuthInput, setShowAuthInput] = useState(false);
  const [callbackUrl, setCallbackUrl] = useState('');
  const history = useHistory();

  // Check auth status on mount
  React.useEffect(() => {
    api.getAuthStatus().then(s => {
      setAuthenticated(s.authenticated);
      setAuthChecked(true);
    }).catch(() => setAuthChecked(true));
  }, []);

  const startLogin = async () => {
    setAuthLoading(true);
    try {
      const data = await api.getAuthLogin();
      setShowAuthInput(true);
      window.open(data.auth_url, 'tesla-auth', 'width=600,height=700');
    } catch { /* */ } finally { setAuthLoading(false); }
  };

  const submitCallback = async () => {
    if (!callbackUrl.trim()) return;
    setAuthLoading(true);
    try {
      const url = new URL(callbackUrl.trim());
      const code = url.searchParams.get('code');
      if (!code) return;
      await api.postAuthCallback(code, url.searchParams.get('state') || '');
      setAuthenticated(true);
      setShowAuthInput(false);
      setCallbackUrl('');
      refresh();
    } catch { /* */ } finally { setAuthLoading(false); }
  };

  const handleCommand = async (command: string, params?: Record<string, unknown>, label?: string) => {
    const k = label || command;
    setCmdLoading(k);
    try {
      await api.sendCommand({ command, params });
      setTimeout(refresh, 1500);
    } catch {
      // silently fail
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
  const vehicleState = state?.state;
  const isCharging = state?.charging_state === 'Charging' || charge?.charging_state === 'Charging';
  const climateOn = state?.is_climate_on ?? climate?.is_climate_on ?? false;
  const displayName = state?.display_name || 'Model Y';
  const range = state?.battery_range;
  const insideTemp = state?.inside_temp ?? climate?.inside_temp;
  const outsideTemp = state?.outside_temp ?? climate?.outside_temp;
  const isAsleep = vehicleState === 'asleep' || vehicleState === 'sleeping';

  const batteryColor =
    batteryPct == null ? '#86888f'
    : batteryPct > 50 ? '#0BE881'
    : batteryPct > 20 ? '#F99716'
    : '#05C46B';

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
      key: 'horn',
      icon: <HornIcon />,
      label: 'Horn',
      cmd: 'honk_horn',
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
          <div slot="end" style={{ paddingRight: 4 }}>
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

            {!showAuthInput ? (
              <button
                onClick={startLogin}
                disabled={authLoading}
                className="tesla-btn"
                style={{ width: '100%', maxWidth: 300, fontSize: 16, padding: '14px 24px', borderRadius: 12 }}
              >
                {authLoading ? <span style={{ display: 'inline-block', width: 18, height: 18, border: '2px solid rgba(255,255,255,0.2)', borderTopColor: '#fff', borderRadius: '50%', animation: 'spin .7s linear infinite' }} /> : 'Login with Tesla'}
              </button>
            ) : (
              <div style={{ width: '100%', maxWidth: 320 }}>
                <div style={{ color: '#86888f', fontSize: 12, marginBottom: 8, lineHeight: 1.5, textAlign: 'center' }}>
                  After signing in, you'll see a blank page.<br />
                  <strong style={{ color: '#fff' }}>Copy the full URL</strong> and paste it below.
                </div>
                <input
                  type="url"
                  value={callbackUrl}
                  onChange={(e) => setCallbackUrl(e.target.value)}
                  placeholder="https://auth.tesla.com/void/callback?code=..."
                  className="tesla-input mono"
                  style={{ marginBottom: 8, fontSize: 12 }}
                />
                <button
                  onClick={submitCallback}
                  disabled={authLoading || !callbackUrl.trim()}
                  className="tesla-btn"
                  style={{ width: '100%', fontSize: 14, padding: '12px 16px' }}
                >
                  {authLoading ? 'Connecting...' : 'Connect'}
                </button>
              </div>
            )}

            <div style={{ color: '#86888f', fontSize: 11, marginTop: 24, opacity: 0.5 }}>
              Your credentials are sent directly to Tesla — we never see your password.
            </div>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          </div>
        ) : error && !state ? (
          /* ---- Vehicle not connected / pre-delivery ---- */
          <div className="empty-state" style={{ minHeight: 'calc(100vh - 56px)', justifyContent: 'flex-start', paddingTop: '8vh' }}>
            {/* Car silhouette — fills upper space */}
            <div style={{ width: '100%', maxWidth: 360, filter: 'drop-shadow(0 0 40px rgba(5,196,107,0.12))' }}>
              <ModelYSilhouette locked={true} />
            </div>

            {/* Delivery countdown — hero element */}
            <div style={{ width: '100%', maxWidth: 300, background: 'rgba(5,196,107,0.07)', border: '1px solid rgba(5,196,107,0.18)', borderRadius: 16, padding: '20px 24px', marginBottom: 4 }}>
              <div style={{ color: '#86888f', fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 12 }}>Your Model Y Arrives In</div>
              <DeliveryCountdown />
              <div style={{ color: '#86888f', fontSize: 11, marginTop: 12, textAlign: 'center' }}>
                Apr 10, 2026 · RN126460939
              </div>
            </div>

            {/* Status */}
            <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 16, marginTop: 8 }}>
              Vehicle Not Yet Delivered
            </div>
            <div style={{ color: '#86888f', fontSize: 13, lineHeight: 1.5 }}>
              Controls will be available after delivery
            </div>

            {/* Action row */}
            <div style={{ display: 'flex', gap: 8, maxWidth: 300, width: '100%', marginTop: 4 }}>
              <button
                onClick={handleWake}
                disabled={cmdLoading === 'wake'}
                className="tesla-btn secondary"
                style={{ flex: 1, fontSize: 13 }}
              >
                {cmdLoading === 'wake' ? <Spin color="#fff" /> : <WakeIcon />}
                {cmdLoading === 'wake' ? 'Waking...' : 'Try Wake'}
              </button>
              <button
                onClick={() => history.push('/settings')}
                className="tesla-btn secondary"
                style={{ flex: 1, fontSize: 13 }}
              >
                <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor"><path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/></svg>
                Settings
              </button>
            </div>
          </div>
        ) : (
          <div className="page-pad">
            {/* ---- Car silhouette card ---- */}
            <div className="tesla-card" style={{ padding: '8px 4px 4px' }}>
              <ModelYSilhouette
                locked={isLocked}
                chargingState={state?.charging_state || charge?.charging_state}
                batteryPercent={batteryPct}
                climateOn={climateOn}
              />
            </div>

            {/* ---- Hero stats row ---- */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8, marginBottom: 10 }}>
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
            </div>

            {/* ---- Quick actions ---- */}
            <p className="section-title">Quick Actions</p>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(4, 1fr)',
                gap: 8,
                marginBottom: 10,
              }}
            >
              {actions.map((a) => (
                <button
                  key={a.key}
                  onClick={() => handleCommand(a.cmd, undefined, a.key)}
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

            {/* ---- Wake button if asleep ---- */}
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

            {/* ---- Charging progress card ---- */}
            {isCharging && (
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
    </IonPage>
  );
};

export default Dashboard;
