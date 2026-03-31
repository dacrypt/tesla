"""TeslaMate API routes: /api/teslaMate/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from tesla_cli.config import load_config

router = APIRouter()


def _backend():
    """Return a connected TeslaMateBackend or raise 503."""
    cfg = load_config()
    if not cfg.teslaMate.database_url:
        raise HTTPException(
            status_code=503,
            detail="TeslaMate not configured. Set teslaMate.database_url in config.",
        )
    from tesla_cli.backends.teslaMate import TeslaMateBacked
    return TeslaMateBacked(cfg.teslaMate.database_url, car_id=cfg.teslaMate.car_id)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/trips")
def tm_trips(limit: int = 20) -> list:
    """Recent driving trips from TeslaMate.

    Query params:
    - `limit` — number of trips to return (default 20)
    """
    try:
        return _backend().get_trips(limit=limit)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/charges")
def tm_charges(limit: int = 20) -> list:
    """Recent charging sessions from TeslaMate.

    Query params:
    - `limit` — number of sessions to return (default 20)
    """
    try:
        return _backend().get_charging_sessions(limit=limit)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/stats")
def tm_stats() -> dict:
    """Lifetime driving and charging statistics from TeslaMate."""
    try:
        return _backend().get_stats()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/efficiency")
def tm_efficiency(limit: int = 20) -> list:
    """Per-trip energy efficiency (Wh/km) from TeslaMate.

    Query params:
    - `limit` — number of trips to return (default 20)
    """
    try:
        return _backend().get_efficiency(limit=limit)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/heatmap")
def tm_heatmap(days: int = 365) -> list:
    """Driving-day heatmap data (date + km) for the past N days.

    Query params:
    - `days` — lookback window (default 365)
    """
    try:
        return _backend().get_drive_days(days=days)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/vampire")
def tm_vampire(days: int = 30) -> dict:
    """Vampire drain analysis for the past N days.

    Query params:
    - `days` — lookback window (default 30)
    """
    try:
        return _backend().get_vampire_drain(days=days)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/daily-energy")
def tm_daily_energy(days: int = 30) -> list:
    """Daily energy added (kWh) for the past N days.

    Query params:
    - `days` — lookback window (default 30)
    """
    try:
        return _backend().get_daily_energy(days=days)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/report/{month}")
def tm_report(month: str) -> dict:
    """Monthly driving + charging summary.

    Path params:
    - `month` — YYYY-MM format (e.g. 2026-03)
    """
    try:
        return _backend().get_monthly_report(month)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
