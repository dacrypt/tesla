import React, { useState, useEffect } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
  IonToast,
} from '@ionic/react';
import {
  api,
  AuthStatus,
  getBaseUrl,
  ProviderStatus,
  ServerStatus,
  StackStatus,
  TeslaConfig,
  VehicleInvitation,
} from '../api/client';
import Spinner from '../components/icons/Spinner';
import AboutCard from './settings/AboutCard';
import ApiConnectionCard from './settings/ApiConnectionCard';
import ConfigurationCard from './settings/ConfigurationCard';
import DashboardLayoutCard from './settings/DashboardLayoutCard';
import DoctorCard from './settings/DoctorCard';
import FeatureHealthCard from './settings/FeatureHealthCard';
import NotificationHistoryCard from './settings/NotificationHistoryCard';
import NotificationsCard from './settings/NotificationsCard';
import ProvidersCard from './settings/ProvidersCard';
import ServerInfoCard from './settings/ServerInfoCard';
import TeslaAccountCard from './settings/TeslaAccountCard';
import TeslaMateStackCard from './settings/TeslaMateStackCard';
import VehicleSharingCard from './settings/VehicleSharingCard';
import type { FeatureHealth, Notify } from './settings/types';

/**
 * Settings page. Owns the data loaded in one `fetchAll` round-trip and the
 * shared toast; each section lives in `./settings/`.
 */
const Settings: React.FC = () => {
  const [status, setStatus] = useState<ServerStatus | null>(null);
  const [config, setConfig] = useState<TeslaConfig | null>(null);
  const [providers, setProviders] = useState<ProviderStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; color: string } | null>(null);
  const [authStatus, setAuthStatus] = useState<AuthStatus | null>(null);
  const [notifyChannels, setNotifyChannels] = useState<string[]>([]);
  const [invitations, setInvitations] = useState<VehicleInvitation[]>([]);
  const [features, setFeatures] = useState<FeatureHealth[]>([]);
  const [stack, setStack] = useState<StackStatus | null>(null);

  const notify: Notify = (message, color) => setToast({ message, color });

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [s, c, p, st, au, nc, inv] = await Promise.allSettled([
        api.getStatus(), api.getConfig(), api.getProviders(), api.getStackStatus(), api.getAuthStatus(),
        api.getNotifyChannels(), api.getInvitations(),
      ]);
      if (s.status === 'fulfilled') setStatus(s.value);
      if (c.status === 'fulfilled') setConfig(c.value);
      if (p.status === 'fulfilled') setProviders(Array.isArray(p.value) ? p.value : []);
      if (st.status === 'fulfilled') setStack(st.value);
      if (au.status === 'fulfilled') setAuthStatus(au.value);
      if (nc.status === 'fulfilled') setNotifyChannels(nc.value.channels || []);
      if (inv.status === 'fulfilled') setInvitations(Array.isArray(inv.value) ? inv.value : []);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  useEffect(() => {
    const base = getBaseUrl();
    fetch(`${base}/api/doctor`, { credentials: 'include' })
      .then(r => r.ok ? r.json() : [])
      .then((data: unknown) => setFeatures(Array.isArray(data) ? (data as FeatureHealth[]) : []))
      .catch(() => setFeatures([]));
  }, []);

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700 }}>Settings</IonTitle>
        </IonToolbar>
      </IonHeader>

      <IonContent>
        <div className="page-pad">
          <ApiConnectionCard status={status} notify={notify} onUrlSaved={fetchAll} />
          <TeslaAccountCard authStatus={authStatus} notify={notify} onConnected={fetchAll} />

          {loading ? (
            <div className="loading-center"><Spinner /></div>
          ) : (
            <>
              {status && <ServerInfoCard status={status} />}
              {config && <ConfigurationCard config={config} />}
              {(stack || !loading) && (
                <TeslaMateStackCard stack={stack} onStackChange={setStack} notify={notify} />
              )}
              <DoctorCard />
              {providers.length > 0 && <ProvidersCard providers={providers} />}
              {features.length > 0 && <FeatureHealthCard features={features} />}
              <NotificationsCard
                channels={notifyChannels}
                onChannelsChange={setNotifyChannels}
                notify={notify}
              />
              <NotificationHistoryCard />
              <VehicleSharingCard
                invitations={invitations}
                onInvitationsChange={setInvitations}
                notify={notify}
              />
              <DashboardLayoutCard />
              <AboutCard />
            </>
          )}
        </div>

        <IonToast
          isOpen={!!toast}
          message={toast?.message}
          duration={3000}
          color={toast?.color}
          onDidDismiss={() => setToast(null)}
          position="bottom"
        />
      </IonContent>
    </IonPage>
  );
};

export default Settings;
