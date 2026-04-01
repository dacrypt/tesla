import { useState, useEffect, useCallback } from 'react';
import { api, VehicleState, ChargeState, ClimateState } from '../api/client';

export interface VehicleData {
  state: VehicleState | null;
  charge: ChargeState | null;
  climate: ClimateState | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
  lastUpdated: Date | null;
}

export function useVehicleData(): VehicleData {
  const [state, setState] = useState<VehicleState | null>(null);
  const [charge, setCharge] = useState<ChargeState | null>(null);
  const [climate, setClimate] = useState<ClimateState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [s, ch, cl] = await Promise.allSettled([
        api.getVehicleState(),
        api.getChargeState(),
        api.getClimateState(),
      ]);
      if (s.status === 'fulfilled') setState(s.value);
      if (ch.status === 'fulfilled') setCharge(ch.value);
      if (cl.status === 'fulfilled') setClimate(cl.value);
      if (s.status === 'rejected' && ch.status === 'rejected' && cl.status === 'rejected') {
        setError('Vehicle not connected');
      }
      setLastUpdated(new Date());
    } catch (e) {
      setError('Connection failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  // SSE stream
  useEffect(() => {
    let es: EventSource | null = null;
    try {
      es = new EventSource(api.getStreamUrl());
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
        // SSE errors are expected when vehicle is offline
      };
    } catch {
      // SSE not available
    }
    return () => {
      if (es) es.close();
    };
  }, []);

  return { state, charge, climate, loading, error, refresh: fetchAll, lastUpdated };
}
