import React from 'react';
import { RealStatus } from '../../api/client';

const PHASES = [
  { key: 'is_produced', label: 'Produced' },
  { key: 'is_shipped', label: 'Shipped' },
  { key: 'is_in_country', label: 'In Country' },
  { key: 'is_registered', label: 'Registered' },
  { key: 'is_delivery_scheduled', label: 'Scheduled' },
  { key: 'is_delivered', label: 'Delivered' },
] as const;

interface Props {
  status?: RealStatus;
}

export default function StatusPipeline({ status }: Props) {
  if (!status) return null;

  const currentIdx = PHASES.findIndex(p => !status[p.key as keyof RealStatus]);
  const activeIdx = currentIdx === -1 ? PHASES.length - 1 : currentIdx - 1;

  return (
    <div className="tesla-card" style={{ padding: '20px 14px 16px', marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', position: 'relative' }}>
        {/* Connecting line */}
        <div style={{
          position: 'absolute', top: 11, left: 20, right: 20, height: 2,
          background: 'var(--tesla-border)', zIndex: 0,
        }} />
        <div style={{
          position: 'absolute', top: 11, left: 20, height: 2,
          width: activeIdx >= 0 ? `${(activeIdx / (PHASES.length - 1)) * 100}%` : '0%',
          background: 'var(--tesla-green)', zIndex: 1,
          transition: 'width 0.5s ease',
          maxWidth: 'calc(100% - 40px)',
        }} />

        {PHASES.map((phase, i) => {
          const done = !!status[phase.key as keyof RealStatus];
          const isCurrent = i === currentIdx;

          return (
            <div key={phase.key} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, zIndex: 2, flex: 1 }}>
              <div style={{
                width: 22, height: 22, borderRadius: '50%',
                background: done ? 'var(--tesla-green)' : isCurrent ? 'transparent' : 'var(--tesla-card-secondary)',
                border: `2px solid ${done ? 'var(--tesla-green)' : isCurrent ? 'var(--tesla-green)' : 'var(--tesla-border)'}`,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 10, color: done ? '#000' : isCurrent ? 'var(--tesla-green)' : 'var(--tesla-text-secondary)',
                fontWeight: 700,
                animation: isCurrent ? 'pulse 2s infinite' : 'none',
                boxShadow: isCurrent ? '0 0 8px var(--tesla-green-glow)' : 'none',
              }}>
                {done ? '\u2713' : i + 1}
              </div>
              <span style={{
                fontSize: 8, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em',
                color: done ? 'var(--tesla-green)' : isCurrent ? 'var(--tesla-text)' : 'var(--tesla-text-secondary)',
                textAlign: 'center', lineHeight: 1.2,
              }}>
                {phase.label}
              </span>
            </div>
          );
        })}
      </div>
      <style>{`@keyframes pulse { 0%,100% { box-shadow: 0 0 4px var(--tesla-green-glow); } 50% { box-shadow: 0 0 16px var(--tesla-green-glow); } }`}</style>
    </div>
  );
}
