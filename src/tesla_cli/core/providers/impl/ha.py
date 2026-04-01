"""L3 Home Assistant provider — bidirectional state sync.

Pushes vehicle sensor entities to HA via REST API. In the future will
also pull HA entities (e.g., presence detection, solar power available)
to inform vehicle charging decisions.
"""

from __future__ import annotations

import time

from tesla_cli.config import Config
from tesla_cli.providers.base import (
    Capability,
    Provider,
    ProviderPriority,
    ProviderResult,
)

# 18 vehicle sensors pushed as sensor.tesla_* entities
_SENSORS: list[tuple[str, str, str, str | None]] = [
    ("charge_state",  "battery_level",      "battery_level",    "%"),
    ("charge_state",  "battery_range",       "battery_range",    "mi"),
    ("charge_state",  "charging_state",      "charging_state",   None),
    ("charge_state",  "charge_limit_soc",    "charge_limit",     "%"),
    ("charge_state",  "charge_energy_added", "energy_added",     "kWh"),
    ("charge_state",  "charger_power",       "charger_power",    "kW"),
    ("drive_state",   "speed",               "speed",            "mph"),
    ("drive_state",   "shift_state",         "shift_state",      None),
    ("drive_state",   "latitude",            "latitude",         "°"),
    ("drive_state",   "longitude",           "longitude",        "°"),
    ("drive_state",   "heading",             "heading",          "°"),
    ("climate_state", "inside_temp",         "inside_temp",      "°C"),
    ("climate_state", "outside_temp",        "outside_temp",     "°C"),
    ("climate_state", "is_climate_on",       "climate_on",       None),
    ("vehicle_state", "locked",              "locked",           None),
    ("vehicle_state", "odometer",            "odometer",         "mi"),
    ("vehicle_state", "software_version",    "sw_version",       None),
    ("vehicle_state", "is_user_present",     "user_present",     None),
]


class HomeAssistantProvider(Provider):
    """L3 — Home Assistant state sync via REST API.

    Pushes 18 vehicle sensor entities to HA. Each entity becomes
    a sensor.tesla_* entity in Home Assistant, usable in automations,
    dashboards, and energy management.
    """

    name        = "home-assistant"
    description = "Home Assistant REST API (sensor entities)"
    layer       = 3
    priority    = ProviderPriority.LOW
    capabilities = frozenset({Capability.HOME_SYNC})

    def __init__(self, config: Config) -> None:
        self._cfg = config

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._cfg.home_assistant.token}",
            "Content-Type": "application/json",
        }

    def is_available(self) -> bool:
        return bool(self._cfg.home_assistant.url and self._cfg.home_assistant.token)

    def health_check(self) -> dict:
        if not self.is_available():
            return {"status": "down", "latency_ms": 0, "detail": "HA url/token not configured"}
        try:
            import json as _json
            import urllib.request as _req
            url = f"{self._cfg.home_assistant.url.rstrip('/')}/api/"
            req = _req.Request(url, headers=self._headers())
            t0  = time.monotonic()
            with _req.urlopen(req, timeout=5) as resp:  # noqa: S310
                body = _json.loads(resp.read().decode())
            ms  = (time.monotonic() - t0) * 1000
            return {"status": "ok", "latency_ms": round(ms, 1), "detail": f"HA {body.get('version','?')}"}
        except Exception as exc:  # noqa: BLE001
            return {"status": "down", "latency_ms": 0, "detail": str(exc)}

    def execute(self, operation: str, **kwargs) -> ProviderResult:
        if operation not in ("push", "sync"):
            return ProviderResult(ok=False, provider=self.name, error=f"Unknown operation: {operation}")

        data = kwargs.get("data") or {}
        vin  = kwargs.get("vin", "")
        vin_tail = str(vin)[-6:] if vin else "????"

        import json as _json
        import urllib.request as _req

        base    = self._cfg.home_assistant.url.rstrip("/")
        headers = self._headers()
        ok_count = err_count = 0
        errors: list[str] = []

        t0 = time.monotonic()
        for section, key, slug, unit in _SENSORS:
            val = (data.get(section) or {}).get(key)
            if val is None:
                continue
            entity_id = f"sensor.tesla_{slug}"
            attrs: dict = {"friendly_name": f"Tesla {slug.replace('_',' ').title()}", "vin": vin_tail}
            if unit:
                attrs["unit_of_measurement"] = unit
            payload = _json.dumps({"state": str(val), "attributes": attrs}).encode()
            url     = f"{base}/api/states/{entity_id}"
            req     = _req.Request(url, data=payload, method="PUT", headers=headers)
            try:
                with _req.urlopen(req, timeout=8) as _:  # noqa: S310
                    ok_count += 1
            except Exception as exc:  # noqa: BLE001
                err_count += 1
                errors.append(f"{entity_id}: {exc}")

        ms = (time.monotonic() - t0) * 1000
        return ProviderResult(
            ok=err_count == 0,
            provider=self.name,
            latency_ms=round(ms, 1),
            data={"pushed": ok_count, "errors": err_count},
            error="; ".join(errors) if errors else None,
        )
