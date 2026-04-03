import axios, { AxiosInstance } from 'axios';

export function getBaseUrl(): string {
  return localStorage.getItem('tesla_api_url') || '';
}

export function setBaseUrl(url: string): void {
  localStorage.setItem('tesla_api_url', url);
}

function createClient(): AxiosInstance {
  return axios.create({
    baseURL: getBaseUrl(),
    timeout: 15000,
    headers: { 'Content-Type': 'application/json' },
  });
}

function client(): AxiosInstance {
  return createClient();
}

// Types
export interface ServerStatus {
  version: string;
  backend: string;
  vin: string;
}

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
}

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

export interface ClimateState {
  inside_temp?: number;
  outside_temp?: number;
  driver_temp_setting?: number;
  passenger_temp_setting?: number;
  is_climate_on?: boolean;
  seat_heater_left?: number;
  seat_heater_right?: number;
  seat_heater_rear_left?: number;
  seat_heater_rear_center?: number;
  seat_heater_rear_right?: number;
  steering_wheel_heater?: boolean;
  bioweapon_mode?: boolean;
  climate_keeper_mode?: string;
}

export interface LocationState {
  latitude?: number;
  longitude?: number;
  speed?: number;
  heading?: number;
}

export interface OrderStatus {
  order_id?: string;
  status?: string;
  vin?: string;
  estimated_delivery?: string;
  delivery_appointment?: string;
  model?: string;
  trim?: string;
  color?: string;
  gates?: Record<string, boolean>;
}

export interface TeslaConfig {
  backend?: string;
  vin?: string;
  tessie_token?: string;
  teslaMate_url?: string;
}

export interface ProviderStatus {
  name: string;
  status: string;
  message?: string;
}

export interface TripStat {
  id?: string;
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
}

export interface Stats {
  total_trips?: number;
  total_distance?: number;
  total_energy?: number;
  avg_efficiency?: number;
  total_charges?: number;
  total_cost?: number;
}

export interface StackService {
  name: string;
  state: string;
  status?: string;
  image?: string;
  ports?: string;
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

// ── Dossier Types ──────────────────────────────────────────────────────────

export interface VinDecode {
  vin?: string;
  manufacturer?: string;
  model?: string;
  body_type?: string;
  restraint_system?: string;
  energy_type?: string;
  motor_battery?: string;
  check_digit?: string;
  model_year?: string;
  plant?: string;
  serial_number?: string;
  plant_country?: string;
  battery_chemistry?: string;
}

export interface OptionCode {
  code?: string;
  category?: string;
  description?: string;
  description_es?: string;
}

export interface OptionCodes {
  raw_string?: string;
  codes?: OptionCode[];
}

export interface OrderSnapshot {
  timestamp?: string;
  order_status?: string;
  order_substatus?: string;
  vin?: string;
  delivery_window_start?: string;
  delivery_window_end?: string;
  raw?: Record<string, unknown>;
}

export interface OrderTimeline {
  reservation_number?: string;
  vehicle_map_id?: number;
  country_code?: string;
  locale?: string;
  is_b2b?: boolean;
  is_used?: boolean;
  is_tesla_assist_enabled?: boolean;
  current?: OrderSnapshot;
  history?: OrderSnapshot[];
}

export interface ShipPosition {
  timestamp?: string;
  latitude?: number;
  longitude?: number;
  speed_knots?: number;
  course?: number;
}

export interface ShipTracking {
  vessel_name?: string;
  imo?: string;
  mmsi?: string;
  departure_port?: string;
  destination_port?: string;
  eta?: string;
  current_position?: ShipPosition;
  positions_history?: ShipPosition[];
  tracking_url?: string;
}

export interface DossierLogistics {
  factory?: string;
  departure_port?: string;
  arrival_port?: string;
  destination_country?: string;
  ship?: ShipTracking;
  estimated_transit_days?: number;
  customs_status?: string;
  last_mile_status?: string;
}

export interface RuntData {
  queried_at?: string;
  estado?: string;
  placa?: string;
  licencia_transito?: string;
  id_automotor?: number;
  clase_vehiculo?: string;
  clasificacion?: string;
  tipo_servicio?: string;
  marca?: string;
  linea?: string;
  modelo_ano?: string;
  color?: string;
  numero_serie?: string;
  numero_motor?: string;
  numero_chasis?: string;
  numero_vin?: string;
  tipo_combustible?: string;
  tipo_carroceria?: string;
  cilindraje?: string;
  puertas?: number;
  peso_bruto_kg?: number;
  capacidad_pasajeros?: number;
  numero_ejes?: number;
  capacidad_carga?: string;
  pasajeros_total?: number;
  gravamenes?: boolean;
  prendas?: boolean;
  repotenciado?: boolean;
  blindaje?: boolean;
  antiguo_clasico?: boolean;
  vehiculo_ensenanza?: boolean;
  seguridad_estado?: boolean;
  regrabacion_motor?: boolean;
  regrabacion_chasis?: boolean;
  regrabacion_serie?: boolean;
  regrabacion_vin?: boolean;
  soat_vigente?: boolean;
  soat_aseguradora?: string;
  soat_vencimiento?: string;
  tecnomecanica_vigente?: boolean;
  tecnomecanica_vencimiento?: string;
  fecha_matricula?: string;
  fecha_registro?: string;
  autoridad_transito?: string;
  dias_matriculado?: number;
  importacion?: number;
  fecha_expedicion_lt_importacion?: string;
  fecha_vencimiento_lt_importacion?: string;
  nombre_pais?: string;
  ver_valida_dian?: boolean;
  validacion_dian?: string;
  subpartida?: string;
  no_identificacion?: string;
  tarjeta_registro?: string;
  id_clase_vehiculo?: number;
  id_tipo_servicio?: number;
}

export interface SimitData {
  queried_at?: string;
  cedula?: string;
  comparendos?: number;
  multas?: number;
  acuerdos_pago?: number;
  total_deuda?: number;
  paz_y_salvo?: boolean;
  historial?: Record<string, unknown>[];
}

export interface RealStatus {
  phase?: string;
  phase_description?: string;
  tesla_api_status?: string;
  runt_status?: string;
  vin_assigned?: boolean;
  in_runt?: boolean;
  has_placa?: boolean;
  has_soat?: boolean;
  delivery_date?: string;
  delivery_location?: string;
  delivery_appointment?: string;
  is_produced?: boolean;
  is_shipped?: boolean;
  is_in_country?: boolean;
  is_customs_cleared?: boolean;
  is_registered?: boolean;
  is_delivery_scheduled?: boolean;
  is_delivered?: boolean;
}

export interface DossierRecall {
  recall_id?: string;
  date?: string;
  description?: string;
  component?: string;
  remedy?: string;
  status?: string;
  nhtsa_id?: string;
  source?: string;
}

export interface VehicleSpecs {
  model?: string;
  variant?: string;
  generation?: string;
  model_year?: number;
  factory?: string;
  battery_type?: string;
  battery_capacity_kwh?: number;
  range_km?: number;
  motor_config?: string;
  horsepower?: number;
  zero_to_100_kmh?: number;
  top_speed_kmh?: number;
  curb_weight_kg?: number;
  dimensions?: string;
  seating?: number;
  wheels?: string;
  exterior_color?: string;
  interior?: string;
  autopilot_hardware?: string;
  has_fsd?: boolean;
  supercharging?: string;
  connectivity?: string;
}

export interface DossierFinancial {
  currency?: string;
  base_price?: number;
  options_total?: number;
  taxes?: number;
  total_price?: number;
  payment_method?: string;
  deposit_paid?: number;
  balance_due?: number;
}

export interface SoftwareVersion {
  version?: string;
  first_seen?: string;
  release_notes?: string;
}

export interface SoftwareHistory {
  current_version?: string;
  versions?: SoftwareVersion[];
}

export interface ServiceRecord {
  date?: string;
  type?: string;
  description?: string;
  mileage_km?: number;
  location?: string;
}

export interface TeslaAccount {
  email?: string;
  full_name?: string;
  vault_uuid?: string;
  feature_config?: Record<string, unknown>;
  onboarding_data?: Record<string, unknown>;
  service_scheduling_enabled?: boolean;
}

export interface VehicleDossier {
  dossier_version?: string;
  created_at?: string;
  last_updated?: string;
  update_count?: number;
  vin?: string;
  reservation_number?: string;
  vin_decode?: VinDecode;
  option_codes?: OptionCodes;
  specs?: VehicleSpecs;
  real_status?: RealStatus;
  order?: OrderTimeline;
  runt?: RuntData;
  simit?: SimitData;
  logistics?: DossierLogistics;
  recalls?: DossierRecall[];
  software?: SoftwareHistory;
  service_history?: ServiceRecord[];
  financial?: DossierFinancial;
  account?: TeslaAccount;
}

export interface CommandPayload {
  command: string;
  params?: Record<string, unknown>;
}

export interface CommandResult {
  success: boolean;
  message?: string;
  result?: unknown;
}

// API methods
export const api = {
  // Status
  getStatus: () => client().get<ServerStatus>('/api/status').then(r => r.data),
  getConfig: () => client().get<TeslaConfig>('/api/config').then(r => r.data),
  getProviders: () => client().get<ProviderStatus[]>('/api/providers').then(r => r.data),

  // Vehicles
  getVehicles: () => client().get<Vehicle[]>('/api/vehicles').then(r => r.data),
  getVehicleList: () => client().get<Vehicle[]>('/api/vehicle/list').then(r => r.data),

  // Vehicle state
  getVehicleState: () => client().get<VehicleState>('/api/vehicle/state').then(r => r.data),
  getVehicleLocation: () => client().get<LocationState>('/api/vehicle/location').then(r => r.data),

  // Charge
  getChargeState: () => client().get<ChargeState>('/api/charge/status').then(r => r.data),
  getChargeVehicle: () => client().get<ChargeState>('/api/vehicle/charge').then(r => r.data),
  getChargeSessions: (limit = 10) =>
    client().get<ChargingSession[]>(`/api/charge/sessions?limit=${limit}`).then(r => r.data),
  getVehicleSummary: () =>
    client().get<any>('/api/vehicle/summary').then(r => r.data),
  setChargeLimit: (percent: number) => client().post<CommandResult>('/api/charge/limit', { percent }).then(r => r.data),
  setChargingAmps: (amps: number) => client().post<CommandResult>('/api/charge/amps', { amps }).then(r => r.data),
  startCharge: () => client().post<CommandResult>('/api/charge/start').then(r => r.data),
  stopCharge: () => client().post<CommandResult>('/api/charge/stop').then(r => r.data),

  // Climate
  getClimateState: () => client().get<ClimateState>('/api/climate/status').then(r => r.data),
  getClimateVehicle: () => client().get<ClimateState>('/api/vehicle/climate').then(r => r.data),
  climateOn: () => client().post<CommandResult>('/api/climate/on').then(r => r.data),
  climateOff: () => client().post<CommandResult>('/api/climate/off').then(r => r.data),
  setTemps: (driver_temp: number, passenger_temp: number) =>
    client().post<CommandResult>('/api/climate/temp', { driver_temp, passenger_temp }).then(r => r.data),

  // Security
  lockDoors: () => client().post<CommandResult>('/api/security/lock').then(r => r.data),
  unlockDoors: () => client().post<CommandResult>('/api/security/unlock').then(r => r.data),
  getSentryStatus: () => client().get<{ sentry_mode: boolean; sentry_mode_available: boolean }>('/api/security/sentry').then(r => r.data),
  sentryOn: () => client().post<CommandResult>('/api/security/sentry/on').then(r => r.data),
  sentryOff: () => client().post<CommandResult>('/api/security/sentry/off').then(r => r.data),
  openFrunk: () => client().post<CommandResult>('/api/security/trunk/front').then(r => r.data),
  openTrunk: () => client().post<CommandResult>('/api/security/trunk/rear').then(r => r.data),
  honkHorn: () => client().post<CommandResult>('/api/security/horn').then(r => r.data),
  flashLights: () => client().post<CommandResult>('/api/security/flash').then(r => r.data),

  // Notifications
  getNotifyChannels: () => client().get<{ enabled: boolean; channels: string[]; template: string }>('/api/notify/list').then(r => r.data),
  sendNotifyTest: () => client().post<CommandResult>('/api/notify/test').then(r => r.data),
  addNotifyChannel: (url: string) => client().post<CommandResult>('/api/notify/add', { url }).then(r => r.data),
  removeNotifyChannel: (index: number) => client().post<CommandResult>('/api/notify/remove', { index }).then(r => r.data),

  // Vehicle alerts
  getVehicleAlerts: () => client().get<any>('/api/vehicle/alerts').then(r => r.data),

  // Commands (generic)
  sendCommand: (payload: CommandPayload) =>
    client().post<CommandResult>('/api/vehicle/command', payload).then(r => r.data),
  wakeVehicle: () => client().post<CommandResult>('/api/vehicle/wake').then(r => r.data),

  // Order
  getOrderStatus: () => client().get<OrderStatus>('/api/order/status').then(r => r.data),

  // Dossier
  getDossier: () => client().get<VehicleDossier>('/api/dossier', { timeout: 5000 }).then(r => r.data),
  refreshDossier: () => client().get<VehicleDossier>('/api/dossier/refresh', { timeout: 30000 }).then(r => r.data),
  getDossierRunt: () => client().get<RuntData>('/api/dossier/runt', { timeout: 15000 }).then(r => r.data),
  getDossierSimit: () => client().get<SimitData>('/api/dossier/simit', { timeout: 15000 }).then(r => r.data),

  // TeslaMate
  getTrips: () => client().get<TripStat[]>('/api/teslaMate/trips').then(r => r.data),
  getCharges: () => client().get<ChargeStat[]>('/api/teslaMate/charges').then(r => r.data),
  getStats: () => client().get<Stats>('/api/teslaMate/stats').then(r => r.data),
  getEfficiency: () => client().get<unknown>('/api/teslaMate/efficiency').then(r => r.data),
  getVampire: () => client().get<unknown>('/api/teslaMate/vampire').then(r => r.data),
  getCostReport: () => client().get<unknown>('/api/teslaMate/cost-report').then(r => r.data),
  getTripStats: () => client().get<unknown>('/api/teslaMate/trip-stats').then(r => r.data),
  getDailyEnergy: () => client().get<unknown>('/api/teslaMate/daily-energy').then(r => r.data),
  getTimeline: () => client().get<unknown>('/api/teslaMate/timeline').then(r => r.data),
  getHeatmap: () => client().get<unknown>('/api/teslaMate/heatmap').then(r => r.data),
  getMonthlyReport: (month: string) =>
    client().get<unknown>(`/api/teslaMate/report/${month}`).then(r => r.data),

  // TeslaMate managed stack
  getStackStatus: () =>
    client().get<StackStatus>('/api/teslaMate/stack/status').then(r => r.data),
  stackStart: () =>
    client().post<{ ok: boolean }>('/api/teslaMate/stack/start').then(r => r.data),
  stackStop: () =>
    client().post<{ ok: boolean }>('/api/teslaMate/stack/stop').then(r => r.data),
  stackRestart: () =>
    client().post<{ ok: boolean }>('/api/teslaMate/stack/restart').then(r => r.data),
  stackUpdate: () =>
    client().post<{ ok: boolean; output?: string }>('/api/teslaMate/stack/update', {}, { timeout: 120000 }).then(r => r.data),
  getStackLogs: (service?: string, lines = 80) =>
    client().get<{ logs: string; service: string }>('/api/teslaMate/stack/logs', {
      params: { service: service || '', lines },
    }).then(r => r.data),

  // Auth
  getAuthLogin: () =>
    client().get<{ auth_url: string; state: string }>('/api/auth/login').then(r => r.data),
  postAuthCallback: (code: string, state: string) =>
    client().post<{ ok: boolean; expires_in?: number }>('/api/auth/callback', { code, state }).then(r => r.data),
  postAuthTessie: (token: string) =>
    client().post<{ ok: boolean }>('/api/auth/tessie', { token }).then(r => r.data),
  browserLogin: (email: string, password: string, mfa_code?: string) =>
    client().post<any>('/api/auth/browser-login', { email, password, mfa_code }, { timeout: 120000 }).then(r => r.data),
  portalScrape: (email: string, password: string, mfa_code?: string) =>
    client().post<any>('/api/auth/portal-scrape', { email, password, mfa_code }, { timeout: 180000 }).then(r => r.data),
  getAuthStatus: () =>
    client().get<{ authenticated: boolean; backend: string; has_fleet: boolean; has_order: boolean; has_tessie: boolean }>('/api/auth/status').then(r => r.data),

  // Data Sources
  getSources: () =>
    client().get<any[]>('/api/sources').then(r => r.data),
  getSource: (id: string) =>
    client().get<any>(`/api/sources/${id}`).then(r => r.data),
  refreshSource: (id: string) =>
    client().post<any>(`/api/sources/${id}/refresh`).then(r => r.data),
  getMissingAuth: () =>
    client().get<any[]>('/api/sources/missing-auth').then(r => r.data),
  getSourceHistory: (id: string) =>
    client().get<any[]>(`/api/sources/${id}/history`).then(r => r.data),
  getSourceAudits: (id: string) =>
    client().get<any[]>(`/api/sources/${id}/audits`).then(r => r.data),
  getSourceConfig: () =>
    client().get<any>('/api/sources/config').then(r => r.data),
  updateSourceConfig: (data: { cedula?: string; vin?: string }) =>
    client().post<any>('/api/sources/config', data).then(r => r.data),

  // Colombia sources
  getPicoYPlaca: (placa?: string) =>
    client().get<any>('/api/co/pico-y-placa', { params: { placa: placa || '' } }).then(r => r.data),
  getEstacionesEV: (ciudad?: string) =>
    client().get<any>('/api/co/estaciones-ev', { params: { ciudad: ciudad || '' } }).then(r => r.data),
  getFasecolda: () =>
    client().get<any>('/api/co/fasecolda').then(r => r.data),
  getRecallsSIC: () =>
    client().get<any>('/api/co/recalls-sic').then(r => r.data),
  getPeajes: (ruta?: string) =>
    client().get<any>('/api/co/peajes', { params: { ruta: ruta || '' } }).then(r => r.data),

  // SSE stream URL
  getStreamUrl: () => `${getBaseUrl()}/api/vehicle/stream`,
};
