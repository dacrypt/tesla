/** Vehicle identity, live state, location, fleet and sharing. */

export interface Vehicle {
  id: string;
  vin: string;
  display_name: string;
  state: string;
  battery_level?: number;
}

export interface VehicleState {
  id?: string;
  vin?: string;
  display_name?: string;
  state?: string;
  battery_level?: number;
  battery_range?: number;
  charge_limit_soc?: number;
  charging_state?: string;
  charge_rate?: number;
  minutes_to_full_charge?: number;
  inside_temp?: number;
  outside_temp?: number;
  driver_temp_setting?: number;
  passenger_temp_setting?: number;
  is_climate_on?: boolean;
  locked?: boolean;
  sentry_mode?: boolean;
  valet_mode?: boolean;
  latitude?: number;
  longitude?: number;
  speed?: number;
  heading?: number;
  is_charging?: boolean;
  charge_port_door_open?: boolean;
  charge_energy_added?: number;
  charger_power?: number;
  charger_voltage?: number;
  charger_actual_current?: number;
  scheduled_charging_mode?: string;
  scheduled_charging_start_time?: number;
  seat_heater_left?: number;
  seat_heater_right?: number;
  seat_heater_rear_left?: number;
  seat_heater_rear_center?: number;
  seat_heater_rear_right?: number;
  steering_wheel_heater?: boolean;
  bioweapon_mode?: boolean;
  climate_keeper_mode?: string;
  media_state?: { remote_control_enabled: boolean };
  software_update?: { status: string; version: string };
  car_version?: string;
  odometer?: number;
}

export interface LocationState {
  latitude?: number;
  longitude?: number;
  speed?: number;
  heading?: number;
}

export interface FleetVehicle {
  vin: string;
  alias: string;
  battery_level: number | null;
  battery_range: number | null;
  charging_state: string | null;
  locked: boolean | null;
  sentry: boolean | null;
  lat: number | null;
  lon: number | null;
  error: string | null;
}

export interface VehicleInvitation {
  id: string;
  email?: string;
  name?: string;
  created_at?: string;
  status?: string;
}

/** /api/vehicle/summary — compact snapshot (km / °C). */
export interface VehicleSummary {
  vin: string;
  battery: {
    level: number | null;
    range_km: number | null;
    limit: number | null;
    charging_state: string | null;
    charger_power: number | null;
    time_to_full_charge: number | null;
  };
  climate: {
    inside_temp: number | null;
    outside_temp: number | null;
    hvac_on: boolean;
  };
  location: {
    latitude: number | null;
    longitude: number | null;
    speed: number | null;
    heading: number | null;
  };
  state: {
    locked: boolean;
    sentry_mode: boolean;
    software: string | null;
    odometer_km: number | null;
  };
}

/** /api/vehicle/alerts — passed through from the Fleet API (shape varies). */
export type VehicleAlerts = Record<string, unknown>;

/** /api/vehicle/ready */
export interface VehicleReady {
  ready: boolean;
  battery_level: number;
  range_km: number;
  issues: string[];
}

/** /api/vehicle/last-seen */
export interface VehicleLastSeen {
  state: string;
  last_seen: string | null;
  ago_seconds: number | null;
}

/** /api/security/sentry */
export interface SentryStatus {
  sentry_mode: boolean;
  sentry_mode_available: boolean;
}
