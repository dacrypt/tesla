/** Charging: live state, commands, sessions, schedules, analytics and curves. */
import { client } from './http';
import { errorStatusOf } from './errors';
import type {
  ChargeCostSummary,
  ChargeCurve,
  ChargeCurveStats,
  ChargeEnrichment,
  ChargeForecast,
  ChargeSchedule,
  ChargeState,
  ChargingSession,
  CommandResult,
  OkResponse,
} from './types';

export const chargeApi = {
  getChargeState: () => client().get<ChargeState>('/api/charge/status').then(r => r.data),
  getChargeVehicle: () => client().get<ChargeState>('/api/vehicle/charge').then(r => r.data),
  getChargeSessions: (limit = 10) =>
    client().get<ChargingSession[]>(`/api/charge/sessions?limit=${limit}`).then(r => r.data),
  getChargeLast: () =>
    client().get<ChargingSession & { source_name: string }>('/api/charge/last').then(r => r.data),
  setChargeLimit: (percent: number) => client().post<CommandResult>('/api/charge/limit', { percent }).then(r => r.data),
  setChargingAmps: (amps: number) => client().post<CommandResult>('/api/charge/amps', { amps }).then(r => r.data),
  startCharge: () => client().post<CommandResult>('/api/charge/start').then(r => r.data),
  stopCharge: () => client().post<CommandResult>('/api/charge/stop').then(r => r.data),

  // Charge schedules
  getChargeSchedules: () =>
    client().get<ChargeSchedule[]>('/api/charge/schedules').then(r => r.data),
  addChargeSchedule: (body: Omit<ChargeSchedule, 'id'>) =>
    client().post<{ ok: boolean; id: number }>('/api/charge/schedules', body).then(r => r.data),
  removeChargeSchedule: (scheduleId: number) =>
    client().delete<OkResponse>(`/api/charge/schedules/${scheduleId}`).then(r => r.data),

  // Charge analytics
  getChargeAnalyticsSessions: (limit = 20) =>
    client().get<ChargingSession[]>(`/api/charge/analytics/sessions?limit=${limit}`).then(r => r.data),
  getChargeCostSummary: () =>
    client().get<ChargeCostSummary>('/api/charge/analytics/cost-summary').then(r => r.data),
  getChargeForecast: () =>
    client().get<ChargeForecast>('/api/charge/analytics/forecast').then(r => r.data),

  // Charge curves (TeslaMate)
  getChargingCurve: (processId: number, maxSamples = 500) =>
    client().get<ChargeCurve>(`/api/teslaMate/charging/${processId}/curve`, { params: { max_samples: maxSamples } }).then(r => r.data),
  getChargingStats: (processId: number) =>
    client().get<ChargeCurveStats>(`/api/teslaMate/charging/${processId}/stats`).then(r => r.data),
  getChargingEnrichment: (processId: number) =>
    client().get<ChargeEnrichment>(`/api/teslaMate/charging/${processId}/enrichment`)
      .then(r => r.data)
      .catch((e: unknown) => {
        const status = errorStatusOf(e);
        if (status === 404 || status === 503) return null;
        throw e;
      }) as Promise<ChargeEnrichment | null>,
};
