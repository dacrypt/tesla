/** Vehicle dossier. */
import { client } from './http';
import type { RuntData, SimitData, VehicleDossier } from './types';

export const dossierApi = {
  getDossier: () => client().get<VehicleDossier>('/api/dossier', { timeout: 5000 }).then(r => r.data),
  refreshDossier: () => client().post<VehicleDossier>('/api/dossier/refresh', undefined, { timeout: 120000 }).then(r => r.data),
  getDossierRunt: () => client().get<RuntData>('/api/dossier/runt', { timeout: 15000 }).then(r => r.data),
  getDossierSimit: () => client().get<SimitData>('/api/dossier/simit', { timeout: 15000 }).then(r => r.data),
};
