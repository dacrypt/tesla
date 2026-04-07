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
      const [s, ch, cl] = await Promise.allSettled([
        api.getVehicleState(),
        api.getChargeState(),
        api.getClimateState(),
      ]);
      const anyFulfilled = s.status === 'fulfilled' || ch.status === 'fulfilled' || cl.status === 'fulfilled';
      if (s.status === 'fulfilled') setState(s.value);
      if (ch.status === 'fulfilled') setCharge(ch.value);
      if (cl.status === 'fulfilled') setClimate(cl.value);
      if (s.status === 'rejected' && ch.status === 'rejected' && cl.status === 'rejected') {
        setError('Vehicle not connected');
        loadFromCache();
      } else if (s.status === 'rejected' || ch.status === 'rejected' || cl.status === 'rejected') {
        // Partial failure — some sources unavailable, show warning but don't block
        const failed = [s, ch, cl].filter(r => r.status === 'rejected').length;
        setError(`${failed} data source(s) unavailable`);
      }
      if (anyFulfilled) {
        setStale(false);
        // Cache successful data
        const newState = s.status === 'fulfilled' ? s.value : state;
        const newCharge = ch.status === 'fulfilled' ? ch.value : charge;
        const newClimate = cl.status === 'fulfilled' ? cl.value : climate;
        localStorage.setItem(CACHE_KEY, JSON.stringify({
          state: newState,
          charge: newCharge,
          climate: newClimate,
          timestamp: Date.now(),
        }));
      }
      setLastUpdated(new Date());
    } catch (e) {
      setError('Connection failed');
      loadFromCache();
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  // SSE stream with exponential backoff reconnection
  useEffect(() => {
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
