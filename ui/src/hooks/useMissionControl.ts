import { useCallback, useEffect, useState } from 'react';
import { api, MissionControlData } from '../api/client';
import { subscribe } from './sseHub';

export interface MissionControlState {
  data: MissionControlData | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useMissionControl(enabled = true): MissionControlState {
  const [data, setData] = useState<MissionControlData | null>(null);
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.getMissionControl();
      setData(result);
    } catch (e: any) {
      setError(e?.message || 'Failed to load Mission Control');
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }

    refresh();
    const unsub = subscribe('source', () => {
      refresh().catch(() => {});
    });
    return () => {
      unsub();
    };
  }, [enabled, refresh]);

  return { data, loading, error, refresh };
}
