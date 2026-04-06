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
    type: str  # notify, command, exec (alias for command), webhook
    message: str = ""
    command: str = ""
    webhook_url: str = ""  # URL to POST to (for type="webhook")
    webhook_payload: str = ""  # JSON template; supports {battery_level}, {ts}, etc.


class AutomationCondition(BaseModel):
    """Additional condition that must be true for rule to fire."""

    field: str = ""  # e.g. "climate_state.inside_temp", "charge_state.battery_level"
    operator: str = "lt"  # lt, gt, eq, ne, contains
    value: str = ""  # compared as float if numeric, string otherwise


class AutomationRule(BaseModel):
    name: str
    trigger: AutomationTrigger
    action: AutomationAction
    conditions: list[AutomationCondition] = Field(default_factory=list)
    enabled: bool = True
    last_fired: datetime | None = None
    cooldown_minutes: int = 30  # prevent rapid re-firing
    delay_seconds: int = 0  # Delay before executing action
    retry_count: int = 0  # Number of retries on action failure
    retry_delay_seconds: int = 60


class AutomationConfig(BaseModel):
    rules: list[AutomationRule] = Field(default_factory=list)
