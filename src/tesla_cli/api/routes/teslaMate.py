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


@router.get("/timeline")
def teslaMate_timeline(days: int = 30) -> list:
    """Unified event timeline: trips, charges, OTA updates (chronological, newest first)."""
    try:
        backend = _backend()
        return backend.get_timeline(days=days)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc))


@router.get("/cost-report")
def teslaMate_cost_report(month: str = "", limit: int = 100) -> dict:
    """Monthly charging cost report grouped by month.

    Query params:
    - `month` — filter to YYYY-MM (optional)
    - `limit` — max sessions to analyse (default 100)

    Returns {cost_per_kwh, months: {YYYY-MM: {sessions, kwh, cost}}, sessions: N}
    """
    import collections
    try:
        backend = _backend()
        cfg     = load_config()
        sessions = backend.get_charging_sessions(limit=limit)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc))

    cost_per_kwh = cfg.general.cost_per_kwh or 0.0

    if month:
        sessions = [s for s in sessions if str(s.get("start_date") or "").startswith(month)]

    by_month: dict = collections.defaultdict(lambda: {"sessions": 0, "kwh": 0.0, "cost": 0.0})
    for s in sessions:
        ym  = str(s.get("start_date") or "")[:7]
        kwh = float(s.get("energy_added_kwh") or 0)
        by_month[ym]["sessions"] += 1
        by_month[ym]["kwh"]      = round(by_month[ym]["kwh"] + kwh, 3)
        by_month[ym]["cost"]     = round(by_month[ym]["cost"] + kwh * cost_per_kwh, 2)

    return {
        "cost_per_kwh": cost_per_kwh,
        "months":   dict(sorted(by_month.items(), reverse=True)),
        "sessions": len(sessions),
    }


@router.get("/trip-stats")
def teslaMate_trip_stats_api(days: int = 30) -> dict:
    """Aggregate trip statistics: totals, averages, and top routes.

    Query params:
    - `days` — look-back window (default 30)

    Returns {summary, top_routes, days}
    """
    try:
        backend = _backend()
        return backend.get_trip_stats(days=days)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc))
