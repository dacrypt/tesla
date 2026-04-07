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
const ControlsContent = React.lazy(() => import('./vehicle/ControlsContent'));
const ClimateContent = React.lazy(() => import('./vehicle/ClimateContent'));

/* ── Sub-tab icons ── */
const ControlsIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <path d="M3 17v2h6v-2H3zM3 5v2h10V5H3zm10 16v-2h8v-2h-8v-2h-2v6h2zM7 9v2H3v2h4v2h2V9H7zm14 4v-2H11v2h10zm-6-4h2V7h4V5h-4V3h-2v6z" />
  </svg>
);
const ClimateIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <path d="M22 11h-4.17l3.24-3.24-1.41-1.42L15 11h-2V9l4.66-4.66-1.42-1.41L13 6.17V2h-2v4.17L7.76 2.93 6.34 4.34 11 9v2H9L4.34 6.34 2.93 7.76 6.17 11H2v2h4.17l-3.24 3.24 1.41 1.42L9 13h2v2l-4.66 4.66 1.42 1.41L11 17.83V22h2v-4.17l3.24 3.24 1.42-1.41L13 15v-2h2l4.66 4.66 1.41-1.42L17.83 13H22z" />
  </svg>
);
type Tab = 'controls' | 'climate';

const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
  { key: 'controls', label: 'Controls', icon: <ControlsIcon /> },
  { key: 'climate', label: 'Climate', icon: <ClimateIcon /> },
];

const Vehicle: React.FC = () => {
  const [activeTab, setActiveTab] = useState<Tab>('controls');

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle style={{ fontWeight: 700 }}>Vehicle</IonTitle>
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
              <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
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
            {activeTab === 'controls' && <ControlsContent />}
            {activeTab === 'climate' && <ClimateContent />}
          </React.Suspense>
        </ErrorBoundary>
      </IonContent>
    </IonPage>
  );
};

export default Vehicle;
