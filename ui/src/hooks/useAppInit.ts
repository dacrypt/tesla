/**
 * useAppInit — single request for all initial app data.
 *
 * Fetches /api/init once per session. Returns source data (order, runt),
 * computed fields (real_status, specs), auth, automations, and vehicle.
 * Falls back to individual requests if /api/init is unavailable.
 */
import { useState, useEffect, useCallback } from 'react';
import { api } from '../api/client';
import { subscribe } from './sseHub';

export interface RealStatus {
  phase: string;
  phase_description: string;
  tesla_api_status: string;
  runt_status: string;
  vin_assigned: boolean;
  in_runt: boolean;
  has_placa: boolean;
  has_soat: boolean;
  delivery_date: string;
  delivery_location: string;
  delivery_appointment: string;
  is_produced: boolean;
  is_shipped: boolean;
  is_in_country: boolean;
  is_customs_cleared: boolean;
  is_registered: boolean;
  is_delivery_scheduled: boolean;
  is_delivered: boolean;
}

export interface VehicleSpecs {
  model: string;
  variant: string;
  generation: string;
  model_year: number;
  exterior_color: string;
  interior: string;
  wheels: string;
  battery_type: string;
  range_km: number;
  horsepower: number;
  [key: string]: unknown;
}

export interface AppInitData {
  sources: {
    order: Record<string, any> | null;
    runt: Record<string, any> | null;
  };
  computed: {
    real_status: RealStatus | null;
    specs: VehicleSpecs | null;
  };
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

const _initListeners: Set<() => void> = new Set();

const EMPTY_SOURCES = { order: null, runt: null };
const EMPTY_COMPUTED = { real_status: null, specs: null };

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
          sources: result.sources || EMPTY_SOURCES,
          computed: result.computed || EMPTY_COMPUTED,
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
            order: dossier?.order || null,
            runt: dossier?.runt || null,
          },
          computed: {
            real_status: (dossier?.real_status as any) || null,
            specs: (dossier?.specs as any) || null,
          },
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
      // Source changed — re-fetch init to get updated computed fields
      api.getInit()
        .then(result => {
          _initData = {
            sources: result.sources || EMPTY_SOURCES,
            computed: result.computed || EMPTY_COMPUTED,
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
    auth: data?.auth ?? null,
    automations: data?.automations ?? null,
    vehicle: data?.vehicle ?? null,
    loading,
    error,
  };
}
