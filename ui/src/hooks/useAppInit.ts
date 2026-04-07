/**
 * useAppInit — single request for all initial app data.
 *
 * Fetches /api/init once per session, providing dossier, auth,
 * automations, and vehicle state in one payload. Eliminates
 * waterfall loading and UI flicker.
 */
import { useState, useEffect, useCallback } from 'react';
import { api, VehicleDossier } from '../api/client';
import { seedDossierCache } from './useDossierData';

export interface AppInitData {
  dossier: VehicleDossier | null;
  auth: {
    authenticated: boolean;
    backend: string;
    has_fleet: boolean;
    has_order: boolean;
    has_tessie: boolean;
  } | null;
  automations: {
    total: number;
    enabled: number;
  } | null;
  vehicle: Record<string, unknown> | null;
  loading: boolean;
  error: string | null;
}

// Module-level cache — one fetch per session
let _initData: Omit<AppInitData, 'loading' | 'error'> | null = null;
let _initPromise: Promise<void> | null = null;
let _initLoaded = false;

// Listeners for source-driven updates
const _initListeners: Set<() => void> = new Set();

export function useAppInit(): AppInitData {
  const [data, setData] = useState<Omit<AppInitData, 'loading' | 'error'> | null>(_initData);
  const [loading, setLoading] = useState(!_initLoaded);
  const [error, setError] = useState<string | null>(null);

  const fetchInit = useCallback(async () => {
    if (_initLoaded && _initData) {
      setData(_initData);
      setLoading(false);
      return;
    }

    if (_initPromise) {
      await _initPromise;
      setData(_initData);
      setLoading(false);
      return;
    }

    setLoading(true);

    _initPromise = (async () => {
      try {
        const result = await api.getInit();
        _initData = {
          dossier: result.dossier || null,
          auth: result.auth || null,
          automations: result.automations || null,
          vehicle: result.vehicle || null,
        };
        // Seed dossier cache so useDossierData() won't make a separate request
        if (result.dossier) {
          seedDossierCache(result.dossier);
        }
      } catch {
        // /api/init not available — fallback to individual requests
        const [dossierResult, authResult, autoResult] = await Promise.allSettled([
          api.getDossier(),
          api.getAuthStatus(),
          api.getAutomationsStatus(),
        ]);
        const dossier = dossierResult.status === 'fulfilled' ? dossierResult.value : null;
        const auth = authResult.status === 'fulfilled' ? authResult.value : null;
        const automations = autoResult.status === 'fulfilled' ? autoResult.value : null;

        _initData = { dossier, auth, automations, vehicle: null };
        if (dossier) seedDossierCache(dossier);
      } finally {
        _initLoaded = true;
        _initPromise = null;
      }
    })();

    await _initPromise;
    setData(_initData);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchInit();

    // Subscribe to updates from source events
    const onUpdate = () => setData(_initData ? { ..._initData } : null);
    _initListeners.add(onUpdate);
    return () => { _initListeners.delete(onUpdate); };
  }, [fetchInit]);

  return {
    dossier: data?.dossier ?? null,
    auth: data?.auth ?? null,
    automations: data?.automations ?? null,
    vehicle: data?.vehicle ?? null,
    loading,
    error,
  };
}

/** Update the cached dossier (called when source events arrive). */
export function updateInitDossier(dossier: VehicleDossier): void {
  if (_initData) {
    _initData = { ..._initData, dossier };
    _initListeners.forEach(fn => fn());
  }
}
