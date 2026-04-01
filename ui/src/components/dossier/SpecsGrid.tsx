import React from 'react';
import { VehicleSpecs } from '../../api/client';

interface Props {
  specs?: VehicleSpecs;
}

export default function SpecsGrid({ specs }: Props) {
  if (!specs) return null;

  const heroStats = [
    { value: specs.range_km || '--', unit: 'km', label: 'Range' },
    { value: specs.horsepower || '--', unit: 'hp', label: 'Power' },
    { value: specs.zero_to_100_kmh ? specs.zero_to_100_kmh.toFixed(1) : '--', unit: 's', label: '0-100' },
  ];

  const details: [string, string | number | undefined][] = [
    ['Model', specs.model],
    ['Variant', specs.variant],
    ['Generation', specs.generation],
    ['Year', specs.model_year],
    ['Battery', specs.battery_type],
    ['Capacity', specs.battery_capacity_kwh ? `${specs.battery_capacity_kwh} kWh` : undefined],
    ['Motor', specs.motor_config],
    ['Top Speed', specs.top_speed_kmh ? `${specs.top_speed_kmh} km/h` : undefined],
    ['Weight', specs.curb_weight_kg ? `${specs.curb_weight_kg} kg` : undefined],
    ['Dimensions', specs.dimensions],
    ['Seats', specs.seating],
    ['Wheels', specs.wheels],
    ['Color', specs.exterior_color],
    ['Interior', specs.interior],
    ['Autopilot', specs.autopilot_hardware],
    ['FSD', specs.has_fsd ? 'Yes' : 'No'],
    ['Charging', specs.supercharging],
  ];

  return (
    <>
      {/* Hero numbers */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 16 }}>
        {heroStats.map(s => (
          <div key={s.label} style={{
            background: 'var(--tesla-card-secondary)', borderRadius: 12, padding: '16px 8px',
            textAlign: 'center', border: '1px solid var(--tesla-card-border)',
          }}>
            <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'center', gap: 3 }}>
              <span className="hero-number-md" style={{ color: 'var(--tesla-text)' }}>{s.value}</span>
              <span style={{ fontSize: 12, color: 'var(--tesla-text-secondary)', fontWeight: 500 }}>{s.unit}</span>
            </div>
            <div style={{ fontSize: 10, color: 'var(--tesla-text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.1em', marginTop: 4 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Detail rows */}
      {details.filter(([, v]) => v != null && v !== '' && v !== 0).map(([label, val]) => (
        <div key={label} className="stat-row">
          <span style={{ color: 'var(--tesla-text-secondary)', fontSize: 13 }}>{label}</span>
          <span style={{ color: 'var(--tesla-text)', fontSize: 13, fontWeight: 500 }}>{val}</span>
        </div>
      ))}
    </>
  );
}
