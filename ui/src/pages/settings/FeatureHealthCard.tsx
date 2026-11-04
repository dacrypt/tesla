import React from 'react';
import { InfoIcon } from './icons';
import type { FeatureHealth } from './types';

function featureStatusColor(status: FeatureHealth['status']): string {
  if (status === 'ok') return '#0BE881';
  if (status === 'external-blocker' || status === 'failing') return '#FF6B6B';
  if (status === 'unused' || status === 'not-installed') return '#86888f';
  return '#F99716'; // missing-scope / not-configured
}

/** Per-feature availability on this install (`/api/doctor`). */
const FeatureHealthCard: React.FC<{ features: FeatureHealth[] }> = ({ features }) => {
  return (
    <div className="tesla-card">
      <div className="flex-center gap-sm" style={{ marginBottom: 14 }}>
        <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(11,232,129,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#0BE881' }}>
          <InfoIcon />
        </div>
        <div>
          <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Feature Health</div>
          <div style={{ color: '#86888f', fontSize: 12 }}>Per-feature availability on this install</div>
        </div>
      </div>
      {features.map((f, i) => {
        const color = featureStatusColor(f.status);
        return (
          <div key={f.name} className="stat-row" style={{ borderBottom: i < features.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none' }}>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="flex-center gap-xs" style={{ justifyContent: 'flex-start' }}>
                <span style={{ color: '#ffffff', fontSize: 14 }}>{f.name}</span>
                <span style={{
                  fontSize: 10, fontWeight: 600, padding: '1px 6px', borderRadius: 4,
                  background: 'rgba(255,255,255,0.06)', color: '#86888f',
                }}>{f.tier}</span>
              </div>
              {f.remediation && (
                <div title={f.remediation} style={{ color: '#86888f', fontSize: 11, marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {f.remediation}
                </div>
              )}
            </div>
            <div className="flex-center gap-xs" style={{ flexShrink: 0 }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: color, boxShadow: `0 0 5px ${color}` }} />
              <span style={{ color, fontWeight: 600, fontSize: 12 }}>{f.status}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default FeatureHealthCard;
