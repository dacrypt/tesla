/** Locks, sentry, trunks, horn and lights. */
import { client } from './http';
import type { CommandResult, SentryStatus } from './types';

export const securityApi = {
  lockDoors: () => client().post<CommandResult>('/api/security/lock').then(r => r.data),
  unlockDoors: () => client().post<CommandResult>('/api/security/unlock').then(r => r.data),
  getSentryStatus: () => client().get<SentryStatus>('/api/security/sentry').then(r => r.data),
  sentryOn: () => client().post<CommandResult>('/api/security/sentry/on').then(r => r.data),
  sentryOff: () => client().post<CommandResult>('/api/security/sentry/off').then(r => r.data),
  openFrunk: () => client().post<CommandResult>('/api/security/trunk/front').then(r => r.data),
  openTrunk: () => client().post<CommandResult>('/api/security/trunk/rear').then(r => r.data),
  honkHorn: () => client().post<CommandResult>('/api/security/horn').then(r => r.data),
  flashLights: () => client().post<CommandResult>('/api/security/flash').then(r => r.data),
};
