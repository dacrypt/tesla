import { useState, useEffect, useCallback, useRef } from 'react';
import { api, VehicleState, ChargeState, ClimateState } from '../api/client';
import { subscribe, isConnected } from './sseHub';

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

  // SSE stream — receives push updates from shared hub connection
  useEffect(() => {
    if (preDeliveryRef.current) return;

    // Subscribe to vehicle state updates
    const unsubVehicle = subscribe('vehicle', (evt) => {
      try {
        const parsed = JSON.parse(evt.data);
        const data = parsed.data || parsed;
        if (data.battery_level !== undefined || data.charge_state) {
          applyData(data);
          setConnected(true);
        }
      } catch {
        // ignore parse errors
      }
    });

    // Subscribe to error events (pre-delivery, asleep, etc.)
    const unsubError = subscribe('error', (evt) => {
      try {
        const parsed = JSON.parse(evt.data);
        if (parsed.error === 'pre_delivery') {
          preDeliveryRef.current = true;
          setError('Vehicle not accessible (pre-delivery)');
          setConnected(false);
        }
      } catch {
        // ignore
      }
    });

    // Track connection state
    const checkInterval = setInterval(() => {
      setConnected(isConnected());
    }, 5000);

    return () => {
      unsubVehicle();
      unsubError();
      clearInterval(checkInterval);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return { state, charge, climate, loading, error, refresh, lastUpdated, connected, stale };
}
