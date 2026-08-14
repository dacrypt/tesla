"""Charge state models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

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
    scheduled_charging_start_time: str | None = None


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
            total_label = f"{total.get('value', '')} {total.get('after_adornment', '')}".strip()

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


class ChargingInvoice(BaseModel):
    """A Supercharging invoice from Tesla."""

    invoice_id: str = ""
    date: str = ""
    location: str = ""
    kwh: float = 0.0
    amount: float = 0.0
    currency: str = "USD"
    duration_minutes: int = 0
    vin: str = ""


class ChargingSession(BaseModel):
    """Unified charging session from any source (TeslaMate, Fleet API, Tessie)."""

    date: str = ""
    location: str = ""
    kwh: float = 0.0
    cost: float | None = None
    cost_estimated: bool = False
    battery_start: int | None = None
    battery_end: int | None = None
    source: str = ""  # "teslamate", "fleet", "tessie"
    process_id: int | None = None  # TeslaMate charging_processes.id, for curve lookup

    @classmethod
    def from_teslamate(cls, row: dict, cost_per_kwh: float = 0.0) -> ChargingSession:
        """Create from TeslaMate charging_processes row."""
        kwh = float(row.get("energy_added_kwh") or 0)
        cost = row.get("cost")
        estimated = False
        if cost is None and cost_per_kwh > 0 and kwh > 0:
            cost = round(kwh * cost_per_kwh, 2)
            estimated = True
        return cls(
            date=str(row.get("start_date") or "")[:16],
            location=(row.get("location") or "Unknown")[:40],
            kwh=round(kwh, 2),
            cost=round(float(cost), 2) if cost is not None else None,
            cost_estimated=estimated,
            battery_start=row.get("start_battery_level"),
            battery_end=row.get("end_battery_level"),
            source="teslamate",
            process_id=row.get("process_id") or row.get("id"),
        )

    @classmethod
    def from_fleet_point(
        cls, pt: ChargingHistoryPoint, cost_per_kwh: float = 0.0
    ) -> ChargingSession:
        """Create from Fleet API charging history data point."""
        cost = None
        estimated = False
        if cost_per_kwh > 0 and pt.kwh > 0:
            cost = round(pt.kwh * cost_per_kwh, 2)
            estimated = True
        return cls(
            date=pt.timestamp,
            location=pt.location,
            kwh=pt.kwh,
            cost=cost,
            cost_estimated=estimated,
            source="fleet",
        )


class ChargeSample(BaseModel):
    """A single sample point from a TeslaMate `charges` row."""

    ts: datetime
    soc: int
    power_kw: float
    current_a: float | None = None
    voltage_v: float | None = None
    phases: int | None = None
    ideal_range_km: float | None = None


class ChargeCurve(BaseModel):
    """Downsampled charge-session curve payload."""

    samples: list[ChargeSample]
    downsampled: bool
    total_samples: int
    stride: int  # 1 if not downsampled


class ChargeCurveStats(BaseModel):
    """Charge-session statistics computed over the full (un-downsampled) curve."""

    peak_kw: float
    avg_kw_20_80: float | None
    taper_knee_soc: int | None
    time_above_100kw_s: int
    energy_above_100kw_kwh: float
    phases_used: list[int]
    duration_s: int
    kwh_added: float


# ── Curiosities / enrichment (Phase 3) ──────────────────────────────────────


class RankInfo(BaseModel):
    """Where a session ranks among recent 20→80% charges."""

    fastest_20_to_80_position: int | None = None
    fastest_20_to_80_total: int | None = None
    is_personal_best: bool = False


class PreconditioningInfo(BaseModel):
    """Heuristic preconditioning detection from the early-session power signature."""

    detected: bool = False
    duration_minutes: int | None = None
    confidence: Literal["high", "medium", "low"] | None = None


class SharedStallInfo(BaseModel):
    """Detection of a Supercharger stall being shared mid-session."""

    detected: bool = False
    timestamp: datetime | None = None
    power_drop_kw: float | None = None


class AbrpCost(BaseModel):
    """Cost estimate vs actual session cost (ABRP fallback model in Phase 3)."""

    estimated_cost: float | None = None
    actual_cost: float | None = None
    delta_pct: float | None = None
    currency: str = "USD"
    available: bool = False


class ChargeEnrichment(BaseModel):
    """Aggregated session curiosities (rank, preconditioning, shared stall, ABRP cost)."""

    rank: RankInfo
    preconditioning: PreconditioningInfo
    shared_stall: SharedStallInfo
    abrp_cost: AbrpCost
