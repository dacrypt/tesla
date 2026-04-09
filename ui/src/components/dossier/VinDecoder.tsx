import React, { useState } from 'react';
import type { VinDecode } from '../../api/client';

/* ── Color mapping for VIN position groups ── */
const VIN_GROUPS = [
  { positions: [0, 1, 2], label: 'WMI', color: '#0FBCF9', field: 'manufacturer' },
  { positions: [3],       label: 'MODEL', color: '#A55EEA', field: 'model' },
  { positions: [4],       label: 'BODY', color: '#05C46B', field: 'body_type' },
  { positions: [5],       label: 'SAFETY', color: '#F99716', field: 'restraint_system' },
  { positions: [6],       label: 'BATTERY', color: '#FF6B6B', field: 'energy_type' },
  { positions: [7],       label: 'MOTOR', color: '#e74c3c', field: 'motor_battery' },
  { positions: [8],       label: 'CHECK', color: '#636e72', field: 'check_digit' },
  { positions: [9],       label: 'YEAR', color: '#00D8D6', field: 'model_year' },
  { positions: [10],      label: 'PLANT', color: '#fd79a8', field: 'plant' },
  { positions: [11, 12, 13, 14, 15, 16], label: 'SERIAL', color: '#636e72', field: 'serial_number' },
];

/* ── Airbag icons ── */
const CheckMark = () => (
  <svg width={12} height={12} viewBox="0 0 24 24" fill="#05C46B">
    <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"/>
  </svg>
);
const XMark = () => (
  <svg width={12} height={12} viewBox="0 0 24 24" fill="#636e72">
    <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
  </svg>
);

/* ── Parse airbag info from restraint_system string ── */
function parseAirbags(restraint?: string): { name: string; present: boolean }[] {
  if (!restraint) return [];
  const types = ['Front', 'Side', 'PODS', 'Knee', 'Active Hood'];
  return types.map(name => ({
    name,
    present: restraint.toLowerCase().includes(name.toLowerCase()),
  }));
}

/* ── Main Component ── */
export default function VinDecoder({ data }: { data: VinDecode }) {
  const [expanded, setExpanded] = useState(false);
  const vin = data.vin || '';

  if (!vin || vin.length < 17) return null;

  const chars = vin.split('');

  return (
    <div className="tesla-card" style={{ padding: 16, marginBottom: 12 }}>
      {/* Header */}
      <div
        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
        onClick={() => setExpanded(e => !e)}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <svg width={14} height={14} viewBox="0 0 24 24" fill="#0FBCF9">
            <path d="M17 3H7c-1.1 0-2 .9-2 2v16l7-3 7 3V5c0-1.1-.9-2-2-2z"/>
          </svg>
          <span style={{ color: '#f5f5f7', fontWeight: 600, fontSize: 14 }}>VIN Decoder</span>
        </div>
        <span style={{
          fontSize: 11, fontWeight: 700, color: '#05C46B',
          background: '#05C46B18', padding: '3px 10px',
          borderRadius: 100, border: '1px solid #05C46B30',
        }}>
          DECODED
        </span>
      </div>

      {/* VIN character boxes */}
      <div style={{
        display: 'flex', gap: 2, marginTop: 14, overflowX: 'auto',
        paddingBottom: 4, justifyContent: 'center',
      }}>
        {chars.map((char, i) => {
          const group = VIN_GROUPS.find(g => g.positions.includes(i));
          const color = group?.color || '#636e72';
          const isGroupStart = group?.positions[0] === i;
          const isGroupEnd = group?.positions[group.positions.length - 1] === i;

          return (
            <div key={i} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <div style={{
                width: 30, height: 36,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                background: `${color}18`,
                border: `1px solid ${color}40`,
                borderRadius: isGroupStart && isGroupEnd ? 6
                  : isGroupStart ? '6px 0 0 6px'
                  : isGroupEnd ? '0 6px 6px 0' : 0,
                borderRight: !isGroupEnd ? 'none' : undefined,
                color, fontWeight: 700, fontSize: 15,
                fontFamily: 'monospace',
              }}>
                {char}
              </div>
            </div>
          );
        })}
      </div>

      {/* Group labels */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: 2, marginTop: 3 }}>
        {VIN_GROUPS.map(g => (
          <div key={g.label} style={{
            width: g.positions.length * 30 + (g.positions.length - 1) * 2,
            textAlign: 'center',
            fontSize: 8, fontWeight: 700, letterSpacing: '0.05em',
            color: g.color, opacity: 0.7,
          }}>
            {g.label}
          </div>
        ))}
      </div>

      {/* Expandable details */}
      {expanded && (
        <div style={{ marginTop: 16, borderTop: '1px solid rgba(255,255,255,0.06)', paddingTop: 12 }}>
          {/* Manufacture */}
          {data.plant && (
            <DetailRow icon="🏭" label="Manufacture" value={`Made in ${data.plant_country || '?'} — ${data.plant}`} />
          )}

          {/* Vehicle */}
          {data.model && (
            <DetailRow icon="🚗" label="Vehicle" value={`${data.model} · ${data.model_year || '?'} · ${data.body_type || ''}`} />
          )}

          {/* Powertrain */}
          {data.motor_battery && (
            <DetailRow icon="⚡" label="Powertrain" value={`${data.motor_battery}${data.battery_chemistry ? ` · ${data.battery_chemistry}` : ''}`} />
          )}

          {/* Safety / Airbags */}
          {data.restraint_system && (
            <div className="stat-row" style={{ borderBottom: '1px solid rgba(255,255,255,0.04)', padding: '8px 0' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
                <span style={{ fontSize: 12 }}>🛡️</span>
                <span style={{ fontSize: 11, color: '#86888f', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Safety (Airbags)</span>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {parseAirbags(data.restraint_system).map(ab => (
                  <span key={ab.name} style={{
                    display: 'inline-flex', alignItems: 'center', gap: 4,
                    fontSize: 12, color: ab.present ? '#05C46B' : '#636e72',
                    background: ab.present ? '#05C46B12' : 'transparent',
                    padding: '2px 8px', borderRadius: 6,
                    border: `1px solid ${ab.present ? '#05C46B25' : '#636e7225'}`,
                  }}>
                    {ab.present ? <CheckMark /> : <XMark />}
                    {ab.name}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Serial */}
          {data.serial_number && (
            <DetailRow icon="#" label="Serial" value={`#${data.serial_number}`} />
          )}
        </div>
      )}
    </div>
  );
}

function DetailRow({ icon, label, value }: { icon: string; label: string; value: string }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 8,
      padding: '8px 0', borderBottom: '1px solid rgba(255,255,255,0.04)',
    }}>
      <span style={{ fontSize: 12, marginTop: 1 }}>{icon}</span>
      <div>
        <div style={{ fontSize: 11, color: '#86888f', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</div>
        <div style={{ fontSize: 13, color: '#f5f5f7', marginTop: 2 }}>{value}</div>
      </div>
    </div>
  );
}
