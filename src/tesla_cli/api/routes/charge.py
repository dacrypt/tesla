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
    except Exception as exc:
        if "412" in str(exc):
            raise HTTPException(
                status_code=412,
                detail="Vehicle not accessible. May be pre-delivery or require Fleet API.",
            )
        raise HTTPException(status_code=502, detail=str(exc))


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
    except Exception as exc:
        if "429" in str(exc):
            raise HTTPException(status_code=429, detail="Rate limited. Try again in a few seconds.")
        raise HTTPException(status_code=502, detail=str(exc))


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
    except Exception as exc:
        if "429" in str(exc):
            raise HTTPException(status_code=429, detail="Rate limited. Try again in a few seconds.")
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/start")
def charge_start(request: Request) -> dict:
    """Start charging."""
    backend, v = _bv(request)
    try:
        backend.command(v, "charge_start")
        return {"status": "ok"}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")
    except Exception as exc:
        if "429" in str(exc):
            raise HTTPException(status_code=429, detail="Rate limited. Try again in a few seconds.")
        raise HTTPException(status_code=502, detail=str(exc))


@router.post("/stop")
def charge_stop(request: Request) -> dict:
    """Stop charging."""
    backend, v = _bv(request)
    try:
        backend.command(v, "charge_stop")
        return {"status": "ok"}
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")
    except Exception as exc:
        if "429" in str(exc):
            raise HTTPException(status_code=429, detail="Rate limited. Try again in a few seconds.")
        raise HTTPException(status_code=502, detail=str(exc))


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
        return []

    return [s.model_dump() for s in sessions]


@router.get("/last")
def charge_last() -> dict:
    """Most recent charging session with cost details."""
    from tesla_cli.cli.commands.charge import _fetch_sessions

    sessions, source = _fetch_sessions(limit=1)
    if not sessions:
        return []

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
        return []

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


# ── Charge Schedules ───────────────────────────────────────────────────────────

_SCHEDULES_FILE_NAME = ".tesla-cli/charge_schedules.json"


def _load_schedules() -> list[dict]:
    import json
    from pathlib import Path

    path = Path.home() / _SCHEDULES_FILE_NAME
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:  # noqa: BLE001
        return []


def _save_schedules(schedules: list[dict]) -> None:
    import json
    from pathlib import Path

    path = Path.home() / _SCHEDULES_FILE_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(schedules, indent=2))


@router.get("/schedules")
def list_charge_schedules() -> list[dict]:
    """List configured location-based charging schedules."""
    return _load_schedules()


class ChargeScheduleBody(BaseModel):
    name: str
    location: str = ""
    latitude: float | None = None
    longitude: float | None = None
    radius_km: float = 0.5
    start_time: str = ""  # HH:MM
    end_time: str = ""  # HH:MM
    limit_percent: int = 80
    days: list[str] = []  # ["Mon", "Tue", ...] — empty means every day
    enabled: bool = True


@router.post("/schedules")
def add_charge_schedule(body: ChargeScheduleBody) -> dict:
    """Add a location-based charging schedule."""
    schedules = _load_schedules()
    new_id = max((s.get("id", 0) for s in schedules), default=0) + 1
    entry = {**body.model_dump(), "id": new_id}
    schedules.append(entry)
    _save_schedules(schedules)
    return {"ok": True, "id": new_id}


@router.delete("/schedules/{schedule_id}")
def remove_charge_schedule(schedule_id: int) -> dict:
    """Remove a charging schedule by ID."""
    schedules = _load_schedules()
    before = len(schedules)
    schedules = [s for s in schedules if s.get("id") != schedule_id]
    if len(schedules) == before:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id} not found")
    _save_schedules(schedules)
    return {"ok": True}


# ── Charge Analytics ───────────────────────────────────────────────────────────


@router.get("/analytics/sessions")
def charge_sessions_api(limit: int = 20) -> list[dict]:
    """Recent charging sessions from the best available source."""
    from tesla_cli.cli.commands.charge import _fetch_sessions

    sessions, _source = _fetch_sessions(limit=limit)
    if not sessions:
        return []
    return [s.model_dump() for s in sessions]


@router.get("/analytics/cost-summary")
def charge_cost_summary_api() -> dict:
    """Monthly cost breakdown across all charging sessions."""
    from collections import defaultdict
    from datetime import datetime

    from tesla_cli.cli.commands.charge import _fetch_sessions

    sessions, source = _fetch_sessions(limit=1000)
    if not sessions:
        return []

    monthly: dict[str, dict] = defaultdict(
        lambda: {"kwh": 0.0, "cost": 0.0, "sessions": 0, "cost_estimated": False}
    )
    total_kwh = 0.0
    total_cost = 0.0

    for s in sessions:
        try:
            dt = datetime.strptime(s.date[:10], "%Y-%m-%d")
            month_key = dt.strftime("%Y-%m")
            monthly[month_key]["kwh"] += s.kwh
            monthly[month_key]["sessions"] += 1
            total_kwh += s.kwh
            if s.cost is not None:
                monthly[month_key]["cost"] += s.cost
                total_cost += s.cost
            if s.cost_estimated:
                monthly[month_key]["cost_estimated"] = True
        except (ValueError, TypeError):
            continue

    sorted_months = sorted(monthly.items(), reverse=True)[:12]

    return {
        "source": source,
        "total_kwh": round(total_kwh, 2),
        "total_cost": round(total_cost, 2),
        "months": [
            {
                "month": m,
                "kwh": round(d["kwh"], 2),
                "cost": round(d["cost"], 2),
                "sessions": d["sessions"],
                "cost_estimated": d["cost_estimated"],
            }
            for m, d in sorted_months
        ],
    }


@router.get("/analytics/forecast")
def charge_forecast_api(request: Request) -> dict:
    """Forecast: time to reach charge limit given current charge rate."""
    backend, v = _bv(request)
    try:
        state = backend.get_charge_state(v)
    except VehicleAsleepError:
        raise HTTPException(status_code=503, detail="Vehicle is asleep.")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    battery_level = state.get("battery_level") or state.get("charge_state", {}).get("battery_level")
    charge_limit = state.get("charge_limit_soc") or state.get("charge_state", {}).get(
        "charge_limit_soc"
    )
    minutes_to_full = state.get("minutes_to_full_charge") or state.get("charge_state", {}).get(
        "minutes_to_full_charge"
    )
    charging_state = state.get("charging_state") or state.get("charge_state", {}).get(
        "charging_state", "Unknown"
    )
    charge_rate = state.get("charge_rate") or state.get("charge_state", {}).get("charge_rate")
    energy_added = state.get("charge_energy_added") or state.get("charge_state", {}).get(
        "charge_energy_added"
    )

    return {
        "battery_level": battery_level,
        "charge_limit_soc": charge_limit,
        "charging_state": charging_state,
        "minutes_to_full_charge": minutes_to_full,
        "charge_rate_mph": charge_rate,
        "charge_energy_added_kwh": energy_added,
        "is_charging": charging_state == "Charging",
    }
