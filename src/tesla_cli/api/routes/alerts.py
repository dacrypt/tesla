"""Alert stream API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from tesla_cli.core import events

router = APIRouter()


@router.get("")
def alerts_list(limit: int = 50, active_only: bool = True) -> list:
    """List recent alerts."""
    return events.list_alerts(limit=limit, active_only=active_only)


@router.post("/{alert_id}/ack")
def alerts_ack(alert_id: str) -> dict:
    """Acknowledge one alert without resolving it."""
    result = events.ack_alert(alert_id)
    if result is None:
        raise HTTPException(404, f"Unknown alert: {alert_id}")
    return result
