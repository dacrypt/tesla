import React, { useState, useEffect } from 'react';
import {
  IonToggle,
  IonToast,
} from '@ionic/react';
import { api } from '../../api/client';
import { useVehicleData } from '../../hooks/useVehicleData';

// ---- SVG Icons ----
const ClockIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>;
const DepartIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M21 3L3 10.53v.98l6.84 2.65L12.48 21h.98L21 3z"/></svg>;
const SpeedIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M20.38 8.57l-1.23 1.85a8 8 0 0 1-.22 7.58H5.07A8 8 0 0 1 15.58 6.85l1.85-1.23A10 10 0 0 0 3.35 19a2 2 0 0 0 1.72 1h13.85a2 2 0 0 0 1.74-1 10 10 0 0 0-.27-10.44zm-9.79 6.84a2 2 0 0 0 2.83 0l5.66-8.49-8.49 5.66a2 2 0 0 0 0 2.83z"/></svg>;
const LockIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zM12 17c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1s3.1 1.39 3.1 3.1v2z"/></svg>;

function Spin() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none">
      <circle cx={12} cy={12} r={9} stroke="rgba(255,255,255,0.15)" strokeWidth={3} />
      <path d="M12 3a9 9 0 019 9" stroke="#fff" strokeWidth={3} strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

function minutesToTime(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

function timeToMinutes(time: string): number {
  const [h, m] = time.split(':').map(Number);
  return h * 60 + m;
}

function SpeedLimitSection({ cmdLoading, runCmd }: {
  cmdLoading: string | null;
  runCmd: (fn: () => Promise<unknown>, key: string, msg: string) => void;
}) {
  const [pin, setPin] = useState('');

  return (
    <>
      <div className="label-xs" style={{ marginBottom: 6 }}>PIN</div>
      <input
        type="password"
        inputMode="numeric"
        maxLength={4}
        value={pin}
        onChange={(e) => setPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
        placeholder="4-digit PIN"
        style={{
          background: 'rgba(255,255,255,0.06)',
          color: '#ffffff',
          border: '1px solid rgba(255,255,255,0.1)',
          borderRadius: 10,
          padding: '10px 14px',
          fontSize: 18,
          fontWeight: 700,
          fontFamily: 'inherit',
          width: '100%',
          outline: 'none',
          colorScheme: 'dark',
          marginBottom: 12,
          letterSpacing: '0.3em',
          textAlign: 'center',
        }}
      />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <button
          onClick={() => runCmd(() => api.sendCommand({ command: 'speed_limit_activate', params: { pin } }), 'spd_on', 'Speed limit on')}
          disabled={!!cmdLoading || pin.length !== 4}
          style={{ background: 'rgba(255,152,0,0.1)', color: '#F99716', border: '1px solid rgba(255,152,0,0.3)', borderRadius: 10, padding: '12px 8px', fontWeight: 600, fontSize: 13, fontFamily: 'inherit', cursor: pin.length === 4 ? 'pointer' : 'not-allowed', transition: 'all 0.15s', opacity: pin.length !== 4 ? 0.5 : 1 }}
        >
          Activate
        </button>
        <button
          onClick={() => runCmd(() => api.sendCommand({ command: 'speed_limit_deactivate', params: { pin } }), 'spd_off', 'Speed limit off')}
          disabled={!!cmdLoading || pin.length !== 4}
          className="tesla-btn secondary"
          style={{ fontSize: 13 }}
        >
          Deactivate
        </button>
      </div>
    </>
  );
}

export default function ScheduleContent() {
  const { state, charge, refresh } = useVehicleData();
  const [cmdLoading, setCmdLoading] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; color: string } | null>(null);
  const [schedEnabled, setSchedEnabled] = useState(false);
  const [schedTime, setSchedTime] = useState('22:00');
  const [departTime, setDepartTime] = useState('07:00');
  const [dirty, setDirty] = useState(false);

  const scheduledMode = state?.scheduled_charging_mode ?? charge?.scheduled_charging_mode ?? 'Off';
  const scheduledStart = state?.scheduled_charging_start_time ?? charge?.scheduled_charging_start_time;
  const chargeLimit = state?.charge_limit_soc ?? charge?.charge_limit_soc ?? 80;
  const batteryPct = state?.battery_level ?? charge?.battery_level ?? 0;
  const chargingState = state?.charging_state ?? charge?.charging_state ?? 'Disconnected';

  const batteryColor = batteryPct > 50 ? '#0BE881' : batteryPct > 20 ? '#F99716' : '#FF6B6B';
  const chargeColor = chargingState === 'Charging' ? '#0BE881' : chargingState === 'Complete' ? '#0FBCF9' : '#86888f';

  useEffect(() => {
    if (!dirty) {
      setSchedEnabled(scheduledMode !== 'Off');
      if (scheduledStart) setSchedTime(minutesToTime(scheduledStart));
    }
  }, [scheduledMode, scheduledStart, dirty]);

  const runCmd = async (fn: () => Promise<unknown>, key: string, msg: string) => {
    setCmdLoading(key);
    try {
      await fn();
      setToast({ message: msg, color: 'success' });
      setDirty(false);
      setTimeout(refresh, 1500);
    } catch {
      setToast({ message: 'Command failed', color: 'danger' });
    } finally {
      setCmdLoading(null);
    }
  };

  const saveSchedule = () => {
    runCmd(
      () => api.sendCommand({ command: 'set_scheduled_charging', params: { enable: schedEnabled, time: schedEnabled ? timeToMinutes(schedTime) : 0 } }),
      'save_sched',
      schedEnabled ? `Scheduled at ${schedTime}` : 'Scheduling disabled'
    );
  };

  return (
    <>
        <div className="page-pad">
          {/* Charge status card */}
          <div className="tesla-card">
            <p className="section-title" style={{ paddingTop: 0 }}>Current Status</p>
            <div className="stat-row">
              <span className="label-sm">Charge Level</span>
              <span style={{ color: batteryColor, fontWeight: 700, fontSize: 18 }}>{batteryPct}%</span>
            </div>
            <div className="stat-row">
              <span className="label-sm">Charge Limit</span>
              <span style={{ color: '#ffffff', fontWeight: 600, fontSize: 16 }}>{chargeLimit}%</span>
            </div>
            <div className="stat-row" style={{ borderBottom: 'none' }}>
              <span className="label-sm">State</span>
              <span style={{ color: chargeColor, fontWeight: 600, fontSize: 14 }}>{chargingState}</span>
            </div>
          </div>

          {/* Scheduled charging */}
          <div className="tesla-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: schedEnabled ? 16 : 0 }}>
              <div style={{ width: 36, height: 36, borderRadius: '50%', background: schedEnabled ? 'rgba(5,196,107,0.2)' : 'rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: schedEnabled ? '#05C46B' : '#86888f' }}>
                <ClockIcon />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Scheduled Charging</div>
                <div style={{ color: '#86888f', fontSize: 12 }}>
                  {scheduledMode === 'Off' ? 'Disabled' : `Active — ${scheduledMode}`}
                </div>
              </div>
              <IonToggle
                checked={schedEnabled}
                onIonChange={(e) => { setSchedEnabled(e.detail.checked); setDirty(true); }}
              />
            </div>

            {schedEnabled && (
              <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 16 }}>
                <div className="label-xs" style={{ marginBottom: 8 }}>START CHARGING AT</div>
                <input
                  type="time"
                  value={schedTime}
                  onChange={(e) => { setSchedTime(e.target.value); setDirty(true); }}
                  style={{
                    background: 'rgba(255,255,255,0.06)',
                    color: '#ffffff',
                    border: '1px solid rgba(255,255,255,0.1)',
                    borderRadius: 10,
                    padding: '12px 14px',
                    fontSize: 22,
                    fontWeight: 700,
                    fontFamily: 'inherit',
                    width: '100%',
                    outline: 'none',
                    colorScheme: 'dark',
                    marginBottom: 12,
                  }}
                />
                <div className="info-box" style={{ marginBottom: 12 }}>
                  Vehicle must be plugged in for scheduled charging to activate.
                </div>
              </div>
            )}

            <button
              onClick={saveSchedule}
              disabled={cmdLoading === 'save_sched'}
              className={`tesla-btn${dirty ? '' : ' secondary'}`}
            >
              {cmdLoading === 'save_sched' ? <Spin /> : null}
              {dirty ? 'Save Schedule' : 'Saved'}
            </button>
          </div>

          {/* Departure time */}
          <div className="tesla-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'rgba(33,150,243,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0FBCF9' }}>
                <DepartIcon />
              </div>
              <div>
                <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Departure Time</div>
                <div style={{ color: '#86888f', fontSize: 12 }}>Set when you plan to leave</div>
              </div>
            </div>
            <input
              type="time"
              value={departTime}
              onChange={(e) => setDepartTime(e.target.value)}
              style={{
                background: 'rgba(255,255,255,0.06)',
                color: '#ffffff',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 10,
                padding: '12px 14px',
                fontSize: 22,
                fontWeight: 700,
                fontFamily: 'inherit',
                width: '100%',
                outline: 'none',
                colorScheme: 'dark',
                marginBottom: 14,
              }}
            />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <button
                onClick={() => runCmd(() => api.sendCommand({ command: 'set_preconditioning_max', params: { on: true } }), 'precond_max', 'Max preconditioning on')}
                disabled={!!cmdLoading}
                className="tesla-btn blue"
                style={{ fontSize: 13 }}
              >
                Max Precondition
              </button>
              <button
                onClick={() => runCmd(() => api.sendCommand({ command: 'set_preconditioning_max', params: { on: false } }), 'precond_off', 'Preconditioning off')}
                disabled={!!cmdLoading}
                className="tesla-btn secondary"
                style={{ fontSize: 13 }}
              >
                Stop Precond.
              </button>
            </div>
          </div>

          {/* Speed limit */}
          <div className="tesla-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
              <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'rgba(255,152,0,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#F99716' }}>
                <SpeedIcon />
              </div>
              <div>
                <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Speed Limit Mode</div>
                <div style={{ color: '#86888f', fontSize: 12 }}>Restrict maximum vehicle speed</div>
              </div>
            </div>
            <SpeedLimitSection cmdLoading={cmdLoading} runCmd={runCmd} />
          </div>

          {/* PIN to Drive info */}
          <div className="tesla-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#86888f' }}>
                <LockIcon />
              </div>
              <div>
                <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>PIN to Drive</div>
                <div style={{ color: '#86888f', fontSize: 12 }}>Manage via Tesla app or touchscreen</div>
              </div>
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
      </>
  );
}
