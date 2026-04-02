"""Vehicle API routes: /api/vehicle/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import load_config, resolve_vin
from tesla_cli.core.exceptions import VehicleAsleepError

router = APIRouter()


def _backend_and_vin(request: Request):
    cfg = load_config()
    vin_override = request.query_params.get("vin") or request.app.state.override_vin
    v = resolve_vin(cfg, vin_override)
    return get_vehicle_backend(cfg), v


# ── Read endpoints ────────────────────────────────────────────────────────────


@router.get("/state")
def vehicle_state(request: Request) -> dict:
    """Full vehicle data (all states)."""
    backend, v = _backend_and_vin(request)
    try:
        return backend.get_vehicle_data(v)
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep. Call /wake first.")


@router.get("/location")
def vehicle_location(request: Request) -> dict:
    """Drive state including GPS location."""
    backend, v = _backend_and_vin(request)
    try:
        return backend.get_drive_state(v)
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.get("/charge")
def vehicle_charge(request: Request) -> dict:
    """Charge state."""
    backend, v = _backend_and_vin(request)
    try:
        return backend.get_charge_state(v)
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.get("/climate")
def vehicle_climate(request: Request) -> dict:
    """Climate state."""
    backend, v = _backend_and_vin(request)
    try:
        return backend.get_climate_state(v)
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.get("/vehicle-state")
def vehicle_vehicle_state(request: Request) -> dict:
    """Vehicle state (locks, doors, software, etc.)."""
    backend, v = _backend_and_vin(request)
    try:
        return backend.get_vehicle_state(v)
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.get("/list")
def vehicle_list(request: Request) -> list:
    """List all vehicles on the account."""
    backend, _ = _backend_and_vin(request)
    try:
        return backend.list_vehicles()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Command endpoint ──────────────────────────────────────────────────────────


class CommandRequest(BaseModel):
    command: str
    params: dict = {}


@router.get("/odometer")
def vehicle_odometer(request: Request) -> dict:
    """Current odometer reading and software version.

    Returns {vin, odometer_miles, car_version, queried_at}.
    """
    backend, v = _backend_and_vin(request)
    try:
        vs = backend.get_vehicle_state(v)
        from datetime import UTC, datetime

        return {
            "vin": v,
            "odometer_miles": vs.get("odometer"),
            "car_version": vs.get("car_version"),
            "queried_at": datetime.now(UTC).isoformat(),
        }
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/command")
def vehicle_command(body: CommandRequest, request: Request) -> dict:
    """Send a command to the vehicle.

    Commands: lock, unlock, honk_horn, flash_lights, charge_start,
              charge_stop, climate_on, climate_off, wake_up, ...
    """
    backend, v = _backend_and_vin(request)
    try:
        result = backend.command(v, body.command, **body.params)
        return {"status": "ok", "command": body.command, "result": result}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/wake")
def vehicle_wake(request: Request) -> dict:
    """Wake up the vehicle."""
    backend, v = _backend_and_vin(request)
    try:
        result = backend.wake_up(v)
        return {"status": "ok", "result": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
