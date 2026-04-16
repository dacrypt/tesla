"""Mission Control read model API."""

from __future__ import annotations

from fastapi import APIRouter

from tesla_cli.core import mission_control

router = APIRouter()


@router.get("")
def mission_control_view() -> dict:
    """Build and return the derived Mission Control payload."""
    return mission_control.build_mission_control()


@router.get("/dashboard-summary")
def mission_control_dashboard_summary() -> dict:
    """Build and return a compact Mission Control summary."""
    return mission_control.build_dashboard_summary()
