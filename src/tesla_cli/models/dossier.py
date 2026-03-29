"""Comprehensive vehicle dossier — every piece of data about the vehicle.

This is the master data model that catalogs ALL information from ALL sources
into a single, structured, historically-tracked dossier.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# ── VIN Decode ──────────────────────────────────────────────────────────────


class VinDecode(BaseModel):
    """Full VIN breakdown position by position."""

    vin: str = ""
    manufacturer: str = ""  # LRW = Tesla Shanghai
    model: str = ""  # Y = Model Y
    body_type: str = ""  # G = SUV
    restraint_system: str = ""  # C = airbags + curtains
    energy_type: str = ""  # E = Electric NMC/NCA
    motor_battery: str = ""  # K = Dual Motor LR Juniper
    check_digit: str = ""
    model_year: str = ""  # T = 2026
    plant: str = ""  # C = Shanghai
    serial_number: str = ""
    plant_country: str = ""  # China
    battery_chemistry: str = ""  # NMC/NCA or LFP


# ── Option Codes ────────────────────────────────────────────────────────────


class OptionCode(BaseModel):
    """A single decoded option code."""

    code: str = ""
    category: str = ""  # model, motor, paint, interior, wheels, seats, autopilot, charging, connectivity
    description: str = ""
    description_es: str = ""  # Spanish


class OptionCodes(BaseModel):
    """All option codes with raw string and decoded list."""

    raw_string: str = ""  # "APFA,IPB12,PN01,..."
    codes: list[OptionCode] = Field(default_factory=list)


# ── Order Tracking ──────────────────────────────────────────────────────────


class OrderSnapshot(BaseModel):
    """A point-in-time snapshot of order state."""

    timestamp: datetime = Field(default_factory=datetime.now)
    order_status: str = ""
    order_substatus: str = ""
    vin: str = ""
    delivery_window_start: str = ""
    delivery_window_end: str = ""
    raw: dict = Field(default_factory=dict)


class OrderTimeline(BaseModel):
    """Complete order history with all state transitions."""

    reservation_number: str = ""
    vehicle_map_id: int = 0
    country_code: str = ""
    locale: str = ""
    is_b2b: bool = False
    is_used: bool = False
    is_tesla_assist_enabled: bool = False
    current: OrderSnapshot = Field(default_factory=OrderSnapshot)
    history: list[OrderSnapshot] = Field(default_factory=list)  # every state change


# ── Shipping / Logistics ────────────────────────────────────────────────────


class ShipPosition(BaseModel):
    """A tracked position of a cargo vessel."""

    timestamp: datetime = Field(default_factory=datetime.now)
    latitude: float = 0.0
    longitude: float = 0.0
    speed_knots: float = 0.0
    course: float = 0.0


class ShipTracking(BaseModel):
    """Vessel tracking data for the car carrier."""

    vessel_name: str = ""
    imo: str = ""
    mmsi: str = ""
    departure_port: str = ""
    destination_port: str = ""
    eta: str = ""
    current_position: ShipPosition = Field(default_factory=ShipPosition)
    positions_history: list[ShipPosition] = Field(default_factory=list)
    tracking_url: str = ""  # MarineTraffic / shipinfo link


class Logistics(BaseModel):
    """Full logistics chain from factory to delivery."""

    factory: str = ""  # Gigafactory Shanghai
    departure_port: str = ""  # Shanghai / Nangang
    arrival_port: str = ""  # Cartagena / Buenaventura
    destination_country: str = ""
    ship: ShipTracking = Field(default_factory=ShipTracking)
    estimated_transit_days: int = 0
    customs_status: str = ""
    last_mile_status: str = ""  # transit to dealer, ready for pickup, etc.


# ── RUNT (Colombia vehicle registry) ───────────────────────────────────────


class RuntData(BaseModel):
    """Data from Colombia's RUNT (Registro Único Nacional de Tránsito).

    All 55 fields from the RUNT API response (infoVehiculo).
    Source: https://runtproapi.runt.gov.co/CYRConsultaVehiculoMS/auth
    """

    queried_at: datetime = Field(default_factory=datetime.now)

    # ── Identificación del vehículo ──
    estado: str = ""  # REGISTRADO, NO REGISTRADO, MATRICULADO
    placa: str = ""
    licencia_transito: str = ""  # numLicencia
    id_automotor: int = 0  # Internal RUNT ID (e.g. 613149469)
    tarjeta_registro: str = ""  # Registration card number

    # ── Clasificación ──
    clase_vehiculo: str = ""  # CAMIONETA
    id_clase_vehiculo: int = 0  # 5
    clasificacion: str = ""  # AUTOMOVIL
    tipo_servicio: str = ""
    id_tipo_servicio: int | None = None

    # ── Datos del fabricante ──
    marca: str = ""  # TESLA
    linea: str = ""  # MODELO Y
    modelo_ano: str = ""  # 2026
    color: str = ""  # GRIS GRAFITO

    # ── Identificadores ──
    numero_serie: str = ""  # numSerie
    numero_motor: str = ""  # numMotor
    numero_chasis: str = ""  # numChasis
    numero_vin: str = ""  # vin

    # ── Especificaciones técnicas ──
    tipo_combustible: str = ""  # ELECTRICO
    tipo_carroceria: str = ""  # SUV
    cilindraje: str = ""  # 0
    puertas: int = 0
    peso_bruto_kg: int = 0  # pesoBruto
    capacidad_carga: str = ""  # capacidadCarga (for trucks)
    capacidad_pasajeros: int = 0  # pasajerosSentados
    pasajeros_total: int | None = None  # pasajerosTotal
    numero_ejes: int = 0

    # ── Estado legal ──
    gravamenes: bool = False  # Liens
    prendas: bool = False  # Pledges
    repotenciado: bool = False  # Re-powered
    blindaje: bool = False  # Armored
    antiguo_clasico: bool = False  # Classic/antique vehicle
    vehiculo_ensenanza: bool = False  # Driving school vehicle
    seguridad_estado: bool = False  # State security vehicle

    # ── Regrabaciones (VIN/chassis re-stamps) ──
    regrabacion_motor: bool = False
    num_regrabacion_motor: str = ""
    regrabacion_chasis: bool = False
    num_regrabacion_chasis: str = ""
    regrabacion_serie: bool = False
    num_regrabacion_serie: str = ""
    regrabacion_vin: bool = False
    num_regrabacion_vin: str = ""

    # ── SOAT (seguro obligatorio) ──
    soat_vigente: bool = False
    soat_aseguradora: str = ""
    soat_vencimiento: str = ""

    # ── RTM (revisión técnico-mecánica) ──
    tecnomecanica_vigente: bool = False
    tecnomecanica_vencimiento: str = ""

    # ── Registro y matrícula ──
    fecha_matricula: str = ""  # fechaMatricula
    fecha_registro: str = ""  # fechaRegistro
    autoridad_transito: str = ""  # organismoTransito
    dias_matriculado: int | None = None  # diasMatriculado

    # ── Importación ──
    importacion: int = 0  # 0 = not imported via special regime
    fecha_expedicion_lt_importacion: str = ""  # fechaExpedLTImportacion
    fecha_vencimiento_lt_importacion: str = ""  # fechaVenciLTImportacion
    nombre_pais: str = ""  # nombrePais (country of origin)

    # ── DIAN (tax authority) ──
    ver_valida_dian: bool = False
    validacion_dian: str = ""

    # ── Arancelaria ──
    subpartida: str = ""  # Customs subheading
    tipo_maquinaria: str = ""  # Machinery type (for non-vehicles)

    # ── Identificación propietario ──
    no_identificacion: str = ""  # Owner's document number (masked)

    # ── Control flags ──
    mostrar_solicitudes: bool = True  # Show pending requests


# ── SIMIT (Colombian traffic fines) ─────────────────────────────────────────


class SimitData(BaseModel):
    """Data from Colombia's SIMIT (Sistema Integrado de Información sobre
    Multas y Sanciones por Infracciones de Tránsito).

    Source: https://www.fcm.org.co/simit/#/estado-cuenta
    """

    queried_at: datetime = Field(default_factory=datetime.now)
    cedula: str = ""
    comparendos: int = 0
    multas: int = 0
    acuerdos_pago: int = 0
    total_deuda: float = 0.0
    paz_y_salvo: bool = False  # True if no fines ($0)
    historial: list[dict] = Field(default_factory=list)  # Historical records


# ── Real Status (multi-source intelligence) ─────────────────────────────────


class RealStatus(BaseModel):
    """Actual vehicle status derived from ALL sources, not just Tesla API.

    Tesla's API may say "BOOKED" while RUNT shows "REGISTRADO" and
    delivery is scheduled. This model reconciles all signals.
    """

    # Computed real phase
    phase: str = ""  # produced, shipped, in_country, registered, delivery_scheduled, delivered
    phase_description: str = ""

    # Source signals
    tesla_api_status: str = ""  # what Tesla API says
    runt_status: str = ""  # what RUNT says
    vin_assigned: bool = False
    in_runt: bool = False
    has_placa: bool = False
    has_soat: bool = False
    delivery_date: str = ""  # confirmed delivery date (YYYY-MM-DD)
    delivery_location: str = ""  # pickup location name
    delivery_appointment: str = ""  # human-readable appointment text

    # Timeline flags
    is_produced: bool = False
    is_shipped: bool = False
    is_in_country: bool = False
    is_customs_cleared: bool = False
    is_registered: bool = False
    is_delivery_scheduled: bool = False
    is_delivered: bool = False


# ── Recalls & Safety ───────────────────────────────────────────────────────


class Recall(BaseModel):
    """A recall notice for the vehicle."""

    recall_id: str = ""
    date: str = ""
    description: str = ""
    component: str = ""
    remedy: str = ""
    status: str = ""  # open, completed, not_applicable
    nhtsa_id: str = ""
    source: str = ""  # tesla, nhtsa


# ── Software / Firmware ────────────────────────────────────────────────────


class SoftwareVersion(BaseModel):
    """A software version record."""

    version: str = ""
    first_seen: datetime = Field(default_factory=datetime.now)
    release_notes: str = ""


class SoftwareHistory(BaseModel):
    """Track all OTA updates."""

    current_version: str = ""
    versions: list[SoftwareVersion] = Field(default_factory=list)


# ── Service & Maintenance ──────────────────────────────────────────────────


class ServiceRecord(BaseModel):
    """A service/maintenance event."""

    date: str = ""
    type: str = ""  # scheduled, repair, recall_fix, tire_rotation, etc.
    description: str = ""
    mileage_km: float = 0.0
    location: str = ""
    correction_code: str = ""
    details: dict = Field(default_factory=dict)


# ── Tesla Account Data ──────────────────────────────────────────────────────


class TeslaAccount(BaseModel):
    """Data from Tesla's owner API about the account."""

    email: str = ""
    full_name: str = ""
    vault_uuid: str = ""
    feature_config: dict = Field(default_factory=dict)
    onboarding_data: dict = Field(default_factory=dict)
    service_scheduling_enabled: bool = False


# ── Vehicle Specs ───────────────────────────────────────────────────────────


class VehicleSpecs(BaseModel):
    """Known specifications for this vehicle configuration."""

    model: str = ""  # Model Y
    variant: str = ""  # Long Range Dual Motor
    generation: str = ""  # Juniper (2025+ refresh)
    model_year: int = 0
    factory: str = ""
    battery_type: str = ""  # NMC/NCA
    battery_capacity_kwh: float = 0.0  # estimated
    range_km: int = 0  # estimated WLTP
    motor_config: str = ""  # Dual Motor AWD
    horsepower: int = 0  # estimated
    zero_to_100_kmh: float = 0.0
    top_speed_kmh: int = 0
    curb_weight_kg: int = 0
    dimensions: str = ""  # LxWxH
    seating: int = 5
    wheels: str = ""  # 19" Gemini
    exterior_color: str = ""
    interior: str = ""
    autopilot_hardware: str = ""  # HW5
    has_fsd: bool = False
    supercharging: str = ""  # pay per use
    connectivity: str = ""  # standard


# ── Financial ───────────────────────────────────────────────────────────────


class Financial(BaseModel):
    """Financial details about the purchase."""

    currency: str = "COP"
    base_price: float = 0.0
    options_total: float = 0.0
    taxes: float = 0.0
    total_price: float = 0.0
    payment_method: str = ""  # cash, financing, lease
    deposit_paid: float = 0.0
    balance_due: float = 0.0
    financing_details: dict = Field(default_factory=dict)
    trade_in: dict = Field(default_factory=dict)


# ── Master Dossier ──────────────────────────────────────────────────────────


class VehicleDossier(BaseModel):
    """The complete, comprehensive vehicle dossier.

    This is the single source of truth — every piece of information
    from every source, structured and historically tracked.
    """

    # Metadata
    dossier_version: str = "1.0"
    created_at: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    update_count: int = 0

    # Core identity
    vin: str = ""
    reservation_number: str = ""

    # Decoded identity
    vin_decode: VinDecode = Field(default_factory=VinDecode)
    option_codes: OptionCodes = Field(default_factory=OptionCodes)
    specs: VehicleSpecs = Field(default_factory=VehicleSpecs)

    # Real status (multi-source intelligence)
    real_status: RealStatus = Field(default_factory=RealStatus)

    # Order lifecycle
    order: OrderTimeline = Field(default_factory=OrderTimeline)

    # RUNT (Colombia)
    runt: RuntData = Field(default_factory=RuntData)

    # SIMIT (Colombia — traffic fines)
    simit: SimitData = Field(default_factory=SimitData)

    # Logistics
    logistics: Logistics = Field(default_factory=Logistics)

    # Safety
    recalls: list[Recall] = Field(default_factory=list)

    # Software
    software: SoftwareHistory = Field(default_factory=SoftwareHistory)

    # Service
    service_history: list[ServiceRecord] = Field(default_factory=list)

    # Financial
    financial: Financial = Field(default_factory=Financial)

    # Tesla account
    account: TeslaAccount = Field(default_factory=TeslaAccount)

    # Raw API snapshots (for anything not yet modeled)
    raw_snapshots: list[dict] = Field(default_factory=list)
