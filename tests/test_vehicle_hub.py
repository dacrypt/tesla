"""Unit tests for tesla_cli.api.vehicle_hub.VehicleStateHub.

The poll loop is driven synchronously: the hub's wake event is replaced by a
fake whose ``wait()`` records the requested interval and stops the loop after
a fixed number of iterations. No real threads, no sleeps.
"""

from __future__ import annotations

import asyncio
import json
import math
from unittest.mock import MagicMock, patch

import pytest

from tesla_cli.api import vehicle_hub as hub_mod
from tesla_cli.api.vehicle_hub import (
    DEGRADED_INTERVAL,
    MAX_CONSECUTIVE_ERRORS,
    NORMAL_INTERVAL,
    VehicleStateHub,
    _sanitize,
)
from tesla_cli.core.exceptions import (
    ApiError,
    EndpointDeprecatedError,
    VehicleAsleepError,
)

VIN = "5YJ3E1EA1PF000001"


class _FakeWake:
    """Stand-in for threading.Event that drives the poll loop deterministically."""

    def __init__(self, hub: VehicleStateHub, iterations: int) -> None:
        self._hub = hub
        self._left = iterations
        self.waits: list[float] = []
        self.set_calls = 0
        self.clear_calls = 0

    def wait(self, timeout: float | None = None) -> bool:
        self.waits.append(timeout)
        self._left -= 1
        if self._left <= 0:
            self._hub._stopped = True
        return False

    def clear(self) -> None:
        self.clear_calls += 1

    def set(self) -> None:
        self.set_calls += 1


def _run(hub: VehicleStateHub, iterations: int) -> _FakeWake:
    fake = _FakeWake(hub, iterations)
    hub._wake_event = fake  # type: ignore[assignment]
    hub._poll_loop()
    return fake


def _events(q: asyncio.Queue) -> list[tuple[str, dict]]:
    out = []
    while not q.empty():
        raw = q.get_nowait()
        head, data = raw.split("\n", 1)
        assert raw.endswith("\n\n")
        out.append((head.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return out


@pytest.fixture
def backend():
    return MagicMock()


# ── Initial state / simple accessors ─────────────────────────────────────────


def test_initial_state(backend):
    hub = VehicleStateHub(backend, VIN)
    assert hub.get_latest() is None
    assert hub.get_latest_ts() == 0
    assert hub.get_error() is None
    assert hub.is_pre_delivery() is False
    assert hub._interval == NORMAL_INTERVAL


def test_custom_interval_is_used_as_base(backend):
    backend.get_vehicle_data.return_value = {"x": 1}
    hub = VehicleStateHub(backend, VIN, interval=7)
    fake = _run(hub, 1)
    assert fake.waits == [7]


def test_stop_sets_flag_and_wakes(backend):
    hub = VehicleStateHub(backend, VIN)
    hub.stop()
    assert hub._stopped is True
    assert hub._wake_event.is_set()


def test_invalidate_wakes_poller(backend):
    hub = VehicleStateHub(backend, VIN)
    assert not hub._wake_event.is_set()
    hub.invalidate()
    assert hub._wake_event.is_set()


def test_poll_loop_exits_immediately_when_stopped(backend):
    hub = VehicleStateHub(backend, VIN)
    hub._stopped = True
    hub._poll_loop()
    backend.get_vehicle_data.assert_not_called()


def test_start_spawns_daemon_thread_targeting_poll_loop(backend):
    hub = VehicleStateHub(backend, VIN)
    with patch.object(hub_mod.threading, "Thread") as thread_cls:
        hub.start()
    kwargs = thread_cls.call_args.kwargs
    assert kwargs["target"] == hub._poll_loop
    assert kwargs["daemon"] is True
    assert kwargs["name"] == "vehicle-hub"
    thread_cls.return_value.start.assert_called_once()


# ── Successful polling ───────────────────────────────────────────────────────


def test_success_updates_state_and_broadcasts(backend):
    backend.get_vehicle_data.return_value = {"vin": VIN, "battery": 80}
    hub = VehicleStateHub(backend, VIN)
    q = hub.subscribe()
    with patch.object(hub_mod.time, "time", return_value=1700000000.5):
        fake = _run(hub, 1)

    backend.get_vehicle_data.assert_called_once_with(VIN)
    assert hub.get_latest() == {"vin": VIN, "battery": 80}
    assert hub.get_latest_ts() == 1700000000.5
    assert hub.get_error() is None
    assert fake.waits == [NORMAL_INTERVAL]
    assert fake.clear_calls == 1

    events = _events(q)
    assert events == [("vehicle", {"ts": 1700000000, "data": {"vin": VIN, "battery": 80}})]


def test_success_after_degraded_resets_interval_and_flags(backend):
    backend.get_vehicle_data.return_value = {"ok": True}
    hub = VehicleStateHub(backend, VIN)
    hub._interval = DEGRADED_INTERVAL
    hub._pre_delivery = True
    hub._consecutive_errors = 5
    hub._error = "old"
    fake = _run(hub, 1)
    assert fake.waits == [NORMAL_INTERVAL]
    assert hub._interval == NORMAL_INTERVAL
    assert hub.is_pre_delivery() is False
    assert hub._consecutive_errors == 0
    assert hub.get_error() is None


# ── Error / backoff paths ────────────────────────────────────────────────────


def test_generic_errors_backoff_only_after_threshold(backend):
    backend.get_vehicle_data.side_effect = RuntimeError("boom")
    hub = VehicleStateHub(backend, VIN)
    q = hub.subscribe()
    fake = _run(hub, MAX_CONSECUTIVE_ERRORS + 1)

    expected = [NORMAL_INTERVAL] * (MAX_CONSECUTIVE_ERRORS - 1) + [DEGRADED_INTERVAL] * 2
    assert fake.waits == expected
    assert hub._consecutive_errors == MAX_CONSECUTIVE_ERRORS + 1
    assert hub.get_error() == "boom"
    assert hub.get_latest() is None
    # Generic errors are not broadcast to clients
    assert q.empty()


def test_error_keeps_previous_latest(backend):
    backend.get_vehicle_data.side_effect = [{"v": 1}, RuntimeError("down")]
    hub = VehicleStateHub(backend, VIN)
    _run(hub, 2)
    assert hub.get_latest() == {"v": 1}
    assert hub.get_error() == "down"


@pytest.mark.parametrize(
    "exc",
    [EndpointDeprecatedError("gone"), ApiError(412, "precondition failed")],
    ids=["deprecated", "http412"],
)
def test_pre_delivery_slows_down_and_broadcasts(backend, exc):
    backend.get_vehicle_data.side_effect = exc
    hub = VehicleStateHub(backend, VIN)
    q = hub.subscribe()
    fake = _run(hub, 1)
    assert hub.is_pre_delivery() is True
    assert fake.waits == [DEGRADED_INTERVAL]
    assert _events(q) == [
        ("error", {"error": "pre_delivery", "message": "Vehicle not accessible (pre-delivery)"})
    ]


@pytest.mark.parametrize(
    "exc",
    [VehicleAsleepError("zzz"), ApiError(408, "timeout")],
    ids=["asleep", "http408"],
)
def test_asleep_slows_down_and_broadcasts(backend, exc):
    backend.get_vehicle_data.side_effect = exc
    hub = VehicleStateHub(backend, VIN)
    q = hub.subscribe()
    fake = _run(hub, 1)
    assert hub.is_pre_delivery() is False
    assert fake.waits == [DEGRADED_INTERVAL]
    assert _events(q) == [("error", {"error": "asleep", "message": "Vehicle is asleep"})]


def test_other_api_error_status_is_generic(backend):
    backend.get_vehicle_data.side_effect = ApiError(500, "server")
    hub = VehicleStateHub(backend, VIN)
    q = hub.subscribe()
    fake = _run(hub, 1)
    assert fake.waits == [NORMAL_INTERVAL]
    assert hub.is_pre_delivery() is False
    assert q.empty()


def test_recovery_after_asleep(backend):
    backend.get_vehicle_data.side_effect = [VehicleAsleepError("zzz"), {"awake": True}]
    hub = VehicleStateHub(backend, VIN)
    fake = _run(hub, 2)
    assert fake.waits == [DEGRADED_INTERVAL, NORMAL_INTERVAL]
    assert hub.get_latest() == {"awake": True}


# ── Subscribers / broadcast ─────────────────────────────────────────────────


def test_subscribe_unsubscribe(backend):
    hub = VehicleStateHub(backend, VIN)
    q1 = hub.subscribe()
    q2 = hub.subscribe()
    assert q1.maxsize == 10
    assert hub._clients == [q1, q2]
    hub.unsubscribe(q1)
    assert hub._clients == [q2]
    # Unsubscribing an unknown queue is a no-op
    hub.unsubscribe(q1)
    assert hub._clients == [q2]


def test_broadcast_source_payload(backend):
    hub = VehicleStateHub(backend, VIN)
    q = hub.subscribe()
    with patch.object(hub_mod.time, "time", return_value=42.9):
        hub.broadcast_source("co.runt", {"placa": "ABC123", "bad": float("nan")})
    assert _events(q) == [
        ("source", {"ts": 42, "id": "co.runt", "data": {"placa": "ABC123", "bad": None}})
    ]


def test_broadcast_reaches_all_clients(backend):
    hub = VehicleStateHub(backend, VIN)
    qs = [hub.subscribe() for _ in range(3)]
    hub._broadcast_error("asleep", "Vehicle is asleep")
    for q in qs:
        assert q.qsize() == 1


def test_full_queue_drops_oldest(backend):
    hub = VehicleStateHub(backend, VIN)
    q = hub.subscribe()
    for i in range(q.maxsize):
        q.put_nowait(f"old-{i}")
    hub._send_to_clients("newest")
    items = [q.get_nowait() for _ in range(q.qsize())]
    assert len(items) == q.maxsize
    assert items[0] == "old-1"
    assert items[-1] == "newest"
    assert q in hub._clients


def test_unrecoverable_queue_is_removed(backend):
    hub = VehicleStateHub(backend, VIN)
    good = hub.subscribe()
    bad = MagicMock()
    bad.put_nowait.side_effect = asyncio.QueueFull
    bad.get_nowait.side_effect = RuntimeError("broken")
    hub._clients.append(bad)

    hub._send_to_clients("evt")
    assert bad not in hub._clients
    assert good in hub._clients
    assert good.get_nowait() == "evt"


# ── _sanitize ───────────────────────────────────────────────────────────────


def test_sanitize_replaces_nan_and_inf_recursively():
    data = {
        "a": float("nan"),
        "b": [1.5, float("inf"), {"c": -math.inf}],
        "d": "text",
        "e": None,
        "f": 3,
    }
    assert _sanitize(data) == {
        "a": None,
        "b": [1.5, None, {"c": None}],
        "d": "text",
        "e": None,
        "f": 3,
    }


def test_sanitized_payload_is_strict_json(backend):
    backend.get_vehicle_data.return_value = {"temp": float("nan")}
    hub = VehicleStateHub(backend, VIN)
    q = hub.subscribe()
    _run(hub, 1)
    raw = q.get_nowait()
    payload = raw.split("data: ", 1)[1].strip()
    # Would raise on NaN if not sanitized
    parsed = json.loads(payload, parse_constant=lambda c: pytest.fail(f"non-JSON {c}"))
    assert parsed["data"] == {"temp": None}
