"""Security API routes: /api/security/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import load_config, resolve_vin
from tesla_cli.core.exceptions import VehicleAsleepError

router = APIRouter()


def _bv(request: Request):
    cfg = load_config()
    v = resolve_vin(cfg, request.query_params.get("vin") or request.app.state.override_vin)
    return get_vehicle_backend(cfg), v


@router.post("/lock")
def security_lock(request: Request) -> dict:
    """Lock the vehicle."""
    backend, v = _bv(request)
    try:
        backend.command(v, "door_lock")
        return {"status": "ok", "action": "locked"}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.post("/unlock")
def security_unlock(request: Request) -> dict:
    """Unlock the vehicle."""
    backend, v = _bv(request)
    try:
        backend.command(v, "door_unlock")
        return {"status": "ok", "action": "unlocked"}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.get("/sentry")
def security_sentry_status(request: Request) -> dict:
    """Get sentry mode status."""
    backend, v = _bv(request)
    try:
        data = backend.get_vehicle_state(v)
        return {
            "sentry_mode": data.get("sentry_mode", False),
            "sentry_mode_available": data.get("sentry_mode_available", True),
        }
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.post("/sentry/on")
def security_sentry_on(request: Request) -> dict:
    """Enable sentry mode."""
    backend, v = _bv(request)
    try:
        backend.command(v, "set_sentry_mode", on=True)
        return {"status": "ok", "sentry_mode": True}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.post("/sentry/off")
def security_sentry_off(request: Request) -> dict:
    """Disable sentry mode."""
    backend, v = _bv(request)
    try:
        backend.command(v, "set_sentry_mode", on=False)
        return {"status": "ok", "sentry_mode": False}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.post("/trunk/front")
def security_frunk(request: Request) -> dict:
    """Open the frunk."""
    backend, v = _bv(request)
    try:
        backend.command(v, "actuate_trunk", which_trunk="front")
        return {"status": "ok", "action": "frunk_opened"}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.post("/trunk/rear")
def security_trunk(request: Request) -> dict:
    """Open/close the trunk."""
    backend, v = _bv(request)
    try:
        backend.command(v, "actuate_trunk", which_trunk="rear")
        return {"status": "ok", "action": "trunk_toggled"}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.post("/horn")
def security_horn(request: Request) -> dict:
    """Honk the horn."""
    backend, v = _bv(request)
    try:
        backend.command(v, "honk_horn")
        return {"status": "ok", "action": "horn_honked"}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.post("/flash")
def security_flash(request: Request) -> dict:
    """Flash the lights."""
    backend, v = _bv(request)
    try:
        backend.command(v, "flash_lights")
        return {"status": "ok", "action": "lights_flashed"}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")
