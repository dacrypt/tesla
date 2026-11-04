/** Vehicle dossier (VIN decode, specs, RUNT/SIMIT, logistics, ...). */

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
