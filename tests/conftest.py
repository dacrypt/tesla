"""Shared fixtures for tesla-cli tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tesla_cli.backends.fleet import FleetBackend

MOCK_VIN = "5YJ3E1EA1PF000001"

MOCK_VEHICLE_DATA = {
    "vin": MOCK_VIN,
    "display_name": "Test Tesla",
    "vehicle_name": "Test Tesla",
    "state": "online",
    "charge_state": {
        "battery_level": 72,
        "battery_range": 220.5,
        "charging_state": "Disconnected",
        "charge_limit_soc": 80,
        "charge_rate": 0.0,
        "charger_voltage": 0,
        "charger_actual_current": 0,
        "charge_amps": 16,
        "charger_power": 0,
        "time_to_full_charge": 0.0,
        "charge_port_door_open": False,
        "charge_port_latch": "Engaged",
        "scheduled_charging_pending": False,
        "scheduled_charging_start_time": "",
    },
    "climate_state": {
        "inside_temp": 22.5,
        "outside_temp": 18.0,
        "driver_temp_setting": 21.0,
        "passenger_temp_setting": 21.0,
        "is_climate_on": False,
        "is_preconditioning": False,
        "fan_status": 0,
        "seat_heater_left": 0,
        "seat_heater_right": 0,
        "seat_heater_rear_left": 0,
        "seat_heater_rear_center": 0,
        "seat_heater_rear_right": 0,
        "steering_wheel_heater": False,
        "is_front_defroster_on": False,
        "is_rear_defroster_on": False,
    },
    "drive_state": {
        "latitude": 4.6097,
        "longitude": -74.0817,
        "heading": 180,
        "speed": None,
        "power": 0,
        "shift_state": None,
    },
    "vehicle_state": {
        "locked": True,
        "sentry_mode": False,
        "valet_mode": False,
        "car_version": "2025.2.6",
        "odometer": 150.5,
    },
    "vehicle_config": {
        "car_type": "modely",
    },
}

MOCK_COMMAND_OK = {"result": True, "reason": ""}


@pytest.fixture
def mock_config():
    """Patch load_config and resolve_vin to return test defaults."""
    with (
        patch("tesla_cli.config.load_config") as mock_load,
        patch("tesla_cli.config.resolve_vin", return_value=MOCK_VIN),
    ):
        cfg = MagicMock()
        cfg.general.backend = "fleet"
        cfg.general.default_vin = MOCK_VIN
        cfg.fleet.region = "na"
        mock_load.return_value = cfg
        yield cfg


@pytest.fixture
def mock_fleet_backend():
    """Return a mocked FleetBackend with common responses."""
    backend = MagicMock(spec=FleetBackend)
    backend.get_vehicle_data.return_value = MOCK_VEHICLE_DATA
    backend.get_charge_state.return_value = MOCK_VEHICLE_DATA["charge_state"]
    backend.get_climate_state.return_value = MOCK_VEHICLE_DATA["climate_state"]
    backend.get_drive_state.return_value = MOCK_VEHICLE_DATA["drive_state"]
    backend.get_vehicle_state.return_value = MOCK_VEHICLE_DATA["vehicle_state"]
    backend.get_vehicle_config.return_value = MOCK_VEHICLE_DATA["vehicle_config"]
    backend.get_nearby_charging_sites.return_value = {"superchargers": [], "destination_charging": []}
    backend.get_release_notes.return_value = {"release_notes": []}
    backend.get_recent_alerts.return_value = {"recent_alerts": []}
    backend.get_charge_history.return_value = []
    backend.get_invitations.return_value = []
    backend.list_vehicles.return_value = [MOCK_VEHICLE_DATA]
    backend.command.return_value = MOCK_COMMAND_OK
    backend.create_invitation.return_value = {"id": "inv-123", "state": "pending"}
    backend.revoke_invitation.return_value = {"result": True}
    backend.wake_up.return_value = True
    return backend
