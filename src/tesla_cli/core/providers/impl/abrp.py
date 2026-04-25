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

    name = "abrp"
    description = "ABRP live telemetry (route planning predictions)"
    layer = 3
    priority = ProviderPriority.LOW
    capabilities = frozenset({Capability.TELEMETRY_PUSH})

    def __init__(self, config: Config) -> None:
        self._cfg = config

    def is_available(self) -> bool:
        # Telemetry push needs the user token; the local cost-fallback only
        # needs a configured cost_per_kwh. Either capability counts as available.
        if self._cfg.abrp.user_token:
            return True
        return bool(getattr(self._cfg.general, "cost_per_kwh", 0.0) or 0.0) > 0.0

    def health_check(self) -> dict:
        if not self.is_available():
            return {"status": "down", "latency_ms": 0, "detail": "user_token not configured"}
        return {"status": "ok", "latency_ms": 0, "detail": f"endpoint={_ABRP_API}"}

    def execute(self, operation: str, **kwargs) -> ProviderResult:
        if operation == "estimate_charge_cost":
            return self._estimate_charge_cost(**kwargs)

        if operation not in ("push", "send"):
            return ProviderResult(
                ok=False, provider=self.name, error=f"Unknown operation: {operation}"
            )

        data = kwargs.get("data") or {}
        cs = data.get("charge_state") or {}
        ds = data.get("drive_state") or {}
        clim = data.get("climate_state") or {}

        tlm: dict = {
            "utc": int(time.time()),
            "soc": cs.get("battery_level"),
            "speed": round((ds.get("speed") or 0) * 1.60934, 1),
            "power": ds.get("power") or 0,
            "is_charging": int(cs.get("charging_state") in ("Charging", "Complete")),
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

            params = f"token={self._cfg.abrp.user_token}"
            if self._cfg.abrp.api_key:
                params += f"&api_key={self._cfg.abrp.api_key}"
            url = f"{_ABRP_API}?{params}"
            payload = _json.dumps({"tlm": tlm}).encode()
            req = _req.Request(url, data=payload, headers={"Content-Type": "application/json"})

            t0 = time.monotonic()
            with _req.urlopen(req, timeout=10) as resp:  # noqa: S310
                resp_data = _json.loads(resp.read().decode())
            ms = (time.monotonic() - t0) * 1000

            return ProviderResult(
                ok=True, data={"tlm": tlm, "response": resp_data}, provider=self.name, latency_ms=ms
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(ok=False, provider=self.name, error=str(exc))

    # ── Cost estimation (Phase 3 fallback) ───────────────────────────────────

    def _estimate_charge_cost(
        self,
        kwh_added: float = 0.0,
        location_name: str | None = None,
        location_lat: float | None = None,
        location_lon: float | None = None,
        currency: str = "USD",
        **_: object,
    ) -> ProviderResult:
        """Phase 3 MVP — local fallback cost estimator.

        ABRP's public API does not expose a cost endpoint, so we fall back to
        either a TeslaMate geofence's `cost_per_kwh` (when the caller supplies a
        DSN via `database_url`) or `cfg.general.cost_per_kwh`. Returning a
        stable shape lets a future real-ABRP implementation slot in without
        breaking callers.
        """
        rate: float | None = None
        source = "abrp_fallback"

        # Optional geofence lookup — only when the caller wires it in.
        try:
            db_url = getattr(self._cfg.teslaMate, "database_url", "") or ""
        except Exception:  # noqa: BLE001
            db_url = ""
        if db_url and (location_lat is not None and location_lon is not None):
            try:
                import psycopg2
                import psycopg2.extras

                with psycopg2.connect(db_url) as conn:
                    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                    cur.execute(
                        "SELECT cost_per_unit FROM geofences "
                        "WHERE latitude IS NOT NULL AND longitude IS NOT NULL "
                        "ORDER BY (latitude - %s) * (latitude - %s) "
                        "       + (longitude - %s) * (longitude - %s) ASC LIMIT 1",
                        (location_lat, location_lat, location_lon, location_lon),
                    )
                    row = cur.fetchone()
                    cur.close()
                if row and row.get("cost_per_unit") is not None:
                    rate = float(row["cost_per_unit"])
                    source = "geofence"
            except Exception:  # noqa: BLE001
                rate = None

        if rate is None:
            cfg_rate = float(getattr(self._cfg.general, "cost_per_kwh", 0.0) or 0.0)
            if cfg_rate > 0:
                rate = cfg_rate

        if rate is None or rate <= 0 or kwh_added <= 0:
            return ProviderResult(
                ok=False,
                provider=self.name,
                error="cost_per_kwh not configured",
                data={"estimated_cost": None, "currency": currency, "source": source},
            )

        estimated = round(rate * float(kwh_added), 2)
        return ProviderResult(
            ok=True,
            provider=self.name,
            data={"estimated_cost": estimated, "currency": currency, "source": source},
        )
