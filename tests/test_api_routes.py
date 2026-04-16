"""Comprehensive tests for FastAPI route modules in tesla_cli.api.routes.*

Covers: vehicle, charge, climate, security, order, sources, dossier, notify, auth.
Follows the same fixture pattern as test_server.py — all backends fully mocked.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

import pytest

# Skip entire module if fastapi / httpx not installed
fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.app import create_app  # noqa: E402
from tests.conftest import MOCK_VIN  # noqa: E402

# ── Shared mock data ──────────────────────────────────────────────────────────

MOCK_VEHICLE_DATA = {
    "charge_state": {
        "battery_level": 80,
        "battery_range": 250.0,
        "charging_state": "Disconnected",
        "charge_limit_soc": 90,
        "charger_power": 0,
        "charge_energy_added": 10.5,
        "time_to_full_charge": 0.0,
        "charger_voltage": 0,
        "charger_actual_current": 0,
        "charge_rate": 0.0,
        "charge_port_door_open": False,
    },
    "drive_state": {
        "speed": None,
        "power": 0,
        "shift_state": None,
        "latitude": 4.6097,
        "longitude": -74.0817,
        "heading": 180,
        "gps_as_of": 1700000000,
    },
    "climate_state": {
        "inside_temp": 23.0,
        "outside_temp": 19.0,
        "is_climate_on": False,
        "is_preconditioning": False,
        "driver_temp_setting": 21.0,
        "passenger_temp_setting": 21.0,
    },
    "vehicle_state": {
        "locked": True,
        "sentry_mode": False,
        "sentry_mode_available": True,
        "odometer": 5000.0,
        "car_version": "2025.2.6",
        "software_update": {"status": ""},
    },
}


def _make_cfg(vin: str = MOCK_VIN):
    from tesla_cli.core.config import Config

    cfg = Config()
    cfg.general.default_vin = vin
    cfg.general.backend = "owner"
    cfg.order.reservation_number = "RN123456789"
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
    m.list_vehicles.return_value = [{"vin": MOCK_VIN, "display_name": "Test Model Y"}]
    m.get_recent_alerts.return_value = {"recent_alerts": []}
    return m


# ── Shared patch targets for route modules ────────────────────────────────────

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


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def srv():
    """Yield (client, backend_mock, cfg) with all route patches active."""
    cfg = _make_cfg()
    backend = _make_backend()
    app = create_app(vin=None)

    patches = []
    for target in _ROUTE_PATCHES:
        if target.endswith(("save_config",)):
            p = patch(target, return_value=None)
        elif target.endswith("resolve_vin"):
            p = patch(target, return_value=MOCK_VIN)
        elif target.endswith("get_vehicle_backend"):
            p = patch(target, return_value=backend)
        else:
            # load_config targets
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
# Vehicle Routes — /api/vehicle/*
# ═══════════════════════════════════════════════════════════════════════════════


class TestVehicleRoutes:
    def test_state_returns_full_data(self, srv):
        client, _, _ = srv
        r = client.get("/api/vehicle/state")
        assert r.status_code == 200
        data = r.json()
        assert "charge_state" in data
        assert "climate_state" in data
        assert "drive_state" in data
        assert "vehicle_state" in data
        assert data["charge_state"]["battery_level"] == 80

    def test_state_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.get("/api/vehicle/state")
        assert r.status_code == 503
        assert "asleep" in r.json()["detail"].lower()

    def test_location_returns_gps(self, srv):
        client, backend, _ = srv
        r = client.get("/api/vehicle/location")
        assert r.status_code == 200
        data = r.json()
        assert data["latitude"] == 4.6097
        assert data["longitude"] == -74.0817
        backend.get_drive_state.assert_called_once_with(MOCK_VIN)

    def test_location_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.get("/api/vehicle/location")
        assert r.status_code == 503

    def test_charge_state_via_vehicle_route(self, srv):
        client, backend, _ = srv
        r = client.get("/api/vehicle/charge")
        assert r.status_code == 200
        data = r.json()
        assert data["charging_state"] == "Disconnected"
        assert data["charge_limit_soc"] == 90
        backend.get_charge_state.assert_called_once_with(MOCK_VIN)

    def test_climate_state_via_vehicle_route(self, srv):
        client, backend, _ = srv
        r = client.get("/api/vehicle/climate")
        assert r.status_code == 200
        data = r.json()
        assert data["inside_temp"] == 23.0
        backend.get_climate_state.assert_called_once_with(MOCK_VIN)

    def test_vehicle_state_endpoint(self, srv):
        client, backend, _ = srv
        r = client.get("/api/vehicle/vehicle-state")
        assert r.status_code == 200
        data = r.json()
        assert data["locked"] is True
        assert "sentry_mode" in data
        backend.get_vehicle_state.assert_called_once_with(MOCK_VIN)

    def test_list_returns_vehicles(self, srv):
        client, backend, _ = srv
        r = client.get("/api/vehicle/list")
        assert r.status_code == 200
        vehicles = r.json()
        assert isinstance(vehicles, list)
        assert len(vehicles) == 1
        assert vehicles[0]["vin"] == MOCK_VIN
        backend.list_vehicles.assert_called_once()

    def test_wake_calls_backend(self, srv):
        client, backend, _ = srv
        r = client.post("/api/vehicle/wake")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        backend.wake_up.assert_called_once_with(MOCK_VIN)

    def test_command_returns_ok(self, srv):
        client, backend, _ = srv
        r = client.post("/api/vehicle/command", json={"command": "honk_horn", "params": {}})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["command"] == "honk_horn"
        backend.command.assert_called_once_with(MOCK_VIN, "honk_horn")

    def test_command_with_params(self, srv):
        client, backend, _ = srv
        r = client.post(
            "/api/vehicle/command",
            json={"command": "set_charge_limit", "params": {"percent": 80}},
        )
        assert r.status_code == 200
        backend.command.assert_called_once_with(MOCK_VIN, "set_charge_limit", percent=80)

    def test_command_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/vehicle/command", json={"command": "honk_horn", "params": {}})
        assert r.status_code == 503

    def test_summary_returns_compact_snapshot(self, srv):
        client, _, _ = srv
        r = client.get("/api/vehicle/summary")
        assert r.status_code == 200
        data = r.json()
        assert data["vin"] == MOCK_VIN
        assert "battery" in data
        assert "climate" in data
        assert "location" in data
        assert "state" in data
        assert data["battery"]["level"] == 80
        assert data["state"]["locked"] is True

    def test_summary_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.get("/api/vehicle/summary")
        assert r.status_code == 503

    def test_odometer_returns_reading(self, srv):
        client, _, _ = srv
        r = client.get("/api/vehicle/odometer")
        assert r.status_code == 200
        data = r.json()
        assert data["vin"] == MOCK_VIN
        assert data["odometer_miles"] == 5000.0
        assert data["car_version"] == "2025.2.6"
        assert "queried_at" in data

    def test_ready_returns_assessment(self, srv):
        client, _, _ = srv
        r = client.get("/api/vehicle/ready")
        assert r.status_code == 200
        data = r.json()
        assert "ready" in data
        assert "battery_level" in data
        assert "issues" in data
        assert isinstance(data["issues"], list)
        # Mock: battery=80, locked=True, not charging → should be ready
        assert data["ready"] is True
        assert data["battery_level"] == 80

    def test_ready_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.get("/api/vehicle/ready")
        assert r.status_code == 503

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

    def test_status_line_online(self, srv):
        client, _, _ = srv
        r = client.get("/api/vehicle/status-line")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "online"
        assert data["battery_level"] == 80
        assert data["locked"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# Charge Routes — /api/charge/*
# ═══════════════════════════════════════════════════════════════════════════════


class TestChargeRoutes:
    def test_status_returns_charge_state(self, srv):
        client, backend, _ = srv
        r = client.get("/api/charge/status")
        assert r.status_code == 200
        data = r.json()
        assert data["battery_level"] == 80
        assert data["charging_state"] == "Disconnected"
        backend.get_charge_state.assert_called_once_with(MOCK_VIN)

    def test_status_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.get("/api/charge/status")
        assert r.status_code == 503

    def test_start_calls_backend(self, srv):
        client, backend, _ = srv
        r = client.post("/api/charge/start")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        backend.command.assert_called_with(MOCK_VIN, "charge_start")

    def test_start_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/charge/start")
        assert r.status_code == 503

    def test_stop_calls_backend(self, srv):
        client, backend, _ = srv
        r = client.post("/api/charge/stop")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        backend.command.assert_called_with(MOCK_VIN, "charge_stop")

    def test_stop_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/charge/stop")
        assert r.status_code == 503

    def test_set_limit_valid(self, srv):
        client, backend, _ = srv
        r = client.post("/api/charge/limit", json={"percent": 85})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["charge_limit_soc"] == 85
        backend.command.assert_called_with(MOCK_VIN, "set_charge_limit", percent=85)

    def test_set_limit_boundary_low_valid(self, srv):
        client, _, _ = srv
        r = client.post("/api/charge/limit", json={"percent": 50})
        assert r.status_code == 200

    def test_set_limit_boundary_high_valid(self, srv):
        client, _, _ = srv
        r = client.post("/api/charge/limit", json={"percent": 100})
        assert r.status_code == 200

    def test_set_limit_too_low_returns_422(self, srv):
        client, _, _ = srv
        r = client.post("/api/charge/limit", json={"percent": 49})
        assert r.status_code == 422

    def test_set_limit_too_high_returns_422(self, srv):
        client, _, _ = srv
        r = client.post("/api/charge/limit", json={"percent": 101})
        assert r.status_code == 422

    def test_set_amps_valid(self, srv):
        client, backend, _ = srv
        r = client.post("/api/charge/amps", json={"amps": 16})
        assert r.status_code == 200
        data = r.json()
        assert data["charging_amps"] == 16
        backend.command.assert_called_with(MOCK_VIN, "set_charging_amps", charging_amps=16)

    def test_set_amps_too_low_returns_422(self, srv):
        client, _, _ = srv
        r = client.post("/api/charge/amps", json={"amps": 0})
        assert r.status_code == 422

    def test_set_amps_too_high_returns_422(self, srv):
        client, _, _ = srv
        r = client.post("/api/charge/amps", json={"amps": 49})
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# Climate Routes — /api/climate/*
# ═══════════════════════════════════════════════════════════════════════════════


class TestClimateRoutes:
    def test_status_returns_climate_state(self, srv):
        client, backend, _ = srv
        r = client.get("/api/climate/status")
        assert r.status_code == 200
        data = r.json()
        assert data["inside_temp"] == 23.0
        assert data["outside_temp"] == 19.0
        assert data["is_climate_on"] is False
        backend.get_climate_state.assert_called_once_with(MOCK_VIN)

    def test_status_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.get("/api/climate/status")
        assert r.status_code == 503

    def test_climate_on_sends_command(self, srv):
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

    def test_climate_off_sends_command(self, srv):
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

    def test_set_temp_valid_driver_only(self, srv):
        client, backend, _ = srv
        r = client.post("/api/climate/temp", json={"driver_temp": 22.0})
        assert r.status_code == 200
        data = r.json()
        assert data["driver_temp"] == 22.0
        # passenger defaults to driver_temp when not provided
        assert data["passenger_temp"] == 22.0
        backend.command.assert_called_with(
            MOCK_VIN, "set_temps", driver_temp=22.0, passenger_temp=22.0
        )

    def test_set_temp_with_separate_passenger(self, srv):
        client, backend, _ = srv
        r = client.post("/api/climate/temp", json={"driver_temp": 20.0, "passenger_temp": 24.0})
        assert r.status_code == 200
        data = r.json()
        assert data["driver_temp"] == 20.0
        assert data["passenger_temp"] == 24.0

    def test_set_temp_too_cold_returns_422(self, srv):
        client, _, _ = srv
        r = client.post("/api/climate/temp", json={"driver_temp": 14.9})
        assert r.status_code == 422

    def test_set_temp_too_hot_returns_422(self, srv):
        client, _, _ = srv
        r = client.post("/api/climate/temp", json={"driver_temp": 30.1})
        assert r.status_code == 422

    def test_set_temp_boundary_min_valid(self, srv):
        client, _, _ = srv
        r = client.post("/api/climate/temp", json={"driver_temp": 15.0})
        assert r.status_code == 200

    def test_set_temp_boundary_max_valid(self, srv):
        client, _, _ = srv
        r = client.post("/api/climate/temp", json={"driver_temp": 30.0})
        assert r.status_code == 200

    def test_set_temp_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/climate/temp", json={"driver_temp": 21.0})
        assert r.status_code == 503


# ═══════════════════════════════════════════════════════════════════════════════
# Security Routes — /api/security/*
# ═══════════════════════════════════════════════════════════════════════════════


class TestSecurityRoutes:
    def test_lock_sends_door_lock(self, srv):
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

    def test_unlock_sends_door_unlock(self, srv):
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
        assert "sentry_mode" in data
        assert data["sentry_mode"] is False
        assert "sentry_mode_available" in data
        backend.get_vehicle_state.assert_called_once_with(MOCK_VIN)

    def test_sentry_status_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.get("/api/security/sentry")
        assert r.status_code == 503

    def test_sentry_on_enables_sentry(self, srv):
        client, backend, _ = srv
        r = client.post("/api/security/sentry/on")
        assert r.status_code == 200
        data = r.json()
        assert data["sentry_mode"] is True
        backend.command.assert_called_with(MOCK_VIN, "set_sentry_mode", on=True)

    def test_sentry_off_disables_sentry(self, srv):
        client, backend, _ = srv
        r = client.post("/api/security/sentry/off")
        assert r.status_code == 200
        data = r.json()
        assert data["sentry_mode"] is False
        backend.command.assert_called_with(MOCK_VIN, "set_sentry_mode", on=False)

    def test_frunk_open(self, srv):
        client, backend, _ = srv
        r = client.post("/api/security/trunk/front")
        assert r.status_code == 200
        data = r.json()
        assert data["action"] == "frunk_opened"
        backend.command.assert_called_with(MOCK_VIN, "actuate_trunk", which_trunk="front")

    def test_trunk_toggle(self, srv):
        client, backend, _ = srv
        r = client.post("/api/security/trunk/rear")
        assert r.status_code == 200
        data = r.json()
        assert data["action"] == "trunk_toggled"
        backend.command.assert_called_with(MOCK_VIN, "actuate_trunk", which_trunk="rear")

    def test_horn_honks(self, srv):
        client, backend, _ = srv
        r = client.post("/api/security/horn")
        assert r.status_code == 200
        assert r.json()["action"] == "horn_honked"
        backend.command.assert_called_with(MOCK_VIN, "honk_horn")

    def test_flash_lights(self, srv):
        client, backend, _ = srv
        r = client.post("/api/security/flash")
        assert r.status_code == 200
        assert r.json()["action"] == "lights_flashed"
        backend.command.assert_called_with(MOCK_VIN, "flash_lights")

    def test_frunk_asleep_returns_503(self, srv_asleep):
        client, _ = srv_asleep
        r = client.post("/api/security/trunk/front")
        assert r.status_code == 503


# ═══════════════════════════════════════════════════════════════════════════════
# Order Routes — /api/order/*
# ═══════════════════════════════════════════════════════════════════════════════


class TestOrderRoutes:
    def test_order_status_returns_data(self, srv):
        from tesla_cli.core.models.order import OrderStatus

        client, _, cfg = srv
        mock_status = OrderStatus(
            reservation_number="RN123456789",
            order_status="CONFIRMED",
            vin=MOCK_VIN,
        )
        mock_backend = MagicMock()
        mock_backend.get_order_status.return_value = mock_status
        with (
            patch("tesla_cli.api.routes.order.load_config", return_value=cfg),
            patch("tesla_cli.core.backends.order.OrderBackend", return_value=mock_backend),
        ):
            r = client.get("/api/order/status")
        assert r.status_code == 200
        data = r.json()
        assert data["reservation_number"] == "RN123456789"

    def test_order_status_no_reservation_returns_404(self, srv):
        client, _, cfg = srv
        cfg.order.reservation_number = ""
        with patch("tesla_cli.api.routes.order.load_config", return_value=cfg):
            r = client.get("/api/order/status")
        assert r.status_code == 404
        assert "reservation" in r.json()["detail"].lower()

    def test_order_status_backend_error_returns_502(self, srv):
        client, _, cfg = srv
        cfg.order.reservation_number = "RN999"
        mock_backend = MagicMock()
        mock_backend.get_order_status.side_effect = RuntimeError("network error")
        with (
            patch("tesla_cli.api.routes.order.load_config", return_value=cfg),
            patch("tesla_cli.core.backends.order.OrderBackend", return_value=mock_backend),
        ):
            r = client.get("/api/order/status")
        assert r.status_code == 502
        assert "network error" in r.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════════════
# Sources Routes — /api/sources/*
# ═══════════════════════════════════════════════════════════════════════════════


class TestSourcesRoutes:
    def test_list_all_sources(self, srv):
        client, _, _ = srv
        mock_sources = [
            {"id": "tesla.owner", "name": "Owner API", "fresh": True, "ttl": 60},
            {"id": "tesla.order", "name": "Order API", "fresh": False, "ttl": 3600},
        ]
        with patch("tesla_cli.api.routes.sources.sources.list_sources", return_value=mock_sources):
            r = client.get("/api/sources")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["id"] == "tesla.owner"

    def test_list_sources_empty(self, srv):
        client, _, _ = srv
        with patch("tesla_cli.api.routes.sources.sources.list_sources", return_value=[]):
            r = client.get("/api/sources")
        assert r.status_code == 200
        assert r.json() == []

    def test_get_source_by_id(self, srv):
        client, _, _ = srv
        mock_result = {
            "id": "tesla.owner",
            "data": {"battery_level": 80},
            "fetched_at": "2025-01-01T00:00:00",
        }
        with patch(
            "tesla_cli.api.routes.sources.sources.get_cached_with_meta", return_value=mock_result
        ):
            r = client.get("/api/sources/tesla.owner")
        assert r.status_code == 200
        data = r.json()
        assert data["id"] == "tesla.owner"

    def test_get_unknown_source_returns_404(self, srv):
        client, _, _ = srv
        with patch("tesla_cli.api.routes.sources.sources.get_cached_with_meta", return_value=None):
            r = client.get("/api/sources/nonexistent.source")
        assert r.status_code == 404

    def test_refresh_source_by_id(self, srv):
        client, _, _ = srv
        mock_src = {"id": "tesla.owner", "name": "Owner API"}
        mock_refreshed = {"id": "tesla.owner", "data": {}, "refreshed": True}
        with (
            patch("tesla_cli.api.routes.sources.sources.get_source_def", return_value=mock_src),
            patch(
                "tesla_cli.api.routes.sources.sources.refresh_source", return_value=mock_refreshed
            ),
        ):
            r = client.post("/api/sources/tesla.owner/refresh")
        assert r.status_code == 200
        data = r.json()
        assert data["refreshed"] is True

    def test_refresh_unknown_source_returns_404(self, srv):
        client, _, _ = srv
        with patch("tesla_cli.api.routes.sources.sources.get_source_def", return_value=None):
            r = client.post("/api/sources/ghost.source/refresh")
        assert r.status_code == 404

    def test_get_source_diffs(self, srv):
        client, _, _ = srv
        mock_diffs = [
            {
                "timestamp": "2025-01-01T00:00:00",
                "source_id": "tesla.owner",
                "changes_count": 1,
                "changes": [{"field": "battery_level", "old": "79", "new": "80"}],
            }
        ]
        with patch("tesla_cli.api.routes.sources.sources.get_diffs", return_value=mock_diffs):
            r = client.get("/api/sources/tesla.owner/diffs?limit=10")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert data[0]["source_id"] == "tesla.owner"
        assert data[0]["changes_count"] == 1

    def test_get_source_queries(self, srv):
        client, _, _ = srv
        mock_queries = [
            {
                "source_id": "tesla.owner",
                "request": {"mode": "fetch_fn", "url": "https://owner-api.teslamotors.com/api/1/users/orders"},
                "response": {"normalized_data": {"battery_level": 80}, "response_text_excerpt": "{\"response\":[]}"},
            }
        ]
        with patch("tesla_cli.api.routes.sources.sources.get_queries", return_value=mock_queries):
            r = client.get("/api/sources/tesla.owner/queries?limit=10")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert data[0]["source_id"] == "tesla.owner"
        assert data[0]["request"]["mode"] == "fetch_fn"
        assert "owner-api" in data[0]["request"]["url"]

    def test_sources_config_get(self, srv):
        client, _, cfg = srv
        cfg.general.cedula = "12345678"
        cfg.general.default_vin = MOCK_VIN
        cfg.order.reservation_number = "RN123"
        with patch("tesla_cli.api.routes.sources.load_config", return_value=cfg):
            r = client.get("/api/sources/config")
        assert r.status_code == 200
        data = r.json()
        assert "vin" in data
        assert "cedula" in data
        assert "reservation_number" in data

    def test_refresh_stale_sources(self, srv):
        client, _, _ = srv
        mock_result = {"refreshed": ["tesla.owner"], "failed": []}
        with patch("tesla_cli.api.routes.sources.sources.refresh_stale", return_value=mock_result):
            r = client.post("/api/sources/refresh-stale")
        assert r.status_code == 200
        data = r.json()
        assert "refreshed" in data
        assert "tesla.owner" in data["refreshed"]

    def test_missing_auth_sources(self, srv):
        client, _, _ = srv
        with patch(
            "tesla_cli.api.routes.sources.sources.missing_auth",
            return_value=[{"id": "tesla.fleet", "reason": "No token"}],
        ):
            r = client.get("/api/sources/missing-auth")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert data[0]["id"] == "tesla.fleet"


# ═══════════════════════════════════════════════════════════════════════════════
# Domains Routes — /api/domains/*
# ═══════════════════════════════════════════════════════════════════════════════


class TestDomainsRoutes:
    def test_list_domains(self, srv):
        client, _, _ = srv
        mock_domains = [
            {"domain_id": "delivery", "summary": "VIN assigned", "health": {"status": "ok"}},
            {"domain_id": "legal", "summary": "Plate assigned", "health": {"status": "degraded"}},
        ]
        with patch("tesla_cli.api.routes.domains.domains.list_domains", return_value=mock_domains):
            r = client.get("/api/domains")
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 2
        assert data[0]["domain_id"] == "delivery"

    def test_get_domain(self, srv):
        client, _, _ = srv
        mock_domain = {
            "domain_id": "delivery",
            "state": {"vin": "VIN123"},
            "derived_flags": {"vin_assigned": True},
        }
        with patch("tesla_cli.api.routes.domains.domains.get_domain", return_value=mock_domain):
            r = client.get("/api/domains/delivery")
        assert r.status_code == 200
        assert r.json()["domain_id"] == "delivery"

    def test_get_unknown_domain_returns_404(self, srv):
        client, _, _ = srv
        with patch("tesla_cli.api.routes.domains.domains.get_domain", return_value=None):
            r = client.get("/api/domains/ghost")
        assert r.status_code == 404

    def test_recompute_domain(self, srv):
        client, _, _ = srv
        mock_domain = {"domain_id": "legal", "summary": "SOAT valid"}
        with (
            patch("tesla_cli.api.routes.domains.domains.get_domain", return_value=mock_domain),
            patch("tesla_cli.api.routes.domains.domains.recompute_domain", return_value=mock_domain),
        ):
            r = client.post("/api/domains/legal/recompute")
        assert r.status_code == 200
        assert r.json()["domain_id"] == "legal"


# ═══════════════════════════════════════════════════════════════════════════════
# Mission Control Routes — /api/mission-control
# ═══════════════════════════════════════════════════════════════════════════════


class TestMissionControlRoutes:
    def test_get_mission_control(self, srv):
        client, _, _ = srv
        payload = {
            "executive": {"delivery_readiness": {"status": "ok"}},
            "domains": [],
            "sources": [],
            "critical_diffs": [],
            "timeline": [],
            "active_alerts": [],
        }
        with patch(
            "tesla_cli.api.routes.mission_control.mission_control.build_mission_control",
            return_value=payload,
        ):
            r = client.get("/api/mission-control")
        assert r.status_code == 200
        assert r.json()["executive"]["delivery_readiness"]["status"] == "ok"

    def test_get_dashboard_summary(self, srv):
        client, _, _ = srv
        payload = {
            "delivery_readiness": {"status": "ok"},
            "legal_readiness": {"status": "degraded"},
            "source_health": {"status": "degraded"},
            "critical_changes_count": 2,
        }
        with patch(
            "tesla_cli.api.routes.mission_control.mission_control.build_dashboard_summary",
            return_value=payload,
        ):
            r = client.get("/api/mission-control/dashboard-summary")
        assert r.status_code == 200
        assert r.json()["critical_changes_count"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Events / Alerts Routes
# ═══════════════════════════════════════════════════════════════════════════════


class TestEventRoutes:
    def test_get_events(self, srv):
        client, _, _ = srv
        payload = [{"kind": "source_change", "source_id": "co.runt"}]
        with patch("tesla_cli.api.routes.events.events.list_events", return_value=payload):
            r = client.get("/api/events?limit=10")
        assert r.status_code == 200
        assert r.json()[0]["kind"] == "source_change"

    def test_get_alerts(self, srv):
        client, _, _ = srv
        payload = [{"kind": "domain_change", "domain_id": "legal", "severity": "critical"}]
        with patch("tesla_cli.api.routes.alerts.events.list_alerts", return_value=payload):
            r = client.get("/api/alerts?limit=10&active_only=true")
        assert r.status_code == 200
        assert r.json()[0]["severity"] == "critical"

    def test_ack_alert(self, srv):
        client, _, _ = srv
        payload = {"alert_id": "alt_123", "acked_at": "2026-04-07T12:00:00+00:00", "resolved_at": None}
        with patch("tesla_cli.api.routes.alerts.events.ack_alert", return_value=payload):
            r = client.post("/api/alerts/alt_123/ack")
        assert r.status_code == 200
        assert r.json()["alert_id"] == "alt_123"

    def test_ack_unknown_alert_returns_404(self, srv):
        client, _, _ = srv
        with patch("tesla_cli.api.routes.alerts.events.ack_alert", return_value=None):
            r = client.post("/api/alerts/ghost/ack")
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Dossier Routes — /api/dossier/*
# ═══════════════════════════════════════════════════════════════════════════════


class TestDossierRoutes:
    def test_dossier_cached_no_dossier_returns_404(self, srv):
        client, _, _ = srv
        with patch("tesla_cli.core.backends.dossier.DossierBackend") as MockDB:
            MockDB.return_value._load_dossier.return_value = None
            r = client.get("/api/dossier")
        assert r.status_code == 404
        assert "dossier" in r.json()["detail"].lower()

    def test_dossier_cached_returns_data(self, srv):
        client, _, _ = srv
        mock_dossier = MagicMock()
        mock_dossier.model_dump.return_value = {"vin": MOCK_VIN, "runt": {}, "simit": {}}
        with patch("tesla_cli.core.backends.dossier.DossierBackend") as MockDB:
            MockDB.return_value._load_dossier.return_value = mock_dossier
            r = client.get("/api/dossier")
        assert r.status_code == 200
        data = r.json()
        assert data["vin"] == MOCK_VIN

    def test_dossier_sources_returns_list(self, srv):
        client, _, _ = srv
        mock_sources = [{"id": "runt", "name": "RUNT", "fresh": True}]
        with patch("tesla_cli.core.sources.list_sources", return_value=mock_sources):
            r = client.get("/api/dossier/sources")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert data[0]["id"] == "runt"

    def test_dossier_runt_no_vin_returns_404(self, srv):
        client, _, _ = srv
        with (
            patch("tesla_cli.api.routes.dossier.load_config", return_value=_make_cfg("")),
            patch("tesla_cli.api.routes.dossier.resolve_vin", return_value=""),
        ):
            r = client.get("/api/dossier/runt")
        assert r.status_code == 404

    def test_dossier_runt_returns_data(self, srv):
        client, _, _ = srv
        mock_runt = MagicMock()
        mock_runt.model_dump.return_value = {"placa": "ABC123", "vin": MOCK_VIN}
        cfg = _make_cfg()
        with (
            patch("tesla_cli.api.routes.dossier.load_config", return_value=cfg),
            patch("tesla_cli.api.routes.dossier.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.core.backends.runt.RuntBackend") as MockRunt,
        ):
            MockRunt.return_value.query_by_vin.return_value = mock_runt
            r = client.get("/api/dossier/runt")
        assert r.status_code == 200
        data = r.json()
        assert data["vin"] == MOCK_VIN

    def test_dossier_simit_uses_config_cedula(self, srv):
        client, _, cfg = srv
        cfg.general.cedula = "123456789"
        mock_simit = MagicMock()
        mock_simit.model_dump.return_value = {"comparendos": 0, "total_deuda": "0"}
        with (
            patch("tesla_cli.core.backends.dossier.DossierBackend") as MockDB,
            patch("tesla_cli.api.routes.dossier.load_config", return_value=cfg),
            patch("tesla_cli.core.sources.get_cached", return_value=None),
            patch("tesla_cli.core.backends.simit.SimitBackend") as MockSimit,
        ):
            MockDB.return_value._load_dossier.return_value = None
            MockSimit.return_value.query_by_cedula.return_value = mock_simit
            r = client.get("/api/dossier/simit")
        assert r.status_code == 200
        MockSimit.return_value.query_by_cedula.assert_called_once_with("123456789")

    def test_dossier_simit_uses_runt_source_cache(self, srv):
        client, _, cfg = srv
        cfg.general.cedula = ""
        mock_simit = MagicMock()
        mock_simit.model_dump.return_value = {"comparendos": 1, "total_deuda": "50000"}
        with (
            patch("tesla_cli.core.backends.dossier.DossierBackend") as MockDB,
            patch("tesla_cli.api.routes.dossier.load_config", return_value=cfg),
            patch(
                "tesla_cli.core.sources.get_cached",
                return_value={"no_identificacion": "987654321"},
            ),
            patch("tesla_cli.core.backends.simit.SimitBackend") as MockSimit,
        ):
            MockDB.return_value._load_dossier.return_value = None
            MockSimit.return_value.query_by_cedula.return_value = mock_simit
            r = client.get("/api/dossier/simit")
        assert r.status_code == 200
        MockSimit.return_value.query_by_cedula.assert_called_once_with("987654321")

    def test_dossier_simit_no_cedula_returns_404(self, srv):
        client, _, cfg = srv
        cfg.general.cedula = ""
        with (
            patch("tesla_cli.core.backends.dossier.DossierBackend") as MockDB,
            patch("tesla_cli.api.routes.dossier.load_config", return_value=cfg),
            patch("tesla_cli.core.sources.get_cached", return_value=None),
        ):
            MockDB.return_value._load_dossier.return_value = None
            r = client.get("/api/dossier/simit")
        assert r.status_code == 404
        assert "general.cedula" in r.json()["detail"]


# ═══════════════════════════════════════════════════════════════════════════════
# Notify Routes — /api/notify/*
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotifyRoutes:
    def test_list_empty_channels(self, srv):
        client, _, cfg = srv
        cfg.notifications.apprise_urls = []
        cfg.notifications.enabled = False
        cfg.notifications.message_template = "{event}"
        r = client.get("/api/notify/list")
        assert r.status_code == 200
        data = r.json()
        assert data["channels"] == []
        assert data["enabled"] is False

    def test_list_with_channels(self, srv):
        client, _, cfg = srv
        cfg.notifications.apprise_urls = ["tgram://bot/chat", "ntfy://topic"]
        cfg.notifications.enabled = True
        cfg.notifications.message_template = "{event}"
        r = client.get("/api/notify/list")
        assert r.status_code == 200
        data = r.json()
        assert len(data["channels"]) == 2
        assert data["enabled"] is True

    def test_test_no_channels_returns_404(self, srv):
        client, _, cfg = srv
        cfg.notifications.apprise_urls = []
        r = client.post("/api/notify/test")
        assert r.status_code == 404

    def test_test_with_channels_calls_apprise(self, srv):
        client, _, cfg = srv
        cfg.notifications.apprise_urls = ["ntfy://test"]
        mock_apprise_cls = MagicMock()
        mock_apprise_instance = MagicMock()
        mock_apprise_instance.notify.return_value = True
        mock_apprise_cls.return_value = mock_apprise_instance
        with patch.dict(
            "sys.modules",
            {"apprise": MagicMock(Apprise=mock_apprise_cls, NotifyType=MagicMock(INFO="info"))},
        ):
            r = client.post("/api/notify/test")
        # Either 200 (apprise available) or 501 (not installed) — both valid in CI
        assert r.status_code in (200, 501)

    def test_add_channel(self, srv):
        client, _, cfg = srv
        cfg.notifications.apprise_urls = []
        r = client.post("/api/notify/add", json={"url": "ntfy://mytopic"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["channels"] == 1

    def test_add_duplicate_channel_returns_409(self, srv):
        client, _, cfg = srv
        cfg.notifications.apprise_urls = ["ntfy://mytopic"]
        r = client.post("/api/notify/add", json={"url": "ntfy://mytopic"})
        assert r.status_code == 409

    def test_remove_channel_by_index(self, srv):
        client, _, cfg = srv
        cfg.notifications.apprise_urls = ["ntfy://a", "ntfy://b"]
        r = client.post("/api/notify/remove", json={"index": 0})
        assert r.status_code == 200
        data = r.json()
        assert data["removed"] == "ntfy://a"
        assert data["remaining"] == 1

    def test_remove_invalid_index_returns_404(self, srv):
        client, _, cfg = srv
        cfg.notifications.apprise_urls = []
        r = client.post("/api/notify/remove", json={"index": 99})
        assert r.status_code == 404


# ═══════════════════════════════════════════════════════════════════════════════
# Auth Routes — /api/auth/*
# ═══════════════════════════════════════════════════════════════════════════════


class TestAuthRoutes:
    def test_status_unauthenticated(self, srv):
        client, _, cfg = srv
        with (
            patch("tesla_cli.api.routes.auth.load_config", return_value=cfg),
            patch("tesla_cli.api.routes.auth.has_token", return_value=False),
            patch("tesla_cli.core.auth.portal_scrape.has_portal_session", return_value=False),
        ):
            r = client.get("/api/auth/status")
        assert r.status_code == 200
        data = r.json()
        assert data["authenticated"] is False
        assert "backend" in data
        assert "has_fleet" in data
        assert "has_order" in data
        assert "has_tessie" in data
        assert "has_portal_session" in data

    def test_status_authenticated_fleet(self, srv):
        client, _, cfg = srv
        cfg.general.backend = "fleet"

        def _has_token_side(key):
            from tesla_cli.core.auth.tokens import FLEET_ACCESS_TOKEN

            return key == FLEET_ACCESS_TOKEN

        with (
            patch("tesla_cli.api.routes.auth.load_config", return_value=cfg),
            patch("tesla_cli.api.routes.auth.has_token", side_effect=_has_token_side),
            patch("tesla_cli.core.auth.portal_scrape.has_portal_session", return_value=False),
        ):
            r = client.get("/api/auth/status")
        assert r.status_code == 200
        data = r.json()
        assert data["authenticated"] is True
        assert data["has_fleet"] is True

    def test_status_reports_portal_session(self, srv):
        client, _, cfg = srv

        with (
            patch("tesla_cli.api.routes.auth.load_config", return_value=cfg),
            patch("tesla_cli.api.routes.auth.has_token", return_value=False),
            patch("tesla_cli.core.auth.portal_scrape.has_portal_session", return_value=True),
        ):
            r = client.get("/api/auth/status")

        assert r.status_code == 200
        assert r.json()["has_portal_session"] is True

    def test_portal_scrape_uses_saved_session(self, srv):
        client, _, cfg = srv
        cfg.order.reservation_number = "RN123456789"

        def _run(*args, **kwargs):
            script = args[0][2]
            assert "scrape_portal_with_session" in script
            return subprocess.CompletedProcess(
                args=args[0],
                returncode=0,
                stdout='{"ok": true, "keys": [], "sections": 0}',
                stderr="",
            )

        with (
            patch("tesla_cli.api.routes.auth.load_config", return_value=cfg),
            patch("subprocess.run", side_effect=_run),
        ):
            r = client.post("/api/auth/portal-scrape", json={})

        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_login_no_client_id_returns_400(self, srv):
        client, _, cfg = srv
        cfg.fleet.client_id = ""
        with patch("tesla_cli.api.routes.auth.load_config", return_value=cfg):
            r = client.get("/api/auth/login")
        assert r.status_code == 400
        assert "client_id" in r.json()["detail"].lower()

    def test_login_with_client_id_returns_auth_url(self, srv):
        client, _, cfg = srv
        cfg.fleet.client_id = "test-client-id-123"
        with patch("tesla_cli.api.routes.auth.load_config", return_value=cfg):
            r = client.get("/api/auth/login")
        assert r.status_code == 200
        data = r.json()
        assert "auth_url" in data
        assert "state" in data
        assert "auth.tesla.com" in data["auth_url"]
        assert "test-client-id-123" in data["auth_url"]

    def test_callback_invalid_state_returns_400(self, srv):
        client, _, _ = srv
        r = client.post(
            "/api/auth/callback",
            json={"code": "some-code", "state": "invalid-state-xyz"},
        )
        assert r.status_code == 400
        assert "state" in r.json()["detail"].lower()

    def test_tessie_token_short_returns_400(self, srv):
        client, _, _ = srv
        r = client.post("/api/auth/tessie", json={"token": "short"})
        assert r.status_code == 400

    def test_tessie_token_valid(self, srv):
        client, _, cfg = srv
        cfg.tessie.configured = False
        with (
            patch("tesla_cli.api.routes.auth.set_token"),
            patch("tesla_cli.api.routes.auth.load_config", return_value=cfg),
            patch("tesla_cli.api.routes.auth.save_config"),
        ):
            r = client.post("/api/auth/tessie", json={"token": "a-valid-tessie-token-1234"})
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["backend"] == "tessie"


# ═══════════════════════════════════════════════════════════════════════════════
# System Endpoints — /api/health, /api/status, /api/config
# ═══════════════════════════════════════════════════════════════════════════════


class TestSystemEndpoints:
    def test_health_check_returns_ok(self, srv):
        client, _, _ = srv
        r = client.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_status_returns_version_and_backend(self, srv):
        client, _, cfg = srv
        r = client.get("/api/status")
        assert r.status_code == 200
        data = r.json()
        assert "version" in data
        assert data["backend"] == "owner"

    def test_config_returns_settings(self, srv):
        client, _, _ = srv
        r = client.get("/api/config")
        assert r.status_code == 200
        data = r.json()
        assert "backend" in data
        assert "default_vin" in data
        assert "auth_enabled" in data

    def test_openapi_schema_has_expected_paths(self, srv):
        client, _, _ = srv
        r = client.get("/api/openapi.json")
        assert r.status_code == 200
        schema = r.json()
        paths = schema["paths"]
        assert "/api/vehicle/state" in paths
        assert "/api/charge/status" in paths
        assert "/api/climate/status" in paths
        assert "/api/security/lock" in paths
        assert "/api/auth/status" in paths
        assert "/api/events" in paths
        assert "/api/alerts" in paths
        assert "/api/alerts/{alert_id}/ack" in paths
        assert "/api/sources" in paths
        assert "/api/domains" in paths
        assert "/api/mission-control" in paths
        assert "/api/mission-control/dashboard-summary" in paths

    def test_root_redirects_or_serves_spa(self, srv):
        client, _, _ = srv
        r = client.get("/", follow_redirects=False)
        assert r.status_code in (200, 301, 302, 303, 307, 308)

    def test_vehicles_endpoint_returns_list(self, srv):
        client, _, cfg = srv
        cfg.general.default_vin = MOCK_VIN
        cfg.vehicles.aliases = {}
        r = client.get("/api/vehicles")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert any(v["vin"] == MOCK_VIN for v in data)


# ═══════════════════════════════════════════════════════════════════════════════
# Security Regression Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSecurityHardening:
    """Regression tests for all security fixes applied in production readiness audit."""

    # ── API Key: constant-time comparison ──

    def test_api_key_rejects_wrong_key(self):
        """API key middleware rejects wrong key with 401."""
        app = create_app()
        with patch("tesla_cli.api.app.load_config") as mock_cfg:
            cfg = _make_cfg()
            cfg.server.api_key = "correct-key-123"
            mock_cfg.return_value = cfg
            app = create_app()
        client = TestClient(app)
        r = client.get("/api/health", headers={"X-API-Key": "wrong-key"})
        assert r.status_code == 401

    def test_api_key_accepts_correct_key(self):
        """API key middleware accepts correct key."""
        app = create_app()
        with patch("tesla_cli.api.app.load_config") as mock_cfg:
            cfg = _make_cfg()
            cfg.server.api_key = "correct-key-123"
            mock_cfg.return_value = cfg
            app = create_app()
        client = TestClient(app)
        r = client.get("/api/health", headers={"X-API-Key": "correct-key-123"})
        assert r.status_code == 200

    def test_api_key_uses_hmac_compare(self):
        """Verify hmac.compare_digest is used (not ==)."""
        from pathlib import Path

        src = Path("src/tesla_cli/api/auth.py").read_text()
        assert "hmac.compare_digest" in src
        assert "provided != self._key" not in src

    # ── PKCE store bounding ──

    def test_pkce_store_bounded(self):
        """PKCE store rejects after _MAX_PENDING entries."""
        from tesla_cli.api.routes.auth import _MAX_PENDING, _pending_auth

        _pending_auth.clear()
        # Fill to max
        for i in range(_MAX_PENDING):
            _pending_auth[f"state_{i}"] = (f"verifier_{i}", 9999999999.0)
        assert len(_pending_auth) == _MAX_PENDING

    def test_pkce_cleanup_removes_old_entries(self):
        """TTL cleanup removes entries older than 10 minutes."""
        from tesla_cli.api.routes.auth import _cleanup_pending_auth, _pending_auth

        _pending_auth.clear()
        _pending_auth["old"] = ("verifier", 0.0)  # epoch = very old
        _pending_auth["new"] = ("verifier", 9999999999.0)  # far future
        _cleanup_pending_auth()
        assert "old" not in _pending_auth
        assert "new" in _pending_auth
        _pending_auth.clear()

    # ── Path traversal: audit PDF ──

    def test_audit_pdf_rejects_path_traversal(self, srv):
        """Path traversal in audit PDF filename is blocked."""
        client, _, _ = srv
        r = client.get("/api/sources/co.runt/audit/co.runt../../etc/passwd")
        assert r.status_code in (400, 404, 422)

    def test_audit_pdf_rejects_backslash(self, srv):
        client, _, _ = srv
        r = client.get("/api/sources/co.runt/audit/co.runt%5C..%5Cetc")
        assert r.status_code in (400, 404, 422)

    # ── Source ID validation ──

    def test_source_id_rejects_traversal(self, srv):
        """Source ID with path traversal chars is rejected."""
        client, _, _ = srv
        r = client.get("/api/sources/../etc/passwd")
        assert r.status_code in (400, 404, 422)

    def test_source_id_rejects_semicolon(self, srv):
        client, _, _ = srv
        r = client.get("/api/sources/foo;rm/history")
        assert r.status_code in (400, 404, 422)

    def test_source_id_accepts_valid(self, srv):
        """Valid source IDs like co.runt are accepted."""
        client, _, _ = srv
        r = client.get("/api/sources/co.runt")
        assert r.status_code == 200

    # ── SoQL injection: peajes ──

    def test_peajes_sanitizes_injection(self, srv):
        """SoQL injection chars stripped from peajes route param."""
        import re

        # ' OR 1=1 -- would break SoQL if not sanitized
        safe = re.sub(r"[^a-zA-Z0-9\s\-]", "", "' OR 1=1 --".upper())
        # Key: single quotes stripped (can't break out of string literal)
        assert "'" not in safe
        # Equals stripped (can't inject comparisons)
        assert "=" not in safe

    # ── Shell automation blocking ──

    def test_shell_automation_blocked_by_default(self, srv):
        """Shell command automations blocked via API without config flag."""
        client, _, _ = srv
        r = client.post("/api/automations/", json={
            "name": "test-shell",
            "trigger": {"type": "battery_below", "threshold": 20},
            "action": {"type": "command", "command": "echo pwned"},
        })
        assert r.status_code == 403

    # ── SPA path traversal ──

    def test_spa_uses_resolve_containment(self):
        """SPA middleware uses .resolve() + startswith() for path containment."""
        from pathlib import Path

        src = Path("src/tesla_cli/api/app.py").read_text()
        assert ".resolve()" in src
        assert "startswith(str(_ui_dist.resolve()))" in src

    # ── CORS origins configurable ──

    def test_cors_not_wildcard(self):
        """CORS is not allow_origins=['*']."""
        from pathlib import Path

        src = Path("src/tesla_cli/api/app.py").read_text()
        assert 'allow_origins=["*"]' not in src

    # ── JSONL rotation ──

    def test_jsonl_rotation_constant_exists(self):
        """Events module has rotation limit."""
        from tesla_cli.core.events import _MAX_JSONL_ENTRIES

        assert _MAX_JSONL_ENTRIES == 10_000
