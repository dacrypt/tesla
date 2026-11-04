"""Tests for CachedVehicleBackend (TTL cache / coalescing) and TessieBackend (HTTP)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from tesla_cli.core.backends import cached as cached_mod
from tesla_cli.core.backends.cached import CachedVehicleBackend
from tesla_cli.core.backends.tessie import TESSIE_API, TessieBackend
from tesla_cli.core.exceptions import ApiError, BackendNotSupportedError, VehicleAsleepError

VIN = "5YJ3E1EA1PF000001"

FULL = {
    "charge_state": {"battery_level": 80},
    "climate_state": {"inside_temp": 21},
    "drive_state": {"speed": 0},
    "vehicle_state": {"locked": True},
    "vehicle_config": {"car_type": "modely"},
}


class _Clock:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


@pytest.fixture
def clock(monkeypatch):
    c = _Clock()
    monkeypatch.setattr(cached_mod.time, "time", c)
    return c


@pytest.fixture
def inner():
    m = MagicMock()
    m.get_vehicle_data.return_value = FULL
    m.list_vehicles.return_value = [{"vin": VIN}]
    return m


# ── CachedVehicleBackend ───────────────────────────────────────────────────


def test_vehicle_data_cached_within_ttl(inner, clock):
    b = CachedVehicleBackend(inner, ttl=45)
    assert b.get_vehicle_data(VIN) is FULL
    clock.t += 44
    b.get_vehicle_data(VIN)
    assert inner.get_vehicle_data.call_count == 1
    clock.t += 2  # now 46s old
    b.get_vehicle_data(VIN)
    assert inner.get_vehicle_data.call_count == 2


def test_per_vin_keys(inner, clock):
    b = CachedVehicleBackend(inner)
    b.get_vehicle_data(VIN)
    b.get_vehicle_data("OTHER")
    assert inner.get_vehicle_data.call_count == 2


def test_list_vehicles_cached(inner, clock):
    b = CachedVehicleBackend(inner)
    assert b.list_vehicles() == [{"vin": VIN}]
    b.list_vehicles()
    inner.list_vehicles.assert_called_once()


@pytest.mark.parametrize(
    "method,key",
    [
        ("get_charge_state", "charge_state"),
        ("get_climate_state", "climate_state"),
        ("get_drive_state", "drive_state"),
        ("get_vehicle_state", "vehicle_state"),
        ("get_vehicle_config", "vehicle_config"),
    ],
)
def test_sub_states_derived_from_single_fetch(inner, clock, method, key):
    b = CachedVehicleBackend(inner)
    assert getattr(b, method)(VIN) == FULL[key]
    b.get_charge_state(VIN)
    assert inner.get_vehicle_data.call_count == 1


def test_sub_state_missing_returns_whole_blob(inner, clock):
    inner.get_vehicle_data.return_value = {"battery_level": 50}
    b = CachedVehicleBackend(inner)
    assert b.get_charge_state(VIN) == {"battery_level": 50}


def test_fetch_error_not_cached_and_pending_cleared(inner, clock):
    inner.get_vehicle_data.side_effect = [RuntimeError("boom"), FULL]
    b = CachedVehicleBackend(inner)
    with pytest.raises(RuntimeError):
        b.get_vehicle_data(VIN)
    assert b._pending == {}
    assert b.get_vehicle_data(VIN) is FULL


def test_command_invalidates_only_that_vin(inner, clock):
    inner.command.return_value = {"result": True}
    b = CachedVehicleBackend(inner)
    b.get_vehicle_data(VIN)
    b.get_vehicle_data("OTHER")
    b.list_vehicles()
    assert b.command(VIN, "door_lock", x=1) == {"result": True}
    inner.command.assert_called_once_with(VIN, "door_lock", x=1)
    assert set(b._cache) == {"vdata:OTHER", "list_vehicles"}


def test_command_not_supported_still_invalidates(inner, clock):
    inner.command.side_effect = BackendNotSupportedError("cmd")
    b = CachedVehicleBackend(inner)
    b.get_vehicle_data(VIN)
    with pytest.raises(BackendNotSupportedError):
        b.command(VIN, "honk_horn")
    assert "vdata:" + VIN not in b._cache


def test_command_other_error_keeps_cache(inner, clock):
    inner.command.side_effect = RuntimeError("net")
    b = CachedVehicleBackend(inner)
    b.get_vehicle_data(VIN)
    with pytest.raises(RuntimeError):
        b.command(VIN, "honk_horn")
    assert "vdata:" + VIN in b._cache


def test_invalidate_all(inner, clock):
    b = CachedVehicleBackend(inner)
    b.get_vehicle_data(VIN)
    b.list_vehicles()
    b.invalidate()
    assert b._cache == {}


def test_wake_up_invalidates(inner, clock):
    inner.wake_up.return_value = True
    b = CachedVehicleBackend(inner)
    b.get_vehicle_data(VIN)
    assert b.wake_up(VIN) is True
    assert b._cache == {}


@pytest.mark.parametrize(
    "method,args",
    [
        ("mobile_enabled", (VIN,)),
        ("get_nearby_charging_sites", (VIN,)),
        ("get_service_data", (VIN,)),
        ("get_release_notes", (VIN,)),
        ("get_recent_alerts", (VIN,)),
        ("get_fleet_status", (VIN,)),
        ("get_charge_history", ()),
        ("get_safety_score", (VIN,)),
        ("get_drive_score", (VIN,)),
        ("get_service_visits", (VIN,)),
        ("get_service_appointments", ()),
        ("get_invitations", (VIN,)),
    ],
)
def test_passthrough_methods(inner, clock, method, args):
    getattr(inner, method).return_value = {"m": method}
    b = CachedVehicleBackend(inner)
    b.get_vehicle_data(VIN)
    assert getattr(b, method)(*args) == {"m": method}
    getattr(inner, method).assert_called_once_with(*args)
    assert "vdata:" + VIN in b._cache  # reads do not invalidate


@pytest.mark.parametrize(
    "method,args",
    [
        ("create_invitation", (VIN,)),
        ("revoke_invitation", (VIN, "inv1")),
        ("add_charge_schedule", (VIN, "All", 600, 4.6, -74.0, True)),
        ("remove_charge_schedule", (VIN, 3)),
        ("add_precondition_schedule", (VIN, "Weekdays", 420, 4.6, -74.0, False)),
        ("remove_precondition_schedule", (VIN, 4)),
    ],
)
def test_mutating_passthrough_invalidates(inner, clock, method, args):
    getattr(inner, method).return_value = {"ok": method}
    b = CachedVehicleBackend(inner)
    b.get_vehicle_data(VIN)
    assert getattr(b, method)(*args) == {"ok": method}
    getattr(inner, method).assert_called_once_with(*args)
    assert "vdata:" + VIN not in b._cache


class _FakeEvent:
    """Pending-fetch event whose wait() simulates the other thread finishing."""

    def __init__(self, on_wait) -> None:
        self._on_wait = on_wait
        self.waited_with: float | None = None

    def wait(self, timeout=None):
        self.waited_with = timeout
        self._on_wait()
        return True

    def set(self):
        pass


def test_coalesced_waiter_gets_result_of_inflight_fetch(inner, clock):
    b = CachedVehicleBackend(inner)
    key = f"vdata:{VIN}"

    def other_thread_finishes():
        # Lock is released while waiting, so the "other thread" can write.
        assert b._lock.acquire(blocking=False)
        b._cache[key] = ({"from": "other"}, clock.t)
        b._lock.release()

    ev = _FakeEvent(other_thread_finishes)
    b._pending[key] = ev
    assert b.get_vehicle_data(VIN) == {"from": "other"}
    assert ev.waited_with == 30
    inner.get_vehicle_data.assert_not_called()


def test_coalesced_waiter_raises_when_inflight_fetch_failed(inner, clock):
    b = CachedVehicleBackend(inner)
    key = f"vdata:{VIN}"
    b._pending[key] = _FakeEvent(lambda: None)
    with pytest.raises(RuntimeError, match="Coalesced request"):
        b.get_vehicle_data(VIN)
    inner.get_vehicle_data.assert_not_called()


def test_lock_released_after_fetch(inner, clock):
    b = CachedVehicleBackend(inner)
    b.get_vehicle_data(VIN)
    assert b._lock.acquire(blocking=False)
    b._lock.release()
    assert b._pending == {}


# ── TessieBackend ──────────────────────────────────────────────────────────


@pytest.fixture
def tessie():
    b = TessieBackend("tok-123")
    yield b
    b._client.close()


def test_tessie_auth_header_and_base_url(httpx_mock, tessie):
    httpx_mock.add_response(url=f"{TESSIE_API}/{VIN}/state", json=FULL)
    assert tessie.get_vehicle_data(VIN) == FULL
    req = httpx_mock.get_requests()[0]
    assert req.headers["Authorization"] == "Bearer tok-123"


def test_tessie_list_vehicles_unwraps_response(httpx_mock, tessie):
    httpx_mock.add_response(url=f"{TESSIE_API}/api/1/vehicles", json={"response": [{"vin": VIN}]})
    assert tessie.list_vehicles() == [{"vin": VIN}]


def test_tessie_list_vehicles_plain_list(httpx_mock, tessie):
    httpx_mock.add_response(url=f"{TESSIE_API}/api/1/vehicles", json=[{"vin": VIN}])
    assert tessie.list_vehicles() == [{"vin": VIN}]


@pytest.mark.parametrize(
    "method,expected",
    [
        ("get_charge_state", FULL["charge_state"]),
        ("get_climate_state", FULL["climate_state"]),
        ("get_drive_state", FULL["drive_state"]),
        ("get_vehicle_config", FULL["vehicle_config"]),
        ("get_vehicle_state", FULL["vehicle_state"]),
        ("get_service_data", {}),
    ],
)
def test_tessie_sub_states(httpx_mock, tessie, method, expected):
    httpx_mock.add_response(url=f"{TESSIE_API}/{VIN}/state", json=FULL)
    assert getattr(tessie, method)(VIN) == expected


def test_tessie_sub_state_fallbacks(httpx_mock, tessie):
    httpx_mock.add_response(url=f"{TESSIE_API}/{VIN}/state", json={"x": 1}, is_reusable=True)
    assert tessie.get_charge_state(VIN) == {"x": 1}
    assert tessie.get_vehicle_state(VIN) == {}


def test_tessie_asleep_408(httpx_mock, tessie):
    httpx_mock.add_response(url=f"{TESSIE_API}/{VIN}/state", status_code=408)
    with pytest.raises(VehicleAsleepError):
        tessie.get_vehicle_data(VIN)


def test_tessie_http_error(httpx_mock, tessie):
    httpx_mock.add_response(url=f"{TESSIE_API}/{VIN}/state", status_code=500, text="oops")
    with pytest.raises(ApiError) as ei:
        tessie.get_vehicle_data(VIN)
    assert ei.value.status_code == 500


@pytest.mark.parametrize(
    "method,path,payload,expected",
    [
        ("get_charging_invoices", "charging_invoices", [{"id": 1}], [{"id": 1}]),
        ("get_charging_invoices", "charging_invoices", {"invoices": [{"id": 2}]}, [{"id": 2}]),
        ("get_charging_invoices", "charging_invoices", {"results": [{"id": 3}]}, [{"id": 3}]),
        ("get_firmware_alerts", "firmware_alerts", [{"a": 1}], [{"a": 1}]),
        ("get_firmware_alerts", "firmware_alerts", {"alerts": [{"a": 2}]}, [{"a": 2}]),
        ("get_firmware_alerts", "firmware_alerts", {}, []),
        ("get_tire_pressure_history", "tire_pressure", [{"p": 1}], [{"p": 1}]),
        ("get_tire_pressure_history", "tire_pressure", {"results": [{"p": 2}]}, [{"p": 2}]),
        ("get_tire_pressure_history", "tire_pressure", {"data": [{"p": 3}]}, [{"p": 3}]),
        ("get_weather", "weather", {"temp": 20}, {"temp": 20}),
        ("get_consumption", "consumption", {"wh_mi": 250}, {"wh_mi": 250}),
        ("get_nearby_charging_sites", "nearby_charging_sites", {"sc": []}, {"sc": []}),
    ],
)
def test_tessie_simple_gets(httpx_mock, tessie, method, path, payload, expected):
    httpx_mock.add_response(url=f"{TESSIE_API}/{VIN}/{path}", json=payload)
    assert getattr(tessie, method)(VIN) == expected


def test_tessie_wake_up(httpx_mock, tessie):
    httpx_mock.add_response(method="POST", url=f"{TESSIE_API}/{VIN}/wake", json={"result": True})
    assert tessie.wake_up(VIN) is True
    assert httpx_mock.get_requests()[0].content == b""


def test_tessie_wake_up_missing_result(httpx_mock, tessie):
    httpx_mock.add_response(method="POST", url=f"{TESSIE_API}/{VIN}/wake", json={})
    assert tessie.wake_up(VIN) is False


def test_tessie_command_sends_json_params(httpx_mock, tessie):
    httpx_mock.add_response(
        method="POST",
        url=f"{TESSIE_API}/{VIN}/command/set_charge_limit",
        json={"result": True},
    )
    assert tessie.command(VIN, "set_charge_limit", percent=80) == {"result": True}
    assert json.loads(httpx_mock.get_requests()[0].content) == {"percent": 80}


def test_tessie_command_403_maps_to_vcp_hint(httpx_mock, tessie):
    httpx_mock.add_response(
        method="POST", url=f"{TESSIE_API}/{VIN}/command/door_unlock", status_code=403
    )
    with pytest.raises(BackendNotSupportedError) as ei:
        tessie.command(VIN, "door_unlock")
    assert isinstance(ei.value.__cause__, ApiError)


def test_tessie_command_other_errors_propagate(httpx_mock, tessie):
    httpx_mock.add_response(
        method="POST", url=f"{TESSIE_API}/{VIN}/command/door_unlock", status_code=500
    )
    with pytest.raises(ApiError) as ei:
        tessie.command(VIN, "door_unlock")
    assert ei.value.status_code == 500


def test_tessie_command_asleep(httpx_mock, tessie):
    httpx_mock.add_response(
        method="POST", url=f"{TESSIE_API}/{VIN}/command/door_unlock", status_code=408
    )
    with pytest.raises(VehicleAsleepError):
        tessie.command(VIN, "door_unlock")


@pytest.mark.parametrize(
    "method,args",
    [
        ("get_release_notes", (VIN,)),
        ("get_recent_alerts", (VIN,)),
        ("get_charge_history", ()),
        ("get_invitations", (VIN,)),
        ("create_invitation", (VIN,)),
        ("revoke_invitation", (VIN, "x")),
    ],
)
def test_tessie_fleet_only_methods(tessie, method, args):
    with (
        patch.object(tessie, "_get") as g,
        patch.object(tessie, "_post") as p,
        pytest.raises(BackendNotSupportedError),
    ):
        getattr(tessie, method)(*args)
    g.assert_not_called()
    p.assert_not_called()
