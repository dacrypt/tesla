/** Registered data sources (core/sources.py) and the Colombian /api/co/* helpers. */

export interface SourceChange {
  field: string;
  old?: string | null;
  new?: string | null;
}

/** One row of /api/sources. */
export interface SourceInfo {
  id: string;
  name: string;
  category: string;
  country?: string;
  requires_auth?: string | boolean | null;
  auto_refresh?: boolean;
  manual_only?: boolean;
  ttl?: number;
  refreshed_at?: string | null;
  stale?: boolean;
  has_data?: boolean;
  error?: string | null;
  uses_playwright?: boolean;
}

/** /api/sources/{id} — cached payload plus metadata. `data` depends on the source. */
export interface SourceSnapshot {
  id: string;
  data: unknown;
  refreshed_at: string | null;
  error: string | null;
  stale: boolean;
  changes?: SourceChange[];
}

/** /api/sources/{id}/refresh — the refresh outcome (shape depends on the source). */
export type SourceRefreshResult = Record<string, unknown>;

/** /api/sources/refresh-stale */
export interface RefreshStaleResult {
  refreshed: string[];
  failed: Array<{ id: string; error: string }>;
}

/** /api/sources/missing-auth */
export interface MissingAuthEntry {
  source: string;
  name: string;
  auth_type: string;
  message: string;
}

/** /api/sources/{id}/history — one snapshot per data change. */
export interface SourceHistoryEntry {
  timestamp?: string;
  data_hash?: string;
  changes?: SourceChange[];
  [key: string]: unknown;
}

/** /api/sources/{id}/queries — request/response audit of each query. */
export interface SourceQueryEntry {
  queried_at?: string;
  status?: string;
  request?: {
    mode?: string;
    source_name?: string;
    url?: string;
    method?: string;
    status_code?: number | null;
    openquery_source?: string;
  };
  response?: {
    error?: string | null;
    normalized_data?: unknown;
    response_text_excerpt?: string;
    raw_output_excerpt?: string;
    raw_error_excerpt?: string;
  };
}

/** /api/sources/{id}/audits — evidence PDFs captured by browser-driven sources. */
export interface SourceAudit {
  filename: string;
  size_kb: number;
  timestamp?: string;
  source: string;
  duration_ms?: number | null;
}

/** GET /api/sources/config */
export interface SourceConfig {
  cedula: string;
  vin: string;
  reservation_number: string;
}

/** POST /api/sources/config */
export interface SourceConfigUpdateResult {
  ok: boolean;
  changed: string[];
}

// ── Colombia (/api/co/*) ───────────────────────────────────────────────────

/** /api/co/pico-y-placa */
export interface PicoYPlaca {
  placa?: string;
  ciudad?: string;
  restringido?: boolean;
  restricted?: boolean;
  motivo?: string;
  message?: string;
  error?: string;
  available?: boolean;
  [key: string]: unknown;
}

export interface EvStation {
  nombre: string;
  ciudad: string;
  direccion: string;
  tipo: string;
  horario: string;
  operador: string;
  latitude: number | string | null;
  longitude: number | string | null;
}

/** /api/co/estaciones-ev */
export interface EstacionesEV {
  total: number;
  ciudad: string;
  estaciones: EvStation[];
}

/** /api/co/fasecolda, /api/co/recalls-sic, /api/co/peajes — openquery payloads. */
export type ColombiaSourceResult = Record<string, unknown>;
