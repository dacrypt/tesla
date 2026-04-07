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

// Module-level session cache — survives component unmounts, shared across pages
let _cachedDossier: VehicleDossier | null = null;
let _cacheError: string | null = null;
let _cacheLoaded = false;
let _cachePromise: Promise<void> | null = null;

export function useDossierData(): DossierData {
  const [dossier, setDossier] = useState<VehicleDossier | null>(_cachedDossier);
  const [runtLive, setRuntLive] = useState<RuntData | null>(null);
  const [simitLive, setSimitLive] = useState<SimitData | null>(null);
  const [loading, setLoading] = useState(!_cacheLoaded);
  const [runtLoading, setRuntLoading] = useState(false);
  const [simitLoading, setSimitLoading] = useState(false);
  const [error, setError] = useState<string | null>(_cacheError);
  const [runtError, setRuntError] = useState<string | null>(null);
  const [simitError, setSimitError] = useState<string | null>(null);

  // Load cached dossier — fetches once per session, reuses across components
  const fetchCached = useCallback(async () => {
    if (_cacheLoaded) {
      setDossier(_cachedDossier);
      setError(_cacheError);
      setLoading(false);
      return;
    }

    // Deduplicate: if another component already started the fetch, wait for it
    if (_cachePromise) {
      await _cachePromise;
      setDossier(_cachedDossier);
      setError(_cacheError);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    _cachePromise = (async () => {
      try {
        const d = await api.getDossier();
        _cachedDossier = d;
        _cacheError = null;
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : 'Failed to load dossier';
        if (msg.includes('404') || msg.includes('No dossier') || msg.includes('Network Error') || msg.includes('ECONNREFUSED') || msg.includes('timeout')) {
          _cacheError = 'no_dossier';
        } else {
          _cacheError = 'no_dossier';
        }
      } finally {
        _cacheLoaded = true;
        _cachePromise = null;
      }
    })();

    await _cachePromise;
    setDossier(_cachedDossier);
    setError(_cacheError);
    setLoading(false);
  }, []);

  // Full rebuild (slow) — also refreshes the session cache
  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await api.refreshDossier();
      _cachedDossier = d;
      _cacheError = null;
      _cacheLoaded = true;
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

  // On mount: load from session cache (instant if already loaded)
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
