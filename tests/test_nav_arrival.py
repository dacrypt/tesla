"""Tests for core/nav/arrival.py — Step 3 (v4.9.2)."""

from __future__ import annotations

import _thread
import threading
import time

import pytest

from tesla_cli.core.nav.arrival import (
    ArrivalDetector,
    ArrivalSource,
    LocationEvent,
    NullArrivalSource,
)
from tesla_cli.core.nav.route import Waypoint


def _wp(lat: float = 0.0, lon: float = 0.0) -> Waypoint:
    return Waypoint(
        raw_address=f"{lat},{lon}",
        lat=lat,
        lon=lon,
        geocode_provider="user",
        geocode_at="2026-04-21T00:00:00Z",
    )


def test_null_source_fires_after_simulate_delay() -> None:
    wp = _wp(0.0, 0.0)
    source = NullArrivalSource(simulate_after_seconds=0.1)
    detector = ArrivalDetector(
        waypoint=wp, tolerance_meters=150.0, source=source, max_wait_seconds=5.0
    )
    t0 = time.monotonic()
    arrived = detector.wait()
    elapsed = time.monotonic() - t0
    assert arrived is True
    assert elapsed < 1.5  # well under the 5s deadline


def test_null_source_no_simulate_times_out() -> None:
    wp = _wp(0.0, 0.0)
    source = NullArrivalSource(simulate_after_seconds=None)
    detector = ArrivalDetector(
        waypoint=wp, tolerance_meters=150.0, source=source, max_wait_seconds=1.0
    )
    arrived = detector.wait()
    assert arrived is False


def test_sigint_during_wait_propagates_cleanly() -> None:
    """KeyboardInterrupt raised mid-wait must propagate, not be swallowed."""
    wp = _wp(0.0, 0.0)
    source = NullArrivalSource(simulate_after_seconds=None)
    detector = ArrivalDetector(
        waypoint=wp, tolerance_meters=150.0, source=source, max_wait_seconds=30.0
    )

    def _interrupt_soon() -> None:
        time.sleep(0.2)
        _thread.interrupt_main()

    killer = threading.Thread(target=_interrupt_soon, daemon=True)
    killer.start()
    with pytest.raises(KeyboardInterrupt):
        detector.wait()
    killer.join(timeout=1.0)


class _ApproachingSource:
    """Yields events that gradually close in on the waypoint."""

    def __init__(self, waypoint: Waypoint) -> None:
        self.waypoint = waypoint

    def events(self):
        # start ~11 km away, then ~2 km, then effectively on top.
        offsets = [0.1, 0.02, 0.0]
        for off in offsets:
            yield LocationEvent(
                lat=self.waypoint.lat + off,
                lon=self.waypoint.lon,
                at="2026-04-21T00:00:00Z",
            )


def test_arrival_detector_exits_on_distance_threshold() -> None:
    wp = _wp(4.6487, -74.0672)
    source = _ApproachingSource(wp)
    # Protocol compliance sanity check.
    assert isinstance(source, ArrivalSource)
    detector = ArrivalDetector(
        waypoint=wp, tolerance_meters=150.0, source=source, max_wait_seconds=10.0
    )
    arrived = detector.wait()
    assert arrived is True
