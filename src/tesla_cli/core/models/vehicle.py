"""Vehicle data models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class VehicleSummary(BaseModel):
    """Minimal vehicle info for listing."""

    vin: str = ""
    display_name: str = ""
    state: str = ""  # online, asleep, offline
    model: str = ""
    color: str = ""


class VehicleData(BaseModel):
    """Complete vehicle data snapshot."""

    vin: str = ""
    display_name: str = ""
    state: str = ""
    odometer: float = 0.0
    car_version: str = ""
    raw: dict = Field(default_factory=dict)
