import React, { useState, useEffect } from 'react';
import {
  IonRange,
  IonToast,
} from '@ionic/react';
import BatteryGauge from '../../components/BatteryGauge';
import { api } from '../../api/client';
import { useVehicleData } from '../../hooks/useVehicleData';
import Spinner from '../../components/icons/Spinner';
import { BoltIcon, StopIcon, PortOpenIcon, PortCloseIcon } from '../../components/icons/Icons';

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

  useEffect(() => {
    if (!limitDirty) setLimitValue(chargeLimit);
  }, [chargeLimit, limitDirty]);

  useEffect(() => {
    if (!ampsDirty) setAmpsValue(amps || 16);
  }, [amps, ampsDirty]);

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
    { label: 'Voltage', value: voltage ? `${voltage}V` : '--', color: '#ffffff' },
    { label: 'Current', value: amps ? `${amps}A` : '--', color: '#ffffff' },
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
