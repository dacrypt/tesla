"""Base types for the Provider architecture.

Every provider in the ecosystem implements the Provider ABC.
The Capability enum defines what each provider can do.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from enum import IntEnum
from typing import Any

# ── Capability taxonomy ───────────────────────────────────────────────────────


class Capability:
    """String-typed capability constants.

    Grouped by direction:
        vehicle.*      — read or control a physical vehicle
        history.*      — read archived / aggregated data
        telemetry.*    — push live telemetry to an external service
        home.*         — sync with home automation platforms
        notify.*       — send push notifications
        visual.*       — open dashboards / visualizations
    """

    # ── Vehicle (real-time) ────────────────────────────────────────────────
    VEHICLE_STATE = "vehicle.state"  # full multi-state snapshot
    VEHICLE_COMMAND = "vehicle.command"  # send control commands
    VEHICLE_LOCATION = "vehicle.location"  # GPS coordinates
    VEHICLE_STREAM = "vehicle.stream"  # continuous real-time telemetry

    # ── Historical / aggregated ────────────────────────────────────────────
    HISTORY_TRIPS = "history.trips"  # past drive sessions
    HISTORY_CHARGES = "history.charges"  # past charging sessions
    HISTORY_STATS = "history.stats"  # lifetime/period statistics

    # ── Outbound integrations ──────────────────────────────────────────────
    TELEMETRY_PUSH = "telemetry.push"  # push live telemetry (ABRP, MQTT)
    HOME_SYNC = "home.sync"  # push state to home automation
    NOTIFY = "notify.push"  # push notifications (Apprise)

    # ── Visualization ──────────────────────────────────────────────────────
    VISUALIZATION = "visual.open"  # open a dashboard (Grafana)

    @classmethod
    def all(cls) -> list[str]:
        return [v for k, v in vars(cls).items() if not k.startswith("_") and isinstance(v, str)]


# ── Priority ──────────────────────────────────────────────────────────────────


class ProviderPriority(IntEnum):
    """Higher number = higher priority = picked first by registry."""

    CRITICAL = 100  # L0 BLE — offline, no latency, no internet
    HIGH = 80  # L1 Direct API — Owner / Tessie / Fleet
    MEDIUM = 60  # L2 Local DB  — TeslaMate
    LOW = 40  # L3 External  — ABRP, HA, Grafana
    MINIMAL = 20  # Fallback / auxiliary


# ── Result envelope ───────────────────────────────────────────────────────────


class ProviderResult:
    """Standardized result from any provider call."""

    def __init__(
        self,
        *,
        ok: bool,
        data: Any = None,
        provider: str = "",
        latency_ms: float = 0.0,
        error: str | None = None,
    ) -> None:
        self.ok = ok
        self.data = data
        self.provider = provider
        self.latency_ms = latency_ms
        self.error = error

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "provider": self.provider,
            "latency_ms": round(self.latency_ms, 1),
            "error": self.error,
            "data": self.data if self.ok else None,
        }

    def __repr__(self) -> str:  # pragma: no cover
        status = "ok" if self.ok else f"err({self.error})"
        return f"ProviderResult({self.provider} {status} {self.latency_ms:.0f}ms)"


# ── Provider ABC ──────────────────────────────────────────────────────────────


class Provider(ABC):
    """Abstract base for every ecosystem provider.

    Subclasses implement:
        - capabilities: frozenset of Capability strings this provider can serve
        - is_available(): fast check (no I/O if possible)
        - health_check(): full connectivity probe, returns {status, latency_ms, detail}
        - fetch(operation, **kwargs): read data
        - execute(operation, **kwargs): write / send commands
    """

    #: Human-readable name shown in `tesla providers status`
    name: str = "unnamed"

    #: Short description
    description: str = ""

    #: Layer (0=BLE, 1=API, 2=LocalDB, 3=External)
    layer: int = 1

    #: Priority (ProviderPriority)
    priority: int = ProviderPriority.MEDIUM

    #: Set of Capability strings
    capabilities: frozenset[str] = frozenset()

    # ── Availability ──────────────────────────────────────────────────────

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if this provider is configured and likely reachable.

        This must be fast (check config, binary presence) — no network I/O.
        """

    @abstractmethod
    def health_check(self) -> dict:
        """Perform a real connectivity probe. Returns dict with at minimum:
        {"status": "ok"|"degraded"|"down", "latency_ms": float, "detail": str}
        """

    # ── Operations ────────────────────────────────────────────────────────

    def fetch(self, operation: str, **kwargs) -> ProviderResult:
        """Read data. Override per-provider. Returns ProviderResult."""
        return ProviderResult(
            ok=False, provider=self.name, error=f"fetch({operation}) not implemented"
        )

    def execute(self, operation: str, **kwargs) -> ProviderResult:
        """Send a command or push data. Override per-provider. Returns ProviderResult."""
        return ProviderResult(
            ok=False, provider=self.name, error=f"execute({operation}) not implemented"
        )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _timed(self, fn, *args, **kwargs) -> tuple[Any, float]:
        """Run fn and return (result, elapsed_ms)."""
        t0 = time.monotonic()
        result = fn(*args, **kwargs)
        return result, (time.monotonic() - t0) * 1000

    def status_row(self) -> dict:
        """One-line status dict for `tesla providers status`."""
        available = self.is_available()
        return {
            "name": self.name,
            "layer": f"L{self.layer}",
            "priority": self.priority,
            "available": available,
            "capabilities": list(self.capabilities),
            "description": self.description,
        }

    def __repr__(self) -> str:  # pragma: no cover
        return f"{type(self).__name__}(name={self.name!r}, layer=L{self.layer})"
