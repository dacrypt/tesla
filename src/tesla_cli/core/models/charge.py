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
    charge_amps: int = 0
    charger_power: int = 0
    time_to_full_charge: float = 0.0
    charge_port_door_open: bool = False
    charge_port_latch: str = ""
    scheduled_charging_pending: bool = False
    scheduled_charging_start_time: str = ""


class ChargingHistoryPoint(BaseModel):
    """A single data point from Fleet API charge_history."""

    timestamp: str = ""
    kwh: float = 0.0
    location: str = ""


class ChargingHistory(BaseModel):
    """Parsed Fleet API charge_history response."""

    total_kwh: float = 0.0
    total_label: str = ""
    points: list[ChargingHistoryPoint] = []
    breakdown: dict[str, str] = {}  # category -> "value unit"

    @classmethod
    def from_api(cls, data: dict) -> ChargingHistory:
        """Parse raw Fleet API charge_history response into a structured model."""
        total = data.get("total_charged", {})
        total_kwh = 0.0
        total_label = ""
        if total:
            try:
                total_kwh = float(total.get("value", 0))
            except (ValueError, TypeError):
                pass
            total_label = (
                f"{total.get('value', '')} {total.get('after_adornment', '')}".strip()
            )

        points: list[ChargingHistoryPoint] = []
        graph = data.get("charging_history_graph", {})
        for pt in graph.get("data_points", []):
            raw_val = 0.0
            location = ""
            if pt.get("values"):
                v = pt["values"][0]
                try:
                    raw_val = float(v.get("raw_value", 0))
                except (ValueError, TypeError):
                    pass
                location = v.get("sub_title", "")
            if raw_val > 0:
                points.append(
                    ChargingHistoryPoint(
                        timestamp=pt.get("timestamp", {}).get("display_string", ""),
                        kwh=raw_val,
                        location=location,
                    )
                )

        breakdown: dict[str, str] = {}
        for key, item in data.get("total_charged_breakdown", {}).items():
            breakdown[key] = (
                f"{item.get('value', '')} {item.get('after_adornment', '')} "
                f"{item.get('sub_title', '')}".strip()
            )

        return cls(
            total_kwh=total_kwh,
            total_label=total_label,
            points=points,
            breakdown=breakdown,
        )
