"""L2 TeslaMate provider — local PostgreSQL database.

Provides historical trip data, charging sessions, lifetime statistics,
and efficiency analytics. Does NOT provide real-time vehicle state
(use VehicleApiProvider for that) but is the authoritative source for
anything time-series or aggregated.
"""

from __future__ import annotations

from tesla_cli.core.config import Config
from tesla_cli.core.providers.base import (
    Capability,
    Provider,
    ProviderPriority,
    ProviderResult,
)


class TeslaMateProvider(Provider):
    """L2 — TeslaMate local database.

    Historical data, trip/charging analytics, efficiency, vampire drain.
    Requires a PostgreSQL TeslaMate database URL in config.
    """

    name = "teslaMate"
    description = "TeslaMate local DB (historical trips, charges, stats)"
    layer = 2
    priority = ProviderPriority.MEDIUM
    capabilities = frozenset(
        {
            Capability.HISTORY_TRIPS,
            Capability.HISTORY_CHARGES,
            Capability.HISTORY_STATS,
        }
    )

    def __init__(self, config: Config) -> None:
        self._cfg = config

    def _backend(self) -> object:
        from tesla_cli.core.backends.teslaMate import TeslaMateBacked

        return TeslaMateBacked(
            self._cfg.teslaMate.database_url,
            car_id=self._cfg.teslaMate.car_id,
        )

    def is_available(self) -> bool:
        if not self._cfg.teslaMate.database_url:
            return False
        # If managed stack, check it's running
        if self._cfg.teslaMate.managed:
            try:
                from pathlib import Path

                from tesla_cli.infra.teslamate_stack import TeslaMateStack

                stack = TeslaMateStack(
                    Path(self._cfg.teslaMate.stack_dir) if self._cfg.teslaMate.stack_dir else None
                )
                return stack.is_running()
            except Exception:  # noqa: BLE001
                return False
        return True

    def health_check(self) -> dict:
        if not self._cfg.teslaMate.database_url:
            return {"status": "down", "latency_ms": 0, "detail": "database_url not configured"}
        # Managed stack health
        stack_health = {}
        if self._cfg.teslaMate.managed:
            try:
                from pathlib import Path

                from tesla_cli.infra.teslamate_stack import TeslaMateStack

                stack = TeslaMateStack(
                    Path(self._cfg.teslaMate.stack_dir) if self._cfg.teslaMate.stack_dir else None
                )
                stack_health = stack.health_check()
            except Exception:  # noqa: BLE001
                pass
        try:
            backend = self._backend()
            ok, ms = self._timed(backend.ping)
            detail = f"car_id={self._cfg.teslaMate.car_id}"
            if self._cfg.teslaMate.managed:
                detail += " (managed)"
            result = {
                "status": "ok" if ok else "down",
                "latency_ms": round(ms, 1),
                "detail": detail,
            }
            if stack_health:
                result["stack"] = stack_health
            return result
        except Exception as exc:  # noqa: BLE001
            return {"status": "down", "latency_ms": 0, "detail": str(exc)}

    def fetch(self, operation: str, **kwargs) -> ProviderResult:
        try:
            backend = self._backend()
            if operation == "trips":
                limit = kwargs.get("limit", 20)
                data, ms = self._timed(backend.get_trips, limit=limit)
            elif operation == "charges":
                limit = kwargs.get("limit", 20)
                data, ms = self._timed(backend.get_charging_sessions, limit=limit)
            elif operation == "stats":
                data, ms = self._timed(backend.get_stats)
                charging, _ = self._timed(backend.get_charging_stats)
                data = {"drives": data, "charging": charging}
            elif operation == "efficiency":
                limit = kwargs.get("limit", 20)
                data, ms = self._timed(backend.get_efficiency, limit=limit)
            elif operation == "vampire":
                days = kwargs.get("days", 30)
                data, ms = self._timed(backend.get_vampire_drain, days=days)
            elif operation == "drive_days":
                days = kwargs.get("days", 365)
                data, ms = self._timed(backend.get_drive_days, days=days)
            elif operation == "daily_energy":
                days = kwargs.get("days", 30)
                data, ms = self._timed(backend.get_daily_energy, days=days)
            else:
                return ProviderResult(
                    ok=False, provider=self.name, error=f"Unknown operation: {operation}"
                )
            return ProviderResult(ok=True, data=data, provider=self.name, latency_ms=ms)
        except Exception as exc:  # noqa: BLE001
            return ProviderResult(ok=False, provider=self.name, error=str(exc))
