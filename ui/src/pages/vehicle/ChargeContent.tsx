import React, { useState, useEffect } from 'react';
import {
  IonRange,
  IonToggle,
  IonToast,
} from '@ionic/react';
import BatteryGauge from '../../components/BatteryGauge';
import { api } from '../../api/client';
import { useVehicleData } from '../../hooks/useVehicleData';
import Spinner from '../../components/icons/Spinner';
import { BoltIcon, StopIcon, PortOpenIcon, PortCloseIcon } from '../../components/icons/Icons';

const ClockIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>;

function minutesToTime(minutes: number): string {
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
}

function timeToMinutes(time: string): number {
  const [h, m] = time.split(':').map(Number);
  return h * 60 + m;
}

function chargingColor(state: string): string {
  if (state === 'Charging') return '#0BE881';
  if (state === 'Complete') return '#0FBCF9';
  if (state === 'Stopped') return '#F99716';
  return '#86888f';
}

function formatTime(minutes: number): string {
  if (!minutes) return '--';
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (h === 0) return `${m}m`;
  return `${h}h ${m}m`;
}

export default function ChargeContent() {
  const { state, charge, loading, error, refresh } = useVehicleData();
  const [cmdLoading, setCmdLoading] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; color: string } | null>(null);
  const [limitValue, setLimitValue] = useState<number>(80);
  const [ampsValue, setAmpsValue] = useState<number>(16);
  const [limitDirty, setLimitDirty] = useState(false);
  const [ampsDirty, setAmpsDirty] = useState(false);
  const [schedEnabled, setSchedEnabled] = useState(false);
  const [schedTime, setSchedTime] = useState('22:00');
  const [schedDirty, setSchedDirty] = useState(false);

  const batteryPct = state?.battery_level ?? charge?.battery_level ?? 0;
  const chargeLimit = state?.charge_limit_soc ?? charge?.charge_limit_soc ?? 80;
  const chargingState = state?.charging_state ?? charge?.charging_state ?? 'Disconnected';
  const isCharging = chargingState === 'Charging';
  const chargerPower = state?.charger_power ?? charge?.charger_power ?? 0;
  const minutesToFull = state?.minutes_to_full_charge ?? charge?.minutes_to_full_charge ?? 0;
  const chargeRate = state?.charge_rate ?? charge?.charge_rate ?? 0;
  const voltage = state?.charger_voltage ?? charge?.charger_voltage ?? 0;
  const amps = state?.charger_actual_current ?? charge?.charger_actual_current ?? 0;
  const energyAdded = state?.charge_energy_added ?? charge?.charge_energy_added ?? 0;
  const portOpen = state?.charge_port_door_open ?? charge?.charge_port_door_open ?? false;
  const range = state?.battery_range;
  const stateColor = chargingColor(chargingState);
  const scheduledMode = state?.scheduled_charging_mode ?? charge?.scheduled_charging_mode ?? 'Off';
  const scheduledStart = state?.scheduled_charging_start_time ?? charge?.scheduled_charging_start_time;

  useEffect(() => {
    if (!limitDirty) setLimitValue(chargeLimit);
  }, [chargeLimit, limitDirty]);

  useEffect(() => {
    if (!ampsDirty) setAmpsValue(amps || 16);
  }, [amps, ampsDirty]);

  useEffect(() => {
    if (!schedDirty) {
      setSchedEnabled(scheduledMode !== 'Off');
      if (scheduledStart) setSchedTime(minutesToTime(scheduledStart));
    }
  }, [scheduledMode, scheduledStart, schedDirty]);

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

  const stats = [
    { label: 'Power', value: isCharging ? `${chargerPower} kW` : '--', color: isCharging ? '#0BE881' : '#86888f' },
    { label: 'Time Left', value: isCharging ? formatTime(minutesToFull) : '--', color: '#ffffff' },
    { label: 'Rate', value: isCharging ? `${chargeRate} mi/hr` : '--', color: '#ffffff' },
    { label: 'Added', value: energyAdded > 0 ? `${energyAdded.toFixed(1)} kWh` : '--', color: '#ffffff' },
    // Fleet API returns charger_voltage=2 even when unplugged (sensor floor),
    // so gate on isCharging to avoid showing noise as real readings.
    { label: 'Voltage', value: isCharging && voltage > 5 ? `${voltage}V` : '--', color: '#ffffff' },
    { label: 'Current', value: isCharging && amps ? `${amps}A` : '--', color: '#ffffff' },
  ];

  return (
    <>
        <div className="page-pad">
          {loading && !state ? (
            <div className="loading-center">
              <Spinner size={32} trackOpacity={0.1} />
            </div>
          ) : (
            <>
              {/* Battery gauge */}
              <div className="tesla-card" style={{ paddingTop: 24, paddingBottom: 16 }}>
                <BatteryGauge
                  percent={batteryPct}
                  limit={chargeLimit}
                  range={range}
                  size={220}
                  offline={!!(error && !state && !charge)}
                />
              </div>

              {/* Charge stats grid */}
              <div
                style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}
              >
                {stats.map((stat) => (
                  <div
                    key={stat.label}
                    style={{
                      background: 'rgba(255,255,255,0.04)',
                      border: '1px solid rgba(255,255,255,0.07)',
                      borderRadius: 10,
                      padding: '12px 14px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                    }}
                  >
                    <span style={{ color: '#86888f', fontSize: 13 }}>{stat.label}</span>
                    <span style={{ color: stat.color, fontWeight: 600, fontSize: 14 }}>{stat.value}</span>
                  </div>
                ))}
              </div>

              {/* Charge limit slider */}
              <div className="tesla-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <span className="label-xs">Charge Limit</span>
                  <span style={{ color: '#05C46B', fontWeight: 700, fontSize: 20 }}>{limitValue}%</span>
                </div>
                <IonRange
                  min={50} max={100} step={1}
                  value={limitValue}
                  onIonChange={(e) => { setLimitValue(e.detail.value as unknown as number); setLimitDirty(true); }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2, marginBottom: 12 }}>
                  <span style={{ color: '#86888f', fontSize: 11 }}>50%</span>
                  <span style={{ color: '#86888f', fontSize: 11 }}>Daily 80%</span>
                  <span style={{ color: '#86888f', fontSize: 11 }}>100%</span>
                </div>
                <button
                  onClick={() => { setLimitDirty(false); runCmd(() => api.setChargeLimit(limitValue), 'set_limit', `Limit set to ${limitValue}%`); }}
                  disabled={cmdLoading === 'set_limit'}
                  className="tesla-btn"
                >
                  {cmdLoading === 'set_limit' ? <Spinner size={16} /> : null}
                  Set Charge Limit
                </button>
              </div>

              {/* Charging amps slider */}
              <div className="tesla-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                  <span className="label-xs">Charging Amps</span>
                  <span style={{ color: '#0FBCF9', fontWeight: 700, fontSize: 20 }}>{ampsValue}A</span>
                </div>
                <IonRange
                  min={5} max={48} step={1}
                  value={ampsValue}
                  onIonChange={(e) => { setAmpsValue(e.detail.value as unknown as number); setAmpsDirty(true); }}
                />
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 2, marginBottom: 12 }}>
                  <span style={{ color: '#86888f', fontSize: 11 }}>5A</span>
                  <span style={{ color: '#86888f', fontSize: 11 }}>48A</span>
                </div>
                <button
                  onClick={() => { setAmpsDirty(false); runCmd(() => api.setChargingAmps(ampsValue), 'set_amps', `Amps set to ${ampsValue}A`); }}
                  disabled={cmdLoading === 'set_amps'}
                  className="tesla-btn blue"
                >
                  {cmdLoading === 'set_amps' ? <Spinner size={16} /> : null}
                  Set Charging Amps
                </button>
              </div>

              {/* Action buttons */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                {/* Start */}
                <button
                  onClick={() => runCmd(api.startCharge, 'start', 'Charging started')}
                  disabled={!!cmdLoading || isCharging}
                  style={{
                    background: 'rgba(11,232,129,0.1)',
                    color: '#0BE881',
                    border: '1px solid rgba(0,200,83,0.3)',
                    borderRadius: 10,
                    padding: '14px 8px',
                    fontWeight: 600,
                    fontSize: 13,
                    fontFamily: 'inherit',
                    cursor: cmdLoading || isCharging ? 'not-allowed' : 'pointer',
                    opacity: isCharging ? 0.4 : 1,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 6,
                    transition: 'all 0.15s',
                  }}
                >
                  {cmdLoading === 'start' ? <Spinner size={16} color="#0BE881" /> : <BoltIcon />}
                  <span>Start</span>
                </button>

                {/* Stop */}
                <button
                  onClick={() => runCmd(api.stopCharge, 'stop', 'Charging stopped')}
                  disabled={!!cmdLoading || !isCharging}
                  style={{
                    background: 'rgba(5,196,107,0.1)',
                    color: '#05C46B',
                    border: '1px solid rgba(5,196,107,0.3)',
                    borderRadius: 10,
                    padding: '14px 8px',
                    fontWeight: 600,
                    fontSize: 13,
                    fontFamily: 'inherit',
                    cursor: cmdLoading || !isCharging ? 'not-allowed' : 'pointer',
                    opacity: !isCharging ? 0.4 : 1,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 6,
                    transition: 'all 0.15s',
                  }}
                >
                  {cmdLoading === 'stop' ? <Spinner size={16} color="#05C46B" /> : <StopIcon />}
                  <span>Stop</span>
                </button>

                {/* Port */}
                <button
                  onClick={() => runCmd(
                    () => api.sendCommand({ command: portOpen ? 'charge_port_door_close' : 'charge_port_door_open' }),
                    'port',
                    portOpen ? 'Port closed' : 'Port opened'
                  )}
                  disabled={!!cmdLoading}
                  style={{
                    background: portOpen ? 'rgba(33,150,243,0.1)' : 'rgba(255,255,255,0.04)',
                    color: portOpen ? '#0FBCF9' : '#86888f',
                    border: `1px solid ${portOpen ? 'rgba(15,188,249,0.3)' : 'rgba(255,255,255,0.08)'}`,
                    borderRadius: 10,
                    padding: '14px 8px',
                    fontWeight: 600,
                    fontSize: 13,
                    fontFamily: 'inherit',
                    cursor: cmdLoading ? 'not-allowed' : 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: 6,
                    transition: 'all 0.15s',
                  }}
                >
                  {cmdLoading === 'port' ? <Spinner size={16} color="#0FBCF9" /> : (portOpen ? <PortCloseIcon /> : <PortOpenIcon />)}
                  <span>{portOpen ? 'Close Port' : 'Open Port'}</span>
                </button>
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
                    onIonChange={(e) => { setSchedEnabled(e.detail.checked); setSchedDirty(true); }}
                  />
                </div>

                {schedEnabled && (
                  <div style={{ borderTop: '1px solid rgba(255,255,255,0.08)', paddingTop: 16 }}>
                    <div className="label-xs" style={{ marginBottom: 8 }}>START CHARGING AT</div>
                    <input
                      type="time"
                      value={schedTime}
                      onChange={(e) => { setSchedTime(e.target.value); setSchedDirty(true); }}
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
                  onClick={() => {
                    setSchedDirty(false);
                    runCmd(
                      () => api.sendCommand({ command: 'set_scheduled_charging', params: { enable: schedEnabled, time: schedEnabled ? timeToMinutes(schedTime) : 0 } }),
                      'save_sched',
                      schedEnabled ? `Scheduled at ${schedTime}` : 'Scheduling disabled'
                    );
                  }}
                  disabled={cmdLoading === 'save_sched'}
                  className={`tesla-btn${schedDirty ? '' : ' secondary'}`}
                >
                  {cmdLoading === 'save_sched' ? <Spinner size={16} /> : null}
                  {schedDirty ? 'Save Schedule' : 'Saved'}
                </button>
              </div>
            </>
          )}
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
