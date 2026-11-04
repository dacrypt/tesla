"""Route tests for api/routes/scenes.py, service.py and energy_mgmt.py.

These routers are not included by ``create_app()`` today, so each test mounts
the router on a bare FastAPI app (same prefixes the UI would use) and patches
the module-level backend/config accessors.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.routes import energy_mgmt, scenes, service  # noqa: E402
from tesla_cli.core.config import Config  # noqa: E402
from tests.conftest import MOCK_VIN  # noqa: E402


def _client(router, prefix: str) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix=prefix)
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def vehicle_backend():
    b = MagicMock()
    b.get_charge_state.return_value = {
        "battery_level": 72,
        "battery_range": 220.456,
        "charge_limit_soc": 80,
        "charging_state": "Disconnected",
        "scheduled_charging_pending": False,
    }
    b.get_climate_state.return_value = {
        "is_climate_on": True,
        "inside_temp": 22.5,
        "outside_temp": 18.0,
        "driver_temp_setting": 21.0,
    }
    b.get_drive_state.return_value = {"shift_state": None, "speed": None}
    b.get_vehicle_data.return_value = {
        "vehicle_state": {
            "locked": True,
            "sentry_mode": True,
            "car_version": "2025.2.6",
            "tpms_pressure_fl": 2.9,
            "tpms_pressure_fr": 2.875,
            "tpms_pressure_rl": None,
            "tpms_pressure_rr": "3.0",
        }
    }
    return b


def _patch_vehicle(module: str, backend):
    return [
        patch(f"tesla_cli.api.routes.{module}.load_config", return_value=Config()),
        patch(f"tesla_cli.api.routes.{module}.get_vehicle_backend", return_value=backend),
        patch(f"tesla_cli.api.routes.{module}.resolve_vin", return_value=MOCK_VIN),
    ]


@pytest.fixture
def scenes_client(vehicle_backend):
    ps = _patch_vehicle("scenes", vehicle_backend)
    for p in ps:
        p.start()
    yield _client(scenes.router, "/api/scenes"), vehicle_backend
    for p in ps:
        p.stop()


@pytest.fixture
def service_client(vehicle_backend):
    ps = _patch_vehicle("service", vehicle_backend)
    for p in ps:
        p.start()
    yield _client(service.router, "/api/service"), vehicle_backend
    for p in ps:
        p.stop()


# ── Scenes ───────────────────────────────────────────────────────────────────


def test_list_scenes(scenes_client):
    client, _ = scenes_client
    r = client.get("/api/scenes/")
    assert r.status_code == 200
    assert [s["id"] for s in r.json()] == ["morning", "goodnight", "trip"]


def test_unknown_scene_404(scenes_client):
    client, backend = scenes_client
    r = client.post("/api/scenes/party/execute")
    assert r.status_code == 404
    assert "party" in r.json()["detail"]
    backend.get_vehicle_data.assert_not_called()


def test_backend_unavailable_maps_to_502():
    with patch("tesla_cli.api.routes.scenes.load_config", side_effect=RuntimeError("no config")):
        r = _client(scenes.router, "/api/scenes").post("/api/scenes/morning/execute")
    assert r.status_code == 502
    assert "no config" in r.json()["detail"]


def test_morning_scene(scenes_client):
    client, backend = scenes_client
    r = client.post("/api/scenes/morning/execute")
    assert r.status_code == 200
    body = r.json()
    assert body["scene"] == "morning"
    assert body["battery"] == {
        "level": 72,
        "limit": 80,
        "range_mi": 220.5,
        "charging_state": "Disconnected",
    }
    assert body["climate"]["on"] is True
    assert body["drive"] == {"shift_state": "P", "speed": None}
    assert body["security"] == {"locked": True, "sentry_mode": True}
    assert body["software"] == "2025.2.6"
    backend.get_charge_state.assert_called_once_with(MOCK_VIN)


def test_morning_scene_tolerates_partial_failures(scenes_client):
    client, backend = scenes_client
    backend.get_charge_state.side_effect = RuntimeError("asleep")
    backend.get_vehicle_data.side_effect = RuntimeError("asleep")
    backend.get_charge_state.return_value = None
    r = client.post("/api/scenes/morning/execute")
    assert r.status_code == 200
    body = r.json()
    assert body["battery"]["level"] is None
    assert body["battery"]["range_mi"] is None
    assert body["security"] == {"locked": None, "sentry_mode": None}
    # climate still came through
    assert body["climate"]["inside_temp_c"] == 22.5


def test_morning_scene_uses_est_range_fallback(scenes_client):
    client, backend = scenes_client
    backend.get_charge_state.return_value = {"battery_level": 50, "est_battery_range": 100.04}
    r = client.post("/api/scenes/morning/execute")
    assert r.json()["battery"]["range_mi"] == 100.0


def test_goodnight_all_ok(scenes_client):
    client, backend = scenes_client
    backend.get_charge_state.return_value = {
        "battery_level": 60,
        "charge_limit_soc": 90,
        "charging_state": "Charging",
    }
    body = client.post("/api/scenes/goodnight/execute").json()
    assert body["scene"] == "goodnight"
    assert body["security"] == {
        "locked": True,
        "locked_ok": True,
        "sentry_mode": True,
        "sentry_ok": True,
    }
    assert body["battery"]["charge_ok"] is True
    assert body["warnings"] == []


def test_goodnight_warnings(scenes_client):
    client, backend = scenes_client
    backend.get_vehicle_data.return_value = {
        "vehicle_state": {"locked": False, "sentry_mode": False}
    }
    backend.get_charge_state.return_value = {"charging_state": "Disconnected"}
    body = client.post("/api/scenes/goodnight/execute").json()
    assert body["warnings"] == [
        "Doors are UNLOCKED",
        "Sentry mode is OFF",
        "Vehicle is not charging",
    ]
    assert body["battery"]["limit"] == 80  # default
    assert body["security"]["locked_ok"] is False


def test_goodnight_scheduled_charging_counts_as_ok(scenes_client):
    client, backend = scenes_client
    backend.get_charge_state.return_value = {
        "charging_state": "Disconnected",
        "scheduled_charging_pending": True,
    }
    body = client.post("/api/scenes/goodnight/execute").json()
    assert body["battery"]["charge_ok"] is True
    assert body["battery"]["scheduled_charging"] is True
    assert "Vehicle is not charging" not in body["warnings"]


def test_goodnight_unknown_lock_state_no_warning(scenes_client):
    client, backend = scenes_client
    backend.get_vehicle_data.side_effect = RuntimeError("offline")
    backend.get_charge_state.return_value = {"charging_state": "Complete"}
    body = client.post("/api/scenes/goodnight/execute").json()
    assert body["security"]["locked"] is None
    assert body["warnings"] == []
    assert body["battery"]["charging_state"] == "Complete"


def test_trip_scene(scenes_client):
    client, _ = scenes_client
    body = client.post("/api/scenes/trip/execute").json()
    assert body["scene"] == "trip"
    assert body["battery"]["battery_ok"] is True
    assert body["battery"]["range_mi"] == 220.5
    # None pressures are skipped, string pressure is coerced
    assert body["tires"] == {"fl": 2.9, "fr": 2.88, "rr": 3.0}
    assert body["navigation_sent"] is False


def test_trip_scene_low_battery_no_tires(scenes_client):
    client, backend = scenes_client
    backend.get_charge_state.return_value = {"battery_level": 15}
    backend.get_vehicle_data.return_value = {"vehicle_state": {}}
    body = client.post("/api/scenes/trip/execute").json()
    assert body["battery"]["battery_ok"] is False
    assert body["tires"] is None


def test_safe_helper():
    assert scenes._safe({"a": {"_error": "x"}}, "a") == {}
    assert scenes._safe({"a": [1, 2]}, "a") == {}
    assert scenes._safe({}, "missing") == {}
    assert scenes._safe({"a": {"k": 1}}, "a") == {"k": 1}


def test_fetch_parallel_captures_errors():
    def boom():
        raise ValueError("bad")

    out = scenes._fetch_parallel({"ok": lambda: 1, "bad": boom})
    assert out == {"ok": 1, "bad": {"_error": "bad"}}


# ── Service ──────────────────────────────────────────────────────────────────


def test_service_history_list(service_client):
    client, backend = service_client
    backend.get_service_visits.return_value = [{"id": 1}]
    r = client.get("/api/service/history")
    assert r.status_code == 200
    assert r.json() == [{"id": 1}]
    backend.get_service_visits.assert_called_once_with(MOCK_VIN)


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"service_visits": [{"id": 2}]}, [{"id": 2}]),
        ({"visits": [{"id": 3}]}, [{"id": 3}]),
        ({"other": 1}, []),
    ],
)
def test_service_history_dict_shapes(service_client, payload, expected):
    client, backend = service_client
    backend.get_service_visits.return_value = payload
    assert client.get("/api/service/history").json() == expected


def test_service_history_unsupported_backend_returns_empty(service_client):
    client, backend = service_client
    backend.get_service_visits.side_effect = AttributeError("nope")
    r = client.get("/api/service/history")
    assert r.status_code == 200
    assert r.json() == []


def test_service_history_error_502(service_client):
    client, backend = service_client
    backend.get_service_visits.side_effect = RuntimeError("tesla down")
    r = client.get("/api/service/history")
    assert r.status_code == 502
    assert "tesla down" in r.json()["detail"]


def test_service_appointments_shapes(service_client):
    client, backend = service_client
    backend.get_service_appointments.return_value = [{"when": "tomorrow"}]
    assert client.get("/api/service/appointments").json() == [{"when": "tomorrow"}]
    backend.get_service_appointments.return_value = {"appointments": [{"when": "x"}]}
    assert client.get("/api/service/appointments").json() == [{"when": "x"}]
    backend.get_service_appointments.return_value = {}
    assert client.get("/api/service/appointments").json() == []


def test_service_appointments_unsupported_and_error(service_client):
    client, backend = service_client
    backend.get_service_appointments.side_effect = AttributeError("nope")
    assert client.get("/api/service/appointments").json() == []
    backend.get_service_appointments.side_effect = RuntimeError("boom")
    r = client.get("/api/service/appointments")
    assert r.status_code == 502


def test_service_reminders_from_odometer(service_client):
    client, backend = service_client
    # 15_000 mi -> 24_140 km
    backend.get_vehicle_state.return_value = {"odometer": 15_000}
    r = client.get("/api/service/reminders")
    assert r.status_code == 200
    by_id = {x["id"]: x for x in r.json()}
    assert set(by_id) == {"tires", "cabin_air", "brake_fluid", "hepa_filter", "ac_desiccant"}
    tires = by_id["tires"]
    assert tires["current_odometer_km"] == 24_140
    assert tires["next_service_km"] == 30_000
    assert tires["km_until_service"] == 5_860
    assert tires["progress_pct"] == 41
    assert tires["due_soon"] is False
    cabin = by_id["cabin_air"]
    assert cabin["next_service_km"] == 48_000
    assert cabin["km_until_service"] == 23_860
    assert cabin["progress_pct"] == 1


def test_service_reminders_due_soon(service_client):
    client, backend = service_client
    # 5_600 mi -> 9_012 km, 988 km until tire rotation
    backend.get_vehicle_state.return_value = {"odometer": 5_600}
    tires = next(x for x in client.get("/api/service/reminders").json() if x["id"] == "tires")
    assert tires["km_until_service"] == 988
    assert tires["due_soon"] is True
    assert tires["overdue"] is False


def test_service_reminders_without_odometer(service_client):
    client, backend = service_client
    backend.get_vehicle_state.side_effect = RuntimeError("asleep")
    items = client.get("/api/service/reminders").json()
    assert all(x["current_odometer_km"] == 0 for x in items)
    assert all(x["progress_pct"] == 0 for x in items)
    assert all(x["km_until_service"] == x["interval_km"] for x in items)


def test_service_reminders_backend_failure_502():
    with patch("tesla_cli.api.routes.service.load_config", side_effect=RuntimeError("cfg")):
        r = _client(service.router, "/api/service").get("/api/service/reminders")
    assert r.status_code == 502


# ── Energy management ───────────────────────────────────────────────────────


@pytest.fixture
def energy():
    backend = MagicMock()
    backend.list_energy_sites.return_value = [{"energy_site_id": 111}, {"energy_site_id": 222}]
    backend.live_status.return_value = {"solar_power": 1000}
    backend.get_site_info.return_value = {"site_name": "Home"}
    backend.energy_history.return_value = {"time_series": []}
    backend.set_backup_reserve.return_value = {"ok": True}
    backend.set_operation_mode.return_value = {"ok": True}
    backend.set_storm_mode.return_value = {"ok": True}
    cfg = Config()
    ps = [
        patch("tesla_cli.api.routes.energy_mgmt.load_energy_backend", return_value=backend),
        patch("tesla_cli.api.routes.energy_mgmt.load_config", return_value=cfg),
    ]
    for p in ps:
        p.start()
    yield _client(energy_mgmt.router, "/api/energy/mgmt"), backend, cfg
    for p in ps:
        p.stop()


def test_energy_sites(energy):
    client, backend, _ = energy
    r = client.get("/api/energy/mgmt/sites")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_energy_sites_error(energy):
    client, backend, _ = energy
    backend.list_energy_sites.side_effect = RuntimeError("no token")
    r = client.get("/api/energy/mgmt/sites")
    assert r.status_code == 502
    assert "no token" in r.json()["detail"]


@pytest.mark.parametrize(
    "path,method",
    [("status", "live_status"), ("info", "get_site_info"), ("history", "energy_history")],
)
def test_energy_reads_explicit_site(energy, path, method):
    client, backend, _ = energy
    r = client.get(f"/api/energy/mgmt/{path}?site_id=999")
    assert r.status_code == 200
    assert getattr(backend, method).call_args.args[0] == 999
    backend.list_energy_sites.assert_not_called()


@pytest.mark.parametrize(
    "path,method",
    [("status", "live_status"), ("info", "get_site_info"), ("history", "energy_history")],
)
def test_energy_reads_config_site(energy, path, method):
    client, backend, cfg = energy
    cfg.energy.site_id = 555
    client.get(f"/api/energy/mgmt/{path}")
    assert getattr(backend, method).call_args.args[0] == 555
    backend.list_energy_sites.assert_not_called()


@pytest.mark.parametrize(
    "path,method",
    [("status", "live_status"), ("info", "get_site_info"), ("history", "energy_history")],
)
def test_energy_reads_first_site_fallback(energy, path, method):
    client, backend, _ = energy
    r = client.get(f"/api/energy/mgmt/{path}")
    assert r.status_code == 200
    assert getattr(backend, method).call_args.args[0] == 111


@pytest.mark.parametrize("path", ["status", "info", "history"])
def test_energy_reads_no_sites_404(energy, path):
    client, backend, _ = energy
    backend.list_energy_sites.return_value = []
    r = client.get(f"/api/energy/mgmt/{path}")
    assert r.status_code == 404
    assert "No energy sites" in r.json()["detail"]


@pytest.mark.parametrize(
    "path,method",
    [("status", "live_status"), ("info", "get_site_info"), ("history", "energy_history")],
)
def test_energy_reads_backend_error_502(energy, path, method):
    client, backend, _ = energy
    getattr(backend, method).side_effect = RuntimeError("upstream")
    r = client.get(f"/api/energy/mgmt/{path}?site_id=1")
    assert r.status_code == 502
    assert "upstream" in r.json()["detail"]


def test_energy_history_period_passthrough(energy):
    client, backend, _ = energy
    client.get("/api/energy/mgmt/history?site_id=1&period=month")
    backend.energy_history.assert_called_once_with(1, period="month")


def test_set_backup(energy):
    client, backend, _ = energy
    r = client.post("/api/energy/mgmt/backup?site_id=1&percent=30")
    assert r.status_code == 200
    backend.set_backup_reserve.assert_called_once_with(1, 30)


@pytest.mark.parametrize("pct", [-1, 101])
def test_set_backup_out_of_range(energy, pct):
    client, backend, _ = energy
    r = client.post(f"/api/energy/mgmt/backup?site_id=1&percent={pct}")
    assert r.status_code == 422
    backend.set_backup_reserve.assert_not_called()


def test_set_backup_error(energy):
    client, backend, _ = energy
    backend.set_backup_reserve.side_effect = RuntimeError("denied")
    assert client.post("/api/energy/mgmt/backup?site_id=1&percent=30").status_code == 502


def test_set_mode(energy):
    client, backend, _ = energy
    r = client.post("/api/energy/mgmt/mode?site_id=1&mode=autonomous")
    assert r.status_code == 200
    backend.set_operation_mode.assert_called_once_with(1, "autonomous")


def test_set_mode_invalid(energy):
    client, backend, _ = energy
    r = client.post("/api/energy/mgmt/mode?site_id=1&mode=turbo")
    assert r.status_code == 422
    assert "autonomous, backup, self_consumption" in r.json()["detail"]
    backend.set_operation_mode.assert_not_called()


def test_set_mode_error(energy):
    client, backend, _ = energy
    backend.set_operation_mode.side_effect = RuntimeError("x")
    assert client.post("/api/energy/mgmt/mode?site_id=1&mode=backup").status_code == 502


def test_set_storm(energy):
    client, backend, _ = energy
    r = client.post("/api/energy/mgmt/storm?site_id=1&enabled=true")
    assert r.status_code == 200
    backend.set_storm_mode.assert_called_once_with(1, True)
    backend.set_storm_mode.side_effect = RuntimeError("x")
    assert client.post("/api/energy/mgmt/storm?site_id=1&enabled=false").status_code == 502
