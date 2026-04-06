import { useState, useEffect } from 'react';
import { IonCard, IonCardHeader, IonCardTitle, IonCardContent } from '@ionic/react';
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
    <IonCard>
      <IonCardHeader>
        <IonCardTitle style={{ fontSize: '1rem' }}>
          ⚡ Recent Charges
          <span style={{ float: 'right', fontSize: '0.8rem', opacity: 0.7 }}>
            {sessions[0]?.source === 'teslamate' ? 'TeslaMate' : 'Fleet API'}
          </span>
        </IonCardTitle>
      </IonCardHeader>
      <IonCardContent>
        <table style={{ width: '100%', fontSize: '0.85rem', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ opacity: 0.6, textAlign: 'left' }}>
              <th>Date</th>
              <th>Location</th>
              <th style={{ textAlign: 'right' }}>kWh</th>
              <th style={{ textAlign: 'right' }}>Cost</th>
            </tr>
          </thead>
          <tbody>
            {sessions.map((s, i) => (
              <tr key={i} style={{ borderTop: '1px solid var(--ion-color-step-100, #eee)' }}>
                <td style={{ padding: '4px 0' }}>{s.date}</td>
                <td style={{ maxWidth: 120, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {s.location || '—'}
                </td>
                <td style={{ textAlign: 'right', fontWeight: 600 }}>{s.kwh.toFixed(1)}</td>
                <td style={{ textAlign: 'right' }}>
                  {s.cost !== null ? `$${s.cost.toFixed(2)}` : '—'}
                  {s.cost_estimated && ' ~'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div style={{ marginTop: 8, fontSize: '0.8rem', opacity: 0.7 }}>
          {totalKwh.toFixed(1)} kWh total
          {totalCost > 0 && ` · $${totalCost.toFixed(2)}`}
        </div>
      </IonCardContent>
    </IonCard>
  );
}
