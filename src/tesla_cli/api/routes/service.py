"""Service API: /api/service/* — vehicle service history and appointments."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import load_config, resolve_vin

router = APIRouter()


@router.get("/history")
def service_history() -> list:
    """Vehicle service visit history."""
    try:
        cfg = load_config()
        backend = get_vehicle_backend(cfg)
        vin = resolve_vin(cfg, None)
        result = backend.get_service_visits(vin)
        if isinstance(result, list):
            return result
        return result.get("service_visits", result.get("visits", []))
    except AttributeError:
        # Backend doesn't implement get_service_visits
        return []
    except Exception as exc:
        raise HTTPException(502, f"Service history unavailable: {exc}") from exc


@router.get("/appointments")
def service_appointments() -> list:
    """Upcoming service appointments."""
    try:
        cfg = load_config()
        backend = get_vehicle_backend(cfg)
        # Backends expose get_service_appointments() without a VIN (account-level).
        result = backend.get_service_appointments()
        if isinstance(result, list):
            return result
        return result.get("appointments", [])
    except AttributeError:
        return []
    except Exception as exc:
        raise HTTPException(502, f"Service appointments unavailable: {exc}") from exc


@router.get("/reminders")
def service_reminders() -> list:
    """Maintenance reminders from the odometer and the log of completed services.

    Items with a logged service report ``basis: "logged"`` and a real
    ``overdue``; others are estimates (next multiple of the interval).
    """
    from tesla_cli.core.service_log import reminders

    try:
        cfg = load_config()
        backend = get_vehicle_backend(cfg)
        vin = resolve_vin(cfg, None)
        try:
            odometer_mi = backend.get_vehicle_state(vin).get("odometer") or 0
            odometer_km = round(odometer_mi * 1.60934)
        except Exception:  # noqa: BLE001 — car asleep / offline: reminders still useful
            odometer_km = 0
        return reminders(odometer_km)
    except Exception as exc:
        raise HTTPException(502, f"Service reminders unavailable: {exc}") from exc


class ServiceLogEntry(BaseModel):
    item: str
    km: float | None = None
    date: str | None = None  # YYYY-MM-DD, default today
    note: str = ""


@router.get("/log")
def service_log() -> list:
    """Completed maintenance services, oldest first."""
    from tesla_cli.core.service_log import load_log

    return load_log()


@router.post("/log")
def service_log_add(body: ServiceLogEntry) -> dict:
    """Record a completed maintenance service."""
    from datetime import date as _date

    from tesla_cli.core.service_log import record

    try:
        on = _date.fromisoformat(body.date) if body.date else None
        return record(body.item, km=body.km, on=on, note=body.note)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
