/** TeslaMate analytics, the managed Docker stack and its doctor. */
import { client } from './http';
import type {
  ChargeStat,
  CostReport,
  DailyEnergyEntry,
  DoctorReport,
  DrivePathPoint,
  EfficiencyEntry,
  GeoPoint,
  HeatmapDay,
  StackLogs,
  StackStatus,
  Stats,
  TeslaMateTimelineEvent,
  TripStat,
  TripStatsReport,
  VampireReport,
} from './types';

export const teslaMateApi = {
  getTrips: (limit = 50) => client().get<TripStat[]>(`/api/teslaMate/trips?limit=${limit}`).then(r => r.data),
  getGeoLocations: () => client().get<GeoPoint[]>('/api/teslaMate/geo').then(r => r.data),
  getDrivePath: (driveId: number) => client().get<DrivePathPoint[]>(`/api/teslaMate/drive-path/${driveId}`).then(r => r.data),
  getCharges: () => client().get<ChargeStat[]>('/api/teslaMate/charges').then(r => r.data),
  getStats: () => client().get<Stats>('/api/teslaMate/stats').then(r => r.data),
  getEfficiency: () => client().get<EfficiencyEntry[]>('/api/teslaMate/efficiency').then(r => r.data),
  getVampire: () => client().get<VampireReport>('/api/teslaMate/vampire').then(r => r.data),
  getCostReport: () => client().get<CostReport>('/api/teslaMate/cost-report').then(r => r.data),
  getTripStats: () => client().get<TripStatsReport>('/api/teslaMate/trip-stats').then(r => r.data),
  getDailyEnergy: () => client().get<DailyEnergyEntry[]>('/api/teslaMate/daily-energy').then(r => r.data),
  getTimeline: () => client().get<TeslaMateTimelineEvent[]>('/api/teslaMate/timeline').then(r => r.data),
  getHeatmap: () => client().get<HeatmapDay[]>('/api/teslaMate/heatmap').then(r => r.data),
  getMonthlyReport: (month: string) =>
    client().get<unknown>(`/api/teslaMate/report/${month}`).then(r => r.data),

  // TeslaMate managed stack
  getStackStatus: () =>
    client().get<StackStatus>('/api/teslaMate/stack/status').then(r => r.data),
  stackStart: () =>
    client().post<{ ok: boolean }>('/api/teslaMate/stack/start').then(r => r.data),
  stackStop: () =>
    client().post<{ ok: boolean }>('/api/teslaMate/stack/stop').then(r => r.data),
  stackRestart: () =>
    client().post<{ ok: boolean }>('/api/teslaMate/stack/restart').then(r => r.data),
  stackUpdate: () =>
    client().post<{ ok: boolean; output?: string }>('/api/teslaMate/stack/update', {}, { timeout: 120000 }).then(r => r.data),
  getStackLogs: (service?: string, lines = 80) =>
    client().get<StackLogs>('/api/teslaMate/stack/logs', {
      params: { service: service || '', lines },
    }).then(r => r.data),

  getTeslaMateDoctor: () =>
    client().get<DoctorReport>('/api/teslaMate/doctor').then(r => r.data),
};
