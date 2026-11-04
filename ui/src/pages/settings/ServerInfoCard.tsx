import React from 'react';
import { ServerStatus } from '../../api/client';
import { InfoIcon } from './icons';

/** Version / backend / VIN reported by the server. */
const ServerInfoCard: React.FC<{ status: ServerStatus }> = ({ status }) => {
  return (
    <div className="tesla-card">
      <div className="flex-center gap-sm" style={{ marginBottom: 14 }}>
        <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(11,232,129,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0BE881' }}>
          <InfoIcon />
        </div>
        <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Server Info</div>
      </div>
      {[
        { label: 'Version', value: status.version },
        { label: 'Backend', value: status.backend },
        { label: 'VIN', value: status.vin || 'Not configured', mono: true },
      ].map((item) => (
        <div key={item.label} className="stat-row">
          <span className="label-sm">{item.label}</span>
          <span style={{ color: '#ffffff', fontSize: 13, fontFamily: item.mono ? 'SF Mono, Menlo, monospace' : 'inherit', fontWeight: item.mono ? 600 : 400, letterSpacing: item.mono ? '0.05em' : 'normal' }}>
            {item.value || '--'}
          </span>
        </div>
      ))}
    </div>
  );
};

export default ServerInfoCard;
