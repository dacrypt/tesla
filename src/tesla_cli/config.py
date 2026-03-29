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
    backend: str = "tessie"  # "tessie" | "fleet"


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


class Config(BaseModel):
    general: GeneralConfig = Field(default_factory=GeneralConfig)
    order: OrderConfig = Field(default_factory=OrderConfig)
    tessie: TessieConfig = Field(default_factory=TessieConfig)
    fleet: FleetConfig = Field(default_factory=FleetConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    vehicles: VehiclesConfig = Field(default_factory=VehiclesConfig)


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
