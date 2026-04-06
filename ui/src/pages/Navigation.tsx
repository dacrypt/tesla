import React, { useState, useEffect } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
  IonRange,
  IonToast,
} from '@ionic/react';
import { api, GeofenceZone } from '../api/client';
import { useVehicleData } from '../hooks/useVehicleData';
import Spinner from '../components/icons/Spinner';
import {
  NavIcon,
  LocationIcon,
  PrevIcon,
  PlayIcon,
  PauseIcon,
  NextIcon,
  VolumeIcon,
  MapPinIcon,
  SpeedIcon,
} from '../components/icons/Icons';
import VehicleMap from '../components/VehicleMap';

const Navigation: React.FC = () => {
  const { state, error } = useVehicleData();
  const [address, setAddress] = useState('');
  const [cmdLoading, setCmdLoading] = useState<string | null>(null);
  const [toast, setToast] = useState<{ message: string; color: string } | null>(null);
  const [volume, setVolume] = useState<number>(5);
  const [isPlaying, setIsPlaying] = useState(false);

  // Geofences
  const [geofences, setGeofences] = useState<GeofenceZone[]>([]);
  const [geoName, setGeoName] = useState('');
  const [geoRadius, setGeoRadius] = useState('0.2');
  const [geoLoading, setGeoLoading] = useState(false);

  // Lifetime map
  const [geoPoints, setGeoPoints] = useState<{ lat: number; lon: number }[]>([]);

  useEffect(() => {
    api.getGeofences().then(setGeofences).catch(() => {});
    api.getGeoLocations().then(setGeoPoints).catch(() => {});
  }, []);

  const addGeofence = async () => {
    if (!geoName.trim()) { setToast({ message: 'Enter a name', color: 'warning' }); return; }
    const lat = state?.latitude;
    const lon = state?.longitude;
    if (lat == null || lon == null) { setToast({ message: 'No vehicle location available', color: 'warning' }); return; }
    setGeoLoading(true);
    try {
      await api.addGeofence(geoName.trim(), lat, lon, parseFloat(geoRadius) || 0.2);
      setGeoName('');
      const updated = await api.getGeofences();
      setGeofences(updated);
      setToast({ message: `Geofence "${geoName.trim()}" saved`, color: 'success' });
    } catch (e: any) {
      setToast({ message: 'Failed: ' + (e.message || e), color: 'danger' });
    } finally {
      setGeoLoading(false);
    }
  };

  const removeGeofence = async (name: string) => {
    try {
      await api.removeGeofence(name);
      setGeofences((prev) => prev.filter((g) => g.name !== name));
      setToast({ message: `Removed "${name}"`, color: 'success' });
    } catch (e: any) {
      setToast({ message: 'Remove failed: ' + (e.message || e), color: 'danger' });
    }
  };

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
              {cmdLoading === 'nav' ? <Spinner color="#fff" /> : <NavIcon />}
              Send to Car
            </button>
          </div>

          {/* ---- Location info ---- */}
          {state?.latitude && (
            <div className="tesla-card">
              <p className="section-title" style={{ paddingTop: 0 }}>Current Location</p>
              <VehicleMap
                latitude={state.latitude}
                longitude={state.longitude ?? 0}
                label={state.speed != null ? `${state.speed} mph` : undefined}
                height="280px"
                geofences={geofences}
              />
              <div className="stat-row" style={{ marginTop: 10 }}>
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

          {/* ---- Lifetime Map ---- */}
          {geoPoints.length > 0 && (
            <div className="tesla-card">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                <p className="section-title" style={{ paddingTop: 0, margin: 0 }}>Lifetime Driving Map</p>
                <span style={{ color: '#86888f', fontSize: 11 }}>{geoPoints.length.toLocaleString()} pts</span>
              </div>
              <VehicleMap
                latitude={0}
                longitude={0}
                height="320px"
                heatPoints={geoPoints}
              />
            </div>
          )}

          {/* ---- Geofences ---- */}
          <div className="tesla-card">
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
              <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(16,185,129,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#10b981' }}>
                <MapPinIcon />
              </div>
              <div>
                <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Geofences</div>
                <div style={{ color: '#86888f', fontSize: 12 }}>Saved zones shown on map</div>
              </div>
            </div>

            {/* Saved geofences list */}
            {geofences.length > 0 ? (
              <div style={{ marginBottom: 14 }}>
                {geofences.map((g) => (
                  <div key={g.name} style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(16,185,129,0.2)',
                    borderRadius: 8, padding: '8px 12px', marginBottom: 6,
                  }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981', flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ color: '#ffffff', fontSize: 13, fontWeight: 500 }}>{g.name}</div>
                      <div style={{ color: '#86888f', fontSize: 11, fontFamily: 'monospace' }}>
                        {g.lat.toFixed(5)}, {g.lon.toFixed(5)} · {g.radius_km} km
                        {g.inside != null && (
                          <span style={{ marginLeft: 6, color: g.inside ? '#10b981' : '#86888f' }}>
                            {g.inside ? '· Inside' : `· ${g.distance_km?.toFixed(2)} km away`}
                          </span>
                        )}
                      </div>
                    </div>
                    <button
                      onClick={() => removeGeofence(g.name)}
                      className="tesla-btn secondary"
                      style={{ fontSize: 11, padding: '4px 10px', color: '#FF6B6B' }}
                    >
                      Delete
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ color: '#86888f', fontSize: 13, textAlign: 'center', padding: '8px 0', marginBottom: 14 }}>
                No geofences saved
              </div>
            )}

            {/* Add geofence form */}
            <div style={{ borderTop: '1px solid rgba(255,255,255,0.07)', paddingTop: 12 }}>
              <div style={{ color: '#86888f', fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 8 }}>
                Add Geofence {!state?.latitude && <span style={{ color: '#FF6B6B', textTransform: 'none', fontWeight: 400 }}>(requires vehicle location)</span>}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 8, marginBottom: 8 }}>
                <input
                  type="text"
                  value={geoName}
                  onChange={(e) => setGeoName(e.target.value)}
                  placeholder="Zone name (e.g. Home)"
                  className="tesla-input"
                  style={{ fontSize: 13 }}
                />
                <input
                  type="number"
                  value={geoRadius}
                  onChange={(e) => setGeoRadius(e.target.value)}
                  placeholder="km"
                  className="tesla-input"
                  style={{ fontSize: 13, width: 70 }}
                  min="0.05"
                  max="50"
                  step="0.05"
                />
              </div>
              {state?.latitude && (
                <div style={{ color: '#86888f', fontSize: 11, marginBottom: 8 }}>
                  Center: {state.latitude.toFixed(5)}, {state.longitude?.toFixed(5)} (current vehicle position)
                </div>
              )}
              <button
                onClick={addGeofence}
                disabled={geoLoading || !geoName.trim() || !state?.latitude}
                className="tesla-btn"
                style={{ width: '100%', fontSize: 13, opacity: !state?.latitude ? 0.4 : 1 }}
              >
                {geoLoading ? <Spinner color="#fff" /> : '+ Add Geofence'}
              </button>
            </div>
          </div>

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
                {cmdLoading === 'prev' ? <Spinner /> : <PrevIcon />}
              </button>

              <button
                className="media-btn primary"
                style={{ width: 68, height: 68 }}
                onClick={() => { mediaCmd('media_toggle_playback', 'play', isPlaying ? 'Paused' : 'Playing'); setIsPlaying(!isPlaying); }}
                disabled={cmdLoading === 'play'}
              >
                {cmdLoading === 'play' ? <Spinner /> : (isPlaying ? <PauseIcon /> : <PlayIcon />)}
              </button>

              <button
                className="media-btn"
                style={{ width: 52, height: 52 }}
                onClick={() => mediaCmd('media_next_track', 'next', 'Next')}
                disabled={cmdLoading === 'next'}
              >
                {cmdLoading === 'next' ? <Spinner /> : <NextIcon />}
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
