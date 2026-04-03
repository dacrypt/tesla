"""TeslaMate API routes: /api/teslaMate/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from tesla_cli.core.config import load_config

router = APIRouter()


def _backend():
    """Return a connected TeslaMateBackend or raise 503."""
    cfg = load_config()
    if not cfg.teslaMate.database_url:
        raise HTTPException(
            status_code=503,
            detail="TeslaMate not configured. Set teslaMate.database_url in config.",
        )
    from tesla_cli.core.backends.teslaMate import TeslaMateBacked

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
        cfg = load_config()
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
        ym = str(s.get("start_date") or "")[:7]
        kwh = float(s.get("energy_added_kwh") or 0)
        by_month[ym]["sessions"] += 1
        by_month[ym]["kwh"] = round(by_month[ym]["kwh"] + kwh, 3)
        by_month[ym]["cost"] = round(by_month[ym]["cost"] + kwh * cost_per_kwh, 2)

    return {
        "cost_per_kwh": cost_per_kwh,
        "months": dict(sorted(by_month.items(), reverse=True)),
        "sessions": len(sessions),
    }


@router.get("/charging-locations")
def teslaMate_charging_locations_api(days: int = 90, limit: int = 10) -> list:
    """Top charging locations by session count.

    Query params:
    - `days`  — look-back window (default 90)
    - `limit` — max locations to return (default 10)

    Returns list of {location, sessions, kwh_total, last_visit}.
    """
    try:
        return _backend().get_charging_locations(days=days, limit=limit)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc))


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


@router.get("/stack/status")
def teslaMate_stack_status() -> dict:
    """Managed TeslaMate stack status (Docker containers).

    Returns {managed, installed, running, services: [...]} or
    {managed: false} when using an external database.
    """
    cfg = load_config()
    if not cfg.teslaMate.managed:
        return {"managed": False, "installed": False, "running": False, "services": []}
    from pathlib import Path

    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)
    return {
        "managed": True,
        "installed": stack.is_installed(),
        "running": stack.is_running(),
        "services": stack.status(),
        "ports": {
            "teslamate": cfg.teslaMate.teslamate_port,
            "grafana": cfg.teslaMate.grafana_port,
            "postgres": cfg.teslaMate.postgres_port,
            "mqtt": cfg.teslaMate.mqtt_port,
        },
    }


def _get_managed_stack():
    """Return (config, TeslaMateStack) or raise 400 if not managed."""
    from pathlib import Path

    from tesla_cli.infra.teslamate_stack import TeslaMateStack

    cfg = load_config()
    if not cfg.teslaMate.managed:
        raise HTTPException(status_code=400, detail="TeslaMate stack is not managed by CLI.")
    stack = TeslaMateStack(Path(cfg.teslaMate.stack_dir) if cfg.teslaMate.stack_dir else None)
    if not stack.is_installed():
        raise HTTPException(status_code=400, detail="TeslaMate stack is not installed.")
    return cfg, stack


@router.post("/stack/start")
def teslaMate_stack_start() -> dict:
    """Start the managed TeslaMate stack."""
    _, stack = _get_managed_stack()
    try:
        stack.start()
        return {"ok": True, "action": "start"}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/stack/stop")
def teslaMate_stack_stop() -> dict:
    """Stop the managed TeslaMate stack."""
    _, stack = _get_managed_stack()
    try:
        stack.stop()
        return {"ok": True, "action": "stop"}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/stack/restart")
def teslaMate_stack_restart() -> dict:
    """Restart the managed TeslaMate stack."""
    _, stack = _get_managed_stack()
    try:
        stack.restart()
        return {"ok": True, "action": "restart"}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/stack/update")
def teslaMate_stack_update() -> dict:
    """Pull latest images and recreate containers."""
    _, stack = _get_managed_stack()
    try:
        output = stack.update()
        return {"ok": True, "action": "update", "output": output}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/stack/logs")
def teslaMate_stack_logs(service: str = "", lines: int = 80) -> dict:
    """Get recent logs from the managed stack."""
    _, stack = _get_managed_stack()
    try:
        result = stack.logs(service=service or None, lines=lines)
        return {"logs": result.stdout or "", "service": service or "all"}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/battery-degradation")
def battery_degradation(months: int = 12) -> dict:
    """Battery degradation trend from high-SoC charges."""
    cfg = load_config()
    if not cfg.teslaMate.database_url:
        raise HTTPException(status_code=404, detail="TeslaMate not configured.")
    try:
        from tesla_cli.core.backends.teslaMate import TeslaMateBacked

        backend = TeslaMateBacked(cfg.teslaMate.database_url, car_id=cfg.teslaMate.car_id)
        return backend.get_battery_degradation(months=months)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
