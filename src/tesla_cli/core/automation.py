"""Automation engine: evaluates rules against vehicle state and fires actions.

Config file: ~/.tesla-cli/automations.json
"""

from __future__ import annotations

import json
import math
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from tesla_cli.core.models.automation import AutomationAction, AutomationConfig, AutomationRule

AUTOMATIONS_FILE = Path.home() / ".tesla-cli" / "automations.json"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two GPS points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.asin(math.sqrt(a))


class AutomationEngine:
    """Config-driven rule engine that watches vehicle state and fires actions."""

    def __init__(self, config_path: Path = AUTOMATIONS_FILE) -> None:
        self.config_path = config_path
        self._config: AutomationConfig = self._load_config()
        self._prev_state: dict = {}
        # Track whether vehicle was inside each location zone (rule name -> bool)
        self._location_inside: dict[str, bool] = {}

    # ── Persistence ────────────────────────────────────────────────────────────

    def _load_config(self) -> AutomationConfig:
        if not self.config_path.exists():
            return AutomationConfig()
        try:
            raw = json.loads(self.config_path.read_text())
            return AutomationConfig.model_validate(raw)
        except Exception:  # noqa: BLE001
            return AutomationConfig()

    def save_config(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.config_path.write_text(
            json.dumps(self._config.model_dump(mode="json"), indent=2)
        )

    @property
    def rules(self) -> list[AutomationRule]:
        return self._config.rules

    def add_rule(self, rule: AutomationRule) -> None:
        self._config.rules.append(rule)
        self.save_config()

    def remove_rule(self, name: str) -> bool:
        before = len(self._config.rules)
        self._config.rules = [r for r in self._config.rules if r.name != name]
        if len(self._config.rules) < before:
            self.save_config()
            return True
        return False

    def set_enabled(self, name: str, enabled: bool) -> bool:
        for rule in self._config.rules:
            if rule.name == name:
                rule.enabled = enabled
                self.save_config()
                return True
        return False

    # ── Evaluation ─────────────────────────────────────────────────────────────

    def evaluate(
        self, vehicle_data: dict, dry_run: bool = False
    ) -> list[tuple[AutomationRule, str]]:
        """Evaluate all enabled rules against current vehicle state.

        Returns list of (rule, formatted_message) that fired.
        Updates last_fired timestamps and executes actions unless dry_run.
        """
        fired: list[tuple[AutomationRule, str]] = []
        now = datetime.now(tz=UTC)

        for rule in self._config.rules:
            if not rule.enabled:
                continue

            # Cooldown check
            if rule.last_fired is not None:
                elapsed_minutes = (now - rule.last_fired).total_seconds() / 60
                if elapsed_minutes < rule.cooldown_minutes:
                    continue

            triggered = self._check_trigger(rule, vehicle_data, self._prev_state)
            if triggered:
                msg = self._format_action(rule.action, vehicle_data)
                fired.append((rule, msg))
                if not dry_run:
                    self._execute_action(rule.action, vehicle_data)
                    rule.last_fired = now

        if not dry_run:
            self.save_config()

        self._prev_state = dict(vehicle_data)
        return fired

    def _check_trigger(
        self, rule: AutomationRule, data: dict, prev_data: dict
    ) -> bool:
        t = rule.trigger
        trigger_type = t.type

        if trigger_type == "battery_below":
            level = _get_battery_level(data)
            return level is not None and t.threshold is not None and level < t.threshold

        if trigger_type == "battery_above":
            level = _get_battery_level(data)
            return level is not None and t.threshold is not None and level > t.threshold

        if trigger_type == "charging_complete":
            prev_state = _get_charging_state(prev_data)
            curr_state = _get_charging_state(data)
            return (
                prev_data != {}
                and prev_state == "Charging"
                and curr_state == "Complete"
            )

        if trigger_type == "charging_started":
            prev_state = _get_charging_state(prev_data)
            curr_state = _get_charging_state(data)
            return (
                prev_data != {}
                and prev_state != "Charging"
                and curr_state == "Charging"
            )

        if trigger_type == "sentry_event":
            prev_sentry = _get_nested(prev_data, "vehicle_state", "sentry_mode_active")
            curr_sentry = _get_nested(data, "vehicle_state", "sentry_mode_active")
            # Fire when sentry becomes active (event detected)
            return prev_data != {} and not prev_sentry and bool(curr_sentry)

        if trigger_type == "location_enter":
            return self._check_location(rule, data, entering=True)

        if trigger_type == "location_exit":
            return self._check_location(rule, data, entering=False)

        if trigger_type == "state_change":
            if not t.field:
                return False
            prev_val = str(_get_nested_flat(prev_data, t.field) or "")
            curr_val = str(_get_nested_flat(data, t.field) or "")
            if prev_data == {}:
                return False
            changed = prev_val != curr_val
            if not changed:
                return False
            if t.from_value is not None and prev_val != t.from_value:
                return False
            return t.to_value is None or curr_val == t.to_value

        if trigger_type == "time_of_day":
            if not t.time:
                return False
            now_str = datetime.now().strftime("%H:%M")
            return now_str == t.time

        return False

    def _check_location(self, rule: AutomationRule, data: dict, *, entering: bool) -> bool:
        t = rule.trigger
        if t.latitude is None or t.longitude is None:
            return False

        lat = _get_nested(data, "drive_state", "latitude")
        lon = _get_nested(data, "drive_state", "longitude")
        if lat is None or lon is None:
            return False

        dist = _haversine_km(float(lat), float(lon), t.latitude, t.longitude)
        inside = dist <= t.radius_km
        was_inside = self._location_inside.get(rule.name, False)
        self._location_inside[rule.name] = inside

        if entering:
            return inside and not was_inside
        else:
            return not inside and was_inside

    def _format_action(self, action: AutomationAction, data: dict) -> str:
        """Format the action message using vehicle data as template vars."""
        template = action.message or action.command or ""
        context = _build_template_context(data)
        try:
            return template.format(**context)
        except (KeyError, ValueError):
            return template

    def _execute_action(self, action: AutomationAction, data: dict) -> None:
        """Execute the action (notify or shell command)."""
        if action.type == "notify":
            self._send_notification(action, data)
        elif action.type in ("command", "exec"):
            cmd = self._format_action(action, data)
            if cmd:
                subprocess.run(cmd, shell=True, check=False)  # noqa: S602

    def _send_notification(self, action: AutomationAction, data: dict) -> None:
        try:
            import apprise  # type: ignore[import-untyped]
        except ImportError:
            return

        from tesla_cli.core.config import load_config

        cfg = load_config()
        if not cfg.notifications.apprise_urls:
            return

        body = self._format_action(action, data)
        apobj = apprise.Apprise()
        for url in cfg.notifications.apprise_urls:
            apobj.add(url)
        apobj.notify(title="Tesla Automation", body=body)


# ── Helpers ────────────────────────────────────────────────────────────────────


def _get_battery_level(data: dict) -> float | None:
    """Extract battery level from vehicle data (handles nested or flat)."""
    # Tessie / Fleet API style: charge_state.battery_level
    val = _get_nested(data, "charge_state", "battery_level")
    if val is not None:
        return float(val)
    # Flat style
    val = data.get("battery_level")
    if val is not None:
        return float(val)
    return None


def _get_charging_state(data: dict) -> str:
    val = _get_nested(data, "charge_state", "charging_state")
    if val is not None:
        return str(val)
    return str(data.get("charging_state", ""))


def _get_nested(data: dict, *keys: str):
    """Navigate nested dicts safely."""
    cur = data
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _get_nested_flat(data: dict, field: str):
    """Get a field that might be top-level or dot-separated."""
    if "." in field:
        parts = field.split(".", 1)
        sub = data.get(parts[0])
        if isinstance(sub, dict):
            return sub.get(parts[1])
        return None
    return data.get(field)


def _build_template_context(data: dict) -> dict:
    """Build a flat dict of common template variables from vehicle data."""
    ctx: dict = {}

    # Battery
    level = _get_battery_level(data)
    if level is not None:
        ctx["battery_level"] = int(level)

    # Range (prefer metric)
    range_val = _get_nested(data, "charge_state", "battery_range")
    if range_val is None:
        range_val = data.get("battery_range")
    if range_val is not None:
        ctx["range"] = round(float(range_val) * 1.60934, 1)  # miles -> km
        ctx["range_miles"] = round(float(range_val), 1)

    # Charging state
    cs = _get_charging_state(data)
    if cs:
        ctx["charging_state"] = cs

    # Location
    lat = _get_nested(data, "drive_state", "latitude") or data.get("latitude")
    lon = _get_nested(data, "drive_state", "longitude") or data.get("longitude")
    if lat is not None:
        ctx["latitude"] = lat
    if lon is not None:
        ctx["longitude"] = lon

    # Speed
    speed = _get_nested(data, "drive_state", "speed") or data.get("speed")
    if speed is not None:
        ctx["speed"] = speed

    # Timestamp
    ctx["ts"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Merge in any top-level flat keys
    for k, v in data.items():
        if k not in ctx and not isinstance(v, dict):
            ctx[k] = v

    return ctx
