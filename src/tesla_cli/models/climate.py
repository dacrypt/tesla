"""Climate state models."""

from __future__ import annotations

from pydantic import BaseModel


class ClimateState(BaseModel):
    inside_temp: float | None = None
    outside_temp: float | None = None
    driver_temp_setting: float = 0.0
    passenger_temp_setting: float = 0.0
    is_climate_on: bool = False
    is_preconditioning: bool = False
    fan_status: int = 0
    seat_heater_left: int = 0
    seat_heater_right: int = 0
    is_front_defroster_on: bool = False
    is_rear_defroster_on: bool = False
