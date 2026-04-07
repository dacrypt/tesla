import { useState, useEffect, useCallback } from 'react';
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
  const [preDelivery, setPreDelivery] = useState(false);

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

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Single API call — /api/vehicle/state returns full vehicle_data including sub-states
      const data = await api.getVehicleState();

      // Extract sub-states from the full vehicle_data response
      const chargeState = (data as any).charge_state || null;
      const climateState = (data as any).climate_state || null;

      setState(data);
      setCharge(chargeState);
      setClimate(climateState);
      setStale(false);
      setLastUpdated(new Date());

      // Cache successful data
      localStorage.setItem(CACHE_KEY, JSON.stringify({
        state: data,
        charge: chargeState,
        climate: climateState,
        timestamp: Date.now(),
      }));
    } catch (e: any) {
      if (String(e).includes('412')) {
        setError('Vehicle not accessible (pre-delivery)');
        setPreDelivery(true);
        loadFromCache();
        setConnected(false);
      } else {
        setError('Connection failed');
        loadFromCache();
      }
    } finally {
      setLoading(false);
    }
  }, [loadFromCache]);

  useEffect(() => {
    fetchAll();
    // Only set up polling interval if NOT pre-delivery
    const interval = setInterval(() => {
      if (!preDelivery) fetchAll();
    }, 30000);
    return () => clearInterval(interval);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // SSE stream with exponential backoff reconnection
  // Skip SSE entirely when pre-delivery (vehicle not accessible)
  useEffect(() => {
    if (preDelivery) return;
    let es: EventSource | null = null;
    let retryCount = 0;
    let retryTimeout: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const connect = () => {
      if (cancelled) return;
      try {
        es = new EventSource(api.getStreamUrl());
        es.onopen = () => {
          setConnected(true);
          retryCount = 0;
        };
        es.onmessage = (evt) => {
          try {
            const data = JSON.parse(evt.data);
            if (data.battery_level !== undefined) {
              setState(prev => prev ? { ...prev, ...data } : data);
              if (data.charge_limit_soc !== undefined) {
                setCharge(prev => prev ? { ...prev, ...data } : data);
              }
            }
            setLastUpdated(new Date());
          } catch {
            // ignore parse errors
          }
        };
        es.onerror = () => {
          setConnected(false);
          es?.close();
          es = null;
          if (!cancelled) {
            const delay = Math.min(1000 * Math.pow(2, retryCount), 30000);
            retryTimeout = setTimeout(() => {
              retryCount++;
              connect();
            }, delay);
          }
        };
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
  }, []);

  return { state, charge, climate, loading, error, refresh: fetchAll, lastUpdated, connected, stale };
}
