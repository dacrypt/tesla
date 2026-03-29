"""Charge state models."""

from __future__ import annotations

from pydantic import BaseModel


class ChargeState(BaseModel):
    battery_level: int = 0
    battery_range: float = 0.0
    charging_state: str = ""  # Charging, Stopped, Disconnected, Complete
    charge_limit_soc: int = 0
    charge_rate: float = 0.0
    charger_voltage: int = 0
    charger_actual_current: int = 0
    charger_power: int = 0
    time_to_full_charge: float = 0.0
    charge_port_door_open: bool = False
    charge_port_latch: str = ""
    scheduled_charging_pending: bool = False
    scheduled_charging_start_time: str = ""
