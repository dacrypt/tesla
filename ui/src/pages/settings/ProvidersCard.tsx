import React from 'react';
import { ProviderStatus } from '../../api/client';
import { PlugIcon } from './icons';

function providerColor(available: boolean): string {
  return available ? '#0BE881' : '#86888f';
}

function providerLabel(available: boolean): string {
  return available ? 'Active' : 'Unavailable';
}

/** Availability of each provider (BLE, Vehicle API, TeslaMate, ...). */
const ProvidersCard: React.FC<{ providers: ProviderStatus[] }> = ({ providers }) => {
  return (
    <div className="tesla-card">
      <div className="flex-center gap-sm" style={{ marginBottom: 14 }}>
        <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(15,188,249,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0FBCF9' }}>
          <PlugIcon />
        </div>
        <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Provider Status</div>
      </div>
      {providers.map((p, i) => {
        const color = providerColor(p.available);
        const label = providerLabel(p.available);
        return (
          <div key={i} className="stat-row" style={{ borderBottom: i < providers.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none' }}>
            <div>
              <div style={{ color: '#ffffff', fontSize: 14 }}>{p.name}</div>
              {(p.description || p.message) && <div style={{ color: '#86888f', fontSize: 11, marginTop: 2 }}>{p.description || p.message}</div>}
            </div>
            <div className="flex-center gap-xs">
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: color, boxShadow: `0 0 5px ${color}` }} />
              <span style={{ color, fontWeight: 600, fontSize: 13 }}>{label}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default ProvidersCard;
