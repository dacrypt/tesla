"""ArrivalSource protocol + NullArrivalSource + ArrivalDetector.

v4.9.2 Step 0 audit: fleet-telemetry receiver has no downstream publisher
in-tree (only port 4443 Tesla ingress). Real TelemetryArrivalSource is
deferred to v4.9.2.1. v4.9.2 ships NullArrivalSource only.

Thread model (explicit, per plan Section 4):
- `ArrivalDetector.wait()` is **synchronous** and runs in the main thread.
- No asyncio, no signal handlers, no worker threads.
- The inner loop sleeps in 1-second bounded slices so `KeyboardInterrupt`
  propagates naturally between iterations.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from tesla_cli.core.geo import haversine_km
from tesla_cli.core.nav.route import Waypoint


@dataclass
class LocationEvent:
    lat: float
    lon: float
    at: str  # ISO-8601 timestamp


@runtime_checkable
class ArrivalSource(Protocol):
    def events(self) -> Iterator[LocationEvent]: ...


class NullArrivalSource:
    """Synthetic arrival source for tests and `--simulate-arrival-after`.

    If `simulate_after_seconds` is a number, fires exactly one event after
    that many seconds (via `time.sleep`) and then returns.
    If `simulate_after_seconds is None`, yields nothing (infinite no-op) and
    the detector will time out.

    When `target` is supplied, the synthetic event fires at the target's
    coords so `ArrivalDetector.wait()` returns True. Without a target,
    the event fires at (0, 0) (useful only for timeout-path tests).
    """

    def __init__(
        self,
        simulate_after_seconds: float | None,
        target: Waypoint | None = None,
    ) -> None:
        self.simulate_after_seconds = simulate_after_seconds
        self.target = target

    def events(self) -> Iterator[LocationEvent]:
        if self.simulate_after_seconds is None:
            return
        time.sleep(self.simulate_after_seconds)
        if self.target is not None:
            yield LocationEvent(lat=self.target.lat, lon=self.target.lon, at="1970-01-01T00:00:00Z")
        else:
            yield LocationEvent(lat=0.0, lon=0.0, at="1970-01-01T00:00:00Z")


class ArrivalDetector:
    """Consumes events from an ArrivalSource and returns True on arrival.

    `wait()` is synchronous. It reads at most one event per loop turn and
    sleeps up to 1 second between reads so SIGINT is delivered promptly.
    """

    def __init__(
        self,
        waypoint: Waypoint,
        tolerance_meters: float,
        source: ArrivalSource,
        max_wait_seconds: float,
    ) -> None:
        self.waypoint = waypoint
        self.tolerance_meters = tolerance_meters
        self.source = source
        self.max_wait_seconds = max_wait_seconds

    def wait(self) -> bool:
        deadline = time.monotonic() + self.max_wait_seconds
        # NullArrivalSource sleeps inside the generator, so we pull events
        # eagerly but guard with a 1s bound between iterations to keep
        # KeyboardInterrupt responsive.
        events = iter(self.source.events())
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            try:
                event = next(events)
            except StopIteration:
                # Source exhausted with no arrival — keep polling (sleep
                # short slices) until the deadline, so the detector remains
                # cancelable via KeyboardInterrupt.
                time.sleep(min(remaining, 1.0))
                continue
            km = haversine_km(self.waypoint.lat, self.waypoint.lon, event.lat, event.lon)
            if km * 1000.0 < self.tolerance_meters:
                return True
            time.sleep(min(remaining, 1.0))
