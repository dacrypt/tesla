import React from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonRefresher,
  IonRefresherContent,
  IonSpinner,
  IonTitle,
  IonToolbar,
} from '@ionic/react';
import { AlertEvent, api } from '../api/client';

const severityColor = (severity: string) =>
  severity === 'critical' ? '#FF6B6B' : severity === 'high' ? '#F99716' : severity === 'warning' ? '#FFD166' : '#0FBCF9';

const Alerts: React.FC = () => {
  const [alerts, setAlerts] = React.useState<AlertEvent[]>([]);
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getAlerts(50, false);
      setAlerts(data);
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
  }, [load]);

  const doRefresh = async (event: CustomEvent) => {
    await load();
    (event.target as HTMLIonRefresherElement).complete();
  };

  const ack = async (alertId: string) => {
    await api.ackAlert(alertId);
    await load();
  };

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700 }}>Alerts</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent>
        <IonRefresher slot="fixed" onIonRefresh={doRefresh}>
          <IonRefresherContent />
        </IonRefresher>
        <div className="page-pad">
          {loading ? (
            <div className="loading-center">
              <IonSpinner name="dots" style={{ '--color': '#05C46B' } as React.CSSProperties} />
            </div>
          ) : alerts.length === 0 ? (
            <div className="tesla-card" style={{ padding: 16, textAlign: 'center', color: '#86888f' }}>
              No alerts yet
            </div>
          ) : (
            alerts.map((alert) => (
              <div key={alert.alert_id} className="tesla-card" style={{ padding: 14, marginBottom: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginBottom: 6 }}>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: severityColor(alert.severity) }}>{alert.title}</div>
                    <div style={{ fontSize: 10, color: '#86888f' }}>{new Date(alert.created_at).toLocaleString()}</div>
                  </div>
                  <div style={{ fontSize: 10, color: '#86888f', textTransform: 'uppercase' }}>{alert.severity}</div>
                </div>
                <div style={{ fontSize: 12, color: '#f5f5f7', marginBottom: 10 }}>{alert.message}</div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                  <div style={{ fontSize: 10, color: '#86888f' }}>
                    {alert.resolved_at ? 'Resolved' : alert.acked_at ? 'Acknowledged' : 'Active'}
                  </div>
                  {!alert.resolved_at && !alert.acked_at && (
                    <button className="tesla-btn" style={{ padding: '8px 14px', fontSize: 12 }} onClick={() => ack(alert.alert_id)}>
                      Acknowledge
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      </IonContent>
    </IonPage>
  );
};

export default Alerts;
