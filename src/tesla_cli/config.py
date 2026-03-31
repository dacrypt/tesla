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
    cost_per_kwh: float = 0.0


class OrderConfig(BaseModel):
    reservation_number: str = ""


class TessieConfig(BaseModel):
    configured: bool = False


class FleetConfig(BaseModel):
    region: str = "na"  # "na" | "eu" | "cn"
    client_id: str = ""


class NotificationsConfig(BaseModel):
    enabled: bool = False
    apprise_urls: list[str] = Field(default_factory=list)


class VehiclesConfig(BaseModel):
    aliases: dict[str, str] = Field(default_factory=dict)


class TeslamateConfig(BaseModel):
    database_url: str = ""  # postgresql://user:pass@host:5432/teslaMate
    car_id: int = 1  # TeslaMate car ID (1-based)


class GeofencesConfig(BaseModel):
    """Named geographic zones for geofence watch alerts."""
    zones: dict[str, dict] = Field(default_factory=dict)
    # zones[name] = {"lat": float, "lon": float, "radius_km": float}


class AbrpConfig(BaseModel):
    """A Better Route Planner live telemetry integration."""
    api_key: str = ""        # Developer API key (get from ABRP dashboard)
    user_token: str = ""     # Per-user token from ABRP app → share → API


class BleConfig(BaseModel):
    """BLE (Bluetooth Low Energy) direct control via tesla-control binary."""
    key_path: str = ""       # Path to private key .pem for BLE pairing
    ble_mac: str = ""        # Vehicle BLE MAC address (optional, auto-detected)


class HomeAssistantConfig(BaseModel):
    """Home Assistant integration."""
    url: str = ""            # e.g. http://homeassistant.local:8123
    token: str = ""          # Long-lived access token


class GrafanaConfig(BaseModel):
    """Grafana / TeslaMate dashboard URLs."""
    url: str = "http://localhost:3000"


class ServerConfig(BaseModel):
    """Local API server settings."""
    api_key: str = ""           # If set, require X-API-Key header on all /api/* requests
    pid_file: str = str(Path.home() / ".tesla-cli" / "server.pid")


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
    server: ServerConfig = Field(default_factory=ServerConfig)


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
            from tesla_cli.exceptions import ConfigurationError

            raise ConfigurationError("No VIN configured. Run: tesla config set default-vin <VIN>")
        return config.general.default_vin
    # Check aliases
    return config.vehicles.aliases.get(vin, vin)
