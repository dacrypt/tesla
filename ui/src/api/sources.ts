/** Registered data sources and the Colombian /api/co/* helpers. */
import { client } from './http';
import type {
  ColombiaSourceResult,
  EstacionesEV,
  MissingAuthEntry,
  PicoYPlaca,
  RefreshStaleResult,
  SourceAudit,
  SourceConfig,
  SourceConfigUpdateResult,
  SourceHistoryEntry,
  SourceInfo,
  SourceQueryEntry,
  SourceRefreshResult,
  SourceSnapshot,
} from './types';

export const sourcesApi = {
  // Data Sources
  getSources: () =>
    client().get<SourceInfo[]>('/api/sources').then(r => r.data),
  getSource: (id: string) =>
    client().get<SourceSnapshot>(`/api/sources/${id}`).then(r => r.data),
  refreshSource: (id: string) =>
    client().post<SourceRefreshResult>(`/api/sources/${id}/refresh`).then(r => r.data),
  refreshStaleSources: () =>
    client().post<RefreshStaleResult>('/api/sources/refresh-stale').then(r => r.data),
  getMissingAuth: () =>
    client().get<MissingAuthEntry[]>('/api/sources/missing-auth').then(r => r.data),
  getSourceHistory: (id: string, limit = 10) =>
    client().get<SourceHistoryEntry[]>(`/api/sources/${id}/history?limit=${limit}`).then(r => r.data),
  getSourceQueries: (id: string, limit = 10) =>
    client().get<SourceQueryEntry[]>(`/api/sources/${id}/queries?limit=${limit}`).then(r => r.data),
  getSourceAudits: (id: string) =>
    client().get<SourceAudit[]>(`/api/sources/${id}/audits`).then(r => r.data),
  getSourceConfig: () =>
    client().get<SourceConfig>('/api/sources/config').then(r => r.data),
  updateSourceConfig: (data: { cedula?: string; vin?: string }) =>
    client().post<SourceConfigUpdateResult>('/api/sources/config', data).then(r => r.data),

  // Colombia sources
  getPicoYPlaca: (placa?: string) =>
    client().get<PicoYPlaca>('/api/co/pico-y-placa', { params: { placa: placa || '' } }).then(r => r.data),
  getEstacionesEV: (ciudad?: string) =>
    client().get<EstacionesEV>('/api/co/estaciones-ev', { params: { ciudad: ciudad || '' } }).then(r => r.data),
  getFasecolda: () =>
    client().get<ColombiaSourceResult>('/api/co/fasecolda').then(r => r.data),
  getRecallsSIC: () =>
    client().get<ColombiaSourceResult>('/api/co/recalls-sic').then(r => r.data),
  getPeajes: (ruta?: string) =>
    client().get<ColombiaSourceResult>('/api/co/peajes', { params: { ruta: ruta || '' } }).then(r => r.data),
};
