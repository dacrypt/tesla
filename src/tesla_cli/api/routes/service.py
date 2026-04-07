"""Service API: /api/service/* — vehicle service history and appointments."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

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
        vin = resolve_vin(cfg, None)
        result = backend.get_service_appointments(vin)
        if isinstance(result, list):
            return result
        return result.get("appointments", [])
    except AttributeError:
        return []
    except Exception as exc:
        raise HTTPException(502, f"Service appointments unavailable: {exc}") from exc


@router.get("/reminders")
def service_reminders() -> list:
    """Service reminders calculated from odometer and maintenance intervals."""
    try:
        cfg = load_config()
        backend = get_vehicle_backend(cfg)
        vin = resolve_vin(cfg, None)

        # Get current odometer from vehicle state
        try:
            vs = backend.get_vehicle_state(vin)
            odometer_mi = vs.get("odometer") or 0
            odometer_km = round(odometer_mi * 1.60934)
        except Exception:
            odometer_km = 0

        # Standard Tesla maintenance intervals (km)
        intervals = [
            {
                "id": "tires",
                "name": "Tire Rotation",
                "interval_km": 10_000,
                "description": "Rotate tires every 10,000 km",
            },
            {
                "id": "cabin_air",
                "name": "Cabin Air Filter",
                "interval_km": 24_000,
                "description": "Replace cabin air filter every 2 years / 24,000 km",
            },
            {
                "id": "brake_fluid",
                "name": "Brake Fluid Test",
                "interval_km": 40_000,
                "description": "Test brake fluid every 2 years / 40,000 km",
            },
            {
                "id": "hepa_filter",
                "name": "HEPA Filter",
                "interval_km": 48_000,
                "description": "Replace HEPA filter every 3 years / 48,000 km",
            },
            {
                "id": "ac_desiccant",
                "name": "A/C Desiccant Bag",
                "interval_km": 96_000,
                "description": "Replace A/C desiccant bag every 6 years / 96,000 km",
            },
        ]

        reminders = []
        for item in intervals:
            if odometer_km > 0:
                cycles_done = odometer_km // item["interval_km"]
                next_service_km = (cycles_done + 1) * item["interval_km"]
                km_until = next_service_km - odometer_km
                pct = round((odometer_km % item["interval_km"]) / item["interval_km"] * 100)
            else:
                next_service_km = item["interval_km"]
                km_until = item["interval_km"]
                pct = 0

            reminders.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "description": item["description"],
                    "interval_km": item["interval_km"],
                    "current_odometer_km": odometer_km,
                    "next_service_km": next_service_km,
                    "km_until_service": km_until,
                    "progress_pct": pct,
                    "due_soon": km_until <= 2_000,
                    "overdue": km_until <= 0,
                }
            )

        return reminders
    except Exception as exc:
        raise HTTPException(502, f"Service reminders unavailable: {exc}") from exc
