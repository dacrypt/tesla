/**
 * useAppInit — single request for all initial app data.
 *
 * Fetches /api/init once per session. Returns all source data for the
 * configured country, computed fields, geolocation, auth, automations,
 * and vehicle state. Falls back to individual requests if unavailable.
 */
import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import type {
  GeoLocation,
  InitAuth,
  InitAutomations,
  InitComputed,
  InitRealStatus,
  InitVehicleSpecs,
  SourcesMap,
} from '../api/client';
import { subscribe } from './sseHub';

// Shapes live in api/types/init.ts; re-exported under their historical names.
export type RealStatus = InitRealStatus;
export type VehicleSpecs = InitVehicleSpecs;
export type { GeoLocation, SourcesMap };

export interface AppInitData {
  sources: SourcesMap;
  computed: InitComputed;
  location: GeoLocation | null;
  auth: InitAuth | null;
  automations: InitAutomations | null;
  vehicle: Record<string, unknown> | null;
  loading: boolean;
  error: string | null;
}

// Convenience accessors for common sources
export function getSource(init: AppInitData, sourceId: string): unknown {
  return init.sources[sourceId] ?? null;
}

// Module-level cache — one fetch per session
let _initData: Omit<AppInitData, 'loading' | 'error'> | null = null;
let _initPromise: Promise<void> | null = null;
let _initLoaded = false;

const _initListeners: Set<() => void> = new Set();

const EMPTY_SOURCES: SourcesMap = {};
const EMPTY_COMPUTED = { real_status: null, specs: null };

export function useAppInit(): AppInitData {
  const [data, setData] = useState<Omit<AppInitData, 'loading' | 'error'> | null>(_initData);
  const [loading, setLoading] = useState(!_initLoaded);
  const [error] = useState<string | null>(null);

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
          sources: result.sources || EMPTY_SOURCES,
          computed: result.computed || EMPTY_COMPUTED,
          location: result.location || null,
          auth: result.auth || null,
          automations: result.automations || null,
          vehicle: result.vehicle || null,
        };
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

        // Map dossier fields to new shape for backwards compatibility
        _initData = {
          sources: {
            'tesla.order': dossier?.order || null,
            'co.runt': dossier?.runt || null,
          },
          computed: {
            // Dossier fields are all-optional; /api/init's computed shape is the target.
            real_status: (dossier?.real_status as InitRealStatus | undefined) || null,
            specs: (dossier?.specs as InitVehicleSpecs | undefined) || null,
          },
          location: null,
          auth,
          automations,
          vehicle: null,
        };
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

    // Re-fetch init when sources update via SSE
    const unsub = subscribe('source', () => {
      api.getInit()
        .then(result => {
          _initData = {
            sources: result.sources || EMPTY_SOURCES,
            computed: result.computed || EMPTY_COMPUTED,
            location: result.location || _initData?.location || null,
            auth: _initData?.auth || result.auth || null,
            automations: _initData?.automations || result.automations || null,
            vehicle: _initData?.vehicle || result.vehicle || null,
          };
          _initListeners.forEach(fn => fn());
        })
        .catch(() => {});
    });

    const onUpdate = () => setData(_initData ? { ..._initData } : null);
    _initListeners.add(onUpdate);

    return () => {
      unsub();
      _initListeners.delete(onUpdate);
    };
  }, [fetchInit]);

  return {
    sources: data?.sources ?? EMPTY_SOURCES,
    computed: data?.computed ?? EMPTY_COMPUTED,
    location: data?.location ?? null,
    auth: data?.auth ?? null,
    automations: data?.automations ?? null,
    vehicle: data?.vehicle ?? null,
    loading,
    error,
  };
}
