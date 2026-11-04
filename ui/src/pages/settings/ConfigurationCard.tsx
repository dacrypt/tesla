import React from 'react';
import { TeslaConfig } from '../../api/client';
import { GearIcon } from './icons';

/** Read-only view of the effective configuration (tokens masked). */
const ConfigurationCard: React.FC<{ config: TeslaConfig }> = ({ config }) => {
  return (
    <div className="tesla-card">
      <div className="flex-center gap-sm" style={{ marginBottom: 14 }}>
        <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(249,151,22,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#F99716' }}>
          <GearIcon />
        </div>
        <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Configuration</div>
      </div>
      {[
        { label: 'Backend', value: config.backend },
        { label: 'VIN', value: config.default_vin, mono: true },
        { label: 'Tessie Token', value: config.tessie_token ? '••••' + config.tessie_token.slice(-4) : 'Not set' },
        { label: 'TeslaMate URL', value: config.teslaMate_url || 'Not configured' },
      ].map((item) => (
        <div key={item.label} className="stat-row">
          <span className="label-sm">{item.label}</span>
          <span style={{ color: item.value ? '#ffffff' : '#86888f', fontSize: 12, fontFamily: (item as { mono?: boolean }).mono ? 'SF Mono, Menlo, monospace' : 'inherit', maxWidth: '55%', textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {item.value || '--'}
          </span>
        </div>
      ))}
    </div>
  );
};

export default ConfigurationCard;
