import React from 'react';
import { RuntData } from '../../api/client';

interface Props {
  runt?: RuntData;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
}

function StatusPill({ label, ok, trueText, falseText }: { label: string; ok?: boolean; trueText?: string; falseText?: string }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, flex: 1,
    }}>
      <div style={{
        background: ok ? 'rgba(11,232,129,0.12)' : 'rgba(255,107,107,0.12)',
        color: ok ? '#0BE881' : '#FF6B6B',
        border: `1px solid ${ok ? 'rgba(11,232,129,0.25)' : 'rgba(255,107,107,0.25)'}`,
        borderRadius: 100, padding: '4px 10px',
        fontSize: 11, fontWeight: 600, whiteSpace: 'nowrap',
      }}>
        {ok ? (trueText || 'OK') : (falseText || 'No')}
      </div>
      <span style={{ fontSize: 8, color: 'var(--tesla-text-secondary)', textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.05em' }}>{label}</span>
    </div>
  );
}

export default function RuntCard({ runt, loading, error, onRetry }: Props) {
  if (loading) {
    return (
      <div style={{ padding: 20, textAlign: 'center' }}>
        <div className="spinner" style={{ width: 20, height: 20, border: '2px solid var(--tesla-border)', borderTopColor: 'var(--tesla-green)', borderRadius: '50%', animation: 'spin .7s linear infinite', display: 'inline-block' }} />
        <div style={{ fontSize: 12, color: 'var(--tesla-text-secondary)', marginTop: 8 }}>Querying RUNT...</div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
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

  if (!runt || !runt.estado) {
    return <div style={{ fontSize: 12, color: 'var(--tesla-text-secondary)', textAlign: 'center', padding: 16 }}>No RUNT data available</div>;
  }

  const details: [string, string | number | undefined][] = [
    ['Estado', runt.estado],
    ['Placa', runt.placa || 'Sin asignar'],
    ['Marca', runt.marca],
    ['Linea', runt.linea],
    ['A\u00f1o', runt.modelo_ano],
    ['Color', runt.color],
    ['Combustible', runt.tipo_combustible],
    ['Carrocer\u00eda', runt.tipo_carroceria],
    ['Puertas', runt.puertas],
    ['Pasajeros', runt.capacidad_pasajeros],
    ['Peso Bruto', runt.peso_bruto_kg ? `${runt.peso_bruto_kg} kg` : undefined],
    ['Ejes', runt.numero_ejes],
    ['Matr\u00edcula', runt.fecha_matricula],
    ['Autoridad', runt.autoridad_transito],
    ['Pa\u00eds', runt.nombre_pais],
  ];

  return (
    <>
      {/* Status pills */}
      <div style={{ display: 'flex', gap: 6, marginBottom: 14, flexWrap: 'wrap', justifyContent: 'center' }}>
        <StatusPill label="Estado" ok={runt.estado === 'REGISTRADO' || runt.estado === 'MATRICULADO'} trueText={runt.estado} falseText={runt.estado || 'N/R'} />
        <StatusPill label="SOAT" ok={runt.soat_vigente} trueText="Vigente" falseText="Vencido" />
        <StatusPill label="RTM" ok={runt.tecnomecanica_vigente} trueText="Vigente" falseText="Vencida" />
        <StatusPill label="Grav\u00e1menes" ok={!runt.gravamenes} trueText="Libre" falseText="S\u00ed" />
        <StatusPill label="Prendas" ok={!runt.prendas} trueText="Libre" falseText="S\u00ed" />
      </div>

      {/* SOAT details */}
      {runt.soat_aseguradora && (
        <div style={{ fontSize: 11, color: 'var(--tesla-text-secondary)', marginBottom: 8, textAlign: 'center' }}>
          SOAT: {runt.soat_aseguradora} &middot; Vence: {runt.soat_vencimiento}
        </div>
      )}

      {/* Detail rows */}
      {details.filter(([, v]) => v != null && v !== '' && v !== 0).map(([label, val]) => (
        <div key={label} className="stat-row">
          <span style={{ color: 'var(--tesla-text-secondary)', fontSize: 12 }}>{label}</span>
          <span style={{ color: 'var(--tesla-text)', fontSize: 12, fontWeight: 500 }}>{val}</span>
        </div>
      ))}

      {/* Last queried */}
      {runt.queried_at && (
        <div style={{ fontSize: 10, color: 'var(--tesla-text-dim)', marginTop: 8, textAlign: 'center' }}>
          Consultado: {new Date(runt.queried_at).toLocaleString()}
        </div>
      )}
    </>
  );
}
