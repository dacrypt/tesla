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
      </div>
      <IonToast isOpen={!!toast} message={toast?.message} duration={2000} color={toast?.color} onDidDismiss={() => setToast(null)} position="bottom" />
    </>
  );
}
