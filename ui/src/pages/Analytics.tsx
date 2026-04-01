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
const TimeIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M11.99 2C6.47 2 2 6.48 2 12s4.47 10 9.99 10C17.52 22 22 17.52 22 12S17.52 2 11.99 2zM12 20c-4.42 0-8-3.58-8-8s3.58-8 8-8 8 3.58 8 8-3.58 8-8 8zm.5-13H11v6l5.25 3.15.75-1.23-4.5-2.67z"/></svg>;
const EnergyIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M11 21h-1l1-7H7.5c-.88 0-.33-.75-.31-.78C8.48 10.94 10.42 7.54 13.01 3h1l-1 7h3.51c.4 0 .62.19.4.66C12.97 17.55 11 21 11 21z"/></svg>;
const CostIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z"/></svg>;
const BatDrainIcon = () => <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor"><path d="M15.67 4H14V2h-4v2H8.33C7.6 4 7 4.6 7 5.33v15.34C7 21.4 7.6 22 8.33 22h7.34c.74 0 1.33-.6 1.33-1.33V5.33C17 4.6 16.4 4 15.67 4zM13 18h-2v-2h2v2zm0-4h-2V9h2v5z"/></svg>;
const ConnectIcon = () => <svg width={32} height={32} viewBox="0 0 24 24" fill="rgba(255,255,255,0.25)"><path d="M1 9l2 2c4.97-4.97 13.03-4.97 18 0l2-2C16.93 2.93 7.08 2.93 1 9zm8 8l3 3 3-3c-1.65-1.66-4.34-1.66-6 0zm-4-4l2 2c2.76-2.76 7.24-2.76 10 0l2-2C15.14 9.14 8.87 9.14 5 13z"/></svg>;

type Tab = 'overview' | 'trips' | 'charges' | 'efficiency' | 'timeline' | 'energy' | 'cost' | 'vampire';

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
  const m = Math.round(mins % 60);
  return h === 0 ? `${m}m` : `${h}h ${m}m`;
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return '--';
  try { return new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }); }
  catch { return dateStr; }
}

function formatDateTime(dateStr?: string): string {
  if (!dateStr) return '--';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' ' +
      d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  } catch { return dateStr; }
}

function NotConfigured() {
  return (
    <div className="empty-state">
      <div className="empty-icon"><ConnectIcon /></div>
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

/* ---- Stat card ---- */
function StatCard({ label, value, color, icon }: { label: string; value: string; color: string; icon: React.ReactNode }) {
  return (
    <div className="tesla-card" style={{ padding: '16px 14px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <div style={{ color, display: 'flex' }}>{icon}</div>
        <span className="label-xs">{label}</span>
      </div>
      <div style={{ color, fontWeight: 700, fontSize: 22, lineHeight: 1, letterSpacing: '-0.5px' }}>{value}</div>
    </div>
  );
}

/* ---- Bar chart ---- */
function BarChart({ items, labelKey, valueKey, color = '#0FBCF9', unit = '' }: {
  items: Record<string, any>[];
  labelKey: string;
  valueKey: string;
  color?: string;
  unit?: string;
}) {
  if (!items.length) return <div style={{ color: '#86888f', fontSize: 13 }}>No data</div>;
  const max = Math.max(...items.map(i => Number(i[valueKey]) || 0), 0.1);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      {items.map((item, i) => {
        const val = Number(item[valueKey]) || 0;
        const pct = (val / max) * 100;
        const lbl = String(item[labelKey] || '').slice(-5); // MM-DD or similar
        return (
          <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 40, fontSize: 10, color: '#86888f', textAlign: 'right', flexShrink: 0 }}>{lbl}</span>
            <div style={{ flex: 1, height: 14, background: 'rgba(255,255,255,0.04)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2, transition: 'width .3s' }} />
            </div>
            <span style={{ width: 50, fontSize: 10, color: '#86888f', flexShrink: 0 }}>{val.toFixed(1)}{unit}</span>
          </div>
        );
      })}
    </div>
  );
}

const Analytics: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [trips, setTrips] = useState<TripStat[]>([]);
  const [charges, setCharges] = useState<ChargeStat[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [efficiency, setEfficiency] = useState<any[]>([]);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [dailyEnergy, setDailyEnergy] = useState<any[]>([]);
  const [costReport, setCostReport] = useState<any>(null);
  const [vampire, setVampire] = useState<any>(null);
  const [tripStats, setTripStats] = useState<any>(null);
  const [heatmap, setHeatmap] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [notConfigured, setNotConfigured] = useState(false);

  const fetchData = async (tab: Tab) => {
    setLoading(true);
    setNotConfigured(false);
    try {
      if (tab === 'overview') {
        const [statsData, tsData] = await Promise.allSettled([api.getStats(), api.getTripStats()]);
        if (statsData.status === 'fulfilled') setStats(statsData.value as Stats);
        if (tsData.status === 'fulfilled') setTripStats(tsData.value);
      } else if (tab === 'trips') {
        const data = await api.getTrips();
        setTrips(Array.isArray(data) ? data : []);
      } else if (tab === 'charges') {
        const data = await api.getCharges();
        setCharges(Array.isArray(data) ? data : []);
      } else if (tab === 'efficiency') {
        const data = await api.getEfficiency();
        setEfficiency(Array.isArray(data) ? data : []);
      } else if (tab === 'timeline') {
        const data = await api.getTimeline();
        setTimeline(Array.isArray(data) ? data : []);
      } else if (tab === 'energy') {
        const [enData, hmData] = await Promise.allSettled([api.getDailyEnergy(), api.getHeatmap()]);
        if (enData.status === 'fulfilled') setDailyEnergy(Array.isArray(enData.value) ? enData.value : []);
        if (hmData.status === 'fulfilled') setHeatmap(Array.isArray(hmData.value) ? hmData.value : []);
      } else if (tab === 'cost') {
        const data = await api.getCostReport();
        setCostReport(data);
      } else if (tab === 'vampire') {
        const data = await api.getVampire();
        setVampire(data);
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
    { key: 'timeline', label: 'Timeline', icon: <TimeIcon /> },
    { key: 'energy', label: 'Energy', icon: <EnergyIcon /> },
    { key: 'cost', label: 'Cost', icon: <CostIcon /> },
    { key: 'vampire', label: 'Vampire', icon: <BatDrainIcon /> },
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
              {/* ---- Overview ---- */}
              {activeTab === 'overview' && stats && (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                    <StatCard label="Total Trips" value={stats.total_trips?.toString() ?? '0'} color="#0FBCF9" icon={<RouteIcon />} />
                    <StatCard label="Total Distance" value={formatDistance(stats.total_distance)} color="#0BE881" icon={<TrendIcon />} />
                    <StatCard label="Total Energy" value={stats.total_energy ? `${stats.total_energy.toFixed(1)} kWh` : '--'} color="#F99716" icon={<BoltIcon />} />
                    <StatCard label="Avg Efficiency" value={stats.avg_efficiency ? `${stats.avg_efficiency.toFixed(0)} Wh/km` : '--'} color="#05C46B" icon={<TrendIcon />} />
                    <StatCard label="Total Charges" value={stats.total_charges?.toString() ?? '0'} color="#0FBCF9" icon={<BoltIcon />} />
                    <StatCard label="Total Cost" value={stats.total_cost ? `$${stats.total_cost.toFixed(2)}` : '--'} color="#0BE881" icon={<CostIcon />} />
                  </div>

                  {/* Top routes from getTripStats */}
                  {tripStats?.top_routes && Array.isArray(tripStats.top_routes) && tripStats.top_routes.length > 0 && (
                    <div className="tesla-card" style={{ marginTop: 12, padding: 16 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#fff', marginBottom: 12 }}>Top Routes</div>
                      {tripStats.top_routes.slice(0, 5).map((route: any, i: number) => (
                        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 0', borderBottom: i < Math.min(tripStats.top_routes.length, 5) - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none' }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ color: '#fff', fontSize: 13 }}>{route.route || route.start_address || 'Unknown'}</div>
                            {route.end_address && <div style={{ color: '#86888f', fontSize: 11 }}>to {route.end_address}</div>}
                          </div>
                          <div style={{ textAlign: 'right', flexShrink: 0 }}>
                            <div style={{ color: '#0BE881', fontSize: 14, fontWeight: 600 }}>{route.count || route.trips || 0}x</div>
                            {route.avg_km != null && <div style={{ color: '#86888f', fontSize: 11 }}>{route.avg_km.toFixed(0)} km avg</div>}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
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
                          {trip.energy_used != null && <span style={{ color: '#86888f', fontSize: 12 }}>{trip.energy_used.toFixed(1)} kWh</span>}
                          {trip.efficiency != null && <span style={{ color: '#86888f', fontSize: 12 }}>{trip.efficiency.toFixed(0)} Wh/km</span>}
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
                            <div style={{ color: '#ffffff', fontSize: 13, fontWeight: 500 }}>{c.address || 'Unknown location'}</div>
                            <div style={{ color: '#86888f', fontSize: 11, marginTop: 3 }}>{formatDate(c.start_date)}</div>
                          </div>
                          <span style={{ color: '#0BE881', fontWeight: 700, fontSize: 14, flexShrink: 0 }}>
                            +{c.charge_energy_added?.toFixed(1) ?? '--'} kWh
                          </span>
                        </div>
                        <div style={{ display: 'flex', gap: 14 }}>
                          <span style={{ color: '#86888f', fontSize: 12 }}>{formatDuration(c.duration)}</span>
                          {c.cost != null && <span style={{ color: '#86888f', fontSize: 12 }}>${c.cost.toFixed(2)}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )
              )}

              {/* ---- Efficiency ---- */}
              {activeTab === 'efficiency' && (
                efficiency.length === 0 ? <NotConfigured /> : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {efficiency.slice(0, 50).map((e: any, i: number) => (
                      <div key={i} className="tesla-card" style={{ padding: '14px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                          <div>
                            <div style={{ color: '#ffffff', fontSize: 13, fontWeight: 500 }}>
                              {e.start_address || e.address || 'Trip'}
                            </div>
                            <div style={{ color: '#86888f', fontSize: 11, marginTop: 2 }}>{formatDate(e.start_date || e.date)}</div>
                          </div>
                          <span style={{ color: '#05C46B', fontWeight: 700, fontSize: 16 }}>
                            {e.wh_per_km != null ? `${e.wh_per_km.toFixed(0)} Wh/km` : e.kwh_per_100mi != null ? `${e.kwh_per_100mi.toFixed(1)} kWh/100mi` : '--'}
                          </span>
                        </div>
                        <div style={{ display: 'flex', gap: 14 }}>
                          {e.distance_km != null && <span style={{ color: '#86888f', fontSize: 12 }}>{e.distance_km.toFixed(1)} km</span>}
                          {e.energy_kwh != null && <span style={{ color: '#86888f', fontSize: 12 }}>{e.energy_kwh.toFixed(2)} kWh</span>}
                          {e.duration_min != null && <span style={{ color: '#86888f', fontSize: 12 }}>{formatDuration(e.duration_min)}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )
              )}

              {/* ---- Timeline ---- */}
              {activeTab === 'timeline' && (
                timeline.length === 0 ? <NotConfigured /> : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {timeline.slice(0, 60).map((event: any, i: number) => {
                      const type = event.type || 'unknown';
                      const color = type === 'drive' ? '#0BE881' : type === 'charge' ? '#0FBCF9' : type === 'update' ? '#F99716' : '#86888f';
                      const icon = type === 'drive' ? 'D' : type === 'charge' ? 'C' : type === 'update' ? 'U' : '?';
                      return (
                        <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                          <div style={{
                            width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
                            background: `${color}22`, color, fontSize: 12, fontWeight: 700,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                          }}>{icon}</div>
                          <div className="tesla-card" style={{ flex: 1, padding: '10px 12px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ color: '#ffffff', fontSize: 13, fontWeight: 500 }}>
                                {event.summary || event.address || event.version || type}
                              </span>
                              <span style={{ color, fontSize: 12, fontWeight: 600, textTransform: 'capitalize' }}>{type}</span>
                            </div>
                            <div style={{ color: '#86888f', fontSize: 11, marginTop: 3 }}>
                              {formatDateTime(event.start_date || event.date)}
                              {event.distance_km != null && ` — ${event.distance_km.toFixed(1)} km`}
                              {event.energy_kwh != null && ` — ${event.energy_kwh.toFixed(1)} kWh`}
                              {event.energy_added_kwh != null && ` — +${event.energy_added_kwh.toFixed(1)} kWh`}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )
              )}

              {/* ---- Daily Energy ---- */}
              {activeTab === 'energy' && (
                dailyEnergy.length === 0 ? <NotConfigured /> : (
                  <div>
                    <div className="tesla-card" style={{ padding: 16 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#fff', marginBottom: 12 }}>
                        Daily Energy Added (kWh) — Last 30 Days
                      </div>
                      <BarChart items={dailyEnergy.slice(-30)} labelKey="date" valueKey="kwh" color="#0FBCF9" unit=" kWh" />
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 10 }}>
                      <StatCard
                        label="Total kWh"
                        value={`${dailyEnergy.reduce((s: number, d: any) => s + (Number(d.kwh) || 0), 0).toFixed(1)}`}
                        color="#0FBCF9"
                        icon={<EnergyIcon />}
                      />
                      <StatCard
                        label="Avg/Day"
                        value={`${(dailyEnergy.reduce((s: number, d: any) => s + (Number(d.kwh) || 0), 0) / (dailyEnergy.length || 1)).toFixed(1)}`}
                        color="#0BE881"
                        icon={<TrendIcon />}
                      />
                    </div>

                    {/* Driving Activity Heatmap (from getHeatmap) */}
                    {heatmap.length > 0 && (
                      <div className="tesla-card" style={{ marginTop: 10, padding: 16 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: '#fff', marginBottom: 12 }}>
                          Driving Activity — Last 12 Months
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
                          {heatmap.slice(-365).map((day: any, i: number) => {
                            const km = Number(day.km || day.distance_km || 0);
                            const opacity = km === 0 ? 0.08 : Math.min(0.2 + (km / 200) * 0.8, 1);
                            return (
                              <div
                                key={i}
                                title={`${day.date}: ${km.toFixed(0)} km`}
                                style={{
                                  width: 10, height: 10, borderRadius: 2,
                                  background: km === 0 ? 'rgba(255,255,255,0.06)' : `rgba(5,196,107,${opacity})`,
                                }}
                              />
                            );
                          })}
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 8 }}>
                          <span style={{ fontSize: 10, color: '#86888f' }}>Less</span>
                          <div style={{ display: 'flex', gap: 3 }}>
                            {[0.08, 0.25, 0.5, 0.75, 1].map((o, i) => (
                              <div key={i} style={{ width: 10, height: 10, borderRadius: 2, background: i === 0 ? 'rgba(255,255,255,0.06)' : `rgba(5,196,107,${o})` }} />
                            ))}
                          </div>
                          <span style={{ fontSize: 10, color: '#86888f' }}>More</span>
                        </div>
                      </div>
                    )}
                  </div>
                )
              )}

              {/* ---- Cost Report ---- */}
              {activeTab === 'cost' && (
                !costReport ? <NotConfigured /> : (
                  <div>
                    {costReport.cost_per_kwh != null && (
                      <div className="tesla-card" style={{ padding: 14, marginBottom: 10, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ color: '#86888f', fontSize: 13 }}>Rate</span>
                        <span style={{ color: '#0BE881', fontWeight: 700, fontSize: 16 }}>${costReport.cost_per_kwh}/kWh</span>
                      </div>
                    )}
                    {costReport.months && Object.keys(costReport.months).length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {Object.entries(costReport.months as Record<string, any>).map(([month, data]: [string, any]) => (
                          <div key={month} className="tesla-card" style={{ padding: '14px' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                              <span style={{ color: '#ffffff', fontSize: 15, fontWeight: 600 }}>{month}</span>
                              <span style={{ color: '#0BE881', fontWeight: 700, fontSize: 16 }}>${data.cost?.toFixed(2) ?? '0'}</span>
                            </div>
                            <div style={{ display: 'flex', gap: 16 }}>
                              <span style={{ color: '#86888f', fontSize: 12 }}>{data.sessions ?? 0} sessions</span>
                              <span style={{ color: '#86888f', fontSize: 12 }}>{data.kwh?.toFixed(1) ?? 0} kWh</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : <NotConfigured />}
                  </div>
                )
              )}

              {/* ---- Vampire Drain ---- */}
              {activeTab === 'vampire' && (
                !vampire ? <NotConfigured /> : (
                  <div>
                    {/* Summary stats */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 10 }}>
                      <StatCard
                        label="Avg Drain/Day"
                        value={vampire.avg_drain_pct_per_day != null ? `${vampire.avg_drain_pct_per_day.toFixed(1)}%` : vampire.avg_daily_loss_pct != null ? `${vampire.avg_daily_loss_pct.toFixed(1)}%` : '--'}
                        color="#FF6B6B"
                        icon={<BatDrainIcon />}
                      />
                      <StatCard
                        label="Total Loss"
                        value={vampire.total_loss_kwh != null ? `${vampire.total_loss_kwh.toFixed(1)} kWh` : vampire.total_drain_kwh != null ? `${vampire.total_drain_kwh.toFixed(1)} kWh` : '--'}
                        color="#F99716"
                        icon={<EnergyIcon />}
                      />
                    </div>
                    {/* Daily breakdown */}
                    {Array.isArray(vampire.days) && vampire.days.length > 0 && (
                      <div className="tesla-card" style={{ padding: 16 }}>
                        <div style={{ fontSize: 13, fontWeight: 600, color: '#fff', marginBottom: 12 }}>Daily Drain</div>
                        <BarChart items={vampire.days.slice(-30)} labelKey="date" valueKey="loss_pct" color="#FF6B6B" unit="%" />
                      </div>
                    )}
                    {Array.isArray(vampire.entries) && vampire.entries.length > 0 && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 10 }}>
                        {vampire.entries.slice(0, 30).map((e: any, i: number) => (
                          <div key={i} className="tesla-card" style={{ padding: '10px 14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div>
                              <div style={{ color: '#fff', fontSize: 13 }}>{formatDate(e.date || e.start_date)}</div>
                              {e.idle_hours != null && <div style={{ color: '#86888f', fontSize: 11 }}>{e.idle_hours.toFixed(1)}h idle</div>}
                            </div>
                            <span style={{ color: '#FF6B6B', fontWeight: 600, fontSize: 14 }}>
                              -{e.loss_pct?.toFixed(1) ?? e.drain_pct?.toFixed(1) ?? '?'}%
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )
              )}
            </>
          )}
        </div>
      </IonContent>
    </IonPage>
  );
};

export default Analytics;
