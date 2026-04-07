// Auto-generated content wrapper for Vehicle sub-tab
// Original: Controls.tsx — strips IonPage/IonHeader/IonContent

import React, { useState } from 'react';
import { IonToast } from '@ionic/react';
import { api } from '../../api/client';
import { useVehicleData } from '../../hooks/useVehicleData';
import Spinner from '../../components/icons/Spinner';
import {
  LockIcon,
  UnlockIcon,
  ShieldIcon,
  PersonIcon,
  HornIcon,
  FlashIcon,
  CargoIcon,
  FrunkIcon,
  WindowUpIcon,
  WindowDownIcon,
  KeyIcon,
  WakeIcon,
  GuestIcon,
} from '../../components/icons/Icons';

const SpeedIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M20.38 8.57l-1.23 1.85a8 8 0 0 1-.22 7.58H5.07A8 8 0 0 1 15.58 6.85l1.85-1.23A10 10 0 0 0 3.35 19a2 2 0 0 0 1.72 1h13.85a2 2 0 0 0 1.74-1 10 10 0 0 0-.27-10.44zm-9.79 6.84a2 2 0 0 0 2.83 0l5.66-8.49-8.49 5.66a2 2 0 0 0 0 2.83z"/></svg>;
const PadlockIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zM12 17c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1s3.1 1.39 3.1 3.1v2z"/></svg>;

type ColorKey = 'default' | 'red' | 'green' | 'blue' | 'orange';
const iconBgMap: Record<ColorKey, string> = { default: 'rgba(255,255,255,0.12)', red: '#05C46B', green: '#0BE881', blue: '#0FBCF9', orange: '#F99716' };
const activeBgMap: Record<ColorKey, string> = { default: 'rgba(255,255,255,0.18)', red: 'rgba(5,196,107,0.15)', green: 'rgba(11,232,129,0.15)', blue: 'rgba(15,188,249,0.15)', orange: 'rgba(249,151,22,0.15)' };
const activeBorderMap: Record<ColorKey, string> = { default: 'rgba(255,255,255,0.2)', red: 'rgba(5,196,107,0.4)', green: 'rgba(11,232,129,0.4)', blue: 'rgba(15,188,249,0.4)', orange: 'rgba(249,151,22,0.4)' };

interface CtrlBtn { icon: React.ReactNode; label: string; key: string; action: () => void; active?: boolean; color?: ColorKey; }
interface Section { title: string; buttons: CtrlBtn[]; }

export default function ControlsContent() {
  const { state, refresh } = useVehicleData();
  const [loading, setLoading] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; color: string } | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [speedPin, setSpeedPin] = useState('');

  const cmd = async (command: string, params?: Record<string, unknown>, key?: string, successMsg?: string) => {
    const k = key || command;
    setLoading(k);
    try {
      await api.sendCommand({ command, params });
      setToast({ message: successMsg || command + ' sent', color: 'success' });
      setFlash(k); setTimeout(() => setFlash(null), 800);
      setTimeout(refresh, 1500);
    } catch { setToast({ message: 'Command failed', color: 'danger' }); }
    finally { setLoading(null); }
  };

  const isLocked = state?.locked ?? true;
  const sentryon = state?.sentry_mode ?? false;
  const valeton = state?.valet_mode ?? false;

  const sections: Section[] = [
    { title: 'Doors', buttons: [
      { icon: <LockIcon />, label: 'Lock', key: 'lock', action: () => cmd('door_lock', undefined, 'lock', 'Doors locked'), active: isLocked, color: 'default' },
      { icon: <UnlockIcon />, label: 'Unlock', key: 'unlock', action: () => cmd('door_unlock', undefined, 'unlock', 'Doors unlocked'), active: !isLocked, color: 'red' },
    ]},
    { title: 'Safety', buttons: [
      { icon: <ShieldIcon />, label: 'Sentry', key: 'sentry', action: () => cmd('set_sentry_mode', { on: !sentryon }, 'sentry', sentryon ? 'Sentry off' : 'Sentry on'), active: sentryon, color: 'blue' },
      { icon: <PersonIcon />, label: 'Valet', key: 'valet', action: () => cmd('set_valet_mode', { on: !valeton, password: '' }, 'valet'), active: valeton, color: 'orange' },
      { icon: <KeyIcon />, label: 'Remote Start', key: 'remote_start', action: () => cmd('remote_start_drive', undefined, 'remote_start', 'Remote start activated'), color: 'green' },
    ]},
    { title: 'Lights & Alerts', buttons: [
      { icon: <FlashIcon />, label: 'Flash Lights', key: 'flash', action: () => cmd('flash_lights', undefined, 'flash', 'Lights flashed'), color: 'orange' },
      { icon: <HornIcon />, label: 'Honk Horn', key: 'horn', action: () => cmd('honk_horn', undefined, 'horn', 'Honk!'), color: 'default' },
    ]},
    { title: 'Trunk & Frunk', buttons: [
      { icon: <CargoIcon />, label: 'Trunk', key: 'trunk', action: () => cmd('actuate_trunk', { which_trunk: 'rear' }, 'trunk', 'Trunk actuated'), color: 'default' },
      { icon: <FrunkIcon />, label: 'Frunk', key: 'frunk', action: () => cmd('actuate_trunk', { which_trunk: 'front' }, 'frunk', 'Frunk actuated'), color: 'default' },
    ]},
    { title: 'Windows', buttons: [
      { icon: <WindowUpIcon />, label: 'Vent', key: 'vent', action: () => cmd('window_control', { command: 'vent', lat: 0, lon: 0 }, 'vent', 'Windows vented'), color: 'blue' },
      { icon: <WindowDownIcon />, label: 'Close', key: 'close_win', action: () => cmd('window_control', { command: 'close', lat: 0, lon: 0 }, 'close_win', 'Windows closed'), color: 'default' },
    ]},
    { title: 'Access', buttons: [
      { icon: <WakeIcon />, label: 'Wake', key: 'wake', action: async () => { setLoading('wake'); try { await api.wakeVehicle(); setToast({ message: 'Wake signal sent', color: 'success' }); setTimeout(refresh, 3000); } catch { setToast({ message: 'Failed to wake', color: 'danger' }); } finally { setLoading(null); } }, color: 'default' },
      { icon: <GuestIcon />, label: 'Guest Mode', key: 'guest', action: () => cmd('guest_mode', { enable: true }, 'guest', 'Guest mode on'), color: 'blue' },
    ]},
  ];

  return (
    <>
      <div className="page-pad">
        {sections.map((section) => (
          <div key={section.title}>
            <p className="section-title">{section.title}</p>
            <div style={{ display: 'grid', gridTemplateColumns: section.buttons.length === 2 ? 'repeat(2, 1fr)' : 'repeat(3, 1fr)', gap: 8, marginBottom: 4 }}>
              {section.buttons.map((btn) => {
                const col: ColorKey = btn.color || 'default';
                const isActive = !!btn.active || flash === btn.key;
                const isLoading = loading === btn.key;
                return (
                  <button key={btn.key} onClick={btn.action} disabled={!!loading}
                    style={{
                      background: isActive ? activeBgMap[col] : 'rgba(255,255,255,0.04)',
                      border: `1px solid ${isActive ? activeBorderMap[col] : 'rgba(255,255,255,0.07)'}`,
                      borderRadius: 12, padding: '14px 6px', cursor: loading ? 'not-allowed' : 'pointer',
                      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
                      opacity: loading && !isLoading ? 0.5 : 1, transition: 'all 0.15s', fontFamily: 'inherit',
                      boxShadow: isActive ? `0 0 0 1px ${activeBorderMap[col]}, 0 0 20px ${activeBorderMap[col]}50` : 'none',
                    }}>
                    <div style={{ width: 38, height: 38, borderRadius: '50%', background: iconBgMap[col], display: 'flex', alignItems: 'center', justifyContent: 'center', color: col === 'green' ? '#000' : '#fff' }}>
                      {isLoading ? <Spinner /> : btn.icon}
                    </div>
                    <span style={{ color: '#fff', fontSize: 11, fontWeight: 600, textAlign: 'center', lineHeight: 1.2 }}>{btn.label}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
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
          <div className="label-xs" style={{ marginBottom: 6 }}>PIN</div>
          <input
            type="password"
            inputMode="numeric"
            maxLength={4}
            value={speedPin}
            onChange={(e) => setSpeedPin(e.target.value.replace(/\D/g, '').slice(0, 4))}
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
              onClick={() => cmd('speed_limit_activate', { pin: speedPin }, 'spd_on', 'Speed limit on')}
              disabled={!!loading || speedPin.length !== 4}
              style={{ background: 'rgba(255,152,0,0.1)', color: '#F99716', border: '1px solid rgba(255,152,0,0.3)', borderRadius: 10, padding: '12px 8px', fontWeight: 600, fontSize: 13, fontFamily: 'inherit', cursor: speedPin.length === 4 ? 'pointer' : 'not-allowed', transition: 'all 0.15s', opacity: speedPin.length !== 4 ? 0.5 : 1 }}
            >
              Activate
            </button>
            <button
              onClick={() => cmd('speed_limit_deactivate', { pin: speedPin }, 'spd_off', 'Speed limit off')}
              disabled={!!loading || speedPin.length !== 4}
              className="tesla-btn secondary"
              style={{ fontSize: 13 }}
            >
              Deactivate
            </button>
          </div>
        </div>

        {/* PIN to Drive info */}
        <div className="tesla-card">
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#86888f' }}>
              <PadlockIcon />
            </div>
            <div>
              <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>PIN to Drive</div>
              <div style={{ color: '#86888f', fontSize: 12 }}>Manage via Tesla app or touchscreen</div>
            </div>
          </div>
        </div>
      </div>
      <IonToast isOpen={!!toast} message={toast?.message} duration={2000} color={toast?.color} onDidDismiss={() => setToast(null)} position="bottom" />
    </>
  );
}
