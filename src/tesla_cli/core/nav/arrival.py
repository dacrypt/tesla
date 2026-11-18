"""ArrivalSource protocol, its implementations, and ArrivalDetector.

- ``MqttTelemetryArrivalSource`` — real arrivals. The self-hosted
  fleet-telemetry server (``tesla telemetry install``) publishes every
  vehicle field to MQTT as ``<topic_base>/<VIN>/v/<field>``; this source
  subscribes to the ``Location`` field.
- ``NullArrivalSource`` — synthetic arrivals for tests and
  ``--simulate-arrival-after``.

Thread model (explicit, per plan Section 4):
- `ArrivalDetector.wait()` is **synchronous** and runs in the main thread.
- No asyncio, no signal handlers, no worker threads.
- The inner loop sleeps in 1-second bounded slices so `KeyboardInterrupt`
  propagates naturally between iterations.
"""

from __future__ import annotations

import json
import logging
import queue
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol, runtime_checkable

from tesla_cli.core.geo import haversine_km
from tesla_cli.core.nav.route import Waypoint

log = logging.getLogger(__name__)

# fleet-telemetry MQTT dispatcher ``topic_base`` written by infra/fleet_telemetry_stack.py.
TELEMETRY_TOPIC_BASE = "tesla/telemetry"


@dataclass
class LocationEvent:
    lat: float
    lon: float
    at: str  # ISO-8601 timestamp


@runtime_checkable
class ArrivalSource(Protocol):
    """Yields location fixes. A live source may yield ``None`` as a heartbeat
    while no fix has arrived, so the detector can enforce its deadline."""

    def events(self) -> Iterator[LocationEvent | None]: ...


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


def location_topic(vin: str, topic_base: str = TELEMETRY_TOPIC_BASE) -> str:
    return f"{topic_base.rstrip('/')}/{vin}/v/Location"


def _num(value: Any) -> float | None:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return f if f == f else None  # reject NaN


def parse_location(payload: bytes | str) -> tuple[float, float] | None:
    """Extract (lat, lon) from a fleet-telemetry ``Location`` MQTT payload.

    The dispatcher JSON-encodes each field value. For ``Location`` that is
    ``{"latitude": .., "longitude": ..}``; firmware/server versions differ, so
    this also accepts ``lat``/``lon`` keys, a ``locationValue`` wrapper,
    numbers sent as strings, a doubly-encoded JSON string and ``"lat,lon"``.
    Returns None for anything unusable (including out-of-range or 0,0 fixes).
    """
    try:
        data: Any = json.loads(payload)
    except (TypeError, ValueError):
        data = payload.decode(errors="replace") if isinstance(payload, bytes) else payload
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError:
            parts = data.split(",")
            data = {"lat": parts[0], "lon": parts[1]} if len(parts) == 2 else None
    if not isinstance(data, dict):
        return None
    for wrapper in ("locationValue", "location_value", "value"):
        if isinstance(data.get(wrapper), dict):
            data = data[wrapper]
            break
    lat = _num(data.get("latitude", data.get("lat")))
    lon = _num(data.get("longitude", data.get("lon")))
    if lat is None or lon is None:
        return None
    if not (-90 <= lat <= 90 and -180 <= lon <= 180) or (lat == 0 and lon == 0):
        return None
    return lat, lon


class MqttTelemetryArrivalSource:
    """Location events from the self-hosted fleet-telemetry MQTT stream.

    Single-threaded: ``events()`` drives the paho network loop itself
    (``client.loop(timeout=1.0)``) and yields as messages arrive, so it fits
    the detector's synchronous model and Ctrl-C stays responsive. The paho
    client is created lazily (optional ``mqtt`` extra); tests inject
    ``client_factory``.
    """

    def __init__(
        self,
        vin: str,
        *,
        host: str = "localhost",
        port: int = 1883,
        username: str = "",
        password: str = "",
        tls: bool = False,
        topic_base: str = TELEMETRY_TOPIC_BASE,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.topic = location_topic(vin, topic_base)
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.tls = tls
        self._client_factory = client_factory or _paho_client
        self._queue: queue.SimpleQueue[LocationEvent] = queue.SimpleQueue()

    def _on_message(self, _client: Any, _userdata: Any, message: Any) -> None:
        coords = parse_location(message.payload)
        if coords is None:
            return
        at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        self._queue.put(LocationEvent(lat=coords[0], lon=coords[1], at=at))

    def _on_connect(self, client: Any, *_args: Any, **_kwargs: Any) -> None:
        # (Re)subscribe on every connect so a broker restart does not
        # silently stop the stream.
        client.subscribe(self.topic, qos=1)

    def events(self) -> Iterator[LocationEvent | None]:
        while not self._queue.empty():  # drop fixes left over from a previous leg
            self._queue.get()
        client = self._client_factory()
        if self.username:
            client.username_pw_set(self.username, self.password or "")
        if self.tls:
            client.tls_set()
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.connect(self.host, self.port, keepalive=60)
        try:
            while True:
                rc = client.loop(timeout=1.0)
                if rc:  # connection lost — let paho reconnect on the next turn
                    time.sleep(1.0)
                    try:
                        client.reconnect()
                    except OSError as exc:
                        log.debug("MQTT reconnect to %s:%s failed: %s", self.host, self.port, exc)
                if self._queue.empty():
                    yield None  # heartbeat: lets the detector check its deadline
                while not self._queue.empty():
                    yield self._queue.get()
        finally:
            try:
                client.disconnect()
            except Exception:  # noqa: BLE001 — best effort on shutdown
                log.debug("MQTT disconnect failed", exc_info=True)


def _paho_client() -> Any:
    try:
        import paho.mqtt.client as mqtt
    except ImportError as exc:  # pragma: no cover - exercised via doctor/CLI
        raise RuntimeError(
            "paho-mqtt is not installed. Install it with: pip install 'tesla-cli[mqtt]'"
        ) from exc
    return mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"tesla-cli-nav-{int(time.time())}",
        protocol=mqtt.MQTTv311,
    )


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
        try:
            return self._consume(events, deadline)
        finally:
            close = getattr(events, "close", None)
            if close is not None:
                close()  # e.g. disconnect a live MQTT client

    def _consume(self, events: Iterator[LocationEvent | None], deadline: float) -> bool:
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
            if event is None:  # heartbeat from a live source (already waited)
                continue
            km = haversine_km(self.waypoint.lat, self.waypoint.lon, event.lat, event.lon)
            if km * 1000.0 < self.tolerance_meters:
                return True
