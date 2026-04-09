import React, { useState, useEffect } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
  IonRefresher,
  IonRefresherContent,
  IonSpinner,
  IonToast,
} from '@ionic/react';
import { useHistory } from 'react-router-dom';
import ModelYSilhouette from '../components/ModelYSilhouette';
import RecentCharges from '../components/RecentCharges';
import StatusBadge from '../components/StatusBadge';
import Spinner from '../components/icons/Spinner';
import { useVehicleData } from '../hooks/useVehicleData';
import { useDashboardTiles } from '../hooks/useDashboardTiles';
import { useAppInit } from '../hooks/useAppInit';
import { useMissionControl, MissionControlState } from '../hooks/useMissionControl';
import { api, FleetVehicle, AutomationsStatus } from '../api/client';

// ---- SVG Icons ----
const LockIcon = () => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor">
    <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zM12 17c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm3.1-9H8.9V6c0-1.71 1.39-3.1 3.1-3.1s3.1 1.39 3.1 3.1v2z"/>
  </svg>
);
const UnlockIcon = () => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor">
    <path d="M18 8h-1V6c0-2.76-2.24-5-5-5S7 3.24 7 6h2c0-1.65 1.35-3 3-3s3 1.35 3 3v2H6c-1.1 0-2 .9-2 2v10c0 1.1.9 2 2 2h12c1.1 0 2-.9 2-2V10c0-1.1-.9-2-2-2zm0 12H6V10h12v10zm-6-3c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2z"/>
  </svg>
);
const AcIcon = () => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor">
    <path d="M22 11h-4.17l3.24-3.24-1.41-1.42L15 11h-2V9l4.66-4.66-1.42-1.41L13 6.17V2h-2v4.17L7.76 2.93 6.34 4.34 11 9v2H9L4.34 6.34 2.93 7.76 6.17 11H2v2h4.17l-3.24 3.24 1.41 1.42L9 13h2v2l-4.66 4.66 1.42 1.41L11 17.83V22h2v-4.17l3.24 3.24 1.42-1.41L13 15v-2h2l4.66 4.66 1.41-1.42L17.83 13H22z"/>
  </svg>
);
const FlashLightsIcon = () => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor">
    <path d="M9 21c0 .55.45 1 1 1h4c.55 0 1-.45 1-1v-1H9v1zm3-19C8.14 2 5 5.14 5 9c0 2.38 1.19 4.47 3 5.74V17c0 .55.45 1 1 1h6c.55 0 1-.45 1-1v-2.26c1.81-1.27 3-3.36 3-5.74 0-3.86-3.14-7-7-7z"/>
  </svg>
);
const HornIcon = () => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor">
    <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z"/>
  </svg>
);
const WakeIcon = () => (
  <svg width={20} height={20} viewBox="0 0 24 24" fill="currentColor">
    <path d="M6.76 4.84l-1.8-1.79-1.41 1.41 1.79 1.79 1.42-1.41zM4 10.5H1v2h3v-2zm9-9.95h-2V3.5h2V.55zm7.45 3.91l-1.41-1.41-1.79 1.79 1.41 1.41 1.79-1.79zm-3.21 13.7l1.79 1.8 1.41-1.41-1.8-1.79-1.4 1.4zM20 10.5v2h3v-2h-3zm-8-5c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6-2.69-6-6-6zm-1 16.95h2V19.5h-2v2.95zm-7.45-3.91l1.41 1.41 1.79-1.8-1.41-1.41-1.79 1.8z"/>
  </svg>
);
const BoltIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <path d="M7 2v11h3v9l7-12h-4l4-8z"/>
  </svg>
);

function DeliveryCountdown({ deliveryDate }: { deliveryDate?: Date | null }) {
  const [, setTick] = React.useState(0);
  React.useEffect(() => {
    const id = setInterval(() => setTick(t => t + 1), 60000);
    return () => clearInterval(id);
  }, []);

  if (!deliveryDate) {
    return <div className="text-secondary text-lg fw-semi mt-xs">Delivery date pending</div>;
  }

  const now = new Date();
  const diff = deliveryDate.getTime() - now.getTime();
  const days = Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
  const hours = Math.max(0, Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60)));
  const isPast = diff <= 0;
  if (isPast) {
    return <div style={{ color: '#0BE881', fontWeight: 700, fontSize: 18 }}>Delivery Day! 🎉</div>;
  }
  return (
    <div className="flex-center gap-lg">
      <div style={{ textAlign: 'center' }}>
        <div style={{ color: '#05C46B', fontWeight: 700, fontSize: 36, lineHeight: 1, letterSpacing: '-1px' }}>{days}</div>
        <div className="text-secondary text-sm mt-xs">days</div>
      </div>
      <div style={{ color: '#86888f', fontSize: 28, lineHeight: 1.3, alignSelf: 'flex-start', marginTop: 4 }}>:</div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ color: '#05C46B', fontWeight: 700, fontSize: 36, lineHeight: 1, letterSpacing: '-1px' }}>{String(hours).padStart(2, '0')}</div>
        <div className="text-secondary text-sm mt-xs">hours</div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/* PRE-DELIVERY MISSION CONTROL                                               */
/* For the anxious customer obsessing over every detail of their order         */
/* ═══════════════════════════════════════════════════════════════════════════ */

function PreDeliveryDashboard({ missionControl, loading }: { missionControl: MissionControlState; loading: boolean }) {
  const history = useHistory();
  const [picoYPlaca, setPicoYPlaca] = React.useState<any>(null);
  const [refreshingSources, setRefreshingSources] = React.useState(false);
  const [refreshNote, setRefreshNote] = React.useState<string | null>(null);
  const [portalSyncing, setPortalSyncing] = React.useState(false);
  const sourceMap = React.useMemo(
    () => Object.fromEntries((missionControl.data?.sources || []).map((source) => [source.id, source])),
    [missionControl.data?.sources],
  );
  const domainMap = React.useMemo(
    () => Object.fromEntries((missionControl.data?.domains || []).map((domain) => [domain.domain_id, domain])),
    [missionControl.data?.domains],
  );

  const runt = sourceMap['co.runt'];
  const simit = sourceMap['co.simit'];
  const delivery = domainMap['delivery'];
  const financial = domainMap['financial'];
  const identity = domainMap['identity'];
  const legal = domainMap['legal'];
  const safety = domainMap['safety'];
  const sourceHealth = domainMap['source_health'];
  const plate = legal?.state?.plate || runt?.data?.placa;
  const deliveryDate = delivery?.state?.delivery_date || delivery?.state?.estimated_delivery || '';
  const deliveryLocation = delivery?.state?.delivery_location || '';
  const orderStatus = delivery?.state?.order_status || 'pending';
  const summaryLine = delivery?.summary || missionControl.data?.executive?.delivery_readiness?.summary || 'Procesando orden';

  React.useEffect(() => {
    const placa = plate;
    if (placa) {
      api.getPicoYPlaca(placa).then(setPicoYPlaca).catch(() => {});
    }
  }, [plate]);

  const refreshSourcesNow = React.useCallback(async () => {
    setRefreshingSources(true);
    setRefreshNote(null);
    try {
      const result = await api.refreshStaleSources();
      await missionControl.refresh();
      if (result.refreshed.length > 0) {
        setRefreshNote(`Refreshed ${result.refreshed.length} source(s)`);
      } else if (result.failed.length > 0) {
        setRefreshNote(`No source refreshed (${result.failed.length} failed)`);
      } else {
        setRefreshNote('No stale sources to refresh');
      }
    } catch (e: any) {
      setRefreshNote(e?.message || 'Failed to refresh sources');
    } finally {
      setRefreshingSources(false);
    }
  }, [missionControl]);

  const phase = delivery?.derived_flags?.delivery_scheduled
    ? 'delivery_scheduled'
    : legal?.derived_flags?.plate_assigned
      ? 'registered'
      : delivery?.derived_flags?.vin_assigned
        ? 'vin_assigned'
        : 'ordered';
  const phaseLabels: Record<string, string> = {
    ordered: 'Ordenado', vin_assigned: 'VIN asignado', shipped: 'En Tránsito',
    in_country: 'En País', registered: 'Registrado', delivery_scheduled: 'Cita Programada', delivered: 'Entregado',
  };
  const phaseColors: Record<string, string> = {
    ordered: '#0FBCF9', vin_assigned: '#F99716', shipped: '#F99716',
    in_country: '#0BE881', registered: '#0BE881', delivery_scheduled: '#05C46B', delivered: '#05C46B',
  };
  const phaseColor = phaseColors[phase] || '#0FBCF9';
  const statusColor = (status?: string) =>
    status === 'ok' ? '#0BE881' : status === 'degraded' ? '#F99716' : status === 'missing' ? '#86888f' : '#FF6B6B';
  const activeAlerts = missionControl.data?.active_alerts || [];
  const timeline = missionControl.data?.timeline || [];
  const timeAgo = (iso?: string | null) => {
    if (!iso) return 'never';
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  };
  const lastUpdatedFor = (...sourceIds: string[]) => {
    const timestamps = sourceIds
      .map((id) => sourceMap[id]?.refreshed_at)
      .filter(Boolean)
      .sort()
      .reverse();
    return timestamps[0] as string | undefined;
  };
  const openSourceHistory = (sourceId?: string, mode: 'history' | 'queries' = 'history') => {
    if (!sourceId) {
      history.push('/info');
      return;
    }
    history.push(`/info?source=${encodeURIComponent(sourceId)}&${mode}=1`);
  };

  const syncPortalDetails = React.useCallback(async () => {
    setPortalSyncing(true);
    setRefreshNote(null);
    try {
      const result = await api.portalScrape();
      if (!result?.ok) {
        setRefreshNote(result?.error || 'Portal sync failed');
        return;
      }
      await missionControl.refresh();
      setRefreshNote('Tesla portal synced');
    } catch (e: any) {
      setRefreshNote(e?.response?.data?.detail || e?.message || 'Portal sync failed');
    } finally {
      setPortalSyncing(false);
    }
  }, [missionControl]);

  if (loading && !missionControl.data) {
    return (
      <div className="page-pad" style={{ paddingTop: 24, textAlign: 'center' }}>
        <IonSpinner name="dots" style={{ '--color': '#05C46B' } as React.CSSProperties} />
      </div>
    );
  }

  return (
    <div className="page-pad" style={{ paddingTop: 8 }}>
      {/* ── Hero: Car + Countdown ── */}
      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        <div style={{ maxWidth: 240, margin: '0 auto', filter: 'drop-shadow(0 0 30px rgba(5,196,107,0.1))' }}>
          <ModelYSilhouette locked={true} />
        </div>
        <DeliveryCountdown deliveryDate={deliveryDate ? new Date(deliveryDate) : null} />
        <div className="text-secondary text-sm" style={{ marginTop: 6 }}>
          {delivery?.state?.vin ? `VIN …${String(delivery.state.vin).slice(-6)}` : ''}
          {deliveryLocation ? ` · ${deliveryLocation}` : ''}
        </div>
      </div>

      {/* ── Status Card ── */}
      <div className="tesla-card p-md mb-sm">
        <div className="flex-start gap-sm mb-sm">
          <span style={{ fontSize: 12, fontWeight: 700, color: phaseColor, background: `${phaseColor}18`, padding: '4px 12px', borderRadius: 100 }}>
            {phaseLabels[phase] || phase}
          </span>
          {orderStatus && orderStatus !== phaseLabels[phase] && (
            <span className="text-secondary text-sm">{orderStatus}</span>
          )}
        </div>
        <div style={{ color: '#fff', fontSize: 14, fontWeight: 500, marginBottom: 4 }}>{summaryLine}</div>
        {delivery?.state?.estimated_delivery && !delivery?.state?.delivery_date && (
          <div className="text-secondary" style={{ fontSize: 12, marginTop: 6 }}>
            Entrega estimada: <span className="text-accent fw-semi">{delivery.state.estimated_delivery}</span>
          </div>
        )}
        {delivery?.state?.delivery_date && (
          <div className="text-accent fw-bold text-lg" style={{ marginTop: 8 }}>
            Cita: {delivery.state.delivery_date}
            {delivery.state.delivery_location && <span style={{ fontWeight: 400, fontSize: 12, color: '#86888f' }}> · {delivery.state.delivery_location}</span>}
          </div>
        )}
        <div
          className="text-secondary text-xs"
          style={{ marginTop: 8, cursor: 'pointer' }}
          onClick={() => openSourceHistory('tesla.order', 'queries')}
        >
          Updated {timeAgo(lastUpdatedFor('tesla.order', 'tesla.portal', 'intl.ship_tracking'))} · tap for query audit
        </div>
        <div className="flex-between gap-sm mt-md">
          <div className="text-secondary text-xs">
            {refreshNote || 'If data looks old, refresh stale sources now'}
          </div>
          <button
            className="tesla-btn secondary"
            style={{ padding: '8px 12px', fontSize: 12, whiteSpace: 'nowrap' }}
            onClick={refreshSourcesNow}
            disabled={refreshingSources}
          >
            {refreshingSources ? 'Refreshing…' : 'Refresh Sources'}
          </button>
        </div>
      </div>

      {/* ── Executive Strip ── */}
      {missionControl.data?.executive && (
        <div className="grid-2" style={{ gap: 8, marginBottom: 12 }}>
          <div className="tesla-card" style={{ padding: '12px 10px', textAlign: 'center' }}>
            <div className="text-secondary mb-xs" style={{ fontSize: 10 }}>Delivery</div>
            <div className="text-base fw-bold" style={{ color: phaseColor }}>{missionControl.data.executive.delivery_readiness.status}</div>
          </div>
          <div className="tesla-card" style={{ padding: '12px 10px', textAlign: 'center' }}>
            <div className="text-secondary mb-xs" style={{ fontSize: 10 }}>Legal</div>
            <div className="text-base fw-bold" style={{ color: statusColor(legal?.health?.status) }}>
              {missionControl.data.executive.legal_readiness.status}
            </div>
          </div>
          <div className="tesla-card" style={{ padding: '12px 10px', textAlign: 'center' }}>
            <div className="text-secondary mb-xs" style={{ fontSize: 10 }}>Financial</div>
            <div className="text-base fw-bold" style={{ color: statusColor(financial?.health?.status) }}>
              {missionControl.data.executive.financial_state.status}
            </div>
          </div>
          <div className="tesla-card" style={{ padding: '12px 10px', textAlign: 'center' }}>
            <div className="text-secondary mb-xs" style={{ fontSize: 10 }}>Safety</div>
            <div className="text-base fw-bold" style={{ color: statusColor(safety?.health?.status) }}>
              {missionControl.data.executive.safety_posture.status}
            </div>
          </div>
          <div className="tesla-card" style={{ padding: '12px 10px', textAlign: 'center' }}>
            <div className="text-secondary mb-xs" style={{ fontSize: 10 }}>Sources</div>
            <div className="text-base fw-bold" style={{ color: '#fff' }}>
              {missionControl.data.executive.source_health.ok_sources}/{missionControl.data.executive.source_health.total_sources}
            </div>
          </div>
          <div className="tesla-card" style={{ padding: '12px 10px', textAlign: 'center' }}>
            <div className="text-secondary mb-xs" style={{ fontSize: 10 }}>Alerts</div>
            <div
              className="text-base fw-bold"
              style={{ color: activeAlerts.length ? '#FF6B6B' : '#0BE881', cursor: 'pointer' }}
              onClick={() => history.push('/alerts')}
            >
              {activeAlerts.length}
            </div>
          </div>
        </div>
      )}

      {/* ── Domain Summary Cards ── */}
      {(financial || safety || identity || sourceHealth) && (
        <div className="grid-2" style={{ gap: 8, marginBottom: 12 }}>
          {financial && (
            <div className="tesla-card" style={{ padding: '12px 14px', cursor: 'pointer' }} onClick={() => openSourceHistory('co.fasecolda')}>
              <div className="text-secondary mb-sm" style={{ fontSize: 10 }}>Financial</div>
              <div className="text-base fw-semi mb-xs" style={{ color: '#fff' }}>{financial.summary}</div>
              <div style={{ fontSize: 10, color: statusColor(financial.health?.status) }}>{financial.health?.status || 'missing'} · updated {timeAgo(lastUpdatedFor('tesla.portal', 'tesla.order', 'co.fasecolda', 'co.simit'))}</div>
              {financial.derived_flags?.portal_refresh_required && (
                <div style={{ marginTop: 8 }}>
                  <button
                    className="tesla-btn secondary"
                    style={{ padding: '8px 10px', fontSize: 11 }}
                    onClick={(event) => {
                      event.stopPropagation();
                      syncPortalDetails();
                    }}
                    disabled={portalSyncing}
                  >
                    {portalSyncing ? 'Waiting for Tesla portal…' : 'Open Tesla Portal Login'}
                  </button>
                </div>
              )}
            </div>
          )}
          {safety && (
            <div className="tesla-card" style={{ padding: '12px 14px', cursor: 'pointer' }} onClick={() => openSourceHistory('us.nhtsa_recalls')}>
              <div className="text-secondary mb-sm" style={{ fontSize: 10 }}>Safety</div>
              <div className="text-base fw-semi mb-xs" style={{ color: '#fff' }}>{safety.summary}</div>
              <div style={{ fontSize: 10, color: statusColor(safety.health?.status) }}>{safety.health?.status || 'missing'} · updated {timeAgo(lastUpdatedFor('us.nhtsa_recalls', 'us.nhtsa_complaints', 'us.nhtsa_investigations', 'co.recalls'))}</div>
            </div>
          )}
          {identity && (
            <div className="tesla-card" style={{ padding: '12px 14px', cursor: 'pointer' }} onClick={() => openSourceHistory('vin.decode')}>
              <div className="text-secondary mb-sm" style={{ fontSize: 10 }}>Identity</div>
              <div className="text-base fw-semi mb-xs" style={{ color: '#fff' }}>{identity.summary}</div>
              <div style={{ fontSize: 10, color: statusColor(identity.health?.status) }}>{identity.health?.status || 'missing'} · updated {timeAgo(lastUpdatedFor('tesla.order', 'vin.decode', 'us.nhtsa_vin', 'tesla.portal'))}</div>
            </div>
          )}
          {sourceHealth && (
            <div className="tesla-card" style={{ padding: '12px 14px', cursor: 'pointer' }} onClick={() => history.push('/info')}>
              <div className="text-secondary mb-sm" style={{ fontSize: 10 }}>Source Health</div>
              <div className="text-base fw-semi mb-xs" style={{ color: '#fff' }}>{sourceHealth.summary}</div>
              <div style={{ fontSize: 10, color: statusColor(sourceHealth.health?.status) }}>
                {sourceHealth.state?.ok_sources}/{sourceHealth.state?.total_sources} healthy · updated {timeAgo(missionControl.data?.executive?.last_successful_refresh)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Pico y Placa ── */}
      {picoYPlaca && picoYPlaca.placa && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', marginBottom: 10,
          borderRadius: 10, border: `1px solid ${picoYPlaca.restringido ? 'rgba(255,107,107,0.2)' : 'rgba(11,232,129,0.15)'}`,
          background: picoYPlaca.restringido ? 'rgba(255,107,107,0.06)' : 'rgba(11,232,129,0.04)',
        }}>
          <span style={{ fontSize: 18 }}>{picoYPlaca.restringido ? '🚫' : '✅'}</span>
          <div>
            <div className="text-base fw-semi" style={{ color: picoYPlaca.restringido ? '#FF6B6B' : '#0BE881' }}>
              {picoYPlaca.restringido ? 'Pico y Placa hoy — No puedes circular' : 'Sin restricción hoy'}
            </div>
            <div className="text-secondary text-xs">
              {picoYPlaca.motivo || `Placa ${picoYPlaca.placa} · ${picoYPlaca.ciudad || ''}`}
            </div>
          </div>
        </div>
      )}

      {/* ── SIMIT — Infracciones ── */}
      {simit?.data && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', marginBottom: 10,
          borderRadius: 10,
          border: `1px solid ${simit.data.paz_y_salvo ? 'rgba(11,232,129,0.15)' : 'rgba(255,107,107,0.2)'}`,
          background: simit.data.paz_y_salvo ? 'rgba(11,232,129,0.04)' : 'rgba(255,107,107,0.06)',
        }}>
          <span style={{ fontSize: 18 }}>{simit.data.paz_y_salvo ? '✅' : '⚠️'}</span>
          <div>
            <div className="text-base fw-semi" style={{ color: simit.data.paz_y_salvo ? '#0BE881' : '#FF6B6B' }}>
              {simit.data.paz_y_salvo ? 'SIMIT — Paz y Salvo' : `SIMIT — ${simit.data.comparendos || 0} comparendos`}
            </div>
            <div className="text-secondary text-xs">
              {simit.data.paz_y_salvo
                ? 'Sin multas ni comparendos pendientes'
                : `Multas: ${simit.data.multas || 0} · Deuda: $${(simit.data.total_deuda || 0).toLocaleString()}`
              }
            </div>
          </div>
        </div>
      )}

      {/* ── Documents — SOAT + RTM ── */}
      {runt && (() => {
        const soatExp = runt?.data?.soat_vencimiento || sourceMap['co.runt_soat']?.data?.vencimiento || '';
        const rtmExp = runt?.data?.tecnomecanica_vencimiento || sourceMap['co.runt_rtm']?.data?.vencimiento || '';
        const daysUntil = (dateStr: string) => {
          if (!dateStr) return null;
          const d = new Date(dateStr);
          if (isNaN(d.getTime())) return null;
          return Math.ceil((d.getTime() - Date.now()) / 86400000);
        };
        const soatDays = daysUntil(soatExp);
        const rtmDays = daysUntil(rtmExp);
        const urgentColor = (days: number | null) => days === null ? '#86888f' : days < 0 ? '#FF6B6B' : days < 30 ? '#F99716' : '#0BE881';
        const urgentLabel = (days: number | null) => days === null ? 'No data' : days < 0 ? 'Expired' : days < 30 ? `${days}d` : `${days}d`;

        return (
          <div className="grid-2" style={{ gap: 8, marginBottom: 10 }}>
            <div style={{
              padding: '10px 12px', borderRadius: 10,
              background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
            }}>
              <div className="text-secondary mb-xs" style={{ fontSize: 10 }}>SOAT</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: urgentColor(soatDays) }}>
                {urgentLabel(soatDays)}
              </div>
              {soatExp && <div className="text-secondary" style={{ fontSize: 9 }}>Vence: {soatExp}</div>}
            </div>
            <div style={{
              padding: '10px 12px', borderRadius: 10,
              background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)',
            }}>
              <div className="text-secondary mb-xs" style={{ fontSize: 10 }}>Técnico-Mecánica</div>
              <div style={{ fontSize: 16, fontWeight: 700, color: urgentColor(rtmDays) }}>
                {urgentLabel(rtmDays)}
              </div>
              {rtmExp && <div className="text-secondary" style={{ fontSize: 9 }}>Vence: {rtmExp}</div>}
            </div>
          </div>
        );
      })()}

      {/* ── Checklist summary ── */}
      {(delivery || legal) && (
        <div className="flex-center" style={{ flexWrap: 'wrap', gap: 4, marginBottom: 12 }}>
          {[
            { flag: delivery?.derived_flags?.vin_assigned, label: 'VIN' },
            { flag: sourceMap['intl.ship_tracking']?.data, label: 'Enviado' },
            { flag: legal?.derived_flags?.runt_registered, label: 'RUNT' },
            { flag: legal?.derived_flags?.plate_assigned, label: 'Placa' },
            { flag: legal?.derived_flags?.has_soat, label: 'SOAT' },
            { flag: legal?.derived_flags?.has_rtm, label: 'RTM' },
            { flag: delivery?.derived_flags?.delivery_scheduled, label: 'Cita' },
          ].filter(f => f.flag != null).map(f => (
            <span key={f.label} style={{
              fontSize: 9, fontWeight: 600, padding: '2px 7px', borderRadius: 100,
              background: f.flag ? 'rgba(11,232,129,0.1)' : 'rgba(255,255,255,0.03)',
              color: f.flag ? '#0BE881' : 'rgba(255,255,255,0.2)',
              border: `1px solid ${f.flag ? 'rgba(11,232,129,0.15)' : 'rgba(255,255,255,0.05)'}`,
            }}>{f.flag ? '✓' : '○'} {f.label}</span>
          ))}
        </div>
      )}

      {/* ── Order Summary (slim) ── */}
      <div
        className="tesla-card"
        style={{ padding: 14, marginBottom: 12, cursor: 'pointer' }}
        onClick={() => history.push('/order')}
      >
        <div className="flex-between">
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="text-secondary mb-xs" style={{ fontSize: 10 }}>Order Status</div>
            <div className="flex-start gap-sm">
              <span style={{
                fontSize: 11, fontWeight: 700, color: phaseColor,
                background: `${phaseColor}18`, padding: '3px 10px', borderRadius: 100,
              }}>
                {phaseLabels[phase] || phase}
              </span>
              <span className="text-secondary text-sm">{orderStatus}</span>
            </div>
            {delivery?.state?.delivery_date && (
              <div className="text-accent fw-semi" style={{ fontSize: 12, marginTop: 6 }}>
                Delivery: {delivery.state.delivery_date}
              </div>
            )}
            {!delivery?.state?.delivery_date && delivery?.state?.estimated_delivery && (
              <div style={{ color: '#F99716', fontSize: 12, marginTop: 6 }}>
                Window: {delivery.state.estimated_delivery}
              </div>
            )}
          </div>
          <div className="text-secondary" style={{ fontSize: 20, paddingLeft: 8 }}>›</div>
        </div>
      </div>

      {/* ── CTA: View full order ── */}
      <button
        onClick={() => history.push('/order')}
        className="tesla-btn"
        style={{ width: '100%', fontSize: 14, padding: '14px 20px', borderRadius: 12, marginBottom: 8 }}
      >
        View Full Order →
      </button>

      {/* ── Active Alerts ── */}
      {activeAlerts.length > 0 && (
        <div className="tesla-card" style={{ padding: '14px 16px', marginBottom: 12, cursor: 'pointer' }} onClick={() => history.push('/alerts')}>
          <div className="uppercase fw-bold mb-md" style={{ fontSize: 11, letterSpacing: '0.08em', color: '#FF6B6B' }}>
            Active Alerts
          </div>
          <div className="flex-col gap-sm">
            {activeAlerts.slice(0, 4).map((alert) => (
              <div key={alert.alert_id} style={{ padding: '10px 12px', borderRadius: 10, background: 'rgba(255,107,107,0.06)', border: '1px solid rgba(255,107,107,0.18)' }}>
                <div className="flex-between gap-sm mb-xs">
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#FF6B6B' }}>{alert.title}</span>
                  <span className="text-secondary text-xs">{alert.severity}</span>
                </div>
                <div style={{ fontSize: 11, color: '#f5f5f7' }}>{alert.message}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Timeline ── */}
      {timeline.length > 0 && (
        <div className="tesla-card" style={{ padding: '14px 16px', marginBottom: 12, cursor: 'pointer' }} onClick={() => history.push('/timeline')}>
          <div className="uppercase fw-bold mb-md" style={{ fontSize: 11, letterSpacing: '0.08em', color: '#86888f' }}>
            Timeline
          </div>
          <div className="flex-col gap-md">
            {timeline.slice(0, 5).map((event, index) => (
              <div key={`${event.kind}-${event.timestamp}-${index}`} className="flex-start gap-md" style={{ alignItems: 'flex-start' }}>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: event.kind === 'domain_change' ? '#0FBCF9' : event.kind === 'source_change' ? '#F99716' : '#86888f', marginTop: 5, flexShrink: 0 }} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: '#fff', fontWeight: 600 }}>{event.title}</div>
                  <div className="text-secondary" style={{ fontSize: 11 }}>{event.message}</div>
                  {event.timestamp && <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', marginTop: 2 }}>{new Date(event.timestamp).toLocaleString()}</div>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Last updated */}
      {missionControl.data?.executive?.last_successful_refresh && (
        <div style={{ textAlign: 'center', fontSize: 10, color: 'rgba(255,255,255,0.2)', paddingBottom: 8 }}>
          Actualizado: {new Date(missionControl.data.executive.last_successful_refresh).toLocaleString()}
        </div>
      )}
    </div>
  );
}

const TeslaIcon = () => (
  <svg width={48} height={48} viewBox="0 0 24 24" fill="#05C46B">
    <path d="M12 3l-4 5h3v5H7l5 8 5-8h-4V8h3z"/>
  </svg>
);

const Dashboard: React.FC = () => {
  const { state, charge, climate, loading, error, refresh, lastUpdated, connected, stale } = useVehicleData();
  const appInit = useAppInit();
  // Post-delivery: vehicle data is available (charge_state present)
  const isPostDelivery = charge !== null || state !== null;
  const missionControl = useMissionControl(!isPostDelivery);
  const { tiles: enabledTiles } = useDashboardTiles();
  const isTileEnabled = (id: string) => enabledTiles.some((t) => t.id === id);
  const [cmdLoading, setCmdLoading] = useState<string | null>(null);
  const [cmdError, setCmdError] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(false);
  const [fleetData, setFleetData] = useState<FleetVehicle[]>([]);
  const [fleetLoading, setFleetLoading] = useState(false);
  const [loginMfa, setLoginMfa] = useState('');
  const [loginError, setLoginError] = useState('');
  const [autoStatus, setAutoStatus] = useState<AutomationsStatus | null>(null);
  const history = useHistory();

  // Derive auth and automations from init bundle (no separate requests)
  const authChecked = !appInit.loading;
  const [authOverride, setAuthOverride] = useState<boolean | null>(null);
  const authenticated = authOverride ?? appInit.auth?.authenticated ?? true;

  React.useEffect(() => {
    if (appInit.automations) {
      setAutoStatus(appInit.automations as AutomationsStatus);
    }
  }, [appInit.automations]);

  // Fetch fleet summary once on mount (not in init bundle — it's slow and calls Tesla API)
  React.useEffect(() => {
    api.getFleetSummary().then(data => {
      setFleetData(data);
    }).catch(() => {
      setFleetData([]);
    });
  }, []);

  const doLogin = async () => {
    setAuthLoading(true);
    setLoginError('');
    try {
      const result = await api.browserLogin(undefined, undefined, loginMfa || undefined);
      if (result.ok) {
        setAuthOverride(true);
        refresh();
      } else {
        setLoginError(result.error || 'Login failed');
      }
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e.message || 'Login failed';
      setLoginError(msg);
    } finally {
      setAuthLoading(false);
    }
  };

  const handleCommand = async (command: string, params?: Record<string, unknown>, label?: string) => {
    const k = label || command;
    setCmdLoading(k);
    setCmdError(null);
    try {
      await api.sendCommand({ command, params });
      setTimeout(refresh, 1500);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Command failed';
      setCmdError(msg);
    } finally {
      setCmdLoading(null);
    }
  };

  const handleWake = async () => {
    setCmdLoading('wake');
    try {
      await api.wakeVehicle();
      setTimeout(refresh, 3000);
    } catch {
      // silently fail
    } finally {
      setCmdLoading(null);
    }
  };

  const doRefresh = async (event: CustomEvent) => {
    if (isPostDelivery) {
      refresh();
    } else {
      await missionControl.refresh();
    }
    await new Promise<void>((r) => setTimeout(r, 1000));
    (event.target as HTMLIonRefresherElement).complete();
  };

  const batteryPct = state?.battery_level ?? charge?.battery_level;
  const isLocked = state?.locked ?? true;
  const sentryOn = state?.sentry_mode ?? false;
  const vehicleState = state?.state;
  const isCharging = state?.charging_state === 'Charging' || charge?.charging_state === 'Charging';
  const climateOn = state?.is_climate_on ?? climate?.is_climate_on ?? false;
  const displayName = state?.display_name || 'Model Y';
  const range = state?.battery_range;
  const insideTemp = state?.inside_temp ?? climate?.inside_temp;
  const outsideTemp = state?.outside_temp ?? climate?.outside_temp;
  const isAsleep = vehicleState === 'asleep' || vehicleState === 'sleeping';

  // Ready-to-drive assessment (mirrors tesla vehicle ready logic)
  const readyIssues: string[] = [];
  if (batteryPct != null && batteryPct < 20) readyIssues.push('Low battery');
  if (isCharging) readyIssues.push('Still charging');
  if (!isLocked) readyIssues.push('Unlocked');
  if (outsideTemp != null && outsideTemp < 5 && !climateOn) readyIssues.push('Cold outside');
  const isReady = !isAsleep && readyIssues.length === 0 && batteryPct != null;

  const batteryColor =
    batteryPct == null ? '#86888f'
    : batteryPct > 50 ? '#0BE881'
    : batteryPct > 20 ? '#F99716'
    : '#FF6B6B';

  const actions = [
    {
      key: 'lock',
      icon: isLocked ? <LockIcon /> : <UnlockIcon />,
      label: isLocked ? 'Unlock' : 'Lock',
      cmd: isLocked ? 'door_unlock' : 'door_lock',
      iconBg: isLocked ? 'rgba(255,255,255,0.1)' : '#05C46B',
    },
    {
      key: 'climate',
      icon: <AcIcon />,
      label: climateOn ? 'AC Off' : 'AC On',
      cmd: climateOn ? 'auto_conditioning_stop' : 'auto_conditioning_start',
      iconBg: climateOn ? 'rgba(15,188,249,0.85)' : 'rgba(255,255,255,0.1)',
    },
    {
      key: 'flash',
      icon: <FlashLightsIcon />,
      label: 'Flash',
      cmd: 'flash_lights',
      iconBg: 'rgba(249,151,22,0.7)',
    },
    {
      key: 'sentry',
      icon: <span style={{ fontSize: 18 }}>{sentryOn ? '🛡' : '🛡'}</span>,
      label: sentryOn ? 'Sentry Off' : 'Sentry On',
      cmd: 'set_sentry_mode',
      cmdParams: { on: !sentryOn },
      iconBg: sentryOn ? 'rgba(5,196,107,0.7)' : 'rgba(255,255,255,0.1)',
    },
    {
      key: 'trunk',
      icon: <span style={{ fontSize: 18 }}>🚗</span>,
      label: 'Trunk',
      cmd: 'actuate_trunk',
      cmdParams: { which_trunk: 'rear' },
      iconBg: 'rgba(255,255,255,0.1)',
    },
  ];

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700, letterSpacing: '-0.3px' }}>
            {displayName}
          </IonTitle>
          <div slot="end" className="flex-center gap-sm" style={{ paddingRight: 4 }}>
            <span
              title={connected ? 'SSE connected' : 'SSE disconnected'}
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: connected ? '#0BE881' : '#86888f',
                display: 'inline-block',
                flexShrink: 0,
              }}
            />
            {!loading && state && !isAsleep && (
              <span style={{
                fontSize: 10,
                fontWeight: 700,
                padding: '2px 8px',
                borderRadius: 10,
                background: isReady ? 'rgba(11,232,129,0.15)' : 'rgba(249,151,22,0.15)',
                color: isReady ? '#0BE881' : '#F99716',
              }}>
                {isReady ? '✓ Ready' : `⚠ ${readyIssues.length}`}
              </span>
            )}
            {loading && !state ? (
              <IonSpinner name="dots" style={{ '--color': '#86888f', width: 20, height: 20 } as React.CSSProperties} />
            ) : (
              <StatusBadge state={vehicleState} />
            )}
          </div>
        </IonToolbar>
      </IonHeader>

      <IonContent>
        <IonRefresher slot="fixed" onIonRefresh={doRefresh}>
          <IonRefresherContent />
        </IonRefresher>

        {stale && (
          <div style={{ background: '#F99716', color: '#000', padding: '8px 16px', textAlign: 'center', fontSize: 13 }}>
            Showing cached data. Server connection lost.
          </div>
        )}

        {/* ---- Onboarding: not authenticated ---- */}
        {authChecked && !authenticated ? (
          <div className="empty-state" style={{ minHeight: 'calc(100vh - 56px)', justifyContent: 'center' }}>
            <div className="flex-center" style={{ width: 80, height: 80, borderRadius: '50%', background: 'rgba(5,196,107,0.12)', marginBottom: 20 }}>
              <TeslaIcon />
            </div>
            <div style={{ color: '#ffffff', fontWeight: 700, fontSize: 22, letterSpacing: '-0.5px' }}>Welcome to Tesla Control</div>
            <div className="text-secondary" style={{ fontSize: 14, lineHeight: 1.6, maxWidth: 280, textAlign: 'center', margin: '8px 0 24px' }}>
              Connect your Tesla account to monitor your vehicle, track deliveries, and access all features.
            </div>

            <div style={{ width: '100%', maxWidth: 320 }}>
              <input
                type="text"
                value={loginMfa}
                onChange={(e) => setLoginMfa(e.target.value)}
                placeholder="Optional MFA code"
                className="tesla-input"
                style={{ marginBottom: 8, fontSize: 14, textAlign: 'center', letterSpacing: '0.1em' }}
                autoFocus
                onKeyDown={(e) => e.key === 'Enter' && doLogin()}
              />
              {loginError && (
                <div style={{ color: '#FF6B6B', fontSize: 12, marginBottom: 8, textAlign: 'center' }}>{loginError}</div>
              )}
              <button
                onClick={doLogin}
                disabled={authLoading}
                className="tesla-btn"
                style={{ width: '100%', fontSize: 16, padding: '14px 24px', borderRadius: 12 }}
              >
                {authLoading ? 'Waiting for Tesla login…' : 'Open Tesla Login'}
              </button>
            </div>

            <div className="text-secondary text-xs" style={{ marginTop: 24, opacity: 0.5 }}>
              Tesla auth opens in a visible browser. Complete login, MFA, or captcha there; only tokens and portal session state are captured.
            </div>
          </div>
        ) : !isPostDelivery && error ? (
          /* ---- PRE-DELIVERY DASHBOARD ---- */
          <PreDeliveryDashboard missionControl={missionControl} loading={missionControl.loading} />
        ) : (
          <div className="page-pad">
            {/* ---- Car silhouette card (always visible) ---- */}
            <div className="tesla-card" style={{ padding: '8px 4px 4px' }}>
              <ModelYSilhouette
                locked={isLocked}
                chargingState={state?.charging_state || charge?.charging_state}
                batteryPercent={batteryPct}
                climateOn={climateOn}
              />
            </div>

            {/* ---- Hero stats row (battery tile) ---- */}
            {isTileEnabled('battery') && <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 10 }}>
              {/* Battery */}
              <div className="tesla-card" style={{ textAlign: 'center', padding: '16px 4px' }}>
                <div style={{ fontSize: 44, fontWeight: 700, color: batteryColor, lineHeight: 1, letterSpacing: '-2px', fontVariantNumeric: 'tabular-nums' }}>
                  {batteryPct ?? '--'}
                </div>
                <div style={{ color: '#f5f5f7', fontSize: 11, fontWeight: 600, marginTop: 2 }}>%</div>
                <div className="text-secondary" style={{ fontSize: 10, marginTop: 3 }}>
                  {range ? `${Math.round(range)} mi` : 'Battery'}
                </div>
              </div>

              {/* Inside temp */}
              <div className="tesla-card" style={{ textAlign: 'center', padding: '16px 4px' }}>
                <div style={{ fontSize: 44, fontWeight: 700, color: climateOn ? '#0FBCF9' : '#86888f', lineHeight: 1, letterSpacing: '-2px', fontVariantNumeric: 'tabular-nums' }}>
                  {insideTemp != null ? Math.round(insideTemp) : '--'}
                </div>
                <div style={{ color: climateOn ? '#0FBCF9' : '#f5f5f7', fontSize: 11, fontWeight: 600, marginTop: 2 }}>°C</div>
                <div className="text-secondary" style={{ fontSize: 10, marginTop: 3 }}>
                  {outsideTemp != null ? `Out ${Math.round(outsideTemp)}°` : 'Interior'}
                </div>
              </div>

              {/* Charge power */}
              <div className="tesla-card" style={{ textAlign: 'center', padding: '16px 4px' }}>
                <div style={{ fontSize: 44, fontWeight: 700, color: isCharging ? '#0BE881' : '#86888f', lineHeight: 1, letterSpacing: '-2px', fontVariantNumeric: 'tabular-nums' }}>
                  {isCharging ? (state?.charger_power ?? charge?.charger_power ?? 0) : '--'}
                </div>
                <div style={{ color: isCharging ? '#0BE881' : '#f5f5f7', fontSize: 11, fontWeight: 600, marginTop: 2 }}>
                  {isCharging ? 'kW' : '···'}
                </div>
                <div className="text-secondary" style={{ fontSize: 10, marginTop: 3 }}>
                  {isCharging ? `${state?.minutes_to_full_charge ?? charge?.minutes_to_full_charge ?? 0}m left` : 'Charging'}
                </div>
              </div>
            </div>}

            {/* ---- Quick actions ---- */}
            {isTileEnabled('quickActions') && (
              <>
                <p className="section-title">Quick Actions</p>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 10 }}>
                  {actions.map((a) => (
                    <button
                      key={a.key}
                      onClick={() => handleCommand(a.cmd, (a as any).cmdParams, a.key)}
                      disabled={!!cmdLoading}
                      style={{
                        background: 'rgba(255,255,255,0.04)',
                        border: `1px solid rgba(255,255,255,0.07)`,
                        borderRadius: 14,
                        padding: '14px 4px',
                        cursor: cmdLoading === a.key ? 'not-allowed' : 'pointer',
                        display: 'flex',
                        flexDirection: 'column' as const,
                        alignItems: 'center',
                        gap: 7,
                        opacity: cmdLoading && cmdLoading !== a.key ? 0.4 : 1,
                        transition: 'all 0.15s',
                        fontFamily: 'inherit',
                      }}
                    >
                      <div
                        style={{
                          width: 40,
                          height: 40,
                          borderRadius: '50%',
                          background: a.iconBg,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: '#ffffff',
                          boxShadow: a.key === 'climate' && climateOn ? '0 0 14px rgba(15,188,249,0.5)' : a.key === 'lock' && !isLocked ? '0 0 14px rgba(5,196,107,0.5)' : 'none',
                        }}
                      >
                        {cmdLoading === a.key ? <Spinner size={18} color="#fff" /> : a.icon}
                      </div>
                      <span style={{ color: '#f5f5f7', fontSize: 10, fontWeight: 600, textAlign: 'center' }}>
                        {a.label}
                      </span>
                    </button>
                  ))}
                </div>
              </>
            )}

            {/* ---- Wake button if asleep (always visible) ---- */}
            {isAsleep && (
              <button
                onClick={handleWake}
                disabled={cmdLoading === 'wake'}
                className="tesla-btn"
                style={{ marginBottom: 10 }}
              >
                {cmdLoading === 'wake' ? <Spinner size={18} color="#fff" /> : <WakeIcon />}
                {cmdLoading === 'wake' ? 'Waking...' : 'Wake Vehicle'}
              </button>
            )}

            {/* ---- Charging progress card (schedule tile) ---- */}
            {isTileEnabled('schedule') && isCharging && (
              <div className="tesla-card">
                <div className="flex-between mb-sm">
                  <div className="flex-start gap-sm fw-semi text-lg" style={{ color: '#0BE881' }}>
                    <BoltIcon />
                    Charging
                  </div>
                  <span className="text-secondary" style={{ fontSize: 12 }}>
                    Limit: {state?.charge_limit_soc ?? charge?.charge_limit_soc ?? '--'}%
                  </span>
                </div>
                {/* Progress bar */}
                <div className="progress-track mb-sm">
                  <div
                    className="progress-fill charging"
                    style={{ width: `${batteryPct ?? 0}%` }}
                  />
                </div>
                <div className="flex-between" style={{ fontSize: 12 }}>
                  <span className="text-secondary">
                    {state?.charger_power ?? charge?.charger_power ?? 0} kW
                  </span>
                  <span className="text-secondary">
                    +{(state?.charge_energy_added ?? charge?.charge_energy_added ?? 0).toFixed(1)} kWh added
                  </span>
                  <span style={{ color: '#0BE881' }}>
                    {state?.minutes_to_full_charge ?? charge?.minutes_to_full_charge ?? 0}m left
                  </span>
                </div>
              </div>
            )}

            {/* ---- Recent Charges ---- */}
            {isTileEnabled('recentCharges') && <RecentCharges />}

            {/* ---- Vehicle info footer (vehicle tile) ---- */}
            {isTileEnabled('vehicle') && state && !isAsleep && (
              <div className="flex-center gap-lg" style={{ padding: '8px 0', fontSize: 11, color: '#86888f' }}>
                {state.car_version && (
                  <span>🚗 {state.car_version}</span>
                )}
                <span>{sentryOn ? '🛡 Sentry' : ''}</span>
                {state.odometer && (
                  <span>📏 {Math.round((state.odometer as number) * 1.60934).toLocaleString()} km</span>
                )}
              </div>
            )}

            {/* ---- Fleet health tile (only shown when >1 vehicle) ---- */}
            {isTileEnabled('fleet') && fleetData.length > 1 && (
              <>
                <p className="section-title">Fleet Health</p>
                <div className="tesla-card p-md mb-sm">
                  {fleetLoading ? (
                    <div style={{ textAlign: 'center', padding: 12 }}>
                      <IonSpinner name="dots" style={{ '--color': '#86888f' } as React.CSSProperties} />
                    </div>
                  ) : (
                    <div className="flex-col gap-sm">
                      {fleetData.map(v => {
                        const battColor = v.battery_level == null ? '#86888f'
                          : v.battery_level > 50 ? '#0BE881'
                          : v.battery_level > 20 ? '#F99716'
                          : '#FF6B6B';
                        return (
                          <div key={v.vin} className="flex-between" style={{
                            padding: '8px 10px',
                            borderRadius: 8,
                            background: 'rgba(255,255,255,0.03)',
                            border: '1px solid rgba(255,255,255,0.06)',
                          }}>
                            <div className="flex-col" style={{ gap: 2 }}>
                              <span style={{ fontSize: 13, fontWeight: 600, color: '#f5f5f7' }}>
                                {v.alias}
                              </span>
                              <span className="text-secondary text-xs">
                                ...{v.vin.slice(-6)}
                              </span>
                            </div>
                            <div className="flex-start gap-md">
                              {v.battery_level != null && (
                                <span style={{ fontSize: 13, fontWeight: 700, color: battColor }}>
                                  {v.battery_level}%
                                </span>
                              )}
                              {v.charging_state === 'Charging' && (
                                <span style={{ fontSize: 10, color: '#0BE881' }}>⚡</span>
                              )}
                              <span style={{ fontSize: 11, color: v.locked ? '#86888f' : '#F99716' }}>
                                {v.locked == null ? '—' : v.locked ? '🔒' : '🔓'}
                              </span>
                              {v.sentry && (
                                <span style={{ fontSize: 11, color: '#0FBCF9' }}>🛡</span>
                              )}
                              {v.error && (
                                <span style={{ fontSize: 10, color: '#FF6B6B' }} title={v.error}>⚠</span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </>
            )}

            {/* ---- Automation status indicator ---- */}
            {autoStatus && autoStatus.enabled > 0 && (
              <div
                className="tesla-card flex-start gap-sm"
                style={{ padding: '10px 14px', marginBottom: 8, cursor: 'pointer' }}
                onClick={() => history.push('/automations')}
              >
                <span style={{ fontSize: 16 }}>⚡</span>
                <div className="flex-1">
                  <span className="text-accent fw-semi text-base">
                    {autoStatus.enabled} automation rule{autoStatus.enabled !== 1 ? 's' : ''} active
                  </span>
                  {autoStatus.total > autoStatus.enabled && (
                    <span className="text-secondary text-sm" style={{ marginLeft: 6 }}>
                      ({autoStatus.total - autoStatus.enabled} disabled)
                    </span>
                  )}
                </div>
                <span className="text-secondary" style={{ fontSize: 16 }}>›</span>
              </div>
            )}

            {/* ---- Last updated ---- */}
            {lastUpdated && (
              <div style={{ textAlign: 'center', paddingTop: 8 }}>
                <span className="text-secondary text-sm" style={{ opacity: 0.7 }}>
                  Updated {lastUpdated.toLocaleTimeString()}
                </span>
              </div>
            )}
          </div>
        )}
      </IonContent>

      <IonToast
        isOpen={!!cmdError}
        message={cmdError ?? ''}
        duration={3000}
        color="danger"
        onDidDismiss={() => setCmdError(null)}
        position="bottom"
      />
    </IonPage>
  );
};

export default Dashboard;
