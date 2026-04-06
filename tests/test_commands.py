"""Tests for all CLI command groups and FleetBackend methods."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tesla_cli.cli.app import app
from tesla_cli.core.backends.fleet import FleetBackend
from tests.conftest import MOCK_VIN, run_cli

runner = CliRunner()

# All modules that import get_vehicle_backend / load_config / resolve_vin
_BACKEND_MODULES = [
    "tesla_cli.core.backends",
    "tesla_cli.cli.commands.vehicle",
    "tesla_cli.cli.commands.charge",
]

_CONFIG_MODULES = [
    "tesla_cli.core.config",
    "tesla_cli.cli.commands.vehicle",
    "tesla_cli.cli.commands.charge",
    "tesla_cli.cli.commands.climate",
    "tesla_cli.cli.commands.security",
    "tesla_cli.cli.commands.media",
]


@pytest.fixture
def _patched_env(mock_fleet_backend):
    """Patch all backend/config references across command modules."""
    cfg = MagicMock()
    cfg.general.backend = "fleet"
    cfg.general.default_vin = MOCK_VIN
    cfg.general.cost_per_kwh = 0.0
    cfg.fleet.region = "na"

    patches = []
    for mod in _BACKEND_MODULES:
        p = patch(f"{mod}.get_vehicle_backend", return_value=mock_fleet_backend)
        patches.append(p)
    for mod in _CONFIG_MODULES:
        p = patch(f"{mod}.load_config", return_value=cfg)
        patches.append(p)
    for mod in _CONFIG_MODULES:
        try:
            p = patch(f"{mod}.resolve_vin", return_value=MOCK_VIN)
            patches.append(p)
        except AttributeError:
            pass

    for p in patches:
        p.start()
    yield mock_fleet_backend
    for p in patches:
        p.stop()


def _run(args: list[str]):
    return run_cli(*args)


# ── Command Registration Tests ──────────────────────────────────────


class TestCommandRegistration:
    def test_help_shows_all_groups(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for group in [
            "vehicle",
            "charge",
            "climate",
            "security",
            "media",
            "order",
            "data",
            "notify",
            "serve",
        ]:
            assert group in result.output, f"Missing command group: {group}"

    def test_charge_subcommands(self):
        result = runner.invoke(app, ["charge", "--help"])
        assert result.exit_code == 0
        for sub in [
            "status",
            "start",
            "stop",
            "limit",
            "amps",
            "port-open",
            "port-close",
            "schedule",
            "history",
        ]:
            assert sub in result.output, f"Missing charge subcommand: {sub}"

    def test_climate_subcommands(self):
        result = runner.invoke(app, ["climate", "--help"])
        assert result.exit_code == 0
        for sub in [
            "on",
            "off",
            "temp",
            "seat-heater",
            "steering-heater",
            "dog-mode",
            "camp-mode",
            "bioweapon",
            "defrost",
        ]:
            assert sub in result.output, f"Missing climate subcommand: {sub}"

    def test_security_subcommands(self):
        result = runner.invoke(app, ["security", "--help"])
        assert result.exit_code == 0
        for sub in [
            "lock",
            "unlock",
            "sentry",
            "valet",
            "speed-limit",
            "pin-to-drive",
            "guest-mode",
        ]:
            assert sub in result.output, f"Missing security subcommand: {sub}"

    def test_media_subcommands(self):
        result = runner.invoke(app, ["media", "--help"])
        assert result.exit_code == 0
        for sub in ["play", "pause", "next", "prev", "volume", "fav"]:
            assert sub in result.output, f"Missing media subcommand: {sub}"

    def test_media_includes_nav(self):
        result = runner.invoke(app, ["media", "--help"])
        assert result.exit_code == 0
        for sub in ["send-destination", "supercharger", "home", "work"]:
            assert sub in result.output, f"Missing media nav subcommand: {sub}"

    def test_vehicle_includes_dashboard_stream_sharing(self):
        result = runner.invoke(app, ["vehicle", "--help"])
        assert result.exit_code == 0
        for sub in ["vehicle", "dashboard", "stream", "invite", "invitations"]:
            assert sub in result.output, f"Missing vehicle subcommand: {sub}"

    def test_data_group_registered(self):
        result = runner.invoke(app, ["data", "--help"])
        assert result.exit_code == 0


# ── FleetBackend Method Tests ───────────────────────────────────────


class TestFleetBackendMethods:
    def test_data_methods_exist(self):
        methods = [
            "list_vehicles",
            "get_vehicle_data",
            "get_charge_state",
            "get_climate_state",
            "get_drive_state",
            "get_vehicle_state",
            "get_vehicle_config",
            "get_nearby_charging_sites",
            "get_release_notes",
            "get_service_data",
            "get_recent_alerts",
            "get_charge_history",
            "get_fleet_status",
            "mobile_enabled",
        ]
        for m in methods:
            assert hasattr(FleetBackend, m), f"FleetBackend missing method: {m}"

    def test_command_methods_exist(self):
        methods = [
            "command",
            "door_lock",
            "door_unlock",
            "charge_start",
            "charge_stop",
            "set_charge_limit",
            "set_charging_amps",
            "charge_port_door_open",
            "charge_port_door_close",
            "set_scheduled_charging",
            "set_scheduled_departure",
            "auto_conditioning_start",
            "auto_conditioning_stop",
            "set_temps",
            "remote_seat_heater_request",
            "remote_steering_wheel_heater_request",
            "set_bioweapon_mode",
            "set_climate_keeper_mode",
            "set_cabin_overheat_protection",
            "window_control",
            "actuate_trunk",
            "honk_horn",
            "flash_lights",
            "set_sentry_mode",
            "set_valet_mode",
            "reset_valet_pin",
            "speed_limit_activate",
            "speed_limit_deactivate",
            "speed_limit_set_limit",
            "speed_limit_clear_pin",
            "set_pin_to_drive",
            "guest_mode",
            "remote_start_drive",
            "share",
            "navigation_sc_request",
            "navigation_gps_request",
            "media_toggle_playback",
            "media_next_track",
            "media_prev_track",
            "media_next_fav",
            "media_prev_fav",
            "media_volume_up",
            "media_volume_down",
            "adjust_volume",
            "schedule_software_update",
            "cancel_software_update",
            "trigger_homelink",
            "remote_boombox",
            "set_preconditioning_max",
            "wake_up",
        ]
        for m in methods:
            assert hasattr(FleetBackend, m), f"FleetBackend missing method: {m}"

    def test_sharing_methods_exist(self):
        methods = ["get_invitations", "create_invitation", "revoke_invitation"]
        for m in methods:
            assert hasattr(FleetBackend, m), f"FleetBackend missing method: {m}"


# ── CLI Execution Tests ─────────────────────────────────────────────


@pytest.mark.usefixtures("_patched_env")
class TestChargeCommands:
    def test_charge_status(self):
        result = _run(["charge", "status"])
        assert result.exit_code == 0

    def test_charge_start(self):
        result = _run(["charge", "start"])
        assert result.exit_code == 0

    def test_charge_stop(self):
        result = _run(["charge", "stop"])
        assert result.exit_code == 0

    def test_charge_limit(self):
        result = _run(["charge", "limit", "80"])
        assert result.exit_code == 0
        assert "80" in result.output

    def test_charge_amps(self):
        result = _run(["charge", "amps", "32"])
        assert result.exit_code == 0

    def test_charge_port_open(self):
        result = _run(["charge", "port-open"])
        assert result.exit_code == 0

    def test_charge_port_close(self):
        result = _run(["charge", "port-close"])
        assert result.exit_code == 0

    def test_charge_history(self):
        result = _run(["charge", "history"])
        assert result.exit_code == 0


@pytest.mark.usefixtures("_patched_env")
class TestClimateCommands:
    def test_climate_on(self):
        result = _run(["climate", "on"])
        assert result.exit_code == 0

    def test_climate_off(self):
        result = _run(["climate", "off"])
        assert result.exit_code == 0

    def test_climate_temp(self):
        result = _run(["climate", "temp", "22"])
        assert result.exit_code == 0

    def test_climate_seat_heater(self):
        result = _run(["climate", "seat-heater", "0", "3"])
        assert result.exit_code == 0

    def test_climate_dog_mode(self):
        result = _run(["climate", "dog-mode", "true"])
        assert result.exit_code == 0

    def test_climate_camp_mode(self):
        result = _run(["climate", "camp-mode", "true"])
        assert result.exit_code == 0

    def test_climate_bioweapon(self):
        result = _run(["climate", "bioweapon", "true"])
        assert result.exit_code == 0

    def test_climate_defrost(self):
        result = _run(["climate", "defrost", "true"])
        assert result.exit_code == 0


@pytest.mark.usefixtures("_patched_env")
class TestSecurityCommands:
    def test_security_lock(self):
        result = _run(["security", "lock"])
        assert result.exit_code == 0

    def test_security_unlock(self):
        result = _run(["security", "unlock"])
        assert result.exit_code == 0

    def test_security_sentry(self):
        result = _run(["security", "sentry", "true"])
        assert result.exit_code == 0

    def test_security_valet(self):
        result = _run(["security", "valet", "true"])
        assert result.exit_code == 0

    def test_security_guest_mode(self):
        result = _run(["security", "guest-mode", "true"])
        assert result.exit_code == 0


@pytest.mark.usefixtures("_patched_env")
class TestMediaCommands:
    def test_media_play(self):
        result = _run(["media", "play"])
        assert result.exit_code == 0

    def test_media_next(self):
        result = _run(["media", "next"])
        assert result.exit_code == 0

    def test_media_prev(self):
        result = _run(["media", "prev"])
        assert result.exit_code == 0

    def test_media_volume_up(self):
        result = _run(["media", "volume"])
        assert result.exit_code == 0

    def test_media_volume_set(self):
        result = _run(["media", "volume", "5.0"])
        assert result.exit_code == 0

    def test_media_fav(self):
        result = _run(["media", "fav"])
        assert result.exit_code == 0


@pytest.mark.usefixtures("_patched_env")
class TestNavCommands:
    def test_media_send_destination(self):
        result = _run(["media", "send-destination", "Times Square, NYC"])
        assert result.exit_code == 0

    def test_media_supercharger(self):
        result = _run(["media", "supercharger"])
        assert result.exit_code == 0

    def test_media_home(self):
        result = _run(["media", "home"])
        assert result.exit_code == 0

    def test_media_work(self):
        result = _run(["media", "work"])
        assert result.exit_code == 0


@pytest.mark.usefixtures("_patched_env")
class TestSharingCommands:
    def test_vehicle_invite(self):
        result = _run(["vehicle", "invite"])
        assert result.exit_code == 0

    def test_vehicle_invitations(self):
        result = _run(["vehicle", "invitations"])
        assert result.exit_code == 0

    def test_vehicle_revoke_invite(self):
        result = _run(["vehicle", "revoke-invite", "inv-123"])
        assert result.exit_code == 0


@pytest.mark.usefixtures("_patched_env")
class TestDashboard:
    def test_vehicle_dashboard(self):
        result = _run(["vehicle", "dashboard"])
        assert result.exit_code == 0

    def test_vehicle_dashboard_json(self):
        result = _run(["--json", "vehicle", "dashboard"])
        assert result.exit_code == 0


@pytest.mark.usefixtures("_patched_env")
class TestJsonOutput:
    def test_charge_status_json(self):
        result = _run(["--json", "charge", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "battery_level" in data

    def test_charge_start_json(self):
        result = _run(["--json", "charge", "start"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"


@pytest.mark.usefixtures("_patched_env")
class TestExistingVehicleCommands:
    def test_vehicle_list(self):
        result = _run(["vehicle", "list"])
        assert result.exit_code == 0

    def test_vehicle_horn(self):
        result = _run(["vehicle", "horn"])
        assert result.exit_code == 0

    def test_vehicle_flash(self):
        result = _run(["vehicle", "flash"])
        assert result.exit_code == 0

    def test_vehicle_lock(self):
        result = _run(["vehicle", "lock"])
        assert result.exit_code == 0

    def test_vehicle_trunk(self):
        result = _run(["vehicle", "trunk", "rear"])
        assert result.exit_code == 0


# ── v2.1.0: charge limit enhanced ────────────────────────────────────────────


@pytest.mark.usefixtures("_patched_env")
class TestChargeLimitEnhanced:
    """charge limit: show-state, validation, JSON."""

    def test_charge_limit_no_arg_shows_current(self):
        result = _run(["charge", "limit"])
        assert result.exit_code == 0
        assert "80" in result.output  # fixture charge_limit_soc = 80

    def test_charge_limit_no_arg_json(self):
        result = _run(["--json", "charge", "limit"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["charge_limit_soc"] == 80

    def test_charge_limit_set_valid(self, _patched_env):
        result = _run(["charge", "limit", "90"])
        assert result.exit_code == 0
        _patched_env.command.assert_called_with(MOCK_VIN, "set_charge_limit", percent=90)

    def test_charge_limit_set_json(self):
        result = _run(["--json", "charge", "limit", "75"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["charge_limit_soc"] == 75
        assert data["status"] == "ok"

    def test_charge_limit_validation_too_low(self):
        result = _run(["charge", "limit", "49"])
        assert result.exit_code != 0

    def test_charge_limit_validation_too_high(self):
        result = _run(["charge", "limit", "101"])
        assert result.exit_code != 0

    def test_charge_limit_boundary_50(self):
        result = _run(["charge", "limit", "50"])
        assert result.exit_code == 0

    def test_charge_limit_boundary_100(self):
        result = _run(["charge", "limit", "100"])
        assert result.exit_code == 0


# ── v2.1.0: charge amps enhanced ─────────────────────────────────────────────


@pytest.mark.usefixtures("_patched_env")
class TestChargeAmpsEnhanced:
    """charge amps: show-state, validation, JSON."""

    def test_charge_amps_no_arg_shows_current(self):
        result = _run(["charge", "amps"])
        assert result.exit_code == 0
        assert "16" in result.output  # fixture charge_amps = 16

    def test_charge_amps_no_arg_json(self):
        result = _run(["--json", "charge", "amps"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "charge_amps" in data

    def test_charge_amps_set_valid(self, _patched_env):
        result = _run(["charge", "amps", "32"])
        assert result.exit_code == 0
        _patched_env.command.assert_called_with(MOCK_VIN, "set_charging_amps", charging_amps=32)

    def test_charge_amps_set_json(self):
        result = _run(["--json", "charge", "amps", "16"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["charge_amps"] == 16
        assert data["status"] == "ok"

    def test_charge_amps_validation_too_low(self):
        result = _run(["charge", "amps", "0"])
        assert result.exit_code != 0

    def test_charge_amps_validation_too_high(self):
        result = _run(["charge", "amps", "49"])
        assert result.exit_code != 0

    def test_charge_amps_boundary_1(self):
        result = _run(["charge", "amps", "1"])
        assert result.exit_code == 0

    def test_charge_amps_boundary_48(self):
        result = _run(["charge", "amps", "48"])
        assert result.exit_code == 0


# ── v2.1.0: climate temp enhanced ────────────────────────────────────────────


@pytest.mark.usefixtures("_patched_env")
class TestClimateTempEnhanced:
    """climate temp: show-state, --passenger option, validation, JSON."""

    def test_climate_temp_no_arg_shows_current(self):
        result = _run(["climate", "temp"])
        assert result.exit_code == 0
        assert "21.0" in result.output  # fixture driver_temp_setting

    def test_climate_temp_no_arg_json(self):
        result = _run(["--json", "climate", "temp"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "driver_temp_setting" in data
        assert "passenger_temp_setting" in data

    def test_climate_temp_set_driver_only(self, _patched_env):
        result = _run(["climate", "temp", "22.0"])
        assert result.exit_code == 0
        _patched_env.command.assert_called_with(
            MOCK_VIN, "set_temps", driver_temp=22.0, passenger_temp=22.0
        )

    def test_climate_temp_set_with_passenger(self, _patched_env):
        result = _run(["climate", "temp", "22.0", "--passenger", "20.0"])
        assert result.exit_code == 0
        _patched_env.command.assert_called_with(
            MOCK_VIN, "set_temps", driver_temp=22.0, passenger_temp=20.0
        )

    def test_climate_temp_set_json(self):
        result = _run(["--json", "climate", "temp", "23.0"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["driver_temp"] == 23.0
        assert data["status"] == "ok"

    def test_climate_temp_validation_too_low(self):
        result = _run(["climate", "temp", "14.9"])
        assert result.exit_code != 0

    def test_climate_temp_validation_too_high(self):
        result = _run(["climate", "temp", "30.1"])
        assert result.exit_code != 0

    def test_climate_temp_boundary_15(self):
        result = _run(["climate", "temp", "15.0"])
        assert result.exit_code == 0

    def test_climate_temp_boundary_30(self):
        result = _run(["climate", "temp", "30.0"])
        assert result.exit_code == 0


# ── v2.1.0: climate seat (named positions) ───────────────────────────────────


@pytest.mark.usefixtures("_patched_env")
class TestClimateSeatNamed:
    """climate seat: named positions, show-all, validation, JSON."""

    def test_seat_no_arg_shows_all(self):
        result = _run(["climate", "seat"])
        assert result.exit_code == 0

    def test_seat_no_arg_json(self):
        result = _run(["--json", "climate", "seat"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "driver" in data
        assert "passenger" in data
        assert "rear-left" in data
        assert "rear-center" in data
        assert "rear-right" in data

    def test_seat_driver_set(self, _patched_env):
        result = _run(["climate", "seat", "driver", "2"])
        assert result.exit_code == 0
        _patched_env.command.assert_called_with(
            MOCK_VIN, "remote_seat_heater_request", heater=0, level=2
        )

    def test_seat_passenger_set(self, _patched_env):
        result = _run(["climate", "seat", "passenger", "1"])
        assert result.exit_code == 0
        _patched_env.command.assert_called_with(
            MOCK_VIN, "remote_seat_heater_request", heater=1, level=1
        )

    def test_seat_rear_left_set(self, _patched_env):
        result = _run(["climate", "seat", "rear-left", "1"])
        assert result.exit_code == 0
        _patched_env.command.assert_called_with(
            MOCK_VIN, "remote_seat_heater_request", heater=2, level=1
        )

    def test_seat_rear_center_set(self, _patched_env):
        result = _run(["climate", "seat", "rear-center", "0"])
        assert result.exit_code == 0
        _patched_env.command.assert_called_with(
            MOCK_VIN, "remote_seat_heater_request", heater=4, level=0
        )

    def test_seat_rear_right_set(self, _patched_env):
        result = _run(["climate", "seat", "rear-right", "3"])
        assert result.exit_code == 0
        _patched_env.command.assert_called_with(
            MOCK_VIN, "remote_seat_heater_request", heater=5, level=3
        )

    def test_seat_json_output(self):
        result = _run(["--json", "climate", "seat", "passenger", "3"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["seat"] == "passenger"
        assert data["heater_id"] == 1
        assert data["level"] == 3
        assert data["status"] == "ok"

    def test_seat_invalid_position(self):
        result = _run(["climate", "seat", "middle", "1"])
        assert result.exit_code != 0

    def test_seat_invalid_level(self):
        result = _run(["climate", "seat", "driver", "4"])
        assert result.exit_code != 0

    def test_seat_position_without_level(self):
        result = _run(["climate", "seat", "driver"])
        assert result.exit_code != 0

    def test_seat_in_help(self):
        result = _run(["climate", "--help"])
        assert "seat" in result.output


# ── v2.1.0: climate steering-wheel ───────────────────────────────────────────


@pytest.mark.usefixtures("_patched_env")
class TestClimateSteeringWheel:
    """climate steering-wheel: show state, --on/--off, JSON."""

    def test_steering_wheel_no_arg_shows_state(self):
        result = _run(["climate", "steering-wheel"])
        assert result.exit_code == 0

    def test_steering_wheel_no_arg_json(self):
        result = _run(["--json", "climate", "steering-wheel"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "steering_wheel_heater" in data
        assert data["steering_wheel_heater"] is False  # fixture default

    def test_steering_wheel_on(self, _patched_env):
        result = _run(["climate", "steering-wheel", "--on"])
        assert result.exit_code == 0
        _patched_env.command.assert_called_with(
            MOCK_VIN, "remote_steering_wheel_heater_request", on=True
        )

    def test_steering_wheel_off(self, _patched_env):
        result = _run(["climate", "steering-wheel", "--off"])
        assert result.exit_code == 0
        _patched_env.command.assert_called_with(
            MOCK_VIN, "remote_steering_wheel_heater_request", on=False
        )

    def test_steering_wheel_on_json(self):
        result = _run(["--json", "climate", "steering-wheel", "--on"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["steering_wheel_heater"] is True
        assert data["status"] == "ok"

    def test_steering_wheel_off_json(self):
        result = _run(["--json", "climate", "steering-wheel", "--off"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["steering_wheel_heater"] is False
        assert data["status"] == "ok"

    def test_steering_wheel_in_help(self):
        result = _run(["climate", "--help"])
        assert "steering-wheel" in result.output


# ── v2.1.0: media volume validation + JSON ───────────────────────────────────


@pytest.mark.usefixtures("_patched_env")
class TestMediaVolumeValidation:
    """media volume: validation + JSON mode via render_success."""

    def test_media_volume_validation_too_high(self):
        result = _run(["media", "volume", "12.0"])
        assert result.exit_code != 0

    def test_media_volume_validation_negative(self):
        result = _run(["media", "volume", "-1.0"])
        assert result.exit_code != 0

    def test_media_volume_boundary_0(self):
        result = _run(["media", "volume", "0.0"])
        assert result.exit_code == 0

    def test_media_volume_boundary_11(self):
        result = _run(["media", "volume", "11.0"])
        assert result.exit_code == 0

    def test_media_play_json(self):
        result = _run(["--json", "media", "play"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    def test_media_next_json(self):
        result = _run(["--json", "media", "next"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    def test_media_prev_json(self):
        result = _run(["--json", "media", "prev"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    def test_media_volume_set_json(self):
        result = _run(["--json", "media", "volume", "5.0"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"


# ── v2.1.0: nav send JSON ─────────────────────────────────────────────────────


@pytest.mark.usefixtures("_patched_env")
class TestNavSendJson:
    """nav send: JSON mode via render_success + address passthrough."""

    def test_nav_send_json(self):
        result = _run(["--json", "media", "send-destination", "1600 Pennsylvania Ave NW"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    def test_nav_send_passes_address(self, _patched_env):
        result = _run(["media", "send-destination", "Times Square"])
        assert result.exit_code == 0
        call_args = _patched_env.command.call_args
        assert call_args[0][1] == "share"
        assert call_args[1]["value"]["android.intent.extra.TEXT"] == "Times Square"
