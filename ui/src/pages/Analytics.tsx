import React, { useState, useEffect } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
} from '@ionic/react';
import { api, TripStat, ChargeStat, Stats } from '../api/client';

// ---- Icons ----
const ChartIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 3c1.93 0 3.5 1.57 3.5 3.5S13.93 13 12 13s-3.5-1.57-3.5-3.5S10.07 6 12 6zm7 13H5v-.23c0-.62.28-1.2.76-1.58C7.47 15.82 9.64 15 12 15s4.53.82 6.24 2.19c.48.38.76.97.76 1.58V19z"/></svg>;
const RouteIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M13.5 5.5c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zM9.8 8.9L7 23h2.1l1.8-8 2.1 2v6h2v-7.5l-2.1-2 .6-3C14.8 12 16.8 13 19 13v-2c-1.9 0-3.5-1-4.3-2.4l-1-1.6c-.4-.6-1-1-1.7-1-.3 0-.5.1-.8.1L6 8.3V13h2V9.6l1.8-.7"/></svg>;
const BoltIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M7 2v11h3v9l7-12h-4l4-8z"/></svg>;
const TrendIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M16 6l2.29 2.29-4.88 4.88-4-4L2 16.59 3.41 18l6-6 4 4 6.3-6.29L22 12V6z"/></svg>;
const ConnectIcon = () => <svg width={32} height={32} viewBox="0 0 24 24" fill="rgba(255,255,255,0.25)"><path d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0zm-4-4l2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z"/></svg>;

type Tab = 'overview' | 'trips' | 'charges' | 'efficiency';

function Spin() {
  return (
    <svg width={28} height={28} viewBox="0 0 24 24" fill="none">
      <circle cx={12} cy={12} r={9} stroke="rgba(255,255,255,0.08)" strokeWidth={3} />
      <path d="M12 3a9 9 0 019 9" stroke="#05C46B" strokeWidth={3} strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

function formatDistance(km?: number): string {
  if (!km) return '--';
  return `${km.toFixed(1)} km`;
}

function formatDuration(mins?: number): string {
  if (!mins) return '--';
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return h === 0 ? `${m}m` : `${h}h ${m}m`;
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return '--';
  try { return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); }
  catch { return dateStr; }
}

function NotConfigured() {
  return (
    <div className="empty-state">
      <div className="empty-icon">
        <ConnectIcon />
      </div>
      <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 18 }}>Connect TeslaMate</div>
      <div style={{ color: '#86888f', fontSize: 14, lineHeight: 1.5 }}>
        TeslaMate is not configured or not reachable.
      </div>
      <div style={{ color: '#86888f', fontSize: 13, opacity: 0.7 }}>
        Set the TeslaMate URL in Settings to enable analytics.
      </div>
    </div>
  );
}

const Analytics: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [trips, setTrips] = useState<TripStat[]>([]);
  const [charges, setCharges] = useState<ChargeStat[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(false);
  const [notConfigured, setNotConfigured] = useState(false);

  const fetchData = async (tab: Tab) => {
    setLoading(true);
    setNotConfigured(false);
    try {
      if (tab === 'overview') {
        const data = await api.getStats();
        setStats(data);
      } else if (tab === 'trips') {
        const data = await api.getTrips();
        setTrips(Array.isArray(data) ? data : []);
      } else if (tab === 'charges') {
        const data = await api.getCharges();
        setCharges(Array.isArray(data) ? data : []);
      } else if (tab === 'efficiency') {
        await api.getEfficiency();
      }
    } catch {
      setNotConfigured(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(activeTab); }, [activeTab]);

  const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
    { key: 'overview', label: 'Overview', icon: <ChartIcon /> },
    { key: 'trips', label: 'Trips', icon: <RouteIcon /> },
    { key: 'charges', label: 'Charges', icon: <BoltIcon /> },
    { key: 'efficiency', label: 'Efficiency', icon: <TrendIcon /> },
  ];

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700 }}>Analytics</IonTitle>
        </IonToolbar>
      </IonHeader>

      <IonContent>
        {/* Tab bar */}
        <div className="sub-tab-bar">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              className={`sub-tab${activeTab === tab.key ? ' active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
            >
              <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {tab.icon}
              </span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        <div className="page-pad">
          {loading ? (
            <div className="loading-center"><Spin /></div>
          ) : notConfigured ? (
            <NotConfigured />
          ) : (
            <>
              {/* ---- Overview / Stats ---- */}
              {activeTab === 'overview' && stats && (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    {[
                      { label: 'Total Trips', value: stats.total_trips?.toString() ?? '0', color: '#0FBCF9', icon: <RouteIcon /> },
                      { label: 'Total Distance', value: formatDistance(stats.total_distance), color: '#0BE881', icon: <TrendIcon /> },
                      { label: 'Total Energy', value: stats.total_energy ? `${stats.total_energy.toFixed(1)} kWh` : '--', color: '#F99716', icon: <BoltIcon /> },
                      { label: 'Avg Efficiency', value: stats.avg_efficiency ? `${stats.avg_efficiency.toFixed(0)} Wh/km` : '--', color: '#05C46B', icon: <TrendIcon /> },
                      { label: 'Total Charges', value: stats.total_charges?.toString() ?? '0', color: '#0FBCF9', icon: <BoltIcon /> },
                      { label: 'Total Cost', value: stats.total_cost ? `$${stats.total_cost.toFixed(2)}` : '--', color: '#0BE881', icon: <ChartIcon /> },
                    ].map((stat) => (
                      <div
                        key={stat.label}
                        className="tesla-card"
                        style={{ padding: '16px 14px' }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                          <div style={{ color: stat.color, display: 'flex' }}>{stat.icon}</div>
                          <span className="label-xs">{stat.label}</span>
                        </div>
                        <div style={{ color: stat.color, fontWeight: 700, fontSize: 22, lineHeight: 1, letterSpacing: '-0.5px' }}>
                          {stat.value}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* ---- Trips ---- */}
              {activeTab === 'trips' && (
                trips.length === 0 ? <NotConfigured /> : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {trips.slice(0, 50).map((trip, i) => (
                      <div key={trip.id || i} className="tesla-card" style={{ padding: '14px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                          <div style={{ flex: 1, marginRight: 12 }}>
                            <div style={{ color: '#ffffff', fontSize: 13, fontWeight: 500, lineHeight: 1.4 }}>
                              {trip.start_address || 'Unknown'}
                            </div>
                            <div style={{ color: '#86888f', fontSize: 12, marginTop: 1 }}>
                              to {trip.end_address || 'Unknown'}
                            </div>
                            <div style={{ color: '#86888f', fontSize: 11, marginTop: 3 }}>
                              {formatDate(trip.start_date)}
                            </div>
                          </div>
                          <span style={{ color: '#0BE881', fontWeight: 700, fontSize: 14, flexShrink: 0 }}>
                            {formatDistance(trip.distance)}
                          </span>
                        </div>
                        <div style={{ display: 'flex', gap: 14 }}>
                          <span style={{ color: '#86888f', fontSize: 12 }}>{formatDuration(trip.duration)}</span>
                          {trip.energy_used && (
                            <span style={{ color: '#86888f', fontSize: 12 }}>{trip.energy_used.toFixed(1)} kWh</span>
                          )}
                          {trip.efficiency && (
                            <span style={{ color: '#86888f', fontSize: 12 }}>{trip.efficiency.toFixed(0)} Wh/km</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )
              )}

              {/* ---- Charges ---- */}
              {activeTab === 'charges' && (
                charges.length === 0 ? <NotConfigured /> : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {charges.slice(0, 50).map((c, i) => (
                      <div key={c.id || i} className="tesla-card" style={{ padding: '14px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
                          <div>
                            <div style={{ color: '#ffffff', fontSize: 13, fontWeight: 500 }}>
                              {c.address || 'Unknown location'}
                            </div>
                            <div style={{ color: '#86888f', fontSize: 11, marginTop: 3 }}>
                              {formatDate(c.start_date)}
                            </div>
                          </div>
                          <span style={{ color: '#0BE881', fontWeight: 700, fontSize: 14, flexShrink: 0 }}>
                            +{c.charge_energy_added?.toFixed(1) ?? '--'} kWh
                          </span>
                        </div>
                        <div style={{ display: 'flex', gap: 14 }}>
                          <span style={{ color: '#86888f', fontSize: 12 }}>{formatDuration(c.duration)}</span>
                          {c.cost != null && (
                            <span style={{ color: '#86888f', fontSize: 12 }}>${c.cost.toFixed(2)}</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )
              )}

              {/* ---- Efficiency ---- */}
              {activeTab === 'efficiency' && <NotConfigured />}
            </>
          )}
        </div>
      </IonContent>
    </IonPage>
  );
};

export default Analytics;
