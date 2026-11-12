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


# ── MqttTelemetryArrivalSource (fleet-telemetry MQTT stream) ─────────────────


from types import SimpleNamespace  # noqa: E402

from tesla_cli.core.nav.arrival import (  # noqa: E402
    MqttTelemetryArrivalSource,
    location_topic,
    parse_location,
)

VIN = "5YJ3E1EA1PF000001"


@pytest.mark.parametrize(
    "payload",
    [
        b'{"latitude": 4.6, "longitude": -74.0}',
        b'{"lat": 4.6, "lon": -74.0}',
        b'{"locationValue": {"latitude": 4.6, "longitude": -74.0}}',
        b'{"latitude": "4.6", "longitude": "-74.0"}',
        b'"{\\"latitude\\": 4.6, \\"longitude\\": -74.0}"',
        b"4.6,-74.0",
        '{"latitude": 4.6, "longitude": -74.0}',
    ],
)
def test_parse_location_formats(payload) -> None:
    assert parse_location(payload) == (4.6, -74.0)


@pytest.mark.parametrize(
    "payload",
    [
        b"",
        b"null",
        b"42",
        b'{"latitude": 4.6}',
        b'{"latitude": 0, "longitude": 0}',
        b'{"latitude": 95, "longitude": 10}',
        b'{"latitude": "x", "longitude": 1}',
        b"\xff\xfe",
    ],
)
def test_parse_location_rejects_garbage(payload) -> None:
    assert parse_location(payload) is None


def test_location_topic_matches_stack_config() -> None:
    from tesla_cli.infra.fleet_telemetry_stack import CONFIG_TEMPLATE

    base = CONFIG_TEMPLATE["mqtt"]["topic_base"]
    assert location_topic(VIN) == f"{base}/{VIN}/v/Location"


class FakeClient:
    """Minimal paho stand-in: delivers queued payloads on loop()."""

    def __init__(self, payloads: list[bytes]) -> None:
        self.payloads = list(payloads)
        self.subscribed: list[str] = []
        self.connected_to = None
        self.disconnected = False
        self.auth = None
        self.on_connect = None
        self.on_message = None

    def username_pw_set(self, user, password):
        self.auth = (user, password)

    def tls_set(self):
        pass

    def connect(self, host, port, keepalive=60):
        self.connected_to = (host, port)

    def loop(self, timeout=1.0):
        if self.on_connect and not self.subscribed:
            self.on_connect(self, None, None, 0, None)
        if self.payloads:
            self.on_message(self, None, SimpleNamespace(payload=self.payloads.pop(0)))
        return 0

    def subscribe(self, topic, qos=0):
        self.subscribed.append(topic)

    def disconnect(self):
        self.disconnected = True


def test_mqtt_source_yields_fixes_and_heartbeats() -> None:
    client = FakeClient([b"garbage", b'{"latitude": 4.6, "longitude": -74.0}'])
    src = MqttTelemetryArrivalSource(
        VIN,
        host="mqtt.local",
        port=1884,
        username="u",
        password="p",
        client_factory=lambda: client,
    )
    gen = src.events()
    assert next(gen) is None  # garbage dropped → heartbeat
    ev = next(gen)
    assert (ev.lat, ev.lon) == (4.6, -74.0)
    gen.close()
    assert client.connected_to == ("mqtt.local", 1884)
    assert client.auth == ("u", "p")
    assert client.subscribed == [f"tesla/telemetry/{VIN}/v/Location"]
    assert client.disconnected


def test_detector_arrives_via_mqtt_and_disconnects() -> None:
    client = FakeClient(
        [
            b'{"latitude": 4.0, "longitude": -74.0}',  # far away
            b'{"latitude": 4.6001, "longitude": -74.0}',  # ~11 m from target
        ]
    )
    src = MqttTelemetryArrivalSource(VIN, client_factory=lambda: client)
    det = ArrivalDetector(_wp(4.6, -74.0), 150.0, src, max_wait_seconds=5.0)
    assert det.wait() is True
    assert client.disconnected


def test_detector_times_out_on_heartbeats_only() -> None:
    client = FakeClient([])
    src = MqttTelemetryArrivalSource(VIN, client_factory=lambda: client)
    det = ArrivalDetector(_wp(4.6, -74.0), 150.0, src, max_wait_seconds=0.05)
    t0 = time.monotonic()
    assert det.wait() is False
    assert time.monotonic() - t0 < 2.0
    assert client.disconnected
