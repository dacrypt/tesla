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


@router.get("/last")
def charge_last() -> dict:
    """Most recent charging session with cost details."""
    from tesla_cli.cli.commands.charge import _fetch_sessions

    sessions, source = _fetch_sessions(limit=1)
    if not sessions:
        raise HTTPException(status_code=404, detail="No charging sessions found.")

    s = sessions[0]
    return {**s.model_dump(), "source_name": source}


@router.get("/weekly")
def charge_weekly(weeks: int = 4) -> dict:
    """Weekly charging summary — kWh, cost, sessions per week."""
    from collections import defaultdict
    from datetime import datetime

    from tesla_cli.cli.commands.charge import _fetch_sessions

    sessions, source = _fetch_sessions(limit=500)
    if not sessions:
        raise HTTPException(status_code=404, detail="No charging sessions found.")

    weekly: dict[str, dict] = defaultdict(lambda: {"kwh": 0.0, "cost": 0.0, "sessions": 0})
    for s in sessions:
        try:
            dt = datetime.strptime(s.date[:10], "%Y-%m-%d")
            week_key = dt.strftime("%Y-W%V")
            weekly[week_key]["kwh"] += s.kwh
            if s.cost is not None:
                weekly[week_key]["cost"] += s.cost
            weekly[week_key]["sessions"] += 1
        except (ValueError, TypeError):
            continue

    sorted_weeks = sorted(weekly.items(), reverse=True)[:weeks]
    sorted_weeks.reverse()

    return {
        "source": source,
        "weeks": [
            {
                "week": w,
                "kwh": round(d["kwh"], 1),
                "cost": round(d["cost"], 2),
                "sessions": d["sessions"],
            }
            for w, d in sorted_weeks
        ],
    }
