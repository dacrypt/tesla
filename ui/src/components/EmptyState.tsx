import React from 'react';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  message?: string;
  action?: React.ReactNode;
}

export default function EmptyState({ icon, title, message, action }: EmptyStateProps) {
  return (
    <div className="tesla-card" style={{
      padding: 'var(--tesla-sp-xl)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: 'var(--tesla-sp-sm)',
      marginBottom: 'var(--tesla-sp-md)',
    }}>
      {icon && <div style={{ color: 'var(--tesla-text-dim)', marginBottom: 4 }}>{icon}</div>}
      <div style={{
        color: 'var(--tesla-text-secondary)',
        fontSize: 'var(--tesla-fs-lg)',
        fontWeight: 'var(--tesla-fw-semi)' as unknown as number,
      }}>{title}</div>
      {message && (
        <div style={{
          color: 'var(--tesla-text-dim)',
          fontSize: 'var(--tesla-fs-base)',
          textAlign: 'center',
          maxWidth: 280,
          lineHeight: '1.4',
        }}>{message}</div>
      )}
      {action && <div style={{ marginTop: 'var(--tesla-sp-sm)' }}>{action}</div>}
    </div>
  );
}
