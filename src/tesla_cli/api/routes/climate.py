"""Climate API routes: /api/climate/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import load_config, resolve_vin
from tesla_cli.core.exceptions import VehicleAsleepError

router = APIRouter()


def _bv(request: Request):
    cfg = load_config()
    v = resolve_vin(cfg, request.app.state.override_vin)
    return get_vehicle_backend(cfg), v


@router.get("/status")
def climate_status(request: Request) -> dict:
    """Current climate state."""
    backend, v = _bv(request)
    try:
        return backend.get_climate_state(v)
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.post("/on")
def climate_on(request: Request) -> dict:
    """Turn climate on."""
    backend, v = _bv(request)
    try:
        backend.command(v, "auto_conditioning_start")
        return {"status": "ok", "climate": "on"}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.post("/off")
def climate_off(request: Request) -> dict:
    """Turn climate off."""
    backend, v = _bv(request)
    try:
        backend.command(v, "auto_conditioning_stop")
        return {"status": "ok", "climate": "off"}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


class SetTempRequest(BaseModel):
    driver_temp: float
    passenger_temp: float | None = None


@router.post("/temp")
def set_temp(body: SetTempRequest, request: Request) -> dict:
    """Set cabin temperature (15–30 °C)."""
    if not 15.0 <= body.driver_temp <= 30.0:
        raise HTTPException(status_code=422, detail="temp must be 15–30 °C")
    backend, v = _bv(request)
    passenger = body.passenger_temp or body.driver_temp
    try:
        backend.command(v, "set_temps", driver_temp=body.driver_temp, passenger_temp=passenger)
        return {"status": "ok", "driver_temp": body.driver_temp, "passenger_temp": passenger}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")
