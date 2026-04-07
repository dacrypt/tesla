import React, { useState, useEffect } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import {
  api,
  EnergyVehicleLocationTariff,
  EnergyCompareResult,
  EnergyTariffsResult,
} from '../../api/client';

// ---- Icons ----
const BoltIcon = () => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor">
    <path d="M7 2v11h3v9l7-12h-4l4-8z" />
  </svg>
);
const LocationIcon = () => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor">
    <path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5s1.12-2.5 2.5-2.5 2.5 1.12 2.5 2.5-1.12 2.5-2.5 2.5z" />
  </svg>
);
const CityIcon = () => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor">
    <path d="M15 11V5l-3-3-3 3v2H3v14h18V11h-6zm-8 8H5v-2h2v2zm0-4H5v-2h2v2zm0-4H5v-2h2v2zm6 8h-2v-2h2v2zm0-4h-2v-2h2v2zm0-4h-2v-2h2v2zm0-4h-2V7h2v2zm6 12h-2v-2h2v2zm0-4h-2v-2h2v2z" />
  </svg>
);
const CalcIcon = () => (
  <svg width={18} height={18} viewBox="0 0 24 24" fill="currentColor">
    <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-7 3c1.93 0 3.5 1.57 3.5 3.5S13.93 13 12 13s-3.5-1.57-3.5-3.5S10.07 6 12 6zm7 13H5v-.23c0-.62.28-1.2.76-1.58C7.47 15.82 9.64 15 12 15s4.53.82 6.24 2.19c.48.38.76.97.76 1.58V19z" />
  </svg>
);

// ---- Theme ----
const C = {
  green: '#05C46B',
  blue: '#0FBCF9',
  orange: '#F99716',
  yellow: '#ffd32a',
  red: '#FF6B6B',
  purple: '#a29bfe',
  text: '#e5e5e5',
  subtext: '#999',
  grid: '#2a2a2a',
  bg: '#111',
  card: '#1a1a1a',
  border: '#2a2a2a',
  tooltipBg: '#1a1a1a',
};

const ESTRATO_COLORS = [C.blue, C.green, C.orange, C.yellow, C.red, C.purple];

const BATTERY_KWH = 79;
const SUPERCHARGER_COP_KWH = 1800;
const GAS_COP_LITRE = 11000;
const GAS_L_100KM = 10;
const TESLA_KWH_100KM = 16;

function Spin() {
  return (
    <svg width={24} height={24} viewBox="0 0 24 24" fill="none">
      <circle cx={12} cy={12} r={9} stroke="rgba(255,255,255,0.08)" strokeWidth={3} />
      <path d="M12 3a9 9 0 019 9" stroke={C.green} strokeWidth={3} strokeLinecap="round">
        <animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite" />
      </path>
    </svg>
  );
}

function Card({ title, icon, children }: { title: string; icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <div style={{ background: C.card, borderRadius: 14, border: `1px solid ${C.border}`, padding: '16px 18px', marginBottom: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
        <span style={{ color: C.green }}>{icon}</span>
        <span style={{ fontSize: 13, fontWeight: 600, color: C.text, letterSpacing: 0.4 }}>{title}</span>
      </div>
      {children}
    </div>
  );
}

const CITY_LABELS: Record<string, string> = {
  bogota: 'Bogotá',
  medellin: 'Medellín',
  cali: 'Cali',
  barranquilla: 'Barranquilla',
  cartagena: 'Cartagena',
  bucaramanga: 'Bucaramanga',
  pereira: 'Pereira',
  manizales: 'Manizales',
};

function cityLabel(name: string) {
  return CITY_LABELS[name] ?? name.charAt(0).toUpperCase() + name.slice(1);
}

function formatCOP(value: number) {
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    maximumFractionDigits: 0,
  }).format(value);
}

// ---- Location Tariff Card ----
function LocationTariffCard() {
  const [data, setData] = useState<EnergyVehicleLocationTariff | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getEnergyTariffsAtVehicle()
      .then(setData)
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const chargeKwh = BATTERY_KWH * 0.6;
  const chargeCost = data ? chargeKwh * data.valor_kwh : null;

  return (
    <Card title="Your Location Tariff" icon={<LocationIcon />}>
      {loading && <div style={{ display: 'flex', justifyContent: 'center', padding: 20 }}><Spin /></div>}
      {error && <div style={{ color: C.red, fontSize: 13 }}>Could not load location tariff</div>}
      {data && (
        <>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 6 }}>
            <span style={{ fontSize: 32, fontWeight: 700, color: C.green }}>{formatCOP(data.valor_kwh)}</span>
            <span style={{ fontSize: 13, color: C.subtext }}>/kWh</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px 12px', marginBottom: 12 }}>
            <div style={{ fontSize: 12, color: C.subtext }}>City</div>
            <div style={{ fontSize: 12, color: C.text }}>{cityLabel(data.city)}</div>
            <div style={{ fontSize: 12, color: C.subtext }}>Estrato</div>
            <div style={{ fontSize: 12, color: C.text }}>{data.estrato}</div>
            <div style={{ fontSize: 12, color: C.subtext }}>Operator</div>
            <div style={{ fontSize: 12, color: C.text }}>{data.empresa}</div>
            <div style={{ fontSize: 12, color: C.subtext }}>Source</div>
            <div style={{ fontSize: 12, color: data.location_source === 'vehicle_gps' ? C.green : C.orange }}>
              {data.location_source === 'vehicle_gps' ? 'Vehicle GPS' : 'Default'}
            </div>
          </div>
          {chargeCost !== null && (
            <div style={{ background: '#0a2a1a', border: `1px solid ${C.green}22`, borderRadius: 8, padding: '10px 12px' }}>
              <div style={{ fontSize: 12, color: C.subtext, marginBottom: 3 }}>
                Charge 20% → 80% ({chargeKwh.toFixed(0)} kWh)
              </div>
              <div style={{ fontSize: 18, fontWeight: 600, color: C.green }}>{formatCOP(chargeCost)}</div>
            </div>
          )}
        </>
      )}
    </Card>
  );
}

// ---- City Comparison Chart ----
function CityComparisonChart() {
  const [data, setData] = useState<EnergyCompareResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getEnergyTariffsCompare()
      .then(setData)
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  const chartData = data?.cities.map(city => {
    const row: Record<string, string | number> = { city: cityLabel(city.name) };
    city.estratos.forEach(e => {
      row[`E${e.estrato}`] = e.valor_kwh;
    });
    return row;
  }) ?? [];

  const estratos = [1, 2, 3, 4, 5, 6];

  return (
    <Card title="Electricity Price by City &amp; Estrato (COP/kWh)" icon={<CityIcon />}>
      {loading && <div style={{ display: 'flex', justifyContent: 'center', padding: 20 }}><Spin /></div>}
      {error && <div style={{ color: C.red, fontSize: 13 }}>Could not load comparison data</div>}
      {data && chartData.length > 0 && (
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={chartData} margin={{ top: 4, right: 4, left: 0, bottom: 4 }}>
            <CartesianGrid strokeDasharray="3 3" stroke={C.grid} vertical={false} />
            <XAxis dataKey="city" tick={{ fill: C.subtext, fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis
              tick={{ fill: C.subtext, fontSize: 10 }}
              axisLine={false}
              tickLine={false}
              width={48}
              tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`}
            />
            <Tooltip
              contentStyle={{ background: C.tooltipBg, border: `1px solid ${C.border}`, borderRadius: 6, fontSize: 11 }}
              labelStyle={{ color: C.text }}
              // eslint-disable-next-line @typescript-eslint/no-unsafe-argument
              formatter={((value: unknown) => [
                typeof value === 'number' ? formatCOP(value) : String(value ?? ''),
              ]) as never}
            />
            <Legend iconSize={8} wrapperStyle={{ fontSize: 10, color: C.subtext }} />
            {estratos.map((e, i) => (
              <Bar key={e} dataKey={`E${e}`} name={`Estrato ${e}`} fill={ESTRATO_COLORS[i]} radius={[2, 2, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      )}
    </Card>
  );
}

// ---- City Detail Table ----
function CityDetailTable({ ciudad }: { ciudad: string }) {
  const [data, setData] = useState<EnergyTariffsResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [myEstrato, setMyEstrato] = useState<number>(4);

  useEffect(() => {
    setLoading(true);
    setData(null);
    setError(null);
    api.getEnergyTariffs(ciudad, 0)
      .then(setData)
      .catch((e: unknown) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [ciudad]);

  return (
    <Card title={`${cityLabel(ciudad)} — All Estratos`} icon={<BoltIcon />}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <span style={{ fontSize: 12, color: C.subtext }}>My estrato:</span>
        {[1, 2, 3, 4, 5, 6].map(e => (
          <button
            key={e}
            onClick={() => setMyEstrato(e)}
            style={{
              background: myEstrato === e ? C.green : C.border,
              color: myEstrato === e ? '#000' : C.subtext,
              border: 'none',
              borderRadius: 6,
              padding: '3px 9px',
              fontSize: 12,
              cursor: 'pointer',
              fontWeight: myEstrato === e ? 700 : 400,
            }}
          >
            {e}
          </button>
        ))}
      </div>
      {loading && <div style={{ display: 'flex', justifyContent: 'center', padding: 16 }}><Spin /></div>}
      {error && <div style={{ color: C.red, fontSize: 13 }}>Could not load tariff data</div>}
      {data && (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: `1px solid ${C.border}` }}>
              <th style={{ textAlign: 'left', padding: '4px 6px', color: C.subtext, fontWeight: 500 }}>Estrato</th>
              <th style={{ textAlign: 'right', padding: '4px 6px', color: C.subtext, fontWeight: 500 }}>COP/kWh</th>
              <th style={{ textAlign: 'left', padding: '4px 6px', color: C.subtext, fontWeight: 500 }}>Operator</th>
            </tr>
          </thead>
          <tbody>
            {data.tariffs.map(t => (
              <tr
                key={t.estrato}
                style={{
                  borderBottom: `1px solid ${C.grid}`,
                  background: t.estrato === myEstrato ? '#0a2a1a' : 'transparent',
                }}
              >
                <td style={{ padding: '6px', color: t.estrato === myEstrato ? C.green : C.text, fontWeight: t.estrato === myEstrato ? 700 : 400 }}>
                  {t.estrato} {t.estrato === myEstrato && '★'}
                </td>
                <td style={{ padding: '6px', textAlign: 'right', color: t.estrato === myEstrato ? C.green : C.text, fontWeight: t.estrato === myEstrato ? 700 : 400 }}>
                  {formatCOP(t.valor_kwh)}
                </td>
                <td style={{ padding: '6px', color: C.subtext }}>{t.empresa}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

// ---- Cost Calculator ----
function CostCalculator({ defaultKwhPrice }: { defaultKwhPrice: number }) {
  const [kwhPrice, setKwhPrice] = useState(defaultKwhPrice || 648);
  const [monthlyKwh, setMonthlyKwh] = useState(120);

  useEffect(() => {
    if (defaultKwhPrice > 0) setKwhPrice(defaultKwhPrice);
  }, [defaultKwhPrice]);

  const monthlyCost = kwhPrice * monthlyKwh;
  const yearlyCost = monthlyCost * 12;
  const costPer100km = kwhPrice * TESLA_KWH_100KM;
  const superchargerPer100km = SUPERCHARGER_COP_KWH * TESLA_KWH_100KM;
  const gasPer100km = GAS_COP_LITRE * GAS_L_100KM;

  const inputStyle: React.CSSProperties = {
    background: '#222',
    border: `1px solid ${C.border}`,
    borderRadius: 6,
    color: C.text,
    padding: '6px 10px',
    fontSize: 13,
    width: '100%',
  };
  const labelStyle: React.CSSProperties = { fontSize: 12, color: C.subtext, marginBottom: 4, display: 'block' };

  return (
    <Card title="Cost Calculator" icon={<CalcIcon />}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
        <div>
          <label style={labelStyle}>COP/kWh</label>
          <input
            type="number"
            value={kwhPrice}
            onChange={e => setKwhPrice(Number(e.target.value))}
            style={inputStyle}
            min={0}
          />
        </div>
        <div>
          <label style={labelStyle}>Monthly kWh</label>
          <input
            type="number"
            value={monthlyKwh}
            onChange={e => setMonthlyKwh(Number(e.target.value))}
            style={inputStyle}
            min={0}
          />
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px 16px', marginBottom: 16 }}>
        <div style={{ background: '#0a2a1a', borderRadius: 8, padding: '10px 12px', border: `1px solid ${C.green}22` }}>
          <div style={{ fontSize: 11, color: C.subtext }}>Monthly cost</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: C.green }}>{formatCOP(monthlyCost)}</div>
        </div>
        <div style={{ background: '#0a2a1a', borderRadius: 8, padding: '10px 12px', border: `1px solid ${C.green}22` }}>
          <div style={{ fontSize: 11, color: C.subtext }}>Yearly cost</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: C.green }}>{formatCOP(yearlyCost)}</div>
        </div>
      </div>

      <div style={{ fontSize: 12, color: C.subtext, marginBottom: 8 }}>Cost per 100 km</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {[
          { label: 'Home charging', value: costPer100km, color: C.green },
          { label: 'Supercharger', value: superchargerPer100km, color: C.orange },
          { label: 'Gasoline (RAV4 10L/100km)', value: gasPer100km, color: C.red },
        ].map(row => (
          <div key={row.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: 12, color: C.subtext }}>{row.label}</span>
            <span style={{ fontSize: 13, fontWeight: 600, color: row.color }}>{formatCOP(row.value)}</span>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 12, padding: '8px 10px', background: '#111', borderRadius: 8, fontSize: 11, color: C.subtext }}>
        Savings vs gasoline:{' '}
        <span style={{ color: C.green, fontWeight: 600 }}>{formatCOP(gasPer100km - costPer100km)}/100km</span>
        {' · '}
        <span style={{ color: C.green, fontWeight: 600 }}>
          {formatCOP((gasPer100km - costPer100km) * 12000 / 100)}/year
        </span>{' '}
        (12,000 km/yr)
      </div>
    </Card>
  );
}

// ---- Main Content ----
export default function CostsContent() {
  const [selectedCity, setSelectedCity] = useState('bogota');
  const [locationKwh, setLocationKwh] = useState(0);

  useEffect(() => {
    api.getEnergyTariffsAtVehicle()
      .then(d => { if (d?.valor_kwh) setLocationKwh(d.valor_kwh); })
      .catch(() => {});
  }, []);

  const cities = ['bogota', 'medellin', 'cali', 'barranquilla', 'cartagena', 'bucaramanga', 'pereira', 'manizales'];

  return (
    <div style={{ padding: '16px 12px 32px', maxWidth: 680, margin: '0 auto' }}>
      <LocationTariffCard />
      <CityComparisonChart />

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        {cities.map(c => (
          <button
            key={c}
            onClick={() => setSelectedCity(c)}
            style={{
              background: selectedCity === c ? C.green : C.card,
              color: selectedCity === c ? '#000' : C.subtext,
              border: `1px solid ${selectedCity === c ? C.green : C.border}`,
              borderRadius: 20,
              padding: '4px 12px',
              fontSize: 12,
              cursor: 'pointer',
              fontWeight: selectedCity === c ? 700 : 400,
            }}
          >
            {cityLabel(c)}
          </button>
        ))}
      </div>
      <CityDetailTable ciudad={selectedCity} />

      <CostCalculator defaultKwhPrice={locationKwh} />
    </div>
  );
}
