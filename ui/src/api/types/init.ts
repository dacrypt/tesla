/** /api/init — all startup data in one request (see hooks/useAppInit). */
import type { OrderTimeline, RuntData } from './dossier';

/** Computed delivery phase (core real_status). */
export interface InitRealStatus {
  phase: string;
  phase_description: string;
  tesla_api_status: string;
  runt_status: string;
  vin_assigned: boolean;
  in_runt: boolean;
  has_placa: boolean;
  has_soat: boolean;
  delivery_date: string;
  delivery_location: string;
  delivery_appointment: string;
  is_produced: boolean;
  is_shipped: boolean;
  is_in_country: boolean;
  is_customs_cleared: boolean;
  is_registered: boolean;
  is_delivery_scheduled: boolean;
  is_delivered: boolean;
}

export interface InitVehicleSpecs {
  model: string;
  variant: string;
  generation: string;
  model_year: number;
  exterior_color: string;
  interior: string;
  wheels: string;
  battery_type: string;
  range_km: number;
  horsepower: number;
  [key: string]: unknown;
}

export interface GeoLocation {
  lat: number;
  lon: number;
  city: string;
  source: 'vehicle_gps' | 'delivery_cache' | 'config' | 'default';
}

/** `tesla.order` source payload. */
export interface InitOrderSource extends OrderTimeline {
  lastActivityDate?: string;
}

/** `co.runt` source payload (older caches nest the plate under `current`). */
export interface InitRuntSource extends RuntData {
  current?: { placa?: string };
}

/**
 * All source data keyed by source ID (e.g., "tesla.order", "co.runt", "co.simit").
 * The sources the dashboard reads are typed; others are opaque.
 */
export interface SourcesMap {
  'tesla.order'?: InitOrderSource | null;
  'co.runt'?: InitRuntSource | null;
  [sourceId: string]: unknown;
}

export interface InitComputed {
  real_status: InitRealStatus | null;
  specs: InitVehicleSpecs | null;
}

export interface InitAuth {
  authenticated: boolean;
  backend: string;
  has_fleet: boolean;
  has_order: boolean;
  has_tessie: boolean;
}

export interface InitAutomations {
  total: number;
  enabled: number;
}

/** Raw /api/init payload; every section is best-effort and may be null. */
export interface AppInitResponse {
  sources?: SourcesMap | null;
  computed?: InitComputed | null;
  location?: GeoLocation | null;
  auth?: InitAuth | null;
  automations?: InitAutomations | null;
  vehicle?: Record<string, unknown> | null;
  drivers?: unknown[];
}
