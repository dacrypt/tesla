/** Geofences and automation rules. */
import { client } from './http';
import type { AutomationRule, AutomationsStatus, GeofenceZone, OkResponse } from './types';

const rulePath = (name: string) => `/api/automations/${encodeURIComponent(name)}`;

export const automationsApi = {
  // Geofences
  getGeofences: () =>
    client().get<GeofenceZone[]>('/api/geofences').then(r => r.data),
  addGeofence: (name: string, lat: number, lon: number, radius_km: number) =>
    client().post<{ status: string; zone: string }>(`/api/geofences/${encodeURIComponent(name)}`, { lat, lon, radius_km }).then(r => r.data),
  removeGeofence: (name: string) =>
    client().delete<{ status: string; removed: string }>(`/api/geofences/${encodeURIComponent(name)}`).then(r => r.data),

  // Automations
  getAutomations: () =>
    client().get<AutomationRule[]>('/api/automations/').then(r => r.data),
  getAutomationsStatus: () =>
    client().get<AutomationsStatus>('/api/automations/status').then(r => r.data),
  getAutomationRule: (name: string) =>
    client().get<AutomationRule>(rulePath(name)).then(r => r.data),
  createAutomation: (rule: Omit<AutomationRule, 'last_fired'>) =>
    client().post<{ ok: boolean; name: string }>('/api/automations/', rule).then(r => r.data),
  deleteAutomation: (name: string) =>
    client().delete<OkResponse>(rulePath(name)).then(r => r.data),
  enableAutomation: (name: string) =>
    client().post<{ ok: boolean; name: string; enabled: boolean }>(`${rulePath(name)}/enable`).then(r => r.data),
  disableAutomation: (name: string) =>
    client().post<{ ok: boolean; name: string; enabled: boolean }>(`${rulePath(name)}/disable`).then(r => r.data),
  testAutomation: (name: string) =>
    client().post<{ name: string; fired: boolean; message: string; dry_run: boolean }>(`${rulePath(name)}/test`).then(r => r.data),
  toggleAutomation: (name: string, enabled: boolean) =>
    enabled
      ? client().post<OkResponse>(`${rulePath(name)}/enable`).then(r => r.data)
      : client().post<OkResponse>(`${rulePath(name)}/disable`).then(r => r.data),
};
