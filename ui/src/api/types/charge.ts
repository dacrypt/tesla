/** Charging state, sessions, curves, schedules and analytics. */

export interface ChargeState {
  battery_level?: number;
  battery_range?: number;
  charge_limit_soc?: number;
  charging_state?: string;
  charge_rate?: number;
  minutes_to_full_charge?: number;
  charger_power?: number;
  charger_voltage?: number;
  charger_actual_current?: number;
  charge_port_door_open?: boolean;
  charge_energy_added?: number;
  scheduled_charging_mode?: string;
  scheduled_charging_start_time?: number;
}

export interface ChargingSession {
  date: string;
  location: string;
  kwh: number;
  cost: number | null;
  cost_estimated: boolean;
  battery_start: number | null;
  battery_end: number | null;
  source: string;
  process_id?: number | null;
  duration_min?: number | null;
}

export interface ChargeSample {
  ts: string; // ISO datetime
  soc: number;
  power_kw: number;
  current_a: number | null;
  voltage_v: number | null;
  phases: number | null;
  ideal_range_km: number | null;
}

export interface ChargeCurve {
  samples: ChargeSample[];
  downsampled: boolean;
  total_samples: number;
  stride: number;
}

export interface ChargeCurveStats {
  peak_kw: number;
  avg_kw_20_80: number | null;
  taper_knee_soc: number | null;
  time_above_100kw_s: number;
  energy_above_100kw_kwh: number;
  phases_used: number[];
  duration_s: number;
  kwh_added: number;
}

export interface ChargeSchedule {
  id: number;
  name: string;
  location?: string;
  latitude?: number | null;
  longitude?: number | null;
  radius_km?: number;
  start_time?: string;
  end_time?: string;
  limit_percent?: number;
  days?: string[];
  enabled?: boolean;
}

export interface ChargeCostSummary {
  source: string;
  total_kwh: number;
  total_cost: number;
  months: Array<{
    month: string;
    kwh: number;
    cost: number;
    sessions: number;
    cost_estimated: boolean;
  }>;
}

export interface ChargeForecast {
  battery_level?: number | null;
  charge_limit_soc?: number | null;
  charging_state?: string;
  minutes_to_full_charge?: number | null;
  charge_rate_mph?: number | null;
  charge_energy_added_kwh?: number | null;
  is_charging?: boolean;
}

export interface ChargeEnrichment {
  rank: {
    fastest_20_to_80_position: number | null;
    fastest_20_to_80_total: number | null;
    is_personal_best: boolean;
  };
  preconditioning: {
    detected: boolean;
    duration_minutes: number | null;
    confidence: 'high' | 'medium' | 'low' | null;
  };
  shared_stall: {
    detected: boolean;
    timestamp: string | null;
    power_drop_kw: number | null;
  };
  abrp_cost: {
    estimated_cost: number | null;
    actual_cost: number | null;
    delta_pct: number | null;
    currency: string;
    available: boolean;
  };
}
