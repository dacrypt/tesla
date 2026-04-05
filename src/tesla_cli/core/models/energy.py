"""Tesla Energy (Powerwall/Solar) data models."""

from __future__ import annotations

from pydantic import BaseModel


class EnergySiteInfo(BaseModel):
    site_id: int = 0
    site_name: str = ""
    battery_count: int = 0
    solar_power: float = 0.0
    battery_power: float = 0.0
    grid_power: float = 0.0
    load_power: float = 0.0
    battery_percentage: float = 0.0
    backup_reserve_percent: int = 0
    operation_mode: str = ""
    storm_mode_enabled: bool = False
    grid_status: str = ""


class EnergyHistory(BaseModel):
    period: str = ""
    solar_energy_exported: float = 0.0
    generator_energy_exported: float = 0.0
    grid_energy_imported: float = 0.0
    grid_energy_exported_from_solar: float = 0.0
    grid_energy_exported_from_battery: float = 0.0
    battery_energy_exported: float = 0.0
    battery_energy_imported_from_grid: float = 0.0
    battery_energy_imported_from_solar: float = 0.0
    consumer_energy_imported_from_grid: float = 0.0
    consumer_energy_imported_from_solar: float = 0.0
    consumer_energy_imported_from_battery: float = 0.0
