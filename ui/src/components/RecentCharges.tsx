import { useState, useEffect } from 'react';
import { api, ChargingSession } from '../api/client';

export default function RecentCharges() {
  const [sessions, setSessions] = useState<ChargingSession[] | null>(null);

  useEffect(() => {
    api.getChargeSessions(5).then(setSessions).catch(() => setSessions(null));
  }, []);

  if (!sessions || sessions.length === 0) return null;

  const totalKwh = sessions.reduce((sum, s) => sum + s.kwh, 0);
  const totalCost = sessions
    .filter(s => s.cost !== null)
    .reduce((sum, s) => sum + (s.cost ?? 0), 0);

  return (
    <div className="tesla-card" style={{ padding: '16px 16px 12px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <span style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Recent Charges</span>
        <span style={{ fontSize: '0.75rem', color: '#86888f' }}>
          {sessions[0]?.source === 'teslamate' ? 'TeslaMate' : 'Fleet API'}
        </span>
      </div>
      <table style={{ width: '100%', fontSize: '0.85rem', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ color: '#86888f', textAlign: 'left' }}>
            <th style={{ fontWeight: 500, paddingBottom: 6 }}>Date</th>
            <th style={{ fontWeight: 500, paddingBottom: 6 }}>Location</th>
            <th style={{ fontWeight: 500, paddingBottom: 6, textAlign: 'right' }}>kWh</th>
            <th style={{ fontWeight: 500, paddingBottom: 6, textAlign: 'right' }}>Cost</th>
          </tr>
        </thead>
        <tbody>
          {sessions.map((s, i) => (
            <tr key={i} style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
              <td style={{ padding: '6px 0', color: '#e5e5e5' }}>{s.date}</td>
              <td style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#86888f' }}>
                {s.location || '—'}
              </td>
              <td style={{ textAlign: 'right', fontWeight: 600, color: '#0BE881' }}>{s.kwh.toFixed(1)}</td>
              <td style={{ textAlign: 'right', color: '#e5e5e5' }}>
                {s.cost !== null ? `$${s.cost.toFixed(2)}` : '—'}
                {s.cost_estimated && ' ~'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 10, fontSize: '0.78rem', color: '#86888f' }}>
        {totalKwh.toFixed(1)} kWh total
        {totalCost > 0 && ` · $${totalCost.toFixed(2)}`}
      </div>
    </div>
  );
}
