"""Automation rule models for the Tesla CLI automation engine."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AutomationTrigger(BaseModel):
    type: str  # battery_below, battery_above, charging_complete, charging_started,
    # sentry_event, location_enter, location_exit, state_change, time_of_day
    threshold: float | None = None  # For battery_below / battery_above
    field: str | None = None  # For state_change
    from_value: str | None = None  # For state_change
    to_value: str | None = None  # For state_change
    latitude: float | None = None  # For location_enter / location_exit
    longitude: float | None = None  # For location_enter / location_exit
    radius_km: float = 0.5  # For location_enter / location_exit
    time: str | None = None  # HH:MM format for time_of_day


class AutomationAction(BaseModel):
    type: str  # notify, command, exec (alias for command)
    message: str = ""
    command: str = ""


class AutomationRule(BaseModel):
    name: str
    trigger: AutomationTrigger
    action: AutomationAction
    enabled: bool = True
    last_fired: datetime | None = None
    cooldown_minutes: int = 30  # prevent rapid re-firing


class AutomationConfig(BaseModel):
    rules: list[AutomationRule] = Field(default_factory=list)
