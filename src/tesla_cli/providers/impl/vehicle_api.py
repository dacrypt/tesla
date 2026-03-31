"""L1 Vehicle API provider — Owner API / Tessie / Fleet API.

This provider wraps the existing backend system and exposes it through
the standard Provider interface. It is the primary source for real-time
vehicle state and commands when internet is available.
"""

from __future__ import annotations

from tesla_cli.config import Config
from tesla_cli.providers.base import (
    Capability,
    Provider,
    ProviderPriority,
    ProviderResult,
)


class VehicleApiProvider(Provider):
    """L1 — Direct Tesla vehicle API (Owner / Tessie / Fleet).

    Wraps the existing backend system. Provides real-time vehicle state,
    GPS location, and full command support.
    """

    name        = "vehicle-api"
    description = "Direct Tesla API (Owner / Tessie / Fleet)"
    layer       = 1
    priority    = ProviderPriority.HIGH
    capabilities = frozenset({
        Capability.VEHICLE_STATE,
        Capability.VEHICLE_COMMAND,
        Capability.VEHICLE_LOCATION,
    })

    def __init__(self, config: Config) -> None:
        self._cfg = config

    def _backend(self):
        from tesla_cli.backends import get_vehicle_backend
        return get_vehicle_backend(self._cfg)

    def _vin(self, vin: str | None) -> str:
        from tesla_cli.config import resolve_vin
        return resolve_vin(self._cfg, vin)

    # ── Availability ─────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        backend_name = self._cfg.general.backend
        try:
            from tesla_cli.auth.tokens import (
                FLEET_ACCESS_TOKEN,
                ORDER_ACCESS_TOKEN,
                TESSIE_TOKEN,
                get_token,
            )
            if backend_name == "owner":
                return bool(get_token(ORDER_ACCESS_TOKEN))
            elif backend_name == "tessie":
                return bool(get_token(TESSIE_TOKEN))
            elif backend_name == "fleet":
                return bool(get_token(FLEET_ACCESS_TOKEN))
        except Exception:  # noqa: BLE001
            pass
        return False

    def health_check(self) -> dict:
        try:
            backend = self._backend()
            vin = self._vin(None)
            data, ms = self._timed(backend.get_vehicle_state, vin)
            return {
                "status":     "ok",
                "latency_ms": round(ms, 1),
                "detail":     f"backend={self._cfg.general.backend} vin={vin[-6:]}",
            }
        except Exception as exc:  # noqa: BLE001
            return {"status": "down", "latency_ms": 0, "detail": str(exc)}

    # ── Data fetching ─────────────────────────────────────────────────────────

    def fetch(self, operation: str, **kwargs) -> ProviderResult:
        vin = self._vin(kwargs.pop("vin", None))
        try:
            backend = self._backend()
            if operation == "vehicle_data":
                data, ms = self._timed(backend.get_vehicle_data, vin)
            elif operation == "charge_state":
                data, ms = self._timed(backend.get_charge_state, vin)
            elif operation == "climate_state":
                data, ms = self._timed(backend.get_climate_state, vin)
            elif operation == "drive_state":
                data, ms = self._timed(backend.get_drive_state, vin)
            elif operation == "vehicle_state":
                data, ms = self._timed(backend.get_vehicle_state, vin)
            elif operation == "list_vehicles":
                data, ms = self._timed(backend.list_vehicles)
            else:
                return ProviderResult(ok=False, provider=self.name, error=f"Unknown operation: {operation}")
            return ProviderResult(ok=True, data=data, provider=self.name, latency_ms=ms)
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(ok=False, provider=self.name, error=str(exc))

    # ── Commands ──────────────────────────────────────────────────────────────

    def execute(self, operation: str, **kwargs) -> ProviderResult:
        vin = self._vin(kwargs.pop("vin", None))
        try:
            backend = self._backend()
            if operation == "wake":
                data, ms = self._timed(backend.wake_up, vin)
            else:
                # Generic command passthrough
                cmd     = kwargs.pop("command", operation)
                data, ms = self._timed(backend.command, vin, cmd, **kwargs)
            return ProviderResult(ok=True, data=data, provider=self.name, latency_ms=ms)
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(ok=False, provider=self.name, error=str(exc))
