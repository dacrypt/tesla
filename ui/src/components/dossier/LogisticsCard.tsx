import React from 'react';
import { DossierLogistics } from '../../api/client';

interface Props {
  logistics?: DossierLogistics;
}

export default function LogisticsCard({ logistics }: Props) {
  if (!logistics) return null;

  const ship = logistics.ship;
  const hasShip = ship && ship.vessel_name;

  const steps = [
    { label: logistics.factory || 'Factory', done: true },
    { label: logistics.departure_port || 'Departure', done: true },
    { label: hasShip ? ship!.vessel_name : 'In Transit', done: !!hasShip },
    { label: logistics.arrival_port || 'Arrival', done: !!logistics.customs_status },
    { label: 'Customs', done: logistics.customs_status === 'cleared' },
    { label: 'Delivery', done: logistics.last_mile_status === 'delivered' },
  ];

  return (
    <>
      {/* Mini pipeline */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 0, marginBottom: 16, overflowX: 'auto', paddingBottom: 4 }}>
        {steps.map((s, i) => (
          <React.Fragment key={s.label}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, minWidth: 52 }}>
              <div style={{
                width: 16, height: 16, borderRadius: '50%',
                background: s.done ? 'var(--tesla-green)' : 'var(--tesla-card-secondary)',
                border: `2px solid ${s.done ? 'var(--tesla-green)' : 'var(--tesla-border)'}`,
                fontSize: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: s.done ? '#000' : 'var(--tesla-text-secondary)', fontWeight: 700,
              }}>
                {s.done ? '\u2713' : ''}
              </div>
              <span style={{ fontSize: 7, fontWeight: 600, color: s.done ? 'var(--tesla-text)' : 'var(--tesla-text-secondary)', textAlign: 'center', textTransform: 'uppercase', letterSpacing: '0.03em', lineHeight: 1.2, maxWidth: 56, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                {s.label}
              </span>
            </div>
            {i < steps.length - 1 && (
              <div style={{ flex: 1, height: 2, background: s.done ? 'var(--tesla-green)' : 'var(--tesla-border)', minWidth: 8, marginTop: -14 }} />
            )}
          </React.Fragment>
        ))}
      </div>

      {/* Ship details */}
      {hasShip && (
        <>
          <div className="stat-row">
            <span style={{ color: 'var(--tesla-text-secondary)', fontSize: 12 }}>Vessel</span>
            <span style={{ color: 'var(--tesla-text)', fontSize: 12, fontWeight: 600 }}>{ship!.vessel_name}</span>
          </div>
          {ship!.imo && (
            <div className="stat-row">
              <span style={{ color: 'var(--tesla-text-secondary)', fontSize: 12 }}>IMO</span>
              <span style={{ color: 'var(--tesla-text)', fontSize: 12, fontFamily: "'SF Mono', monospace" }}>{ship!.imo}</span>
            </div>
          )}
          {ship!.eta && (
            <div className="stat-row">
              <span style={{ color: 'var(--tesla-text-secondary)', fontSize: 12 }}>ETA</span>
              <span style={{ color: 'var(--tesla-blue)', fontSize: 12, fontWeight: 600 }}>{ship!.eta}</span>
            </div>
          )}
          {ship?.current_position?.speed_knots != null && ship.current_position.speed_knots > 0 && (
            <div className="stat-row">
              <span style={{ color: 'var(--tesla-text-secondary)', fontSize: 12 }}>Speed</span>
              <span style={{ color: 'var(--tesla-text)', fontSize: 12 }}>{ship.current_position.speed_knots.toFixed(1)} knots</span>
            </div>
          )}
          {ship!.tracking_url && (
            <a href={ship!.tracking_url} target="_blank" rel="noopener noreferrer" style={{
              display: 'block', textAlign: 'center', color: 'var(--tesla-blue)', fontSize: 12,
              marginTop: 10, textDecoration: 'none',
            }}>
              Track on MarineTraffic &rarr;
            </a>
          )}
        </>
      )}

      {/* Other details */}
      {(logistics.estimated_transit_days ?? 0) > 0 && (
        <div className="stat-row">
          <span style={{ color: 'var(--tesla-text-secondary)', fontSize: 12 }}>Transit Days</span>
          <span style={{ color: 'var(--tesla-text)', fontSize: 12, fontWeight: 500 }}>{logistics.estimated_transit_days}</span>
        </div>
      )}
      {logistics.customs_status && (
        <div className="stat-row">
          <span style={{ color: 'var(--tesla-text-secondary)', fontSize: 12 }}>Customs</span>
          <span style={{ color: 'var(--tesla-text)', fontSize: 12, fontWeight: 500, textTransform: 'capitalize' }}>{logistics.customs_status}</span>
        </div>
      )}
    </>
  );
}
