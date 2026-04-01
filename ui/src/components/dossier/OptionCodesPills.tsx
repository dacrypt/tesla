import React from 'react';
import { OptionCodes } from '../../api/client';

const CATEGORY_COLORS: Record<string, string> = {
  model: '#0BE881',
  motor: '#05C46B',
  paint: '#0FBCF9',
  interior: '#FACC48',
  wheels: '#00D8D6',
  seats: '#F99716',
  autopilot: '#F99716',
  charging: '#0BE881',
  connectivity: '#0FBCF9',
  feature: '#86888f',
  unknown: '#86888f',
};

interface Props {
  options?: OptionCodes;
}

export default function OptionCodesPills({ options }: Props) {
  if (!options?.codes?.length) return null;

  // Group by category
  const groups: Record<string, typeof options.codes> = {};
  for (const code of options.codes) {
    const cat = code.category || 'unknown';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(code);
  }

  return (
    <div>
      {Object.entries(groups).map(([cat, codes]) => (
        <div key={cat} style={{ marginBottom: 10 }}>
          <div style={{ fontSize: 9, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--tesla-text-secondary)', marginBottom: 5 }}>
            {cat}
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {codes.map(c => {
              const color = CATEGORY_COLORS[cat] || '#86888f';
              return (
                <span key={c.code} title={c.description || c.description_es || ''} style={{
                  background: `${color}18`,
                  color,
                  border: `1px solid ${color}40`,
                  borderRadius: 100,
                  padding: '3px 9px',
                  fontSize: 10,
                  fontWeight: 600,
                  fontFamily: "'SF Mono', 'Menlo', monospace",
                  cursor: 'default',
                }}>
                  {c.code}
                </span>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
