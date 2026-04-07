"""Automations API routes: /api/automations/*"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from tesla_cli.core.automation import AutomationEngine
from tesla_cli.core.models.automation import AutomationAction, AutomationRule, AutomationTrigger

router = APIRouter()


def _engine() -> AutomationEngine:
    return AutomationEngine()


@router.get("/status")
def automations_status() -> dict:
    """Daemon running? Rules count?"""
    engine = _engine()
    enabled = sum(1 for r in engine.rules if r.enabled)
    return {
        "total": len(engine.rules),
        "enabled": enabled,
        "disabled": len(engine.rules) - enabled,
    }


@router.get("/")
def list_rules() -> list[dict]:
    """List all automation rules."""
    engine = _engine()
    return [r.model_dump(mode="json") for r in engine.rules]


@router.post("/")
def create_rule(rule: dict) -> dict:
    """Create a new automation rule."""
    engine = _engine()
    try:
        new_rule = AutomationRule(**rule)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    # Validate trigger and action are present
    if not isinstance(new_rule.trigger, AutomationTrigger):
        raise HTTPException(status_code=422, detail="trigger is required")
    if not isinstance(new_rule.action, AutomationAction):
        raise HTTPException(status_code=422, detail="action is required")
    # Reject duplicate names
    if any(r.name == new_rule.name for r in engine.rules):
        raise HTTPException(status_code=409, detail=f"Rule '{new_rule.name}' already exists")
    engine.add_rule(new_rule)
    return {"ok": True, "name": new_rule.name}


@router.get("/{name}")
def get_rule(name: str) -> dict:
    """Get a single automation rule by name."""
    engine = _engine()
    for r in engine.rules:
        if r.name == name:
            return r.model_dump(mode="json")
    raise HTTPException(status_code=404, detail=f"Rule '{name}' not found")


@router.delete("/{name}")
def delete_rule(name: str) -> dict:
    """Delete an automation rule by name."""
    engine = _engine()
    removed = engine.remove_rule(name)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Rule '{name}' not found")
    return {"ok": True}


@router.post("/{name}/enable")
def enable_rule(name: str) -> dict:
    """Enable an automation rule."""
    engine = _engine()
    ok = engine.set_enabled(name, enabled=True)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Rule '{name}' not found")
    return {"ok": True, "name": name, "enabled": True}


@router.post("/{name}/disable")
def disable_rule(name: str) -> dict:
    """Disable an automation rule."""
    engine = _engine()
    ok = engine.set_enabled(name, enabled=False)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Rule '{name}' not found")
    return {"ok": True, "name": name, "enabled": False}


@router.post("/{name}/test")
def test_rule(name: str) -> dict:
    """Dry-run a single rule against a synthetic vehicle state payload."""
    engine = _engine()
    rule = next((r for r in engine.rules if r.name == name), None)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"Rule '{name}' not found")

    # Build a synthetic vehicle state that represents a "worst case" scenario
    # so the rule trigger evaluation can run without a live vehicle connection.
    synthetic_state: dict = {
        "charge_state": {
            "battery_level": rule.trigger.threshold or 50,
            "charging_state": "Charging",
            "battery_range": 150,
        },
        "drive_state": {
            "latitude": rule.trigger.latitude or 0,
            "longitude": rule.trigger.longitude or 0,
            "speed": 0,
        },
        "vehicle_state": {
            "sentry_mode_active": False,
        },
    }

    fired = engine.evaluate(synthetic_state, dry_run=True)
    did_fire = any(r.name == name for r, _ in fired)
    msg = next((m for r, m in fired if r.name == name), "")

    return {
        "name": name,
        "fired": did_fire,
        "message": msg,
        "dry_run": True,
    }
