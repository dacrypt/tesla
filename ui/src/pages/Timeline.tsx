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
import { api, TimelineEvent } from '../api/client';

const kindColor = (kind: string) =>
  kind === 'domain_change' ? '#0FBCF9' : kind === 'source_change' ? '#F99716' : kind === 'health' ? '#FFD166' : '#86888f';

const Timeline: React.FC = () => {
  const [events, setEvents] = React.useState<TimelineEvent[]>([]);
  const [loading, setLoading] = React.useState(true);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getEvents(100);
      setEvents(data);
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

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700 }}>Timeline</IonTitle>
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
          ) : events.length === 0 ? (
            <div className="tesla-card" style={{ padding: 16, textAlign: 'center', color: '#86888f' }}>
              No events yet
            </div>
          ) : (
            <div className="tesla-card" style={{ padding: 16 }}>
              {events.map((event, index) => (
                <div key={`${event.kind}-${event.created_at || event.timestamp}-${index}`} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', paddingBottom: 12, marginBottom: 12, borderBottom: index < events.length - 1 ? '1px solid rgba(255,255,255,0.06)' : 'none' }}>
                  <div style={{ width: 8, height: 8, borderRadius: '50%', background: kindColor(event.kind), marginTop: 5, flexShrink: 0 }} />
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 700, color: '#fff' }}>{event.title}</div>
                    <div style={{ fontSize: 11, color: '#86888f', marginTop: 2 }}>{event.message}</div>
                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', marginTop: 4 }}>
                      {new Date(event.created_at || event.timestamp || Date.now()).toLocaleString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </IonContent>
    </IonPage>
  );
};

export default Timeline;
