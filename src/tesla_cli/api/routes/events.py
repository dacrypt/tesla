"""Event stream API."""

from __future__ import annotations

from fastapi import APIRouter

from tesla_cli.core import events

router = APIRouter()


@router.get("")
def events_list(limit: int = 50) -> list:
    """List recent events."""
    return events.list_events(limit=limit)
