import React, { useState } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
} from '@ionic/react';
import ErrorBoundary from '../components/ErrorBoundary';

/* ── Lazy-load sub-pages ── */
const ChargeContent = React.lazy(() => import('./vehicle/ChargeContent'));
const CostsContent = React.lazy(() => import('./energy/CostsContent'));

/* ── Sub-tab icons ── */
const ChargeIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <path d="M15.67 4H14V2h-4v2H8.33C7.6 4 7 4.6 7 5.33v15.33C7 21.4 7.6 22 8.33 22h7.33c.74 0 1.34-.6 1.34-1.33V5.33C17 4.6 16.4 4 15.67 4zM11 20v-5.5H9L13 7v5.5h2L11 20z" />
  </svg>
);
const CostsIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <path d="M11.8 10.9c-2.27-.59-3-1.2-3-2.15 0-1.09 1.01-1.85 2.7-1.85 1.78 0 2.44.85 2.5 2.1h2.21c-.07-1.72-1.12-3.3-3.21-3.81V3h-3v2.16c-1.94.42-3.5 1.68-3.5 3.61 0 2.31 1.91 3.46 4.7 4.13 2.5.6 3 1.48 3 2.41 0 .69-.49 1.79-2.7 1.79-2.06 0-2.87-.92-2.98-2.1h-2.2c.12 2.19 1.76 3.42 3.68 3.83V21h3v-2.15c1.95-.37 3.5-1.5 3.5-3.55 0-2.84-2.43-3.81-4.7-4.4z" />
  </svg>
);

type Tab = 'charge' | 'costs';

const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
  { key: 'charge', label: 'Charge', icon: <ChargeIcon /> },
  { key: 'costs', label: 'Costs', icon: <CostsIcon /> },
];

const Energy: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('charge');

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700 }}>Energy</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent>
        {/* Sub-tab bar */}
        <div className="sub-tab-bar">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              className={`sub-tab${activeTab === tab.key ? ' active' : ''}`}
              onClick={() => setActiveTab(tab.key)}
            >
              <span className="flex-center">
                {tab.icon}
              </span>
              <span>{tab.label}</span>
            </button>
          ))}
        </div>

        {/* Content */}
        <ErrorBoundary>
          <React.Suspense fallback={
            <div className="loading-center">
              <svg width={24} height={24} viewBox="0 0 24 24" fill="none">
                <circle cx={12} cy={12} r={9} stroke="rgba(255,255,255,0.1)" strokeWidth={3} />
                <path d="M12 3a9 9 0 019 9" stroke="#05C46B" strokeWidth={3} strokeLinecap="round">
                  <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
                </path>
              </svg>
            </div>
          }>
            {activeTab === 'charge' && <ChargeContent />}
            {activeTab === 'costs' && <CostsContent />}
          </React.Suspense>
        </ErrorBoundary>
      </IonContent>
    </IonPage>
  );
};

export default Energy;
