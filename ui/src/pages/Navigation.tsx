import React, { useState } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
  IonRange,
  IonToast,
} from '@ionic/react';
import { api } from '../api/client';
import { useVehicleData } from '../hooks/useVehicleData';

// ---- SVG Icons ----
const NavIcon = () => <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor"><path d="M21 3L3 10.53v.98l6.84 2.65L12.48 21h.98L21 3z"/></svg>;
const LocationIcon = () => <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>;
const PrevIcon = () => <svg width={22} height={22} viewBox="0 0 24 24" fill="currentColor"><path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/></svg>;
const PlayIcon = () => <svg width={26} height={26} viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>;
const PauseIcon = () => <svg width={26} height={26} viewBox="0 0 24 24" fill="currentColor"><path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/></svg>;
const NextIcon = () => <svg width={22} height={22} viewBox="0 0 24 24" fill="currentColor"><path d="M6 18l8.5-6L6 6v12zm2-8.14L11.03 12 8 14.14V9.86zM16 6h2v12h-2z"/></svg>;
const VolumeIcon = () => <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor"><path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/></svg>;
const MapPinIcon = () => <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z"/></svg>;
const SpeedIcon = () => <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor"><path d="M20.38 8.57l-1.23 1.85a8 8 0 0 1-.22 7.58H5.07A8 8 0 0 1 15.58 6.85l1.85-1.23A10 10 0 0 0 3.35 19a2 2 0 0 0 1.72 1h13.85a2 2 0 0 0 1.74-1 10 10 0 0 0-.27-10.44zm-9.79 6.84a2 2 0 0 0 2.83 0l5.66-8.49-8.49 5.66a2 2 0 0 0 0 2.83z"/></svg>;

function Spin() {
  return (
    <svg width={20} height={20} viewBox="0 0 24 24" fill="none">
      <circle cx={12} cy={12} r={9} stroke="rgba(255,255,255,0.15)" strokeWidth={3} />
      <path d="M12 3a9 9 0 019 9" stroke="#fff" strokeWidth={3} strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

const Navigation: React.FC = () => {
  const { state, error } = useVehicleData();
  const [address, setAddress] = useState('');
  const [cmdLoading, setCmdLoading] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; color: string } | null>(null);
  const [volume, setVolume] = useState<number>(5);
  const [isPlaying, setIsPlaying] = useState(false);

  const runCmd = async (fn: () => Promise<unknown>, key: string, msg: string) => {
    setCmdLoading(key);
    try {
      await fn();
      setToast({ message: msg, color: 'success' });
    } catch {
      setToast({ message: 'Command failed', color: 'danger' });
    } finally {
      setCmdLoading(null);
    }
  };

  const sendNav = () => {
    if (!address.trim()) { setToast({ message: 'Enter an address first', color: 'warning' }); return; }
    runCmd(() => api.sendCommand({ command: 'share', params: { value: address } }), 'nav', `Navigating to ${address}`);
  };

  const mediaCmd = (cmd: string, key: string, msg: string) => runCmd(() => api.sendCommand({ command: cmd }), key, msg);

  const handleVolumeChange = (v: number) => {
    setVolume(v);
    runCmd(() => api.sendCommand({ command: 'adjust_volume', params: { volume: v } }), 'volume', `Volume ${v}`);
  };

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700 }}>Nav & Media</IonTitle>
        </IonToolbar>
      </IonHeader>

      <IonContent>
        <div className="page-pad">
          {/* ---- Offline notice ---- */}
          {error && !state && (
            <div className="info-box" style={{ marginBottom: 10 }}>
              Vehicle offline — navigation and media commands will be queued
            </div>
          )}

          {/* ---- Navigation ---- */}
          <div className="tesla-card">
            <p className="section-title" style={{ paddingTop: 0 }}>Send Destination</p>
            <div style={{ position: 'relative', marginBottom: 12 }}>
              <div style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: '#86888f' }}>
                <LocationIcon />
              </div>
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && sendNav()}
                placeholder="Address, city, or place..."
                className="tesla-input"
                style={{ paddingLeft: 38 }}
              />
            </div>
            <button
              onClick={sendNav}
              disabled={cmdLoading === 'nav' || !address.trim()}
              className="tesla-btn"
              style={{ opacity: !address.trim() ? 0.4 : 1 }}
            >
              {cmdLoading === 'nav' ? <Spin /> : <NavIcon />}
              Send to Car
            </button>
          </div>

          {/* ---- Location info ---- */}
          {state?.latitude && (
            <div className="tesla-card">
              <p className="section-title" style={{ paddingTop: 0 }}>Current Location</p>
              <div className="stat-row">
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <MapPinIcon />
                  <span className="label-sm">Coordinates</span>
                </div>
                <span style={{ color: '#ffffff', fontSize: 12, fontFamily: 'monospace' }}>
                  {state.latitude?.toFixed(5)}, {state.longitude?.toFixed(5)}
                </span>
              </div>
              {state.speed != null && (
                <div className="stat-row">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <SpeedIcon />
                    <span className="label-sm">Speed</span>
                  </div>
                  <span style={{ color: '#ffffff', fontWeight: 600 }}>{state.speed} mph</span>
                </div>
              )}
              <a
                href={`https://maps.google.com/?q=${state.latitude},${state.longitude}`}
                target="_blank"
                rel="noopener noreferrer"
                className="tesla-btn blue"
                style={{ marginTop: 14, textDecoration: 'none' }}
              >
                Open in Google Maps
              </a>
            </div>
          )}

          {/* ---- Now Playing placeholder ---- */}
          {!state && (
            <div className="tesla-card" style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '14px 16px' }}>
              <div style={{ width: 48, height: 48, borderRadius: 10, background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                <svg width={20} height={20} viewBox="0 0 24 24" fill="rgba(255,255,255,0.25)"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>
              </div>
              <div>
                <div style={{ color: '#86888f', fontSize: 13 }}>Not playing</div>
                <div style={{ color: '#86888f', fontSize: 11, marginTop: 2, opacity: 0.6 }}>Connect vehicle to see media</div>
              </div>
            </div>
          )}

          {/* ---- Media Controls ---- */}
          <div className="tesla-card">
            <p className="section-title" style={{ paddingTop: 0 }}>Media Controls</p>

            {/* Play controls */}
            <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 20, marginBottom: 28 }}>
              <button
                className="media-btn"
                style={{ width: 52, height: 52 }}
                onClick={() => mediaCmd('media_prev_track', 'prev', 'Previous')}
                disabled={cmdLoading === 'prev'}
              >
                {cmdLoading === 'prev' ? <Spin /> : <PrevIcon />}
              </button>

              <button
                className="media-btn primary"
                style={{ width: 68, height: 68 }}
                onClick={() => { mediaCmd('media_toggle_playback', 'play', isPlaying ? 'Paused' : 'Playing'); setIsPlaying(!isPlaying); }}
                disabled={cmdLoading === 'play'}
              >
                {cmdLoading === 'play' ? <Spin /> : (isPlaying ? <PauseIcon /> : <PlayIcon />)}
              </button>

              <button
                className="media-btn"
                style={{ width: 52, height: 52 }}
                onClick={() => mediaCmd('media_next_track', 'next', 'Next')}
                disabled={cmdLoading === 'next'}
              >
                {cmdLoading === 'next' ? <Spin /> : <NextIcon />}
              </button>
            </div>

            {/* Volume */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#86888f' }}>
                  <VolumeIcon />
                  <span style={{ fontSize: 13 }}>Volume</span>
                </div>
                <span style={{ color: '#ffffff', fontWeight: 700, fontSize: 16 }}>{volume}<span style={{ color: '#86888f', fontWeight: 400, fontSize: 12 }}>/11</span></span>
              </div>
              <IonRange
                min={0} max={11} step={1} value={volume}
                onIonChange={(e) => handleVolumeChange(e.detail.value as unknown as number)}
              />
              {/* Volume quick buttons */}
              <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
                <button
                  onClick={() => handleVolumeChange(Math.max(0, volume - 1))}
                  style={{ flex: 1, background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, height: 40, cursor: 'pointer', color: '#fff', fontWeight: 700, fontSize: 20, fontFamily: 'inherit', transition: 'all 0.15s' }}
                >
                  −
                </button>
                <button
                  onClick={() => handleVolumeChange(Math.min(11, volume + 1))}
                  style={{ flex: 1, background: 'rgba(255,255,255,0.08)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, height: 40, cursor: 'pointer', color: '#fff', fontWeight: 700, fontSize: 20, fontFamily: 'inherit', transition: 'all 0.15s' }}
                >
                  +
                </button>
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
      </IonContent>
    </IonPage>
  );
};

export default Navigation;
