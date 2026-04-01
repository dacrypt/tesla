import React, { useState } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
  IonToast,
} from '@ionic/react';
import { api } from '../api/client';
import { useVehicleData } from '../hooks/useVehicleData';

// ---- SVG Icons (inline, no ionicons) ----
const LockIcon = () => <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zM12 17c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1s3.1 1.39 3.1 3.1v2z"/></svg>;
const UnlockIcon = () => <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor"><path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6h2c0-1.65 1.35-3 3-3s3 1.35 3 3v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm0 12H6V10h12v10zm-6-3c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2z"/></svg>;
const ShieldIcon = () => <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor"><path d="M12 1L3 5v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V5l-9-4zm0 10.99h7c-.53 4.12-3.28 7.79-7 8.94V12H5V6.3l7-3.11v8.8z"/></svg>;
const PersonIcon = () => <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor"><path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/></svg>;
const HornIcon = () => <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/></svg>;
const FlashIcon = () => <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor"><path d="M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9v1zm3-19C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7z"/></svg>;
const CargoIcon = () => <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor"><path d="M17 8C8 10 5.9 16.17 3.82 21L5.71 22l1-2.3A4.49 4.49 0 008 20c4 0 4-2 8-2s4 2 8 2v-2c0 0 0-1.5-1-3 0 0-1-3-6-7zm-1.6 6.93c-1.37-.18-2.6-.77-3.94-1.65l3.64-.88c.17.34.36.68.58 1zM5 4v2h14V4H5zm-2 4v2h18V8H3z"/></svg>;
const FrunkIcon = () => <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor"><path d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11c-.66 0-1.21.42-1.42 1.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99zM6.5 16c-.83 0-1.5-.67-1.5-1.5S5.67 13 6.5 13s1.5.67 1.5 1.5S7.33 16 6.5 16zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM5 11l1.5-4.5h11L19 11H5z"/></svg>;
const WindowUpIcon = () => <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor"><path d="M7 14l5-5 5 5z"/></svg>;
const WindowDownIcon = () => <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor"><path d="M7 10l5 5 5-5z"/></svg>;
const KeyIcon = () => <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor"><path d="M12.65 10C11.83 7.67 9.61 6 7 6c-3.31 0-6 2.69-6 6s2.69 6 6 6c2.61 0 4.83-1.67 5.65-4H17v4h4v-4h2v-4H12.65zM7 14c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2z"/></svg>;
const WakeIcon = () => <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor"><path d="M6.76 4.84l-1.8-1.79-1.41 1.41 1.79 1.79 1.42-1.41zM4 10.5H1v2h3v-2zm9-9.95h-2V3.5h2V.55zm7.45 3.91l-1.41-1.41-1.79 1.79 1.41 1.41 1.79-1.79zm-3.21 13.7l1.79 1.8 1.41-1.41-1.8-1.79-1.4 1.4zM20 10.5v2h3v-2h-3zm-8-5c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm-1 16.95h2V19.5h-2v2.95zm-7.45-3.91l1.41 1.41 1.79-1.8-1.41-1.41-1.79 1.8z"/></svg>;
const GuestIcon = () => <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor"><path d="M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5c-1.66 0-3 1.34-3 3s1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5C6.34 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z"/></svg>;

// Spinner
function Spin() {
  return (
    <svg width={20} height={20} viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
      <circle cx={12} cy={12} r={9} stroke="rgba(255,255,255,0.15)" strokeWidth={3} />
      <path d="M12 3a9 9 0 019 9" stroke="#05C46B" strokeWidth={3} strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

// Button icon background colors
type ColorKey = 'default' | 'red' | 'green' | 'blue' | 'orange';
const iconBgMap: Record<ColorKey, string> = {
  default: 'rgba(255,255,255,0.12)',
  red: '#05C46B',
  green: '#0BE881',
  blue: '#0FBCF9',
  orange: '#F99716',
};
const activeBgMap: Record<ColorKey, string> = {
  default: 'rgba(255,255,255,0.18)',
  red: 'rgba(5,196,107,0.15)',
  green: 'rgba(11,232,129,0.15)',
  blue: 'rgba(15,188,249,0.15)',
  orange: 'rgba(249,151,22,0.15)',
};
const activeBorderMap: Record<ColorKey, string> = {
  default: 'rgba(255,255,255,0.2)',
  red: 'rgba(5,196,107,0.4)',
  green: 'rgba(11,232,129,0.4)',
  blue: 'rgba(15,188,249,0.4)',
  orange: 'rgba(249,151,22,0.4)',
};

interface CtrlBtn {
  icon: React.ReactNode;
  label: string;
  key: string;
  action: () => void;
  active?: boolean;
  color?: ColorKey;
}

interface Section {
  title: string;
  buttons: CtrlBtn[];
}

const Controls: React.FC = () => {
  const { state, refresh } = useVehicleData();
  const [loading, setLoading] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; color: string } | null>(null);
  const [flash, setFlash] = useState<string | null>(null); // key of button to flash success

  const cmd = async (
    command: string,
    params?: Record<string, unknown>,
    key?: string,
    successMsg?: string
  ) => {
    const k = key || command;
    setLoading(k);
    try {
      await api.sendCommand({ command, params });
      setToast({ message: successMsg || `${command} sent`, color: 'success' });
      setFlash(k);
      setTimeout(() => setFlash(null), 800);
      setTimeout(refresh, 1500);
    } catch {
      setToast({ message: 'Command failed', color: 'danger' });
    } finally {
      setLoading(null);
    }
  };

  const isLocked = state?.locked ?? true;
  const sentryon = state?.sentry_mode ?? false;
  const valeton = state?.valet_mode ?? false;

  const sections: Section[] = [
    {
      title: 'Doors',
      buttons: [
        { icon: <LockIcon />, label: 'Lock', key: 'lock', action: () => cmd('door_lock', undefined, 'lock', 'Doors locked'), active: isLocked, color: 'default' },
        { icon: <UnlockIcon />, label: 'Unlock', key: 'unlock', action: () => cmd('door_unlock', undefined, 'unlock', 'Doors unlocked'), active: !isLocked, color: 'red' },
      ],
    },
    {
      title: 'Safety',
      buttons: [
        { icon: <ShieldIcon />, label: 'Sentry', key: 'sentry', action: () => cmd('set_sentry_mode', { on: !sentryon }, 'sentry', sentryon ? 'Sentry off' : 'Sentry on'), active: sentryon, color: 'blue' },
        { icon: <PersonIcon />, label: 'Valet', key: 'valet', action: () => cmd('set_valet_mode', { on: !valeton, password: '' }, 'valet'), active: valeton, color: 'orange' },
        { icon: <KeyIcon />, label: 'Remote Start', key: 'remote_start', action: () => cmd('remote_start_drive', undefined, 'remote_start', 'Remote start activated'), color: 'green' },
      ],
    },
    {
      title: 'Lights & Alerts',
      buttons: [
        { icon: <FlashIcon />, label: 'Flash Lights', key: 'flash', action: () => cmd('flash_lights', undefined, 'flash', 'Lights flashed'), color: 'orange' },
        { icon: <HornIcon />, label: 'Honk Horn', key: 'horn', action: () => cmd('honk_horn', undefined, 'horn', 'Honk!'), color: 'default' },
      ],
    },
    {
      title: 'Trunk & Frunk',
      buttons: [
        { icon: <CargoIcon />, label: 'Trunk', key: 'trunk', action: () => cmd('actuate_trunk', { which_trunk: 'rear' }, 'trunk', 'Trunk actuated'), color: 'default' },
        { icon: <FrunkIcon />, label: 'Frunk', key: 'frunk', action: () => cmd('actuate_trunk', { which_trunk: 'front' }, 'frunk', 'Frunk actuated'), color: 'default' },
      ],
    },
    {
      title: 'Windows',
      buttons: [
        { icon: <WindowUpIcon />, label: 'Vent', key: 'vent', action: () => cmd('window_control', { command: 'vent', lat: 0, lon: 0 }, 'vent', 'Windows vented'), color: 'blue' },
        { icon: <WindowDownIcon />, label: 'Close', key: 'close_win', action: () => cmd('window_control', { command: 'close', lat: 0, lon: 0 }, 'close_win', 'Windows closed'), color: 'default' },
      ],
    },
    {
      title: 'Access',
      buttons: [
        { icon: <WakeIcon />, label: 'Wake', key: 'wake', action: async () => { setLoading('wake'); try { await api.wakeVehicle(); setToast({ message: 'Wake signal sent', color: 'success' }); setTimeout(refresh, 3000); } catch { setToast({ message: 'Failed to wake', color: 'danger' }); } finally { setLoading(null); } }, color: 'default' },
        { icon: <GuestIcon />, label: 'Guest Mode', key: 'guest', action: () => cmd('guest_mode', { enable: true }, 'guest', 'Guest mode on'), color: 'blue' },
      ],
    },
  ];

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700 }}>Controls</IonTitle>
        </IonToolbar>
      </IonHeader>

      <IonContent>
        <div className="page-pad">
          {sections.map((section) => (
            <div key={section.title}>
              <p className="section-title">{section.title}</p>
              <div
                style={{
                  display: 'grid',
                  gridTemplateColumns: section.buttons.length === 2 ? 'repeat(2, 1fr)' : 'repeat(3, 1fr)',
                  gap: 8,
                  marginBottom: 4,
                }}
              >
                {section.buttons.map((btn) => {
                  const col: ColorKey = btn.color || 'default';
                  const isActive = !!btn.active || flash === btn.key;
                  const isLoading = loading === btn.key;
                  return (
                    <button
                      key={btn.key}
                      onClick={btn.action}
                      disabled={!!loading}
                      style={{
                        background: isActive ? activeBgMap[col] : 'rgba(255,255,255,0.04)',
                        border: `1px solid ${isActive ? activeBorderMap[col] : 'rgba(255,255,255,0.07)'}`,
                        borderRadius: 12,
                        padding: '14px 6px',
                        cursor: loading ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: 8,
                        opacity: loading && !isLoading ? 0.5 : 1,
                        transition: 'all 0.15s',
                        fontFamily: 'inherit',
                        boxShadow: isActive ? `0 0 0 1px ${activeBorderMap[col]}, 0 0 20px ${activeBorderMap[col]}50` : 'none',
                      }}
                    >
                      <div
                        style={{
                          width: 38,
                          height: 38,
                          borderRadius: '50%',
                          background: iconBgMap[col],
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: col === 'green' ? '#000' : '#fff',
                        }}
                      >
                        {isLoading ? <Spin /> : btn.icon}
                      </div>
                      <span style={{ color: '#fff', fontSize: 11, fontWeight: 600, textAlign: 'center', lineHeight: 1.2 }}>
                        {btn.label}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
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

export default Controls;
