"""Scenes API: /api/scenes/* — smart composite vehicle workflows."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, HTTPException

from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import load_config, resolve_vin

router = APIRouter()

SCENES = [
    {
        "id": "morning",
        "name": "Morning Briefing",
        "icon": "sunrise",
        "description": "Battery, climate, readiness",
    },
    {
        "id": "goodnight",
        "name": "Goodnight Check",
        "icon": "moon",
        "description": "Lock, sentry, charge schedule",
    },
    {
        "id": "trip",
        "name": "Trip Prep",
        "icon": "map",
        "description": "Battery, range, tires, climate",
    },
]


@router.get("/")
def list_scenes() -> list:
    """Available smart scenes."""
    return SCENES


def _fetch_parallel(tasks: dict) -> dict:
    results: dict = {}
    with ThreadPoolExecutor(max_workers=max(1, len(tasks))) as executor:
        futures = {executor.submit(fn): key for key, fn in tasks.items()}
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as exc:  # noqa: BLE001
                results[key] = {"_error": str(exc)}
    return results


def _safe(results: dict, key: str) -> dict:
    val = results.get(key, {})
    if isinstance(val, dict) and "_error" in val:
        return {}
    return val if isinstance(val, dict) else {}


@router.post("/{scene_id}/execute")
def execute_scene(scene_id: str) -> dict:
    """Execute a scene and return collected data."""
    valid_ids = {s["id"] for s in SCENES}
    if scene_id not in valid_ids:
        raise HTTPException(404, f"Scene '{scene_id}' not found")

    try:
        cfg = load_config()
        backend = get_vehicle_backend(cfg)
        vin = resolve_vin(cfg, None)
    except Exception as exc:
        raise HTTPException(502, f"Backend unavailable: {exc}") from exc

    if scene_id == "morning":
        return _execute_morning(backend, vin)
    if scene_id == "goodnight":
        return _execute_goodnight(backend, vin)
    if scene_id == "trip":
        return _execute_trip(backend, vin)

    raise HTTPException(404, f"Scene '{scene_id}' not implemented")


def _execute_morning(backend, vin: str) -> dict:
    data = _fetch_parallel(
        {
            "charge": lambda: backend.get_charge_state(vin),
            "climate": lambda: backend.get_climate_state(vin),
            "drive": lambda: backend.get_drive_state(vin),
            "vehicle": lambda: backend.get_vehicle_data(vin),
        }
    )

    charge = _safe(data, "charge")
    climate = _safe(data, "climate")
    drive = _safe(data, "drive")
    vehicle = _safe(data, "vehicle")
    vs = vehicle.get("vehicle_state", {}) if isinstance(vehicle, dict) else {}

    battery_level = charge.get("battery_level")
    est_range = charge.get("battery_range") or charge.get("est_battery_range")

    return {
        "scene": "morning",
        "battery": {
            "level": battery_level,
            "limit": charge.get("charge_limit_soc"),
            "range_mi": round(est_range, 1) if isinstance(est_range, (int, float)) else None,
            "charging_state": charge.get("charging_state"),
        },
        "climate": {
            "on": climate.get("is_climate_on", False),
            "inside_temp_c": climate.get("inside_temp"),
            "outside_temp_c": climate.get("outside_temp"),
            "driver_temp_setting": climate.get("driver_temp_setting"),
        },
        "drive": {
            "shift_state": drive.get("shift_state") or "P",
            "speed": drive.get("speed"),
        },
        "security": {
            "locked": vs.get("locked"),
            "sentry_mode": vs.get("sentry_mode"),
        },
        "software": vs.get("car_version"),
    }


def _execute_goodnight(backend, vin: str) -> dict:
    data = _fetch_parallel(
        {
            "charge": lambda: backend.get_charge_state(vin),
            "vehicle": lambda: backend.get_vehicle_data(vin),
        }
    )

    charge = _safe(data, "charge")
    vehicle = _safe(data, "vehicle")
    vs = vehicle.get("vehicle_state", {}) if isinstance(vehicle, dict) else {}

    locked = vs.get("locked")
    sentry_on = vs.get("sentry_mode")
    battery_level = charge.get("battery_level")
    charge_limit = charge.get("charge_limit_soc", 80)
    charging_state = charge.get("charging_state", "Unknown")
    scheduled = charge.get("scheduled_charging_pending", False)
    charge_ok = charging_state in ("Charging", "Complete") or scheduled

    return {
        "scene": "goodnight",
        "security": {
            "locked": locked,
            "locked_ok": locked is True,
            "sentry_mode": sentry_on,
            "sentry_ok": sentry_on is True,
        },
        "battery": {
            "level": battery_level,
            "limit": charge_limit,
            "charging_state": charging_state,
            "charge_ok": charge_ok,
            "scheduled_charging": scheduled,
        },
        "warnings": [
            *(["Doors are UNLOCKED"] if locked is False else []),
            *(["Sentry mode is OFF"] if sentry_on is False else []),
            *(["Vehicle is not charging"] if not charge_ok else []),
        ],
    }


def _execute_trip(backend, vin: str) -> dict:
    data = _fetch_parallel(
        {
            "charge": lambda: backend.get_charge_state(vin),
            "climate": lambda: backend.get_climate_state(vin),
            "vehicle": lambda: backend.get_vehicle_data(vin),
        }
    )

    charge = _safe(data, "charge")
    climate = _safe(data, "climate")
    vehicle = _safe(data, "vehicle")
    vs = vehicle.get("vehicle_state", {}) if isinstance(vehicle, dict) else {}

    battery_level = charge.get("battery_level")
    est_range = charge.get("battery_range") or charge.get("est_battery_range")

    tires: dict[str, float | None] = {}
    for key, label in {
        "tpms_pressure_fl": "fl",
        "tpms_pressure_fr": "fr",
        "tpms_pressure_rl": "rl",
        "tpms_pressure_rr": "rr",
    }.items():
        val = vs.get(key)
        if val is not None:
            tires[label] = round(float(val), 2)

    return {
        "scene": "trip",
        "battery": {
            "level": battery_level,
            "range_mi": round(est_range, 1) if isinstance(est_range, (int, float)) else None,
            "charging_state": charge.get("charging_state"),
            "battery_ok": isinstance(battery_level, int) and battery_level >= 20,
        },
        "climate": {
            "on": climate.get("is_climate_on", False),
            "inside_temp_c": climate.get("inside_temp"),
            "outside_temp_c": climate.get("outside_temp"),
            "driver_temp_setting": climate.get("driver_temp_setting"),
        },
        "tires": tires or None,
        "navigation_sent": False,
    }
