"""Tests for tesla-cli API server (FastAPI endpoints)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Skip entire module if fastapi not installed
fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.app import create_app  # noqa: E402
from tests.conftest import MOCK_VIN  # noqa: E402

# ── Shared mock data ──────────────────────────────────────────────────────────

MOCK_VEHICLE_DATA = {
    "charge_state": {
        "battery_level": 72,
        "battery_range": 220.5,
        "charging_state": "Disconnected",
        "charge_limit_soc": 80,
        "charger_power": 0,
        "charge_energy_added": 5.2,
    },
    "drive_state": {
        "speed": 0,
        "power": 0,
        "shift_state": "P",
        "latitude": 37.4219,
        "longitude": -122.0840,
        "heading": 90,
    },
    "climate_state": {
        "inside_temp": 22.0,
        "outside_temp": 18.5,
        "is_climate_on": False,
        "driver_temp_setting": 21.0,
        "passenger_temp_setting": 21.0,
    },
    "vehicle_state": {
        "locked": True,
        "df": 0,
        "pf": 0,
        "is_user_present": False,
        "sentry_mode": False,
        "odometer": 12500.0,
        "software_version": "2024.14.3",
    },
}


def _make_cfg(vin=MOCK_VIN):
    from tesla_cli.core.config import Config

    cfg = Config()
    cfg.general.default_vin = vin
    cfg.general.backend = "owner"
    return cfg


def _make_backend():
    m = MagicMock()
    m.get_vehicle_data.return_value = MOCK_VEHICLE_DATA
    m.get_charge_state.return_value = MOCK_VEHICLE_DATA["charge_state"]
    m.get_climate_state.return_value = MOCK_VEHICLE_DATA["climate_state"]
    m.get_drive_state.return_value = MOCK_VEHICLE_DATA["drive_state"]
    m.get_vehicle_state.return_value = MOCK_VEHICLE_DATA["vehicle_state"]
    m.command.return_value = {"result": True}
    m.wake_up.return_value = {"state": "online"}
    m.list_vehicles.return_value = [{"vin": MOCK_VIN, "display_name": "Test Car"}]
    return m


# ── Fixture ───────────────────────────────────────────────────────────────────


@pytest.fixture
def srv():
    """Yield (client, backend_mock, cfg) with all server patches active."""
    cfg = _make_cfg()
    backend = _make_backend()
    app = create_app(vin=None)

    targets = [
        ("tesla_cli.api.routes.vehicle.load_config", cfg),
        ("tesla_cli.api.routes.vehicle.get_vehicle_backend", backend),
        ("tesla_cli.api.routes.vehicle.resolve_vin", MOCK_VIN),
        ("tesla_cli.api.routes.charge.load_config", cfg),
        ("tesla_cli.api.routes.charge.get_vehicle_backend", backend),
        ("tesla_cli.api.routes.charge.resolve_vin", MOCK_VIN),
        ("tesla_cli.api.routes.climate.load_config", cfg),
        ("tesla_cli.api.routes.climate.get_vehicle_backend", backend),
        ("tesla_cli.api.routes.climate.resolve_vin", MOCK_VIN),
        ("tesla_cli.api.routes.security.load_config", cfg),
        ("tesla_cli.api.routes.security.get_vehicle_backend", backend),
        ("tesla_cli.api.routes.security.resolve_vin", MOCK_VIN),
        ("tesla_cli.api.routes.notify.load_config", cfg),
        ("tesla_cli.api.routes.notify.save_config", MagicMock()),
        ("tesla_cli.api.routes.geofence.load_config", cfg),
        ("tesla_cli.api.routes.geofence.get_vehicle_backend", backend),
        ("tesla_cli.api.routes.geofence.resolve_vin", MOCK_VIN),
        ("tesla_cli.api.app.load_config", cfg),
        ("tesla_cli.api.app.resolve_vin", MOCK_VIN),
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
    from tesla_cli.core.exceptions import VehicleAsleepError

    cfg = _make_cfg()
    backend = MagicMock()
    backend.get_vehicle_data.side_effect = VehicleAsleepError("asleep")
    backend.get_charge_state.side_effect = VehicleAsleepError("asleep")
    backend.get_climate_state.side_effect = VehicleAsleepError("asleep")
    backend.get_drive_state.side_effect = VehicleAsleepError("asleep")
    backend.command.side_effect = VehicleAsleepError("asleep")
    app = create_app(vin=None)

    targets = [
        ("tesla_cli.api.routes.vehicle.load_config", cfg),
        ("tesla_cli.api.routes.vehicle.get_vehicle_backend", backend),
        ("tesla_cli.api.routes.vehicle.resolve_vin", MOCK_VIN),
        ("tesla_cli.api.routes.charge.load_config", cfg),
        ("tesla_cli.api.routes.charge.get_vehicle_backend", backend),
        ("tesla_cli.api.routes.charge.resolve_vin", MOCK_VIN),
        ("tesla_cli.api.routes.security.load_config", cfg),
        ("tesla_cli.api.routes.security.get_vehicle_backend", backend),
        ("tesla_cli.api.routes.security.resolve_vin", MOCK_VIN),
        ("tesla_cli.api.app.load_config", cfg),
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

    def test_root_serves_ui_or_redirects(self, srv):
        client, _, _ = srv
        r = client.get("/", follow_redirects=False)
        # Serves SPA if ui/dist/ exists, otherwise redirects to docs
        assert r.status_code in (200, 301, 302, 303, 307, 308)

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
        r = client.post(
            "/api/vehicle/command",
            json={
                "command": "set_charge_limit",
                "params": {"percent": 80},
            },
        )
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


# ═══════════════════════════════════════════════════════════════════════════════
# Security API Routes
# ═══════════════════════════════════════════════════════════════════════════════


class TestSecurityRoutes:
    def test_lock(self, srv):
        client, backend, _ = srv
        r = client.post("/api/security/lock")
        assert r.status_code == 200
        assert r.json()["action"] == "locked"
        backend.command.assert_called_with(MOCK_VIN, "door_lock")

    def test_unlock(self, srv):
        client, backend, _ = srv
        r = client.post("/api/security/unlock")
        assert r.status_code == 200
        assert r.json()["action"] == "unlocked"

    def test_sentry_status(self, srv):
        client, _, _ = srv
        r = client.get("/api/security/sentry")
        assert r.status_code == 200
        data = r.json()
        assert "sentry_mode" in data

    def test_sentry_on(self, srv):
        client, backend, _ = srv
        r = client.post("/api/security/sentry/on")
        assert r.status_code == 200
        assert r.json()["sentry_mode"] is True

    def test_sentry_off(self, srv):
        client, _, _ = srv
        r = client.post("/api/security/sentry/off")
        assert r.status_code == 200
        assert r.json()["sentry_mode"] is False

    def test_frunk(self, srv):
        client, backend, _ = srv
        r = client.post("/api/security/trunk/front")
        assert r.status_code == 200
        backend.command.assert_called_with(MOCK_VIN, "actuate_trunk", which_trunk="front")

    def test_trunk(self, srv):
        client, _, _ = srv
        r = client.post("/api/security/trunk/rear")
        assert r.status_code == 200

    def test_horn(self, srv):
        client, backend, _ = srv
        r = client.post("/api/security/horn")
        assert r.status_code == 200
        backend.command.assert_called_with(MOCK_VIN, "honk_horn")

    def test_flash(self, srv):
        client, _, _ = srv
        r = client.post("/api/security/flash")
        assert r.status_code == 200

    def test_lock_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/security/lock")
        assert r.status_code == 503


# ═══════════════════════════════════════════════════════════════════════════════
# Notify API Routes
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotifyRoutes:
    def test_notify_list_empty(self, srv):
        client, _, cfg = srv
        cfg.notifications.apprise_urls = []
        cfg.notifications.enabled = False
        cfg.notifications.message_template = "{event}"
        r = client.get("/api/notify/list")
        assert r.status_code == 200
        data = r.json()
        assert data["channels"] == []

    def test_notify_list_with_channels(self, srv):
        client, _, cfg = srv
        cfg.notifications.apprise_urls = ["tgram://tok/chat"]
        cfg.notifications.enabled = True
        cfg.notifications.message_template = "{event}"
        r = client.get("/api/notify/list")
        assert r.status_code == 200
        assert len(r.json()["channels"]) == 1

    def test_notify_test_no_urls_returns_404(self, srv):
        client, _, cfg = srv
        cfg.notifications.apprise_urls = []
        r = client.post("/api/notify/test")
        assert r.status_code == 404

    def test_notify_add(self, srv):
        client, _, cfg = srv
        cfg.notifications.apprise_urls = []
        r = client.post("/api/notify/add", json={"url": "ntfy://test"})
        assert r.status_code == 200
        assert r.json()["channels"] == 1

    def test_notify_add_duplicate_returns_409(self, srv):
        client, _, cfg = srv
        cfg.notifications.apprise_urls = ["ntfy://test"]
        r = client.post("/api/notify/add", json={"url": "ntfy://test"})
        assert r.status_code == 409

    def test_notify_remove(self, srv):
        client, _, cfg = srv
        cfg.notifications.apprise_urls = ["ntfy://a", "ntfy://b"]
        r = client.post("/api/notify/remove", json={"index": 0})
        assert r.status_code == 200
        assert r.json()["removed"] == "ntfy://a"

    def test_notify_remove_invalid_index(self, srv):
        client, _, cfg = srv
        cfg.notifications.apprise_urls = []
        r = client.post("/api/notify/remove", json={"index": 5})
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Geofence API Routes
# ═══════════════════════════════════════════════════════════════════════════════


class TestGeofenceRoutes:
    def test_geofence_list_empty(self, srv):
        client, _, cfg = srv
        cfg.geofences.zones = {}
        r = client.get("/api/geofences")
        assert r.status_code == 200
        assert r.json() == []

    def test_geofence_list_with_zones(self, srv):
        client, _, cfg = srv
        cfg.geofences.zones = {"home": {"lat": 4.7, "lon": -74.0, "radius_km": 0.2}}
        r = client.get("/api/geofences")
        assert r.status_code == 200
        zones = r.json()
        assert len(zones) == 1
        assert zones[0]["name"] == "home"
        assert "distance_km" in zones[0]  # vehicle location resolved
        assert "inside" in zones[0]

    def test_geofence_status_known_zone(self, srv):
        client, _, cfg = srv
        cfg.geofences.zones = {"office": {"lat": 37.4, "lon": -122.0, "radius_km": 1.0}}
        r = client.get("/api/geofences/office")
        assert r.status_code == 200
        data = r.json()
        assert data["zone"] == "office"
        assert "distance_km" in data
        assert "inside" in data

    def test_geofence_status_unknown_zone(self, srv):
        client, _, cfg = srv
        cfg.geofences.zones = {}
        r = client.get("/api/geofences/nowhere")
        assert r.status_code == 404

    def test_geofence_add(self, srv):
        client, _, cfg = srv
        cfg.geofences.zones = {}
        r = client.post("/api/geofences/park", json={"lat": 40.7, "lon": -74.0, "radius_km": 0.5})
        assert r.status_code == 200
        assert r.json()["zone"] == "park"

    def test_geofence_remove(self, srv):
        client, _, cfg = srv
        cfg.geofences.zones = {"old": {"lat": 0, "lon": 0, "radius_km": 1}}
        r = client.delete("/api/geofences/old")
        assert r.status_code == 200
        assert r.json()["removed"] == "old"

    def test_geofence_remove_not_found(self, srv):
        client, _, cfg = srv
        cfg.geofences.zones = {}
        r = client.delete("/api/geofences/ghost")
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Vehicle Ready + Charge Last API
# ═══════════════════════════════════════════════════════════════════════════════


class TestVehicleReadyApi:
    def test_ready_returns_assessment(self, srv):
        client, _, _ = srv
        r = client.get("/api/vehicle/ready")
        assert r.status_code == 200
        data = r.json()
        assert "ready" in data
        assert "battery_level" in data
        assert "issues" in data
        assert isinstance(data["issues"], list)

    def test_ready_high_battery_is_ready(self, srv):
        client, _, _ = srv
        r = client.get("/api/vehicle/ready")
        data = r.json()
        # Mock has battery_level=72, locked=True → should be ready
        assert data["ready"] is True
        assert data["battery_level"] == 72

    def test_ready_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.get("/api/vehicle/ready")
        assert r.status_code == 503


class TestVehicleLastSeenApi:
    def test_last_seen_online(self, srv):
        client, _, _ = srv
        r = client.get("/api/vehicle/last-seen")
        assert r.status_code == 200
        data = r.json()
        assert data["state"] == "online"

    def test_last_seen_asleep(self, srv_asleep):
        client, _ = srv_asleep
        r = client.get("/api/vehicle/last-seen")
        assert r.status_code == 200
        data = r.json()
        assert data["state"] == "asleep"
