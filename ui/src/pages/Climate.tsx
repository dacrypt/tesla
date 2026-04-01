import React, { useState, useEffect } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
  IonRange,
  IonToggle,
  IonToast,
} from '@ionic/react';
import SeatHeaterGrid from '../components/SeatHeaterGrid';
import { api } from '../api/client';
import { useVehicleData } from '../hooks/useVehicleData';

// ---- SVG Icons ----
const AcIcon = () => <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor"><path d="M22 11h-4.17l3.24-3.24-1.41-1.42L15 11h-2V9l4.66-4.66-1.42-1.41L13 6.17V2h-2v4.17L7.76 2.93 6.34 4.34 11 9v2H9L4.34 6.34 2.93 7.76 6.17 11H2v2h4.17l-3.24 3.24 1.41 1.42L9 13h2v2l-4.66 4.66 1.42 1.41L11 17.83V22h2v-4.17l3.24 3.24 1.42-1.41L13 15v-2h2l4.66 4.66 1.41-1.42L17.83 13H22z"/></svg>;
const HomeIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/></svg>;
const PawIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M4.5 9.5C3.12 9.5 2 8.38 2 7s1.12-2.5 2.5-2.5S7 5.62 7 7 5.88 9.5 4.5 9.5zm0-3.5C3.67 6 3 6.67 3 7.5S3.67 9 4.5 9 6 8.33 6 7.5 5.33 6 4.5 6zm6-2.5C9.12 3.5 8 2.38 8 1S9.12-1.5 10.5-1.5 13-.38 13 1s-1.12 2.5-2.5 2.5zm0-4C9.67 0 9 .67 9 1.5S9.67 3 10.5 3 12 2.33 12 1.5 11.33 1 10.5 1zm4 4C13.12 5 12 3.88 12 2.5S13.12 0 14.5 0 17 1.12 17 2.5 15.88 5 14.5 5zm0-4C13.67 1 13 1.67 13 2.5S13.67 4 14.5 4 16 3.33 16 2.5 15.33 1 14.5 1zm5 8C18.12 9 17 7.88 17 6.5S18.12 4 19.5 4 22 5.12 22 6.5 20.88 9 19.5 9zm0-4C18.67 5 18 5.67 18 6.5S18.67 8 19.5 8 21 7.33 21 6.5 20.33 5 19.5 5zM12 10c-2.76 0-7 3.13-7 6.5V20h14v-3.5c0-3.37-4.24-6.5-7-6.5z"/></svg>;
const TentIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M23.7 16.15L14 2.49a2 2 0 00-3.27-.05l-9.9 13.71A1.53 1.53 0 002 18h20a1.53 1.53 0 001.7-1.85zM11 10.5l-3.41 5.5H7l4-6.5L9.38 8 12 4.31 14.62 8 13 9.5z"/></svg>;
const ShieldAirIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/></svg>;
const SteeringIcon = () => <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 2c1.75 0 3.36.57 4.67 1.52L4.52 16.67C3.57 15.36 3 13.75 3 12c0-4.97 4.03-9 9-9zm0 16c-1.75 0-3.36-.57-4.67-1.52l12.15-12.15C20.43 7.64 21 9.25 21 11c0 4.97-4.03 9-9 9z"/></svg>;

function Spin() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none">
      <circle cx={12} cy={12} r={9} stroke="rgba(255,255,255,0.15)" strokeWidth={3} />
      <path d="M12 3a9 9 0 019 9" stroke="#05C46B" strokeWidth={3} strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

interface KeeperMode {
  id: number;
  label: string;
  icon: React.ReactNode;
  mode: string;
}

const Climate: React.FC = () => {
  const { state, climate, refresh } = useVehicleData();
  const [cmdLoading, setCmdLoading] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; color: string } | null>(null);
  const [driverTemp, setDriverTemp] = useState<number>(21);
  const [passengerTemp, setPassengerTemp] = useState<number>(21);
  const [tempDirty, setTempDirty] = useState(false);
  const [seatLoading, setSeatLoading] = useState<string | null>(null);

  const climateOn = state?.is_climate_on ?? climate?.is_climate_on ?? false;
  const insideTemp = state?.inside_temp ?? climate?.inside_temp;
  const outsideTemp = state?.outside_temp ?? climate?.outside_temp;
  const steeringHeater = state?.steering_wheel_heater ?? climate?.steering_wheel_heater ?? false;
  const bioweapon = state?.bioweapon_mode ?? climate?.bioweapon_mode ?? false;
  const keeperMode = state?.climate_keeper_mode ?? climate?.climate_keeper_mode ?? 'off';

  const seatValues = {
    fl: state?.seat_heater_left ?? climate?.seat_heater_left ?? 0,
    fr: state?.seat_heater_right ?? climate?.seat_heater_right ?? 0,
    rl: state?.seat_heater_rear_left ?? climate?.seat_heater_rear_left ?? 0,
    rc: state?.seat_heater_rear_center ?? climate?.seat_heater_rear_center ?? 0,
    rr: state?.seat_heater_rear_right ?? climate?.seat_heater_rear_right ?? 0,
  };

  useEffect(() => {
    if (!tempDirty) {
      const d = state?.driver_temp_setting ?? climate?.driver_temp_setting;
      const p = state?.passenger_temp_setting ?? climate?.passenger_temp_setting;
      if (d) setDriverTemp(d);
      if (p) setPassengerTemp(p);
    }
  }, [state, climate, tempDirty]);

  const runCmd = async (fn: () => Promise<unknown>, key: string, successMsg: string) => {
    setCmdLoading(key);
    try {
      await fn();
      setToast({ message: successMsg, color: 'success' });
      setTimeout(refresh, 1500);
    } catch {
      setToast({ message: 'Command failed', color: 'danger' });
    } finally {
      setCmdLoading(null);
    }
  };

  const handleSeatChange = async (seat: 'fl' | 'fr' | 'rl' | 'rc' | 'rr', level: number) => {
    const heaterMap: Record<string, number> = { fl: 0, fr: 1, rl: 2, rc: 4, rr: 3 };
    setSeatLoading(seat);
    try {
      await api.sendCommand({ command: 'remote_seat_heater_request', params: { heater: heaterMap[seat], level } });
      setToast({ message: `Seat heater → ${level === 0 ? 'Off' : level === 1 ? 'Low' : level === 2 ? 'Med' : 'High'}`, color: 'success' });
      setTimeout(refresh, 1500);
    } catch {
      setToast({ message: 'Command failed', color: 'danger' });
    } finally {
      setSeatLoading(null);
    }
  };

  const keeperModes: KeeperMode[] = [
    { id: 0, label: 'Off', icon: null, mode: 'off' },
    { id: 1, label: 'Keep', icon: <HomeIcon />, mode: 'keep' },
    { id: 2, label: 'Dog', icon: <PawIcon />, mode: 'dog' },
    { id: 3, label: 'Camp', icon: <TentIcon />, mode: 'camp' },
  ];

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700 }}>Climate</IonTitle>
          <div slot="end" style={{ paddingRight: 4 }}>
            <span style={{ color: climateOn ? '#0FBCF9' : '#86888f', fontWeight: 600, fontSize: 13 }}>
              {climateOn ? 'Active' : 'Off'}
            </span>
          </div>
        </IonToolbar>
      </IonHeader>

      <IonContent>
        <div className="page-pad">
          {/* ---- Temp display + climate toggle ---- */}
          <div className="tesla-card">
            {/* Temperature display — hero */}
            <div style={{ display: 'flex', justifyContent: 'center', gap: 0, marginBottom: 20 }}>
              <div style={{ flex: 1, textAlign: 'center', borderRight: '1px solid rgba(255,255,255,0.07)', paddingRight: 20 }}>
                <div className="label-xs" style={{ marginBottom: 8 }}>INSIDE</div>
                <div style={{ fontSize: 64, fontWeight: 700, color: climateOn ? '#0FBCF9' : '#86888f', lineHeight: 1, letterSpacing: '-3px', fontVariantNumeric: 'tabular-nums', filter: climateOn ? 'drop-shadow(0 0 12px rgba(15,188,249,0.4))' : 'none', transition: 'all 0.3s' }}>
                  {insideTemp != null ? Math.round(insideTemp) : '--'}
                </div>
                <div style={{ color: '#86888f', fontSize: 14, marginTop: 4 }}>°C</div>
              </div>
              <div style={{ flex: 1, textAlign: 'center', paddingLeft: 20 }}>
                <div className="label-xs" style={{ marginBottom: 8 }}>OUTSIDE</div>
                <div style={{ fontSize: 64, fontWeight: 700, color: '#f5f5f7', lineHeight: 1, letterSpacing: '-3px', fontVariantNumeric: 'tabular-nums' }}>
                  {outsideTemp != null ? Math.round(outsideTemp) : '--'}
                </div>
                <div style={{ color: '#86888f', fontSize: 14, marginTop: 4 }}>°C</div>
              </div>
            </div>

            {/* Climate toggle */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                borderTop: '1px solid rgba(255,255,255,0.08)',
                paddingTop: 14,
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{
                  width: 36, height: 36, borderRadius: '50%',
                  background: climateOn ? 'rgba(33,150,243,0.2)' : 'rgba(255,255,255,0.08)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: climateOn ? '#0FBCF9' : '#86888f',
                }}>
                  <AcIcon />
                </div>
                <div>
                  <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Climate Control</div>
                  <div style={{ color: '#86888f', fontSize: 12 }}>{climateOn ? 'On — conditioning active' : 'Off'}</div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {cmdLoading === 'climate_toggle' && <Spin />}
                <IonToggle
                  checked={climateOn}
                  onIonChange={(e) =>
                    runCmd(
                      () => e.detail.checked ? api.climateOn() : api.climateOff(),
                      'climate_toggle',
                      e.detail.checked ? 'Climate on' : 'Climate off'
                    )
                  }
                />
              </div>
            </div>
          </div>

          {/* ---- Temperature setpoints ---- */}
          <div className="tesla-card">
            <p className="section-title" style={{ paddingTop: 0 }}>Temperature</p>
            <div style={{ marginBottom: 14 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ color: '#86888f', fontSize: 13 }}>Driver</span>
                <span style={{ color: '#ffffff', fontWeight: 600, fontSize: 16 }}>{driverTemp.toFixed(1)}°C</span>
              </div>
              <IonRange
                min={16} max={30} step={0.5} value={driverTemp}
                onIonChange={(e) => { setDriverTemp(e.detail.value as unknown as number); setTempDirty(true); }}
              />
            </div>
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                <span style={{ color: '#86888f', fontSize: 13 }}>Passenger</span>
                <span style={{ color: '#ffffff', fontWeight: 600, fontSize: 16 }}>{passengerTemp.toFixed(1)}°C</span>
              </div>
              <IonRange
                min={16} max={30} step={0.5} value={passengerTemp}
                onIonChange={(e) => { setPassengerTemp(e.detail.value as unknown as number); setTempDirty(true); }}
              />
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => { setTempDirty(false); runCmd(() => api.setTemps(driverTemp, passengerTemp), 'set_temps', 'Temperatures set'); }}
                disabled={cmdLoading === 'set_temps'}
                className="tesla-btn"
                style={{ flex: 1 }}
              >
                {cmdLoading === 'set_temps' ? <Spin /> : null}
                Apply
              </button>
              <button
                onClick={() => { setDriverTemp(21); setPassengerTemp(21); runCmd(() => api.setTemps(21, 21), 'sync_temps', 'Synced to 21°C'); }}
                disabled={!!cmdLoading}
                className="tesla-btn secondary"
                style={{ flex: 1 }}
              >
                Sync 21°
              </button>
            </div>
          </div>

          {/* ---- Seat heaters ---- */}
          <div className="tesla-card">
            <p className="section-title" style={{ paddingTop: 0 }}>Seat Heaters</p>
            <SeatHeaterGrid values={seatValues} onChange={handleSeatChange} loading={seatLoading} />
          </div>

          {/* ---- Special features ---- */}
          <div className="tesla-card">
            <p className="section-title" style={{ paddingTop: 0 }}>Special Features</p>

            {/* Steering wheel heater */}
            <div className="stat-row">
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 32, height: 32, borderRadius: '50%', background: steeringHeater ? 'rgba(255,152,0,0.2)' : 'rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: steeringHeater ? '#F99716' : '#86888f' }}>
                  <SteeringIcon />
                </div>
                <div>
                  <div style={{ color: '#ffffff', fontSize: 14, fontWeight: 500 }}>Steering Wheel Heater</div>
                  <div style={{ color: '#86888f', fontSize: 12 }}>{steeringHeater ? 'Active' : 'Off'}</div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {cmdLoading === 'steering' && <Spin />}
                <IonToggle
                  checked={steeringHeater}
                  onIonChange={(e) => runCmd(() => api.sendCommand({ command: 'remote_steering_wheel_heater_request', params: { on: e.detail.checked } }), 'steering', `Steering heater ${e.detail.checked ? 'on' : 'off'}`)}
                />
              </div>
            </div>

            {/* Bioweapon defense */}
            <div className="stat-row" style={{ borderBottom: 'none' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <div style={{ width: 32, height: 32, borderRadius: '50%', background: bioweapon ? 'rgba(0,200,83,0.2)' : 'rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: bioweapon ? '#0BE881' : '#86888f' }}>
                  <ShieldAirIcon />
                </div>
                <div>
                  <div style={{ color: '#ffffff', fontSize: 14, fontWeight: 500 }}>Bioweapon Defense Mode</div>
                  <div style={{ color: '#86888f', fontSize: 12 }}>{bioweapon ? 'Active — max filtration' : 'Off'}</div>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {cmdLoading === 'bioweapon' && <Spin />}
                <IonToggle
                  checked={bioweapon}
                  onIonChange={(e) => runCmd(() => api.sendCommand({ command: 'set_bioweapon_mode', params: { on: e.detail.checked } }), 'bioweapon', `Bioweapon mode ${e.detail.checked ? 'on' : 'off'}`)}
                />
              </div>
            </div>
          </div>

          {/* ---- Keeper mode ---- */}
          <div className="tesla-card">
            <p className="section-title" style={{ paddingTop: 0 }}>Keeper Mode</p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
              {keeperModes.map((km) => {
                const active = keeperMode === km.mode;
                return (
                  <button
                    key={km.id}
                    onClick={() => runCmd(() => api.sendCommand({ command: 'set_climate_keeper_mode', params: { climate_keeper_mode: km.id } }), `keeper_${km.id}`, `${km.label} mode`)}
                    disabled={cmdLoading === `keeper_${km.id}`}
                    style={{
                      background: active ? '#05C46B' : 'rgba(255,255,255,0.05)',
                      border: `1px solid ${active ? '#05C46B' : 'rgba(255,255,255,0.08)'}`,
                      borderRadius: 10,
                      padding: '12px 4px',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      gap: 5,
                      fontFamily: 'inherit',
                      transition: 'all 0.15s',
                      color: active ? '#fff' : '#86888f',
                    }}
                  >
                    {km.icon && (
                      <div style={{ width: 22, height: 22, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        {km.icon}
                      </div>
                    )}
                    {!km.icon && (
                      <div style={{ width: 22, height: 22, borderRadius: '50%', border: `2px solid ${active ? '#fff' : '#86888f'}` }} />
                    )}
                    <span style={{ fontSize: 11, fontWeight: 600 }}>{km.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <IonToast
          isOpen={!!toast}
          message={toast?.message}
          duration={2000}
          color={toast?.color}
          onDidDismiss={() => setToast(null)}
          position="bottom"
        />
      </IonContent>
    </IonPage>
  );
};

export default Climate;
