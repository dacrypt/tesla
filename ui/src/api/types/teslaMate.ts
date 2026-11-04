/** TeslaMate trips/charges/stats, analytics reports and the managed Docker stack. */

export interface TripStat {
  id?: string;
  /** TeslaMate drive id (used for /api/teslaMate/drive-path); some rows only carry `id`. */
  drive_id?: number | string;
  start_date?: string;
  end_date?: string;
  start_address?: string;
  end_address?: string;
  distance?: number;
  duration?: number;
  energy_used?: number;
  efficiency?: number;
}

export interface ChargeStat {
  id?: string;
  start_date?: string;
  end_date?: string;
  address?: string;
  charge_energy_added?: number;
  cost?: number;
  duration?: number;
  battery_level_start?: number | null;
  battery_level_end?: number | null;
  start_battery_level?: number | null;
  end_battery_level?: number | null;
}

export interface Stats {
  total_trips?: number;
  total_distance?: number;
  total_energy?: number;
  avg_efficiency?: number;
  total_charges?: number;
  total_cost?: number;
}

export interface GeoPoint {
  lat: number;
  lon: number;
}

export interface DrivePathPoint {
  latitude: number;
  longitude: number;
  elevation?: number;
  speed?: number;
  timestamp?: string;
}

// ── Analytics reports ──────────────────────────────────────────────────────
// Field names vary across TeslaMate/back-end versions, so most are optional and
// the dashboard falls back between aliases (e.g. `loss_pct` / `drain_pct`).

/** /api/teslaMate/efficiency — one row per trip. */
export interface EfficiencyEntry {
  start_address?: string;
  address?: string;
  start_date?: string;
  date?: string;
  wh_per_km?: number | null;
  efficiency?: number | null;
  kwh_per_100mi?: number | null;
  distance_km?: number | null;
  energy_kwh?: number | null;
  duration_min?: number | null;
}

/** /api/teslaMate/timeline — drives, charges and software updates. */
export interface TeslaMateTimelineEvent {
  type?: string;
  summary?: string;
  address?: string;
  version?: string;
  start_date?: string;
  date?: string;
  distance_km?: number | null;
  energy_kwh?: number | null;
  energy_added_kwh?: number | null;
}

/** /api/teslaMate/daily-energy */
export interface DailyEnergyEntry {
  date?: string;
  kwh?: number | string | null;
}

/** /api/teslaMate/heatmap — one cell per day. */
export interface HeatmapDay {
  date?: string;
  km?: number | null;
  distance_km?: number | null;
}

export interface CostReportMonth {
  cost?: number | null;
  kwh?: number | null;
  sessions?: number;
}

/** /api/teslaMate/cost-report and /api/teslaMate/report/{month} */
export interface CostReport {
  cost_per_kwh?: number | null;
  months?: Record<string, CostReportMonth>;
  [key: string]: unknown;
}

export interface VampireDay {
  date?: string;
  loss_pct?: number | null;
  drain_pct?: number | null;
}

export interface VampireEntry {
  date?: string;
  start_date?: string;
  idle_hours?: number | null;
  loss_pct?: number | null;
  drain_pct?: number | null;
}

/** /api/teslaMate/vampire */
export interface VampireReport {
  avg_drain_pct_per_day?: number | null;
  avg_daily_loss_pct?: number | null;
  total_loss_kwh?: number | null;
  total_drain_kwh?: number | null;
  days?: VampireDay[];
  entries?: VampireEntry[];
}

export interface TopRoute {
  route?: string;
  start_address?: string;
  end_address?: string;
  count?: number;
  trips?: number;
  avg_km?: number | null;
}

/** /api/teslaMate/trip-stats */
export interface TripStatsReport {
  top_routes?: TopRoute[];
  [key: string]: unknown;
}

// ── Managed stack ──────────────────────────────────────────────────────────

export interface StackService {
  name: string;
  state: string;
  status?: string;
  image?: string;
  ports?: string;
}

export interface DoctorCheck {
  name: string;
  label: string;
  ok: boolean;
  message: string;
  hint: string | null;
}

export interface DoctorReport {
  checks: DoctorCheck[];
  failed: number;
  total: number;
}

export interface StackStatus {
  managed: boolean;
  installed: boolean;
  running: boolean;
  services: StackService[];
  ports?: {
    teslamate: number;
    grafana: number;
    postgres: number;
    mqtt: number;
  };
}

export interface StackLogs {
  logs: string;
  service: string;
}
