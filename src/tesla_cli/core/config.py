"""Configuration management for tesla-cli.

Config file: ~/.tesla-cli/config.toml
Tokens: stored in system keyring (never in config file)
"""

from __future__ import annotations

from pathlib import Path

import tomli_w
from pydantic import BaseModel, Field

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

CONFIG_DIR = Path.home() / ".tesla-cli"
CONFIG_FILE = CONFIG_DIR / "config.toml"


class GeneralConfig(BaseModel):
    default_vin: str = ""
    backend: str = "owner"  # "owner" | "tessie" | "fleet"
    cost_per_kwh: float = Field(0.0, ge=0.0)
    cedula: str = ""  # Owner's cedula (Colombia) — used for SIMIT, Procuraduria, etc.
    country: str = ""  # ISO 3166-1 alpha-2 (e.g. "CO", "US", "BR", "MX")
    charge_budget: float = Field(0.0, ge=0.0)  # Monthly charging budget limit (0 = no budget)
    charge_budget_currency: str = "USD"  # Currency code for charge budget
    v491_events_purge_done: bool = False  # Set after one-time v4.9.1 fixture-events purge


class OrderConfig(BaseModel):
    reservation_number: str = ""


class TessieConfig(BaseModel):
    configured: bool = False


class FleetConfig(BaseModel):
    region: str = "na"  # "na" | "eu" | "cn"
    client_id: str = ""
    domain: str = "dacrypt.github.io"  # Domain registered in partner_accounts (bare, no https://)


class NotificationsConfig(BaseModel):
    enabled: bool = False
    apprise_urls: list[str] = Field(default_factory=list)
    message_template: str = "{event}: {vehicle} \u2014 {detail}"


class VehiclesConfig(BaseModel):
    aliases: dict[str, str] = Field(default_factory=dict)


class TeslamateConfig(BaseModel):
    database_url: str = ""  # postgresql://user:pass@host:5432/teslaMate
    car_id: int = Field(1, ge=1)  # TeslaMate car ID (1-based)
    managed: bool = False  # True = stack managed by CLI via Docker Compose
    stack_dir: str = ""  # ~/.tesla-cli/teslamate (set during install)
    postgres_port: int = Field(5432, gt=0, le=65535)
    grafana_port: int = Field(3000, gt=0, le=65535)
    teslamate_port: int = Field(4000, gt=0, le=65535)
    mqtt_port: int = Field(1883, gt=0, le=65535)


class GeofencesConfig(BaseModel):
    """Named geographic zones for geofence watch alerts."""

    zones: dict[str, dict] = Field(default_factory=dict)
    # zones[name] = {"lat": float, "lon": float, "radius_km": float}


class AbrpConfig(BaseModel):
    """A Better Route Planner live telemetry integration."""

    api_key: str = ""  # Developer API key (get from ABRP dashboard)
    user_token: str = ""  # Per-user token from ABRP app → share → API


class BleConfig(BaseModel):
    """BLE (Bluetooth Low Energy) direct control via tesla-control binary."""

    key_path: str = ""  # Path to private key .pem for BLE pairing
    ble_mac: str = ""  # Vehicle BLE MAC address (optional, auto-detected)


class HomeAssistantConfig(BaseModel):
    """Home Assistant integration."""

    url: str = ""  # e.g. http://homeassistant.local:8123
    token: str = ""  # Long-lived access token


class GrafanaConfig(BaseModel):
    """Grafana / TeslaMate dashboard URLs."""

    url: str = "http://localhost:3000"


class MqttConfig(BaseModel):
    """MQTT broker telemetry publisher."""

    broker: str = ""  # e.g. localhost or mqtt.example.com
    port: int = Field(1883, gt=0, le=65535)
    topic_prefix: str = "tesla"  # Base topic; messages go to <prefix>/<vin>/<key>
    username: str = ""
    password: str = ""
    qos: int = Field(0, ge=0, le=2)  # MQTT QoS level (0, 1, or 2)
    retain: bool = False  # Whether to set the retain flag on published messages
    tls: bool = False  # Use TLS/SSL (port 8883 typical)


class ServerConfig(BaseModel):
    """Local API server settings."""

    api_key: str = ""  # If set, require X-API-Key header on all /api/* requests
    pid_file: str = str(Path.home() / ".tesla-cli" / "server.pid")
    cors_origins: list[str] = []  # Custom CORS origins; defaults to localhost if empty
    allow_shell_automations: bool = False  # Allow command/exec automation actions via API


class FleetTelemetryConfig(BaseModel):
    """Self-hosted Fleet Telemetry server configuration.

    Run Tesla's open-source fleet-telemetry Go server yourself.
    Vehicles stream directly to your server — zero third-party dependencies.
    """

    enabled: bool = False
    hostname: str = ""  # FQDN of your fleet-telemetry server
    port: int = 4443
    ca_cert_path: str = ""  # Path to CA certificate PEM
    server_cert_path: str = ""  # Path to server certificate
    server_key_path: str = ""  # Path to server private key
    managed: bool = False  # True = Docker stack managed by CLI
    stack_dir: str = ""  # ~/.tesla-cli/fleet-telemetry


class EnergyConfig(BaseModel):
    """Tesla Energy (Powerwall/Solar) site configuration."""

    site_id: int = 0  # Auto-discovered or set manually via tesla energy sites


class Config(BaseModel):
    general: GeneralConfig = Field(default_factory=GeneralConfig)
    order: OrderConfig = Field(default_factory=OrderConfig)
    tessie: TessieConfig = Field(default_factory=TessieConfig)
    fleet: FleetConfig = Field(default_factory=FleetConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    vehicles: VehiclesConfig = Field(default_factory=VehiclesConfig)
    teslaMate: TeslamateConfig = Field(default_factory=TeslamateConfig)
    geofences: GeofencesConfig = Field(default_factory=GeofencesConfig)
    abrp: AbrpConfig = Field(default_factory=AbrpConfig)
    ble: BleConfig = Field(default_factory=BleConfig)
    home_assistant: HomeAssistantConfig = Field(default_factory=HomeAssistantConfig)
    grafana: GrafanaConfig = Field(default_factory=GrafanaConfig)
    mqtt: MqttConfig = Field(default_factory=MqttConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    telemetry: FleetTelemetryConfig = Field(default_factory=FleetTelemetryConfig)
    energy: EnergyConfig = Field(default_factory=EnergyConfig)


def load_config() -> Config:
    """Load config from TOML file, or return defaults."""
    if CONFIG_FILE.exists():
        data = tomllib.loads(CONFIG_FILE.read_text())
        return Config.model_validate(data)
    return Config()


def save_config(config: Config) -> None:
    """Save config to TOML file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(exclude_defaults=False)
    CONFIG_FILE.write_text(tomli_w.dumps(data))


def resolve_vin(config: Config, vin: str | None) -> str:
    """Resolve a VIN from alias, explicit value, or default."""
    if vin is None:
        if not config.general.default_vin:
            from tesla_cli.core.exceptions import ConfigurationError

            raise ConfigurationError("No VIN configured. Run: tesla config set default-vin <VIN>")
        return config.general.default_vin
    # Check aliases
    return config.vehicles.aliases.get(vin, vin)
