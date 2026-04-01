import React, { useState } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
} from '@ionic/react';

/* ── Lazy-load sub-pages ── */
const ControlsContent = React.lazy(() => import('./vehicle/ControlsContent'));
const ChargeContent = React.lazy(() => import('./vehicle/ChargeContent'));
const ClimateContent = React.lazy(() => import('./vehicle/ClimateContent'));
const ScheduleContent = React.lazy(() => import('./vehicle/ScheduleContent'));

/* ── Sub-tab icons ── */
const ControlsIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <path d="M3 17v2h6v-2H3zM3 5v2h10V5H3zm10 16v-2h8v-2h-8v-2h-2v6h2zM7 9v2H3v2h4v2h2V9H7zm14 4v-2H11v2h10zm-6-4h2V7h4V5h-4V3h-2v6z" />
  </svg>
);
const ChargeIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <path d="M15.67 4H14V2h-4v2H8.33C7.6 4 7 4.6 7 5.33v15.33C7 21.4 7.6 22 8.33 22h7.33c.74 0 1.34-.6 1.34-1.33V5.33C17 4.6 16.4 4 15.67 4zM11 20v-5.5H9L13 7v5.5h2L11 20z" />
  </svg>
);
const ClimateIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <path d="M22 11h-4.17l3.24-3.24-1.41-1.42L15 11h-2V9l4.66-4.66-1.42-1.41L13 6.17V2h-2v4.17L7.76 2.93 6.34 4.34 11 9v2H9L4.34 6.34 2.93 7.76 6.17 11H2v2h4.17l-3.24 3.24 1.41 1.42L9 13h2v2l-4.66 4.66 1.42 1.41L11 17.83V22h2v-4.17l3.24 3.24 1.42-1.41L13 15v-2h2l4.66 4.66 1.41-1.42L17.83 13H22z" />
  </svg>
);
const ScheduleIcon = () => (
  <svg width={16} height={16} viewBox="0 0 24 24" fill="currentColor">
    <path d="M19 3h-1V1h-2v2H8V1H6v2H5c-1.11 0-1.99.9-1.99 2L3 19c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H5V8h14v11zM9 10H7v2h2v-2zm4 0h-2v2h2v-2zm4 0h-2v2h2v-2z" />
  </svg>
);

type Tab = 'controls' | 'charge' | 'climate' | 'schedule';

const tabs: { key: Tab; label: string; icon: React.ReactNode }[] = [
  { key: 'controls', label: 'Controls', icon: <ControlsIcon /> },
  { key: 'charge', label: 'Charge', icon: <ChargeIcon /> },
  { key: 'climate', label: 'Climate', icon: <ClimateIcon /> },
  { key: 'schedule', label: 'Schedule', icon: <ScheduleIcon /> },
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
          {activeTab === 'charge' && <ChargeContent />}
          {activeTab === 'climate' && <ClimateContent />}
          {activeTab === 'schedule' && <ScheduleContent />}
        </React.Suspense>
      </IonContent>
    </IonPage>
  );
};

export default Vehicle;
