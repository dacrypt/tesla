import React, { useState } from 'react';
import { api, DoctorReport } from '../../api/client';
import Spinner from '../../components/icons/Spinner';
import { InfoIcon } from './icons';

/** On-demand TeslaMate stack diagnostics (`/api/teslaMate/doctor`). */
const DoctorCard: React.FC = () => {
  const [doctorReport, setDoctorReport] = useState<DoctorReport | null>(null);
  const [doctorLoading, setDoctorLoading] = useState(false);
  const [doctorError, setDoctorError] = useState<string | null>(null);

  const runDoctor = async () => {
    setDoctorLoading(true);
    setDoctorError(null);
    try {
      const report = await api.getTeslaMateDoctor();
      setDoctorReport(report);
    } catch {
      setDoctorError('No se pudo conectar al API');
    } finally {
      setDoctorLoading(false);
    }
  };

  return (
    <div className="tesla-card">
      <div className="flex-center gap-sm" style={{ marginBottom: 14 }}>
        <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'rgba(249,151,22,0.15)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#F99716' }}>
          <InfoIcon />
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ color: '#ffffff', fontWeight: 600, fontSize: 15 }}>Diagnóstico</div>
          <div style={{ color: '#86888f', fontSize: 12 }}>Estado del stack TeslaMate</div>
        </div>
        <button
          onClick={runDoctor}
          disabled={doctorLoading}
          className="tesla-btn secondary"
          style={{ fontSize: 12, padding: '6px 12px' }}
        >
          {doctorLoading ? <Spinner /> : 'Ejecutar diagnóstico'}
        </button>
      </div>

      {doctorError ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ color: '#FF6B6B', fontSize: 13 }}>{doctorError}</span>
          <button
            onClick={runDoctor}
            className="tesla-btn secondary"
            style={{ fontSize: 11, padding: '4px 10px' }}
          >
            Reintentar
          </button>
        </div>
      ) : doctorReport === null ? (
        <div style={{ color: '#86888f', fontSize: 13, textAlign: 'center', padding: '8px 0' }}>
          Ejecuta el diagnóstico para ver el estado del stack
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {doctorReport.checks.map((check) => (
            <div key={check.name} style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <div className="flex-center gap-xs">
                <span style={{ color: check.ok ? '#0BE881' : '#FF6B6B', fontSize: 15, lineHeight: 1 }}>
                  {check.ok ? '✓' : '✗'}
                </span>
                <span style={{ color: '#ffffff', fontWeight: 600, fontSize: 13 }}>{check.label}</span>
                <span style={{ color: '#86888f', fontSize: 12, marginLeft: 4 }}>{check.message}</span>
              </div>
              {!check.ok && check.hint && (
                <div style={{ paddingLeft: 24, color: '#F99716', fontSize: 11 }}>
                  {'→ '}{check.hint}
                </div>
              )}
            </div>
          ))}
          <div style={{ marginTop: 8, fontWeight: 600, fontSize: 13, color: doctorReport.failed === 0 ? '#0BE881' : '#FF6B6B' }}>
            {doctorReport.failed === 0
              ? 'Todo OK'
              : `${doctorReport.failed}/${doctorReport.total} checks fallaron`}
          </div>
        </div>
      )}
    </div>
  );
};

export default DoctorCard;
