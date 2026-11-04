/**
 * API client barrel.
 *
 * The implementation lives in per-domain modules next to this file:
 *   http.ts      — base URL, shared axios instance, rate-limit / auth events
 *   errors.ts    — typed helpers for reading thrown (axios) errors
 *   types/       — response/request shapes, one file per domain
 *   <domain>.ts  — endpoint groups (vehicle, charge, climate, security, ...)
 *
 * Everything is re-exported here so `import { api, ... } from '../api/client'`
 * keeps working, and `api.<method>` keeps its historical flat namespace.
 */
import { authApi } from './auth';
import { automationsApi } from './automations';
import { chargeApi } from './charge';
import { climateApi } from './climate';
import { dossierApi } from './dossier';
import { energyApi } from './energy';
import { missionControlApi } from './missionControl';
import { notifyApi } from './notify';
import { orderApi } from './order';
import { securityApi } from './security';
import { sourcesApi } from './sources';
import { statusApi } from './status';
import { teslaMateApi } from './teslaMate';
import { vehicleApi } from './vehicle';

export { getBaseUrl, setBaseUrl, onRateLimit, onAuthRequired } from './http';
export { describeError, errorDetailOf, errorMessageOf, errorStatusOf } from './errors';
export * from './types';

export const api = {
  ...statusApi,
  ...vehicleApi,
  ...chargeApi,
  ...climateApi,
  ...securityApi,
  ...notifyApi,
  ...orderApi,
  ...missionControlApi,
  ...dossierApi,
  ...teslaMateApi,
  ...authApi,
  ...sourcesApi,
  ...automationsApi,
  ...energyApi,
};
