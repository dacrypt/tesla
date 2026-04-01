"""L3 ABRP provider — A Better Route Planner telemetry sink.

Outbound-only: receives vehicle state and pushes it to ABRP's live
telemetry API so ABRP can show accurate range predictions in real time.
"""

from __future__ import annotations

import time

from tesla_cli.core.config import Config
from tesla_cli.core.providers.base import (
    Capability,
    Provider,
    ProviderPriority,
    ProviderResult,
)

_ABRP_API = "https://api.iternio.com/1/tlm/send"


class AbrpProvider(Provider):
    """L3 — ABRP live telemetry sink.

    Translates vehicle state dict → ABRP telemetry format and POSTs it.
    """

    name        = "abrp"
    description = "ABRP live telemetry (route planning predictions)"
    layer       = 3
    priority    = ProviderPriority.LOW
    capabilities = frozenset({Capability.TELEMETRY_PUSH})

    def __init__(self, config: Config) -> None:
        self._cfg = config

    def is_available(self) -> bool:
        return bool(self._cfg.abrp.user_token)

    def health_check(self) -> dict:
        if not self.is_available():
            return {"status": "down", "latency_ms": 0, "detail": "user_token not configured"}
        return {"status": "ok", "latency_ms": 0, "detail": f"endpoint={_ABRP_API}"}

    def execute(self, operation: str, **kwargs) -> ProviderResult:
        if operation not in ("push", "send"):
            return ProviderResult(ok=False, provider=self.name, error=f"Unknown operation: {operation}")

        data = kwargs.get("data") or {}
        cs   = data.get("charge_state") or {}
        ds   = data.get("drive_state") or {}
        clim = data.get("climate_state") or {}

        tlm: dict = {
            "utc":           int(time.time()),
            "soc":           cs.get("battery_level"),
            "speed":         round((ds.get("speed") or 0) * 1.60934, 1),
            "power":         ds.get("power") or 0,
            "is_charging":   int(cs.get("charging_state") in ("Charging", "Complete")),
            "charger_power": cs.get("charger_power") or 0,
        }
        if ds.get("latitude") is not None:
            tlm["lat"] = ds["latitude"]
        if ds.get("longitude") is not None:
            tlm["lon"] = ds["longitude"]
        if clim.get("inside_temp") is not None:
            tlm["temp"] = clim["inside_temp"]
        # Remove None values
        tlm = {k: v for k, v in tlm.items() if v is not None}

        try:
            import json as _json
            import urllib.request as _req

            params  = f"token={self._cfg.abrp.user_token}"
            if self._cfg.abrp.api_key:
                params += f"&api_key={self._cfg.abrp.api_key}"
            url     = f"{_ABRP_API}?{params}"
            payload = _json.dumps({"tlm": tlm}).encode()
            req     = _req.Request(url, data=payload, headers={"Content-Type": "application/json"})

            t0 = time.monotonic()
            with _req.urlopen(req, timeout=10) as resp:  # noqa: S310
                resp_data = _json.loads(resp.read().decode())
            ms = (time.monotonic() - t0) * 1000

            return ProviderResult(ok=True, data={"tlm": tlm, "response": resp_data}, provider=self.name, latency_ms=ms)
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(ok=False, provider=self.name, error=str(exc))
