"""Charge API routes: /api/charge/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import load_config, resolve_vin
from tesla_cli.core.exceptions import BackendNotSupportedError, VehicleAsleepError

router = APIRouter()


def _bv(request: Request):
    cfg = load_config()
    v = resolve_vin(cfg, request.app.state.override_vin)
    return get_vehicle_backend(cfg), v


@router.get("/status")
def charge_status(request: Request) -> dict:
    """Current charge state."""
    backend, v = _bv(request)
    try:
        return backend.get_charge_state(v)
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


class SetLimitRequest(BaseModel):
    percent: int


@router.post("/limit")
def set_charge_limit(body: SetLimitRequest, request: Request) -> dict:
    """Set charge limit (50–100)."""
    if not 50 <= body.percent <= 100:
        raise HTTPException(status_code=422, detail="percent must be 50–100")
    backend, v = _bv(request)
    try:
        backend.command(v, "set_charge_limit", percent=body.percent)
        return {"status": "ok", "charge_limit_soc": body.percent}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


class SetAmpsRequest(BaseModel):
    amps: int


@router.post("/amps")
def set_charge_amps(body: SetAmpsRequest, request: Request) -> dict:
    """Set charging amps (1–48)."""
    if not 1 <= body.amps <= 48:
        raise HTTPException(status_code=422, detail="amps must be 1–48")
    backend, v = _bv(request)
    try:
        backend.command(v, "set_charging_amps", charging_amps=body.amps)
        return {"status": "ok", "charging_amps": body.amps}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.post("/start")
def charge_start(request: Request) -> dict:
    """Start charging."""
    backend, v = _bv(request)
    try:
        backend.command(v, "charge_start")
        return {"status": "ok"}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.post("/stop")
def charge_stop(request: Request) -> dict:
    """Stop charging."""
    backend, v = _bv(request)
    try:
        backend.command(v, "charge_stop")
        return {"status": "ok"}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")


@router.get("/history")
def charge_history(request: Request) -> dict:
    """Charging history (Fleet API). Returns parsed history with total kWh and per-session data."""
    from tesla_cli.core.models.charge import ChargingHistory

    cfg = load_config()
    backend = get_vehicle_backend(cfg)
    try:
        raw = backend.get_charge_history()
    except BackendNotSupportedError:
        raise HTTPException(
            status_code=501,
            detail="charge history requires Fleet API backend. "
            "Use /api/teslaMate/charging for TeslaMate data.",
        )

    history = ChargingHistory.from_api(raw)
    return history.model_dump()


@router.get("/sessions")
def charge_sessions(request: Request, limit: int = 20) -> list[dict]:
    """Unified charging sessions from best available source (TeslaMate > Fleet API).

    Returns a list of normalized ChargingSession objects with source attribution.
    Applies cost_per_kwh estimation when actual cost is missing.
    """
    from tesla_cli.cli.commands.charge import _fetch_sessions

    sessions, _source = _fetch_sessions(limit=limit)

    if not sessions:
        raise HTTPException(
            status_code=404,
            detail="No charging sessions. Connect TeslaMate or use Fleet API backend.",
        )

    return [s.model_dump() for s in sessions]
