import { useState, useEffect, useCallback, useRef } from 'react';
import { api, VehicleState, ChargeState, ClimateState } from '../api/client';

const CACHE_KEY = 'tesla_vehicle_data_cache';

export interface VehicleData {
  state: VehicleState | null;
  charge: ChargeState | null;
  climate: ClimateState | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
  lastUpdated: Date | null;
  connected: boolean;
  stale: boolean;
}

export function useVehicleData(): VehicleData {
  const [state, setState] = useState<VehicleState | null>(null);
  const [charge, setCharge] = useState<ChargeState | null>(null);
  const [climate, setClimate] = useState<ClimateState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [connected, setConnected] = useState(false);
  const [stale, setStale] = useState(false);
  const preDeliveryRef = useRef(false);

  const loadFromCache = useCallback(() => {
    try {
      const cached = localStorage.getItem(CACHE_KEY);
      if (cached) {
        const data = JSON.parse(cached);
        if (data.state) setState(data.state);
        if (data.charge) setCharge(data.charge);
        if (data.climate) setClimate(data.climate);
        setStale(true);
      }
    } catch {
      // ignore parse errors
    }
  }, []);

  const applyData = useCallback((data: any) => {
    const chargeState = data.charge_state || null;
    const climateState = data.climate_state || null;

    setState(data);
    setCharge(chargeState);
    setClimate(climateState);
    setStale(false);
    setLastUpdated(new Date());

    localStorage.setItem(CACHE_KEY, JSON.stringify({
      state: data,
      charge: chargeState,
      climate: climateState,
      timestamp: Date.now(),
    }));
  }, []);

  // Initial fetch — single request for first paint
  const fetchInitial = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getVehicleState();
      applyData(data);
    } catch (e: any) {
      if (String(e).includes('412')) {
        setError('Vehicle not accessible (pre-delivery)');
        preDeliveryRef.current = true;
        loadFromCache();
      } else {
        setError('Connection failed');
        loadFromCache();
      }
    } finally {
      setLoading(false);
    }
  }, [applyData, loadFromCache]);

  // Manual refresh — invalidates hub cache server-side then re-fetches
  const refresh = useCallback(async () => {
    try {
      const data = await api.getVehicleState();
      applyData(data);
    } catch {
      // silent — SSE will bring updates
    }
  }, [applyData]);

  // Initial fetch on mount
  useEffect(() => {
    fetchInitial();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // SSE stream — receives push updates from backend hub
  useEffect(() => {
    if (preDeliveryRef.current) return;

    let es: EventSource | null = null;
    let retryCount = 0;
    let retryTimeout: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const connect = () => {
      if (cancelled || preDeliveryRef.current) return;
      try {
        es = new EventSource(api.getStreamUrl());
        es.onopen = () => {
          setConnected(true);
          retryCount = 0;
        };

        // Vehicle state updates from hub
        es.addEventListener('vehicle', (evt) => {
          try {
            const parsed = JSON.parse(evt.data);
            const data = parsed.data || parsed;
            if (data.battery_level !== undefined || data.charge_state) {
              applyData(data);
            }
          } catch {
            // ignore parse errors
          }
        });

        // Error events (pre-delivery, asleep, etc.)
        es.addEventListener('error', (evt) => {
          try {
            // SSE spec fires generic error on disconnect — check if it's our custom event
            if (evt instanceof MessageEvent && evt.data) {
              const parsed = JSON.parse(evt.data);
              if (parsed.error === 'pre_delivery') {
                preDeliveryRef.current = true;
                setError('Vehicle not accessible (pre-delivery)');
                setConnected(false);
                es?.close();
                return;
              }
            }
          } catch {
            // Not a JSON error event — it's a connection error
          }

          setConnected(false);
          es?.close();
          es = null;
          if (!cancelled && !preDeliveryRef.current) {
            const delay = Math.min(1000 * Math.pow(2, retryCount), 30000);
            retryTimeout = setTimeout(() => {
              retryCount++;
              connect();
            }, delay);
          }
        });
      } catch {
        // SSE not available
      }
    };

    connect();

    return () => {
      cancelled = true;
      if (retryTimeout) clearTimeout(retryTimeout);
      if (es) es.close();
      setConnected(false);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return { state, charge, climate, loading, error, refresh, lastUpdated, connected, stale };
}
