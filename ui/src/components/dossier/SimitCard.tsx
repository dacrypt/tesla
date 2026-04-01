import React from 'react';
import { SimitData } from '../../api/client';

interface Props {
  simit?: SimitData;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

export default function SimitCard({ simit, loading, error, onRetry }: Props) {
  if (loading) {
    return (
      <div style={{ padding: 20, textAlign: 'center' }}>
        <div style={{ width: 20, height: 20, border: '2px solid var(--tesla-border)', borderTopColor: 'var(--tesla-green)', borderRadius: '50%', animation: 'spin .7s linear infinite', display: 'inline-block' }} />
        <div style={{ fontSize: 12, color: 'var(--tesla-text-secondary)', marginTop: 8 }}>Querying SIMIT...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', padding: 16 }}>
        <div style={{ fontSize: 12, color: '#FF6B6B', marginBottom: 8 }}>{error}</div>
        {onRetry && <button className="tesla-btn secondary" style={{ width: 'auto', padding: '8px 20px', fontSize: 12 }} onClick={onRetry}>Retry</button>}
      </div>
    );
  }

  if (!simit) {
    return <div style={{ fontSize: 12, color: 'var(--tesla-text-secondary)', textAlign: 'center', padding: 16 }}>No SIMIT data available</div>;
  }

  // Backend may report paz_y_salvo=false even with 0 debt (e.g., query issues)
  // Use actual numbers as ground truth
  const totalFines = (simit.comparendos ?? 0) + (simit.multas ?? 0);
  const isPazYSalvo = simit.paz_y_salvo || (totalFines === 0 && (simit.total_deuda ?? 0) === 0);

  return (
    <>
      {/* Main badge */}
      <div style={{ textAlign: 'center', marginBottom: 16 }}>
        <div style={{
          display: 'inline-flex', alignItems: 'center', gap: 8,
          background: isPazYSalvo ? 'rgba(11,232,129,0.1)' : 'rgba(255,107,107,0.1)',
          border: `2px solid ${isPazYSalvo ? 'rgba(11,232,129,0.3)' : 'rgba(255,107,107,0.3)'}`,
          color: isPazYSalvo ? '#0BE881' : '#FF6B6B',
          borderRadius: 100, padding: '8px 20px',
          fontSize: 14, fontWeight: 700,
        }}>
          {isPazYSalvo ? '✓ Paz y Salvo' : '✗ Con Deudas'}
        </div>
      </div>

      {/* Stats grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8, marginBottom: 12 }}>
        {[
          { label: 'Comparendos', value: simit.comparendos ?? 0 },
          { label: 'Multas', value: simit.multas ?? 0 },
          { label: 'Acuerdos', value: simit.acuerdos_pago ?? 0 },
        ].map(s => (
          <div key={s.label} style={{
            background: 'var(--tesla-card-secondary)', borderRadius: 10, padding: '12px 8px',
            textAlign: 'center', border: '1px solid var(--tesla-card-border)',
          }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: s.value > 0 ? '#FF6B6B' : 'var(--tesla-text)' }}>{s.value}</div>
            <div style={{ fontSize: 9, color: 'var(--tesla-text-secondary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Total debt */}
      {(simit.total_deuda ?? 0) > 0 && (
        <div className="stat-row">
          <span style={{ color: 'var(--tesla-text-secondary)', fontSize: 13 }}>Total Deuda</span>
          <span style={{ color: '#FF6B6B', fontSize: 14, fontWeight: 700 }}>
            ${simit.total_deuda?.toLocaleString('es-CO')} COP
          </span>
        </div>
      )}

      {/* Last queried */}
      {simit.queried_at && (
        <div style={{ fontSize: 10, color: 'var(--tesla-text-dim)', marginTop: 8, textAlign: 'center' }}>
          Consultado: {new Date(simit.queried_at).toLocaleString()}
        </div>
      )}
    </>
  );
}
