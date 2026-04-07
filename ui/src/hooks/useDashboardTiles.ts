import { useState, useEffect } from 'react';

export interface TileConfig {
  id: string;
  label: string;
  enabled: boolean;
  order: number;
}

const STORAGE_KEY = 'dashboard_tiles_v1';

const DEFAULT_TILES: TileConfig[] = [
  { id: 'orderProcess', label: 'Order Process', enabled: true, order: 0 },
  { id: 'battery', label: 'Battery & Charging', enabled: true, order: 1 },
  { id: 'climate', label: 'Climate', enabled: true, order: 2 },
  { id: 'location', label: 'Location', enabled: true, order: 3 },
  { id: 'vehicle', label: 'Vehicle State', enabled: true, order: 4 },
  { id: 'quickActions', label: 'Quick Actions', enabled: true, order: 5 },
  { id: 'recentCharges', label: 'Recent Charges', enabled: true, order: 6 },
  { id: 'schedule', label: 'Charge Schedule', enabled: true, order: 7 },
  { id: 'map', label: 'Map', enabled: true, order: 8 },
  { id: 'fleet', label: 'Fleet Health', enabled: true, order: 9 },
  { id: 'documents', label: 'Documentos', enabled: true, order: 10 },
  { id: 'infractions', label: 'Infracciones', enabled: true, order: 11 },
];

function loadTiles(): TileConfig[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_TILES;
    const saved: TileConfig[] = JSON.parse(raw);
    // Merge: keep saved settings but add any new default tiles missing from saved
    const savedIds = new Set(saved.map((t) => t.id));
    const merged = [...saved];
    let nextOrder = saved.reduce((max, t) => Math.max(max, t.order), -1) + 1;
    for (const def of DEFAULT_TILES) {
      if (!savedIds.has(def.id)) {
        merged.push({ ...def, order: nextOrder++ });
      }
    }
    return merged;
  } catch {
    return DEFAULT_TILES;
  }
}

function saveTiles(tiles: TileConfig[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(tiles));
  } catch {
    // ignore storage errors
  }
}

export function useDashboardTiles() {
  const [tiles, setTiles] = useState<TileConfig[]>(loadTiles);

  useEffect(() => {
    saveTiles(tiles);
  }, [tiles]);

  const toggleTile = (id: string) => {
    setTiles((prev) => prev.map((t) => (t.id === id ? { ...t, enabled: !t.enabled } : t)));
  };

  const moveTile = (id: string, direction: 'up' | 'down') => {
    setTiles((prev) => {
      const sorted = [...prev].sort((a, b) => a.order - b.order);
      const idx = sorted.findIndex((t) => t.id === id);
      if (idx === -1) return prev;
      const swapIdx = direction === 'up' ? idx - 1 : idx + 1;
      if (swapIdx < 0 || swapIdx >= sorted.length) return prev;
      // Swap orders
      const newTiles = prev.map((t) => {
        if (t.id === sorted[idx].id) return { ...t, order: sorted[swapIdx].order };
        if (t.id === sorted[swapIdx].id) return { ...t, order: sorted[idx].order };
        return t;
      });
      return newTiles;
    });
  };

  const resetTiles = () => {
    setTiles(DEFAULT_TILES);
  };

  const enabledTiles = tiles.filter((t) => t.enabled).sort((a, b) => a.order - b.order);
  const allTiles = [...tiles].sort((a, b) => a.order - b.order);

  return { tiles: enabledTiles, allTiles, toggleTile, moveTile, resetTiles };
}
