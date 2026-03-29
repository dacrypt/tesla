"""Tests for all CLI command groups and FleetBackend methods."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tesla_cli.app import app
from tesla_cli.backends.fleet import FleetBackend
from tests.conftest import MOCK_VIN

runner = CliRunner()

# All modules that import get_vehicle_backend / load_config / resolve_vin
_BACKEND_MODULES = [
    "tesla_cli.backends",
    "tesla_cli.commands.vehicle",
    "tesla_cli.commands.charge",
    "tesla_cli.commands.sharing",
]

_CONFIG_MODULES = [
    "tesla_cli.config",
    "tesla_cli.commands.vehicle",
    "tesla_cli.commands.charge",
    "tesla_cli.commands.climate",
    "tesla_cli.commands.security",
    "tesla_cli.commands.media",
    "tesla_cli.commands.nav",
    "tesla_cli.commands.sharing",
    "tesla_cli.commands.dashboard",
]


@pytest.fixture
def _patched_env(mock_fleet_backend):
    """Patch all backend/config references across command modules."""
    cfg = MagicMock()
    cfg.general.backend = "fleet"
    cfg.general.default_vin = MOCK_VIN
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
    return runner.invoke(app, args)


# ── Command Registration Tests ──────────────────────────────────────


class TestCommandRegistration:
    def test_help_shows_all_groups(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for group in ["vehicle", "charge", "climate", "security", "media", "nav", "sharing", "dashboard", "order", "dossier"]:
            assert group in result.output, f"Missing command group: {group}"

    def test_charge_subcommands(self):
        result = runner.invoke(app, ["charge", "--help"])
        assert result.exit_code == 0
        for sub in ["status", "start", "stop", "limit", "amps", "port-open", "port-close", "schedule", "history"]:
            assert sub in result.output, f"Missing charge subcommand: {sub}"

    def test_climate_subcommands(self):
        result = runner.invoke(app, ["climate", "--help"])
        assert result.exit_code == 0
        for sub in ["on", "off", "temp", "seat-heater", "steering-heater", "dog-mode", "camp-mode", "bioweapon", "defrost"]:
            assert sub in result.output, f"Missing climate subcommand: {sub}"

    def test_security_subcommands(self):
        result = runner.invoke(app, ["security", "--help"])
        assert result.exit_code == 0
        for sub in ["lock", "unlock", "sentry", "valet", "speed-limit", "pin-to-drive", "guest-mode"]:
            assert sub in result.output, f"Missing security subcommand: {sub}"

    def test_media_subcommands(self):
        result = runner.invoke(app, ["media", "--help"])
        assert result.exit_code == 0
        for sub in ["play", "pause", "next", "prev", "volume", "fav"]:
            assert sub in result.output, f"Missing media subcommand: {sub}"

    def test_nav_subcommands(self):
        result = runner.invoke(app, ["nav", "--help"])
        assert result.exit_code == 0
        for sub in ["send", "supercharger", "home", "work"]:
            assert sub in result.output, f"Missing nav subcommand: {sub}"

    def test_sharing_subcommands(self):
        result = runner.invoke(app, ["sharing", "--help"])
        assert result.exit_code == 0
        for sub in ["invite", "list", "revoke"]:
            assert sub in result.output, f"Missing sharing subcommand: {sub}"

    def test_dashboard_subcommands(self):
        result = runner.invoke(app, ["dashboard", "--help"])
        assert result.exit_code == 0


# ── FleetBackend Method Tests ───────────────────────────────────────


class TestFleetBackendMethods:
    def test_data_methods_exist(self):
        methods = [
            "list_vehicles", "get_vehicle_data", "get_charge_state",
            "get_climate_state", "get_drive_state", "get_vehicle_state",
            "get_vehicle_config", "get_nearby_charging_sites",
            "get_release_notes", "get_service_data", "get_recent_alerts",
            "get_charge_history", "get_fleet_status", "mobile_enabled",
        ]
        for m in methods:
            assert hasattr(FleetBackend, m), f"FleetBackend missing method: {m}"

    def test_command_methods_exist(self):
        methods = [
            "command", "door_lock", "door_unlock",
            "charge_start", "charge_stop", "set_charge_limit", "set_charging_amps",
            "charge_port_door_open", "charge_port_door_close",
            "set_scheduled_charging", "set_scheduled_departure",
            "auto_conditioning_start", "auto_conditioning_stop",
            "set_temps", "remote_seat_heater_request",
            "remote_steering_wheel_heater_request",
            "set_bioweapon_mode", "set_climate_keeper_mode",
            "set_cabin_overheat_protection", "window_control",
            "actuate_trunk", "honk_horn", "flash_lights",
            "set_sentry_mode", "set_valet_mode", "reset_valet_pin",
            "speed_limit_activate", "speed_limit_deactivate",
            "speed_limit_set_limit", "speed_limit_clear_pin",
            "set_pin_to_drive", "guest_mode", "remote_start_drive",
            "share", "navigation_sc_request", "navigation_gps_request",
            "media_toggle_playback", "media_next_track", "media_prev_track",
            "media_next_fav", "media_prev_fav",
            "media_volume_up", "media_volume_down", "adjust_volume",
            "schedule_software_update", "cancel_software_update",
            "trigger_homelink", "remote_boombox",
            "set_preconditioning_max", "wake_up",
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
    def test_nav_send(self):
        result = _run(["nav", "send", "Times Square, NYC"])
        assert result.exit_code == 0

    def test_nav_supercharger(self):
        result = _run(["nav", "supercharger"])
        assert result.exit_code == 0

    def test_nav_home(self):
        result = _run(["nav", "home"])
        assert result.exit_code == 0

    def test_nav_work(self):
        result = _run(["nav", "work"])
        assert result.exit_code == 0


@pytest.mark.usefixtures("_patched_env")
class TestSharingCommands:
    def test_sharing_invite(self):
        result = _run(["sharing", "invite"])
        assert result.exit_code == 0

    def test_sharing_list(self):
        result = _run(["sharing", "list"])
        assert result.exit_code == 0

    def test_sharing_revoke(self):
        result = _run(["sharing", "revoke", "inv-123"])
        assert result.exit_code == 0


@pytest.mark.usefixtures("_patched_env")
class TestDashboard:
    def test_dashboard_show(self):
        result = _run(["dashboard", "show"])
        assert result.exit_code == 0

    def test_dashboard_json(self):
        result = _run(["--json", "dashboard", "show"])
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
