"""Tests for tesla-cli API server (FastAPI endpoints)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Skip entire module if fastapi not installed
fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.server.app import create_app  # noqa: E402
from tests.conftest import MOCK_VIN  # noqa: E402

# ── Shared mock data ──────────────────────────────────────────────────────────

MOCK_VEHICLE_DATA = {
    "charge_state": {
        "battery_level":      72,
        "battery_range":      220.5,
        "charging_state":     "Disconnected",
        "charge_limit_soc":   80,
        "charger_power":      0,
        "charge_energy_added": 5.2,
    },
    "drive_state": {
        "speed":       0,
        "power":       0,
        "shift_state": "P",
        "latitude":    37.4219,
        "longitude":   -122.0840,
        "heading":     90,
    },
    "climate_state": {
        "inside_temp":              22.0,
        "outside_temp":             18.5,
        "is_climate_on":            False,
        "driver_temp_setting":      21.0,
        "passenger_temp_setting":   21.0,
    },
    "vehicle_state": {
        "locked":           True,
        "df":               0,
        "pf":               0,
        "is_user_present":  False,
        "sentry_mode":      False,
        "odometer":         12500.0,
        "software_version": "2024.14.3",
    },
}


def _make_cfg(vin=MOCK_VIN):
    from tesla_cli.config import Config
    cfg = Config()
    cfg.general.default_vin = vin
    cfg.general.backend     = "owner"
    return cfg


def _make_backend():
    m = MagicMock()
    m.get_vehicle_data.return_value     = MOCK_VEHICLE_DATA
    m.get_charge_state.return_value     = MOCK_VEHICLE_DATA["charge_state"]
    m.get_climate_state.return_value    = MOCK_VEHICLE_DATA["climate_state"]
    m.get_drive_state.return_value      = MOCK_VEHICLE_DATA["drive_state"]
    m.get_vehicle_state.return_value    = MOCK_VEHICLE_DATA["vehicle_state"]
    m.command.return_value              = {"result": True}
    m.wake_up.return_value              = {"state": "online"}
    m.list_vehicles.return_value        = [{"vin": MOCK_VIN, "display_name": "Test Car"}]
    return m


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture
def srv():
    """Yield (client, backend_mock, cfg) with all server patches active."""
    cfg     = _make_cfg()
    backend = _make_backend()
    app     = create_app(vin=None)

    targets = [
        ("tesla_cli.server.routes.vehicle.load_config",         cfg),
        ("tesla_cli.server.routes.vehicle.get_vehicle_backend", backend),
        ("tesla_cli.server.routes.vehicle.resolve_vin",         MOCK_VIN),
        ("tesla_cli.server.routes.charge.load_config",          cfg),
        ("tesla_cli.server.routes.charge.get_vehicle_backend",  backend),
        ("tesla_cli.server.routes.charge.resolve_vin",          MOCK_VIN),
        ("tesla_cli.server.routes.climate.load_config",         cfg),
        ("tesla_cli.server.routes.climate.get_vehicle_backend", backend),
        ("tesla_cli.server.routes.climate.resolve_vin",         MOCK_VIN),
        ("tesla_cli.server.app.load_config",                    cfg),
        ("tesla_cli.server.app.resolve_vin",                    MOCK_VIN),
    ]

    patches = []
    for target, retval in targets:
        if callable(retval) or isinstance(retval, MagicMock):
            p = patch(target, return_value=retval)
        elif isinstance(retval, str):
            # resolve_vin should return the VIN string
            p = patch(target, return_value=retval)
        else:
            p = patch(target, return_value=retval)
        patches.append(p)
        p.start()

    client = TestClient(app, raise_server_exceptions=False)
    yield client, backend, cfg

    for p in patches:
        p.stop()


@pytest.fixture
def srv_asleep():
    """Server with sleeping vehicle."""
    from tesla_cli.exceptions import VehicleAsleepError
    cfg     = _make_cfg()
    backend = MagicMock()
    backend.get_vehicle_data.side_effect  = VehicleAsleepError("asleep")
    backend.get_charge_state.side_effect  = VehicleAsleepError("asleep")
    backend.get_climate_state.side_effect = VehicleAsleepError("asleep")
    backend.get_drive_state.side_effect   = VehicleAsleepError("asleep")
    app = create_app(vin=None)

    targets = [
        ("tesla_cli.server.routes.vehicle.load_config",         cfg),
        ("tesla_cli.server.routes.vehicle.get_vehicle_backend", backend),
        ("tesla_cli.server.routes.vehicle.resolve_vin",         MOCK_VIN),
        ("tesla_cli.server.routes.charge.load_config",          cfg),
        ("tesla_cli.server.routes.charge.get_vehicle_backend",  backend),
        ("tesla_cli.server.routes.charge.resolve_vin",          MOCK_VIN),
        ("tesla_cli.server.app.load_config",                    cfg),
    ]
    patches = [patch(t, return_value=rv) for t, rv in targets]
    for p in patches:
        p.start()
    client = TestClient(app, raise_server_exceptions=False)
    yield client, backend
    for p in patches:
        p.stop()


# ── System endpoints ──────────────────────────────────────────────────────────

class TestSystemEndpoints:

    def test_status_ok(self, srv):
        client, _, _ = srv
        r = client.get("/api/status")
        assert r.status_code == 200
        data = r.json()
        assert "version" in data
        assert data["backend"] == "owner"

    def test_config_endpoint(self, srv):
        client, _, _ = srv
        r = client.get("/api/config")
        assert r.status_code == 200
        data = r.json()
        assert "backend" in data
        assert "default_vin" in data

    def test_openapi_schema(self, srv):
        client, _, _ = srv
        r = client.get("/api/openapi.json")
        assert r.status_code == 200
        schema = r.json()
        assert "paths" in schema
        # Check key paths exist
        assert "/api/vehicle/state" in schema["paths"]
        assert "/api/charge/status" in schema["paths"]

    def test_web_ui_root(self, srv):
        client, _, _ = srv
        r = client.get("/")
        assert r.status_code == 200
        # Should return HTML (either full page or fallback)
        assert "text/html" in r.headers.get("content-type", "")

    def test_manifest_json(self, srv):
        client, _, _ = srv
        r = client.get("/manifest.json")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Tesla Dashboard"
        assert data["display"] == "standalone"
        assert data["theme_color"] == "#e82127"

    def test_api_docs_redirect(self, srv):
        client, _, _ = srv
        r = client.get("/api/docs", follow_redirects=True)
        assert r.status_code == 200


# ── Vehicle endpoints ─────────────────────────────────────────────────────────

class TestVehicleRoutes:

    def test_vehicle_state(self, srv):
        client, backend, _ = srv
        r = client.get("/api/vehicle/state")
        assert r.status_code == 200
        data = r.json()
        assert "charge_state" in data
        assert data["charge_state"]["battery_level"] == 72

    def test_vehicle_location(self, srv):
        client, _, _ = srv
        r = client.get("/api/vehicle/location")
        assert r.status_code == 200
        data = r.json()
        assert data["latitude"] == 37.4219
        assert data["longitude"] == -122.0840

    def test_vehicle_charge(self, srv):
        client, _, _ = srv
        r = client.get("/api/vehicle/charge")
        assert r.status_code == 200
        data = r.json()
        assert data["battery_level"] == 72
        assert data["charging_state"] == "Disconnected"

    def test_vehicle_climate(self, srv):
        client, _, _ = srv
        r = client.get("/api/vehicle/climate")
        assert r.status_code == 200
        data = r.json()
        assert data["inside_temp"] == 22.0

    def test_vehicle_list(self, srv):
        client, _, _ = srv
        r = client.get("/api/vehicle/list")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert data[0]["vin"] == MOCK_VIN

    def test_vehicle_command_lock(self, srv):
        client, backend, _ = srv
        r = client.post("/api/vehicle/command", json={"command": "lock", "params": {}})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["command"] == "lock"

    def test_vehicle_command_with_params(self, srv):
        client, backend, _ = srv
        r = client.post("/api/vehicle/command", json={
            "command": "set_charge_limit",
            "params": {"percent": 80},
        })
        assert r.status_code == 200
        backend.command.assert_called_with(MOCK_VIN, "set_charge_limit", percent=80)

    def test_vehicle_wake(self, srv):
        client, backend, _ = srv
        r = client.post("/api/vehicle/wake")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        backend.wake_up.assert_called_once_with(MOCK_VIN)

    def test_vehicle_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.get("/api/vehicle/state")
        assert r.status_code == 503
        assert "asleep" in r.json()["detail"].lower()

    def test_charge_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.get("/api/vehicle/charge")
        assert r.status_code == 503


# ── Charge routes ─────────────────────────────────────────────────────────────

class TestChargeRoutes:

    def test_charge_status(self, srv):
        client, _, _ = srv
        r = client.get("/api/charge/status")
        assert r.status_code == 200
        data = r.json()
        assert data["battery_level"] == 72

    def test_set_limit_valid(self, srv):
        client, backend, _ = srv
        r = client.post("/api/charge/limit", json={"percent": 85})
        assert r.status_code == 200
        data = r.json()
        assert data["charge_limit_soc"] == 85
        backend.command.assert_called_with(MOCK_VIN, "set_charge_limit", percent=85)

    def test_set_limit_too_low(self, srv):
        client, _, _ = srv
        r = client.post("/api/charge/limit", json={"percent": 30})
        assert r.status_code == 422

    def test_set_limit_too_high(self, srv):
        client, _, _ = srv
        r = client.post("/api/charge/limit", json={"percent": 101})
        assert r.status_code == 422

    def test_set_amps_valid(self, srv):
        client, backend, _ = srv
        r = client.post("/api/charge/amps", json={"amps": 24})
        assert r.status_code == 200
        data = r.json()
        assert data["charging_amps"] == 24

    def test_set_amps_out_of_range(self, srv):
        client, _, _ = srv
        r = client.post("/api/charge/amps", json={"amps": 0})
        assert r.status_code == 422

    def test_charge_start(self, srv):
        client, backend, _ = srv
        r = client.post("/api/charge/start")
        assert r.status_code == 200
        backend.command.assert_called_with(MOCK_VIN, "charge_start")

    def test_charge_stop(self, srv):
        client, backend, _ = srv
        r = client.post("/api/charge/stop")
        assert r.status_code == 200
        backend.command.assert_called_with(MOCK_VIN, "charge_stop")


# ── Climate routes ────────────────────────────────────────────────────────────

class TestClimateRoutes:

    def test_climate_status(self, srv):
        client, _, _ = srv
        r = client.get("/api/climate/status")
        assert r.status_code == 200
        data = r.json()
        assert data["inside_temp"] == 22.0

    def test_climate_on(self, srv):
        client, backend, _ = srv
        r = client.post("/api/climate/on")
        assert r.status_code == 200
        data = r.json()
        assert data["climate"] == "on"
        backend.command.assert_called_with(MOCK_VIN, "auto_conditioning_start")

    def test_climate_off(self, srv):
        client, backend, _ = srv
        r = client.post("/api/climate/off")
        assert r.status_code == 200
        data = r.json()
        assert data["climate"] == "off"

    def test_set_temp_valid(self, srv):
        client, backend, _ = srv
        r = client.post("/api/climate/temp", json={"driver_temp": 22.0})
        assert r.status_code == 200
        data = r.json()
        assert data["driver_temp"] == 22.0
        assert data["passenger_temp"] == 22.0  # defaults to driver temp

    def test_set_temp_with_passenger(self, srv):
        client, backend, _ = srv
        r = client.post("/api/climate/temp", json={"driver_temp": 21.0, "passenger_temp": 23.0})
        assert r.status_code == 200
        data = r.json()
        assert data["passenger_temp"] == 23.0

    def test_set_temp_too_cold(self, srv):
        client, _, _ = srv
        r = client.post("/api/climate/temp", json={"driver_temp": 10.0})
        assert r.status_code == 422

    def test_set_temp_too_hot(self, srv):
        client, _, _ = srv
        r = client.post("/api/climate/temp", json={"driver_temp": 35.0})
        assert r.status_code == 422
