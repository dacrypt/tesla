"""Additional tests for API routes — extends test_api_routes.py coverage.

Covers edge cases, asleep-vehicle error paths, and boundary conditions not
already exercised in the main test_api_routes.py suite.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.app import create_app  # noqa: E402
from tests.conftest import MOCK_VIN  # noqa: E402

# ── Shared mock data ──────────────────────────────────────────────────────────

MOCK_VEHICLE_DATA = {
    "charge_state": {
        "battery_level": 75,
        "battery_range": 200.0,
        "charging_state": "Charging",
        "charge_limit_soc": 80,
        "charger_power": 11,
        "charge_energy_added": 5.0,
        "time_to_full_charge": 1.5,
        "charger_voltage": 240,
        "charger_actual_current": 48,
        "charge_rate": 25.0,
        "charge_port_door_open": True,
    },
    "drive_state": {
        "speed": None,
        "power": 0,
        "shift_state": None,
        "latitude": 6.2442,
        "longitude": -75.5812,
        "heading": 90,
        "gps_as_of": 1700000000,
    },
    "climate_state": {
        "inside_temp": 25.0,
        "outside_temp": 15.0,
        "is_climate_on": True,
        "is_preconditioning": False,
        "driver_temp_setting": 22.0,
        "passenger_temp_setting": 22.0,
    },
    "vehicle_state": {
        "locked": False,
        "sentry_mode": True,
        "sentry_mode_available": True,
        "odometer": 12000.0,
        "car_version": "2025.6.1",
        "software_update": {"status": ""},
    },
}


def _make_cfg(vin: str = MOCK_VIN):
    from tesla_cli.core.config import Config

    cfg = Config()
    cfg.general.default_vin = vin
    cfg.general.backend = "owner"
    cfg.order.reservation_number = "RN987654321"
    cfg.notifications.apprise_urls = []
    cfg.notifications.enabled = False
    cfg.notifications.message_template = "{event}"
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
    m.list_vehicles.return_value = [{"vin": MOCK_VIN, "display_name": "Test Model 3"}]
    m.get_recent_alerts.return_value = {"recent_alerts": []}
    return m


_ROUTE_PATCHES = [
    "tesla_cli.api.routes.vehicle.load_config",
    "tesla_cli.api.routes.vehicle.get_vehicle_backend",
    "tesla_cli.api.routes.vehicle.resolve_vin",
    "tesla_cli.api.routes.charge.load_config",
    "tesla_cli.api.routes.charge.get_vehicle_backend",
    "tesla_cli.api.routes.charge.resolve_vin",
    "tesla_cli.api.routes.climate.load_config",
    "tesla_cli.api.routes.climate.get_vehicle_backend",
    "tesla_cli.api.routes.climate.resolve_vin",
    "tesla_cli.api.routes.security.load_config",
    "tesla_cli.api.routes.security.get_vehicle_backend",
    "tesla_cli.api.routes.security.resolve_vin",
    "tesla_cli.api.routes.notify.load_config",
    "tesla_cli.api.routes.notify.save_config",
    "tesla_cli.api.routes.geofence.load_config",
    "tesla_cli.api.routes.geofence.get_vehicle_backend",
    "tesla_cli.api.routes.geofence.resolve_vin",
    "tesla_cli.api.app.load_config",
    "tesla_cli.api.app.resolve_vin",
]


@pytest.fixture
def srv():
    """Yield (client, backend, cfg) with all route patches active."""
    cfg = _make_cfg()
    backend = _make_backend()
    app = create_app(vin=None)

    patches = []
    for target in _ROUTE_PATCHES:
        if target.endswith("save_config"):
            p = patch(target, return_value=None)
        elif target.endswith("resolve_vin"):
            p = patch(target, return_value=MOCK_VIN)
        elif target.endswith("get_vehicle_backend"):
            p = patch(target, return_value=backend)
        else:
            p = patch(target, return_value=cfg)
        patches.append(p)
        p.start()

    client = TestClient(app, raise_server_exceptions=False)
    yield client, backend, cfg

    for p in patches:
        p.stop()


@pytest.fixture
def srv_asleep():
    """Yield (client, backend) with vehicle in asleep state."""
    from tesla_cli.core.exceptions import VehicleAsleepError

    cfg = _make_cfg()
    backend = MagicMock()
    backend.get_vehicle_data.side_effect = VehicleAsleepError("asleep")
    backend.get_charge_state.side_effect = VehicleAsleepError("asleep")
    backend.get_climate_state.side_effect = VehicleAsleepError("asleep")
    backend.get_drive_state.side_effect = VehicleAsleepError("asleep")
    backend.get_vehicle_state.side_effect = VehicleAsleepError("asleep")
    backend.command.side_effect = VehicleAsleepError("asleep")
    app = create_app(vin=None)

    asleep_patches = [
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
        ("tesla_cli.api.app.load_config", cfg),
    ]
    ps = [patch(t, return_value=rv) for t, rv in asleep_patches]
    for p in ps:
        p.start()
    client = TestClient(app, raise_server_exceptions=False)
    yield client, backend
    for p in ps:
        p.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# Charge Routes — /api/charge/*
# ═══════════════════════════════════════════════════════════════════════════════


class TestChargeRoutes:
    """Additional charge route tests."""

    def test_charge_status_returns_state(self, srv):
        client, backend, _ = srv
        r = client.get("/api/charge/status")
        assert r.status_code == 200
        data = r.json()
        assert data["charging_state"] == "Charging"
        assert data["charger_power"] == 11
        backend.get_charge_state.assert_called_once_with(MOCK_VIN)

    def test_charge_status_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.get("/api/charge/status")
        assert r.status_code == 503

    def test_charge_start_calls_command(self, srv):
        client, backend, _ = srv
        r = client.post("/api/charge/start")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        backend.command.assert_called_with(MOCK_VIN, "charge_start")

    def test_charge_start_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/charge/start")
        assert r.status_code == 503

    def test_charge_stop_calls_command(self, srv):
        client, backend, _ = srv
        r = client.post("/api/charge/stop")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        backend.command.assert_called_with(MOCK_VIN, "charge_stop")

    def test_charge_stop_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/charge/stop")
        assert r.status_code == 503

    def test_set_amps_boundary_low_valid(self, srv):
        client, backend, _ = srv
        r = client.post("/api/charge/amps", json={"amps": 1})
        assert r.status_code == 200
        data = r.json()
        assert data["charging_amps"] == 1
        backend.command.assert_called_with(MOCK_VIN, "set_charging_amps", charging_amps=1)

    def test_set_amps_boundary_high_valid(self, srv):
        client, backend, _ = srv
        r = client.post("/api/charge/amps", json={"amps": 48})
        assert r.status_code == 200
        assert r.json()["charging_amps"] == 48

    def test_set_amps_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/charge/amps", json={"amps": 16})
        assert r.status_code == 503

    def test_set_limit_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/charge/limit", json={"percent": 80})
        assert r.status_code == 503


# ═══════════════════════════════════════════════════════════════════════════════
# Vehicle Routes — /api/vehicle/*
# ═══════════════════════════════════════════════════════════════════════════════


class TestVehicleRoutes:
    """Additional vehicle route tests."""

    def test_vehicle_state_returns_data(self, srv):
        client, backend, _ = srv
        r = client.get("/api/vehicle/state")
        assert r.status_code == 200
        data = r.json()
        assert "charge_state" in data
        assert data["charge_state"]["charging_state"] == "Charging"

    def test_vehicle_wake_returns_ok(self, srv):
        client, backend, _ = srv
        r = client.post("/api/vehicle/wake")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        backend.wake_up.assert_called_once_with(MOCK_VIN)

    def test_vehicle_state_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.get("/api/vehicle/state")
        assert r.status_code == 503

    def test_vehicle_alerts_returns_data(self, srv):
        client, backend, _ = srv
        r = client.get("/api/vehicle/alerts")
        assert r.status_code == 200
        data = r.json()
        assert "recent_alerts" in data
        backend.get_recent_alerts.assert_called_once_with(MOCK_VIN)

    def test_vehicle_ready_unlocked_issue(self, srv):
        """Unlocked vehicle should appear in issues list."""
        client, _, _ = srv
        r = client.get("/api/vehicle/ready")
        assert r.status_code == 200
        data = r.json()
        # MOCK_VEHICLE_DATA has locked=False → issue reported
        assert data["locked"] is False
        assert any("unlock" in i.lower() for i in data["issues"])

    def test_vehicle_status_line_online(self, srv):
        client, _, _ = srv
        r = client.get("/api/vehicle/status-line")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "online"
        assert data["battery_level"] == 75
        assert data["charging_state"] == "Charging"

    def test_vehicle_last_seen_online(self, srv):
        client, _, _ = srv
        r = client.get("/api/vehicle/last-seen")
        assert r.status_code == 200
        assert r.json()["state"] == "online"


# ═══════════════════════════════════════════════════════════════════════════════
# Climate Routes — /api/climate/*
# ═══════════════════════════════════════════════════════════════════════════════


class TestClimateRoutes:
    """Additional climate route tests."""

    def test_climate_status_returns_state(self, srv):
        client, backend, _ = srv
        r = client.get("/api/climate/status")
        assert r.status_code == 200
        data = r.json()
        assert data["inside_temp"] == 25.0
        assert data["is_climate_on"] is True
        backend.get_climate_state.assert_called_once_with(MOCK_VIN)

    def test_climate_status_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.get("/api/climate/status")
        assert r.status_code == 503

    def test_climate_on_calls_command(self, srv):
        client, backend, _ = srv
        r = client.post("/api/climate/on")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["climate"] == "on"
        backend.command.assert_called_with(MOCK_VIN, "auto_conditioning_start")

    def test_climate_on_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/climate/on")
        assert r.status_code == 503

    def test_climate_off_calls_command(self, srv):
        client, backend, _ = srv
        r = client.post("/api/climate/off")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["climate"] == "off"
        backend.command.assert_called_with(MOCK_VIN, "auto_conditioning_stop")

    def test_climate_off_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/climate/off")
        assert r.status_code == 503

    def test_set_temp_boundary_min(self, srv):
        client, backend, _ = srv
        r = client.post("/api/climate/temp", json={"driver_temp": 15.0})
        assert r.status_code == 200
        assert r.json()["driver_temp"] == 15.0

    def test_set_temp_boundary_max(self, srv):
        client, _, _ = srv
        r = client.post("/api/climate/temp", json={"driver_temp": 30.0})
        assert r.status_code == 200

    def test_set_temp_below_min_returns_422(self, srv):
        client, _, _ = srv
        r = client.post("/api/climate/temp", json={"driver_temp": 14.9})
        assert r.status_code == 422

    def test_set_temp_above_max_returns_422(self, srv):
        client, _, _ = srv
        r = client.post("/api/climate/temp", json={"driver_temp": 30.1})
        assert r.status_code == 422

    def test_set_temp_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/climate/temp", json={"driver_temp": 22.0})
        assert r.status_code == 503


# ═══════════════════════════════════════════════════════════════════════════════
# Security Routes — /api/security/*
# ═══════════════════════════════════════════════════════════════════════════════


class TestSecurityRoutes:
    """Additional security route tests."""

    def test_lock_calls_door_lock(self, srv):
        client, backend, _ = srv
        r = client.post("/api/security/lock")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["action"] == "locked"
        backend.command.assert_called_with(MOCK_VIN, "door_lock")

    def test_lock_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/security/lock")
        assert r.status_code == 503

    def test_unlock_calls_door_unlock(self, srv):
        client, backend, _ = srv
        r = client.post("/api/security/unlock")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["action"] == "unlocked"
        backend.command.assert_called_with(MOCK_VIN, "door_unlock")

    def test_unlock_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/security/unlock")
        assert r.status_code == 503

    def test_sentry_status_returns_state(self, srv):
        client, backend, _ = srv
        r = client.get("/api/security/sentry")
        assert r.status_code == 200
        data = r.json()
        # MOCK_VEHICLE_DATA has sentry_mode=True
        assert data["sentry_mode"] is True
        assert data["sentry_mode_available"] is True
        backend.get_vehicle_state.assert_called_once_with(MOCK_VIN)

    def test_sentry_on_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/security/sentry/on")
        assert r.status_code == 503

    def test_sentry_off_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/security/sentry/off")
        assert r.status_code == 503

    def test_horn_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/security/horn")
        assert r.status_code == 503

    def test_flash_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/security/flash")
        assert r.status_code == 503

    def test_frunk_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/security/trunk/front")
        assert r.status_code == 503

    def test_trunk_rear_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/security/trunk/rear")
        assert r.status_code == 503
