import { useState, useEffect, useCallback } from 'react';
import { api, VehicleDossier, RuntData, SimitData } from '../api/client';

export interface DossierData {
  dossier: VehicleDossier | null;
  runtLive: RuntData | null;
  simitLive: SimitData | null;
  loading: boolean;
  runtLoading: boolean;
  simitLoading: boolean;
  error: string | null;
  runtError: string | null;
  simitError: string | null;
  refresh: () => Promise<void>;
  refreshRunt: () => Promise<void>;
  refreshSimit: () => Promise<void>;
}

export function useDossierData(): DossierData {
  const [dossier, setDossier] = useState<VehicleDossier | null>(null);
  const [runtLive, setRuntLive] = useState<RuntData | null>(null);
  const [simitLive, setSimitLive] = useState<SimitData | null>(null);
  const [loading, setLoading] = useState(true);
  const [runtLoading, setRuntLoading] = useState(false);
  const [simitLoading, setSimitLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runtError, setRuntError] = useState<string | null>(null);
  const [simitError, setSimitError] = useState<string | null>(null);

  // Load cached dossier (fast)
  const fetchCached = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await api.getDossier();
      setDossier(d);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to load dossier';
      // 404 means no dossier built yet — not an error per se
      if (msg.includes('404') || msg.includes('No dossier')) {
        setError('no_dossier');
      } else if (msg.includes('Network Error') || msg.includes('ECONNREFUSED') || msg.includes('timeout')) {
        setError('no_dossier');
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  // Full rebuild (slow)
  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await api.refreshDossier();
      setDossier(d);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Refresh failed');
    } finally {
      setLoading(false);
    }
  }, []);

  // Independent RUNT query
  const refreshRunt = useCallback(async () => {
    setRuntLoading(true);
    setRuntError(null);
    try {
      const r = await api.getDossierRunt();
      setRuntLive(r);
    } catch (e: unknown) {
      setRuntError(e instanceof Error ? e.message : 'RUNT query failed');
    } finally {
      setRuntLoading(false);
    }
  }, []);

  // Independent SIMIT query
  const refreshSimit = useCallback(async () => {
    setSimitLoading(true);
    setSimitError(null);
    try {
      const s = await api.getDossierSimit();
      setSimitLive(s);
    } catch (e: unknown) {
      setSimitError(e instanceof Error ? e.message : 'SIMIT query failed');
    } finally {
      setSimitLoading(false);
    }
  }, []);

  // On mount: load cached, then fire RUNT + SIMIT in parallel
  useEffect(() => {
    fetchCached();
  }, [fetchCached]);

  return {
    dossier, runtLive, simitLive,
    loading, runtLoading, simitLoading,
    error, runtError, simitError,
    refresh, refreshRunt, refreshSimit,
  };
}
