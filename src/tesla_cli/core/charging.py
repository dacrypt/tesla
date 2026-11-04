"""Unified charging-session history (TeslaMate + Fleet API).

Framework-independent: used by both ``tesla charge sessions`` and the REST API.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from tesla_cli.core.backends import get_vehicle_backend
from tesla_cli.core.config import Config, load_config


def fetch_charging_sessions(
    limit: int = 20,
    cfg: Config | None = None,
    backend_factory: Callable[[], Any] | None = None,
) -> tuple[list, str]:
    """Fetch unified charging sessions, merging TeslaMate + Fleet API when both available.

    Strategy:
    - TeslaMate provides: per-session costs, battery levels, precise timestamps
    - Fleet API provides: aggregated history with location labels
    - When both available: TeslaMate is primary, Fleet API fills gaps
    - Dedup by matching date prefix (YYYY-MM-DD) + similar kWh (±20%)

    Returns (sessions, source_name). Shared by the CLI (`charge sessions`,
    `cost-summary`) and the REST API.
    """
    from tesla_cli.core.models.charge import ChargingHistory, ChargingSession

    cfg = cfg or load_config()
    cost_per_kwh = cfg.general.cost_per_kwh
    tm_sessions: list[ChargingSession] = []
    fleet_sessions: list[ChargingSession] = []
    sources: list[str] = []

    # Try TeslaMate
    try:
        if cfg.teslaMate.database_url:
            from tesla_cli.core.backends.teslaMate import TeslaMateBacked

            tm = TeslaMateBacked(cfg.teslaMate.database_url)
            rows = tm.get_charging_sessions(limit=limit)
            tm_sessions = [ChargingSession.from_teslamate(r, cost_per_kwh) for r in rows]
            if tm_sessions:
                sources.append("TeslaMate")
    except Exception:
        logging.getLogger(__name__).debug("Ignored error", exc_info=True)

    # Try Fleet API
    try:
        backend = (backend_factory or (lambda: get_vehicle_backend(cfg)))()
        raw = backend.get_charge_history()
        history = ChargingHistory.from_api(raw)
        fleet_sessions = [
            ChargingSession.from_fleet_point(pt, cost_per_kwh) for pt in history.points[:limit]
        ]
        if fleet_sessions:
            sources.append("Fleet API")
    except Exception:
        logging.getLogger(__name__).debug("Ignored error", exc_info=True)

    # Merge: TeslaMate is primary, add Fleet API sessions that don't overlap
    if tm_sessions and fleet_sessions:
        tm_dates = {s.date[:10] for s in tm_sessions if len(s.date) >= 10}
        for fs in fleet_sessions:
            # Fleet API dates are shorter ("Mar 15") — skip dedup if can't parse
            if not any(fs.date in d or d in fs.date for d in tm_dates):
                tm_sessions.append(fs)
        sessions = sorted(tm_sessions, key=lambda s: s.date, reverse=True)[:limit]
        source_used = " + ".join(sources)
    elif tm_sessions:
        sessions = tm_sessions
        source_used = "TeslaMate"
    elif fleet_sessions:
        sessions = fleet_sessions
        source_used = "Fleet API"
    else:
        sessions = []
        source_used = ""

    return sessions, source_used
