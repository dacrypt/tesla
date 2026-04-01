import React, { useState } from 'react';

interface Props {
  title: string;
  defaultOpen?: boolean;
  badge?: React.ReactNode;
  children: React.ReactNode;
}

export default function CollapsibleSection({ title, defaultOpen = false, badge, children }: Props) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="tesla-card" style={{ padding: 0, overflow: 'hidden', marginBottom: 10 }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%', background: 'transparent', border: 'none', color: 'var(--tesla-text)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '14px 18px', cursor: 'pointer', fontFamily: 'var(--ion-font-family)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--tesla-text-secondary)' }}>
            {title}
          </span>
          {badge}
        </div>
        <svg width={16} height={16} viewBox="0 0 24 24" fill="none" style={{ transform: open ? 'rotate(180deg)' : 'rotate(0)', transition: 'transform 0.2s' }}>
          <path d="M6 9l6 6 6-6" stroke="var(--tesla-text-secondary)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      <div style={{
        maxHeight: open ? 2000 : 0,
        overflow: 'hidden',
        transition: 'max-height 0.3s ease',
        padding: open ? '0 18px 18px' : '0 18px 0',
      }}>
        {children}
      </div>
    </div>
  );
}
