/** App init, Mission Control read model, events and alerts. */
import { client } from './http';
import type {
  AlertEvent,
  AppInitResponse,
  DashboardSummary,
  MissionControlData,
  TimelineEvent,
} from './types';

export const missionControlApi = {
  // App init (single request for all startup data)
  getInit: () => client().get<AppInitResponse>('/api/init', { timeout: 10000 }).then(r => r.data),
  getMissionControl: () => client().get<MissionControlData>('/api/mission-control', { timeout: 10000 }).then(r => r.data),
  getDashboardSummary: () => client().get<DashboardSummary>('/api/mission-control/dashboard-summary', { timeout: 10000 }).then(r => r.data),
  getEvents: (limit = 50) => client().get<TimelineEvent[]>(`/api/events?limit=${limit}`, { timeout: 10000 }).then(r => r.data),
  getAlerts: (limit = 50, activeOnly = true) => client().get<AlertEvent[]>(`/api/alerts?limit=${limit}&active_only=${activeOnly}`, { timeout: 10000 }).then(r => r.data),
  ackAlert: (alertId: string) => client().post<AlertEvent>(`/api/alerts/${encodeURIComponent(alertId)}/ack`).then(r => r.data),
};
