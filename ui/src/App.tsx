import React from 'react';
import { Redirect, Route } from 'react-router-dom';
import ErrorBoundary from './components/ErrorBoundary';
import {
  IonApp,
  IonLabel,
  IonRouterOutlet,
  IonTabBar,
  IonTabButton,
  IonTabs,
  IonSpinner,
  IonToast,
  setupIonicReact,
} from '@ionic/react';
import { IonReactRouter } from '@ionic/react-router';
import { onRateLimit } from './api/client';

import Dashboard from './pages/Dashboard';
import Vehicle from './pages/Vehicle';

const Navigation = React.lazy(() => import('./pages/Navigation'));
const Analytics = React.lazy(() => import('./pages/Analytics'));
const Settings = React.lazy(() => import('./pages/Settings'));
const Action = React.lazy(() => import('./pages/Action'));
const Dossier = React.lazy(() => import('./pages/Dossier'));
const Order = React.lazy(() => import('./pages/Order'));
const Energy = React.lazy(() => import('./pages/Energy'));

/* Core CSS required for Ionic components */
import '@ionic/react/css/core.css';
import '@ionic/react/css/normalize.css';
import '@ionic/react/css/structure.css';
import '@ionic/react/css/typography.css';
import '@ionic/react/css/padding.css';
import '@ionic/react/css/float-elements.css';
import '@ionic/react/css/text-alignment.css';
import '@ionic/react/css/text-transformation.css';
import '@ionic/react/css/flex-utils.css';
import '@ionic/react/css/display.css';

/* Tesla Design System */
import './theme/variables.css';

setupIonicReact({ mode: 'ios' });

// ---- Page loading fallback ----
const PageLoader = () => (
  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100vh' }}>
    <IonSpinner name="dots" style={{ '--color': '#05C46B' } as React.CSSProperties} />
  </div>
);

// ---- Inline SVG Tab Icons (no ionicons dependency) ----
const HomeTabIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
    <path d="M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z"/>
  </svg>
);

const VehicleTabIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
    <path d="M18.92 6.01C18.72 5.42 18.16 5 17.5 5h-11c-.66 0-1.21.42-1.42 1.01L3 12v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8l-2.08-5.99zM6.5 16c-.83 0-1.5-.67-1.5-1.5S5.67 13 6.5 13s1.5.67 1.5 1.5S7.33 16 6.5 16zm11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5zM5 11l1.5-4.5h11L19 11H5z"/>
  </svg>
);

const NavTabIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
    <path d="M21 3L3 10.53v.98l6.84 2.65L12.48 21h.98L21 3z"/>
  </svg>
);

const OrderTabIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
    <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 3c1.93 0 3.5 1.57 3.5 3.5S13.93 13 12 13s-3.5-1.57-3.5-3.5S10.07 6 12 6zm7 13H5v-.23c0-.62.28-1.2.76-1.58C7.47 15.82 9.64 15 12 15s4.53.82 6.24 2.19c.48.38.76.97.76 1.58V19z"/>
  </svg>
);

const ChartTabIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
    <path d="M5 9.2h3V19H5zM10.6 5h2.8v14h-2.8zm5.6 8H19v6h-2.8z"/>
  </svg>
);

const GearTabIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
    <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z"/>
  </svg>
);

const EnergyTabIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="22" height="22" fill="currentColor">
    <path d="M7 2v11h3v9l7-12h-4l4-8z"/>
  </svg>
);

const App: React.FC = () => {
  const [rateLimitMsg, setRateLimitMsg] = React.useState<string | null>(null);

  React.useEffect(() => {
    return onRateLimit((retryAfterSeconds: number) => {
      setRateLimitMsg(`Rate limited — retrying in ${retryAfterSeconds}s`);
    });
  }, []);

  return (
  <ErrorBoundary>
  <IonApp>
    <IonToast
      isOpen={rateLimitMsg !== null}
      message={rateLimitMsg ?? ''}
      duration={4000}
      position="top"
      onDidDismiss={() => setRateLimitMsg(null)}
      style={{ '--background': '#1a1a1a', '--color': '#F99716', '--border-radius': '10px' } as React.CSSProperties}
    />
    <IonReactRouter>
      <IonTabs>
        <IonRouterOutlet>
          <Route exact path="/dashboard"><Dashboard /></Route>
          <Route exact path="/vehicle"><Vehicle /></Route>
          <Route exact path="/nav">
            <ErrorBoundary>
              <React.Suspense fallback={<PageLoader />}>
                <Navigation />
              </React.Suspense>
            </ErrorBoundary>
          </Route>
          <Route exact path="/info">
            <ErrorBoundary>
              <React.Suspense fallback={<PageLoader />}>
                <Dossier />
              </React.Suspense>
            </ErrorBoundary>
          </Route>
          <Route exact path="/order">
            <ErrorBoundary>
              <React.Suspense fallback={<PageLoader />}>
                <Order />
              </React.Suspense>
            </ErrorBoundary>
          </Route>
          <Route exact path="/analytics">
            <ErrorBoundary>
              <React.Suspense fallback={<PageLoader />}>
                <Analytics />
              </React.Suspense>
            </ErrorBoundary>
          </Route>
          <Route exact path="/settings">
            <ErrorBoundary>
              <React.Suspense fallback={<PageLoader />}>
                <Settings />
              </React.Suspense>
            </ErrorBoundary>
          </Route>
          <Route exact path="/action">
            <ErrorBoundary>
              <React.Suspense fallback={<PageLoader />}>
                <Action />
              </React.Suspense>
            </ErrorBoundary>
          </Route>
          <Route exact path="/energy">
            <ErrorBoundary>
              <React.Suspense fallback={<PageLoader />}>
                <Energy />
              </React.Suspense>
            </ErrorBoundary>
          </Route>
          <Route exact path="/"><Redirect to="/dashboard" /></Route>
        </IonRouterOutlet>

        <IonTabBar slot="bottom">
          <IonTabButton tab="dashboard" href="/dashboard">
            <HomeTabIcon />
            <IonLabel>Home</IonLabel>
          </IonTabButton>
          <IonTabButton tab="vehicle" href="/vehicle">
            <VehicleTabIcon />
            <IonLabel>Vehicle</IonLabel>
          </IonTabButton>
          <IonTabButton tab="nav" href="/nav">
            <NavTabIcon />
            <IonLabel>Nav</IonLabel>
          </IonTabButton>
          <IonTabButton tab="order" href="/order">
            <OrderTabIcon />
            <IonLabel>Order</IonLabel>
          </IonTabButton>
          <IonTabButton tab="energy" href="/energy">
            <EnergyTabIcon />
            <IonLabel>Energy</IonLabel>
          </IonTabButton>
          <IonTabButton tab="settings" href="/settings">
            <GearTabIcon />
            <IonLabel>Settings</IonLabel>
          </IonTabButton>
        </IonTabBar>
      </IonTabs>
    </IonReactRouter>
  </IonApp>
  </ErrorBoundary>
  );
};

export default App;
