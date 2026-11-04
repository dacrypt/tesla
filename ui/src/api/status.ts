/** Server status, configuration and providers. */
import { client } from './http';
import type { ProviderStatus, ServerStatus, TeslaConfig } from './types';

export const statusApi = {
  getStatus: () => client().get<ServerStatus>('/api/status').then(r => r.data),
  getConfig: () => client().get<TeslaConfig>('/api/config').then(r => r.data),
  getProviders: () => client().get<ProviderStatus[]>('/api/providers').then(r => r.data),
};
