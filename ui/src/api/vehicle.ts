/** Vehicle list, live state, generic commands, fleet, sharing and the SSE stream. */
import { client, getBaseUrl } from './http';
import type {
  CommandPayload,
  CommandResult,
  FleetVehicle,
  LocationState,
  OkResponse,
  Vehicle,
  VehicleAlerts,
  VehicleInvitation,
  VehicleLastSeen,
  VehicleReady,
  VehicleState,
  VehicleSummary,
} from './types';

export const vehicleApi = {
  // Vehicles
  getVehicles: () => client().get<Vehicle[]>('/api/vehicles').then(r => r.data),
  getVehicleList: () => client().get<Vehicle[]>('/api/vehicle/list').then(r => r.data),

  // Vehicle state
  getVehicleState: () => client().get<VehicleState>('/api/vehicle/state').then(r => r.data),
  getVehicleLocation: () => client().get<LocationState>('/api/vehicle/location').then(r => r.data),
  getVehicleSummary: () =>
    client().get<VehicleSummary>('/api/vehicle/summary').then(r => r.data),
  getVehicleReady: () =>
    client().get<VehicleReady>('/api/vehicle/ready').then(r => r.data),
  getVehicleLastSeen: () =>
    client().get<VehicleLastSeen>('/api/vehicle/last-seen').then(r => r.data),

  // Vehicle alerts
  getVehicleAlerts: () => client().get<VehicleAlerts>('/api/vehicle/alerts').then(r => r.data),

  // Commands (generic)
  sendCommand: (payload: CommandPayload) =>
    client().post<CommandResult>('/api/vehicle/command', payload).then(r => r.data),
  wakeVehicle: () => client().post<CommandResult>('/api/vehicle/wake').then(r => r.data),

  // Fleet
  getFleetSummary: () =>
    client().get<FleetVehicle[]>('/api/fleet/summary').then(r => r.data),

  // Vehicle sharing / invitations
  getInvitations: () =>
    client().get<VehicleInvitation[]>('/api/vehicle/invitations').then(r => r.data),
  inviteDriver: (email: string) =>
    client().post<{ ok: boolean; invite_id?: string }>('/api/vehicle/invite', { email }).then(r => r.data),
  revokeInvitation: (inviteId: string) =>
    client().delete<OkResponse>(`/api/vehicle/invite/${encodeURIComponent(inviteId)}`).then(r => r.data),

  // SSE stream URL
  getStreamUrl: () => `${getBaseUrl()}/api/vehicle/stream`,
};
