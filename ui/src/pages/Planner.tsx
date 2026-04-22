import React, { useState } from 'react';
import {
  IonContent,
  IonHeader,
  IonPage,
  IonToolbar,
  IonTitle,
  IonCard,
  IonCardHeader,
  IonCardTitle,
  IonCardContent,
  IonItem,
  IonLabel,
  IonInput,
  IonButton,
  IonRange,
  IonSelect,
  IonSelectOption,
  IonToast,
  IonSpinner,
  IonList,
} from '@ionic/react';
import { getBaseUrl } from '../api/client';

interface ChargerSuggestion {
  ocm_id: number;
  name: string;
  lat: number;
  lon: number;
  network: string;
  max_power_kw?: number | null;
  arrival_soc_kwh?: number | null;
  departure_soc_kwh?: number | null;
  charge_duration_min?: number | null;
  soc_warning?: string | null;
}

interface PlannedRoute {
  origin_address: string;
  destination_address: string;
  origin_latlon: [number, number];
  destination_latlon: [number, number];
  total_distance_km: number;
  total_duration_min: number;
  total_energy_kwh?: number | null;
  stops: ChargerSuggestion[];
  abrp_deep_link?: string | null;
  routing_provider: string;
  consumption_source?: string | null;
}

interface PlanResponse {
  plan: PlannedRoute | null;
  alternatives: PlannedRoute[];
  warnings: string[];
}

const CAR_MODELS = [
  { id: '', label: 'Default (from config)' },
  { id: 'model_y_lr', label: 'Model Y Long Range' },
  { id: 'model_y_rwd', label: 'Model Y RWD' },
  { id: 'model_3_lr', label: 'Model 3 Long Range' },
  { id: 'model_3_rwd', label: 'Model 3 RWD' },
  { id: 'model_s_lr', label: 'Model S Long Range' },
  { id: 'model_x_lr', label: 'Model X Long Range' },
  { id: 'cybertruck_awd', label: 'Cybertruck AWD' },
];

const Planner: React.FC = () => {
  const [origin, setOrigin] = useState('');
  const [destination, setDestination] = useState('');
  const [car, setCar] = useState('');
  const [network, setNetwork] = useState<'any' | 'tesla' | 'ccs'>('any');
  const [minPower, setMinPower] = useState(50);
  const [socStart, setSocStart] = useState(0.8);
  const [socTarget, setSocTarget] = useState(0.2);
  const [batteryKwh, setBatteryKwh] = useState(75);
  const [alternatives, setAlternatives] = useState(1);
  const [saveAs, setSaveAs] = useState('');

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PlanResponse | null>(null);
  const [toast, setToast] = useState<{ message: string; color: string } | null>(null);

  const apiBase = (): string => getBaseUrl() || '';

  const submit = async () => {
    if (!origin.trim() || !destination.trim()) {
      setToast({ message: 'Enter origin and destination', color: 'warning' });
      return;
    }
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${apiBase()}/api/nav/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          origin,
          destination,
          car: car || null,
          network,
          min_power_kw: minPower,
          soc_start: socStart,
          soc_target: socTarget,
          battery_kwh: batteryKwh,
          alternatives,
          router: 'openroute',
          use_elevation: true,
          use_weather: true,
        }),
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
      }
      const data = (await res.json()) as PlanResponse;
      setResult(data);
      setToast({ message: 'Plan computed', color: 'success' });
    } catch (e: any) {
      setToast({ message: `Plan failed: ${e.message || e}`, color: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  const persist = async () => {
    if (!result?.plan || !saveAs.trim()) {
      setToast({ message: 'Enter a name first', color: 'warning' });
      return;
    }
    try {
      const res = await fetch(`${apiBase()}/api/nav/plan/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: saveAs.trim(), plan: result.plan }),
      });
      if (!res.ok) {
        const body = await res.text();
        throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
      }
      setToast({ message: `Saved as '${saveAs.trim()}'`, color: 'success' });
    } catch (e: any) {
      setToast({ message: `Save failed: ${e.message || e}`, color: 'danger' });
    }
  };

  const exportFile = (fmt: 'gpx' | 'kml') => {
    if (!saveAs.trim()) {
      setToast({ message: 'Save the plan first, then export', color: 'warning' });
      return;
    }
    const url = `${apiBase()}/api/nav/plan/${encodeURIComponent(saveAs.trim())}/export?fmt=${fmt}`;
    window.open(url, '_blank');
  };

  const plan = result?.plan;

  return (
    <IonPage>
      <IonHeader>
        <IonToolbar>
          <IonTitle>EV Route Planner</IonTitle>
        </IonToolbar>
      </IonHeader>
      <IonContent className="ion-padding">
        <IonCard>
          <IonCardHeader>
            <IonCardTitle>Plan a trip</IonCardTitle>
          </IonCardHeader>
          <IonCardContent>
            <IonItem>
              <IonLabel position="stacked">Origin</IonLabel>
              <IonInput
                value={origin}
                placeholder="Bogotá or 4.71,-74.07"
                onIonChange={(e) => setOrigin(e.detail.value || '')}
              />
            </IonItem>
            <IonItem>
              <IonLabel position="stacked">Destination</IonLabel>
              <IonInput
                value={destination}
                placeholder="Medellín or 6.24,-75.58"
                onIonChange={(e) => setDestination(e.detail.value || '')}
              />
            </IonItem>
            <IonItem>
              <IonLabel position="stacked">Car</IonLabel>
              <IonSelect value={car} onIonChange={(e) => setCar(e.detail.value)}>
                {CAR_MODELS.map((m) => (
                  <IonSelectOption key={m.id} value={m.id}>
                    {m.label}
                  </IonSelectOption>
                ))}
              </IonSelect>
            </IonItem>
            <IonItem>
              <IonLabel position="stacked">Network</IonLabel>
              <IonSelect
                value={network}
                onIonChange={(e) => setNetwork(e.detail.value)}
              >
                <IonSelectOption value="any">Any</IonSelectOption>
                <IonSelectOption value="tesla">Tesla</IonSelectOption>
                <IonSelectOption value="ccs">CCS</IonSelectOption>
              </IonSelect>
            </IonItem>
            <IonItem>
              <IonLabel>Min power: {minPower} kW</IonLabel>
            </IonItem>
            <IonRange
              min={0}
              max={350}
              step={25}
              value={minPower}
              onIonChange={(e) => setMinPower(Number(e.detail.value))}
            />
            <IonItem>
              <IonLabel>Start SoC: {(socStart * 100).toFixed(0)}%</IonLabel>
            </IonItem>
            <IonRange
              min={0.1}
              max={1.0}
              step={0.05}
              value={socStart}
              onIonChange={(e) => setSocStart(Number(e.detail.value))}
            />
            <IonItem>
              <IonLabel>Target SoC: {(socTarget * 100).toFixed(0)}%</IonLabel>
            </IonItem>
            <IonRange
              min={0.05}
              max={0.95}
              step={0.05}
              value={socTarget}
              onIonChange={(e) => setSocTarget(Number(e.detail.value))}
            />
            <IonItem>
              <IonLabel position="stacked">Battery kWh</IonLabel>
              <IonInput
                type="number"
                value={batteryKwh}
                onIonChange={(e) => setBatteryKwh(Number(e.detail.value) || 75)}
              />
            </IonItem>
            <IonItem>
              <IonLabel>Alternatives: {alternatives}</IonLabel>
            </IonItem>
            <IonRange
              min={1}
              max={5}
              step={1}
              snaps
              value={alternatives}
              onIonChange={(e) => setAlternatives(Number(e.detail.value))}
            />
            <IonButton expand="block" onClick={submit} disabled={loading}>
              {loading ? <IonSpinner name="dots" /> : 'Plan route'}
            </IonButton>
          </IonCardContent>
        </IonCard>

        {plan && (
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>
                {plan.origin_address} → {plan.destination_address}
              </IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              <p>
                <strong>{plan.total_distance_km.toFixed(1)} km</strong> ·{' '}
                {plan.total_duration_min} min
                {plan.total_energy_kwh != null && (
                  <> · {plan.total_energy_kwh.toFixed(1)} kWh</>
                )}
                {' · via '}
                <em>{plan.routing_provider}</em>
              </p>
              {plan.consumption_source && (
                <p style={{ opacity: 0.7 }}>consumption: {plan.consumption_source}</p>
              )}
              <h3>Charging stops</h3>
              {plan.stops.length === 0 ? (
                <p>No intermediate stops needed.</p>
              ) : (
                <IonList>
                  {plan.stops.map((s, i) => (
                    <IonItem key={s.ocm_id}>
                      <IonLabel>
                        <h2>
                          {i + 1}. {s.name}
                        </h2>
                        <p>
                          {s.max_power_kw != null && (
                            <>
                              {s.max_power_kw.toFixed(0)} kW ·{' '}
                            </>
                          )}
                          {s.network}
                          {s.arrival_soc_kwh != null && (
                            <>
                              {' '}· arrive {s.arrival_soc_kwh.toFixed(1)} kWh
                            </>
                          )}
                          {s.charge_duration_min != null && (
                            <> · charge {s.charge_duration_min} min</>
                          )}
                        </p>
                        {s.soc_warning && (
                          <p style={{ color: 'orange' }}>{s.soc_warning}</p>
                        )}
                      </IonLabel>
                    </IonItem>
                  ))}
                </IonList>
              )}
              {plan.abrp_deep_link && (
                <IonButton
                  expand="block"
                  fill="outline"
                  href={plan.abrp_deep_link}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Open in ABRP
                </IonButton>
              )}
              <IonItem>
                <IonLabel position="stacked">Save as</IonLabel>
                <IonInput
                  value={saveAs}
                  placeholder="my-trip"
                  onIonChange={(e) => setSaveAs(e.detail.value || '')}
                />
              </IonItem>
              <IonButton expand="block" onClick={persist}>
                Save Route
              </IonButton>
              <IonButton
                expand="block"
                fill="outline"
                onClick={() => exportFile('gpx')}
              >
                Export GPX
              </IonButton>
              <IonButton
                expand="block"
                fill="outline"
                onClick={() => exportFile('kml')}
              >
                Export KML
              </IonButton>
            </IonCardContent>
          </IonCard>
        )}

        {result?.alternatives && result.alternatives.length > 0 && (
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>
                Alternatives ({result.alternatives.length})
              </IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              {result.alternatives.map((alt, i) => (
                <div key={i} style={{ marginBottom: 12 }}>
                  <strong>Alt {i + 1}:</strong> {alt.stops.length} stop(s)
                  <p>
                    {alt.stops.map((s) => s.name).join(' → ') || '(direct)'}
                  </p>
                </div>
              ))}
            </IonCardContent>
          </IonCard>
        )}

        {result?.warnings && result.warnings.length > 0 && (
          <IonCard>
            <IonCardHeader>
              <IonCardTitle>Warnings</IonCardTitle>
            </IonCardHeader>
            <IonCardContent>
              <ul>
                {result.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </IonCardContent>
          </IonCard>
        )}

        <IonToast
          isOpen={toast !== null}
          message={toast?.message ?? ''}
          color={toast?.color}
          duration={3500}
          onDidDismiss={() => setToast(null)}
        />
      </IonContent>
    </IonPage>
  );
};

export default Planner;
