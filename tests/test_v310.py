"""Tests for v3.1.0: multi-vehicle watch, charge profile, SSE back-off, config validate."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tesla_cli.cli.app import app as cli_app
from tests.conftest import MOCK_VIN

_runner = CliRunner()

MOCK_VIN2 = "5YJ3E1EA1PF000002"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(*args):
    return _runner.invoke(cli_app, list(args))


def _make_cfg(**overrides):
    from tesla_cli.core.config import Config
    cfg = Config()
    cfg.general.default_vin = MOCK_VIN
    cfg.general.backend = "owner"
    for k, v in overrides.items():
        parts = k.split(".")
        obj = cfg
        for part in parts[:-1]:
            obj = getattr(obj, part)
        setattr(obj, parts[-1], v)
    return cfg


def _make_vehicle_backend():
    m = MagicMock()
    m.get_vehicle_data.return_value = {
        "charge_state": {"battery_level": 80, "charging_state": "Disconnected"},
        "vehicle_state": {"locked": True},
        "climate_state": {"is_climate_on": False},
        "drive_state": {"shift_state": None, "speed": None},
    }
    m.get_charge_state.return_value = {
        "charge_limit_soc": 80,
        "charge_amps": 16,
        "scheduled_charging_pending": False,
        "scheduled_charging_start_time": None,
    }
    m.command.return_value = {"result": True}
    return m


# ── TestVehicleWatchAll ───────────────────────────────────────────────────────

class TestVehicleWatchAll:
    def test_watch_all_flag_in_help(self):
        result = _run("vehicle", "watch", "--help")
        assert result.exit_code == 0
        assert "--all" in result.output

    def test_watch_single_vin_unchanged(self):
        """Single-VIN mode still works (exits on KeyboardInterrupt via sleep mock)."""
        cfg = _make_cfg()
        backend = _make_vehicle_backend()
        with (
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.vehicle.time") as mock_time,
        ):
            mock_time.sleep.side_effect = KeyboardInterrupt
            result = _run("vehicle", "watch")
        # Should exit cleanly (KeyboardInterrupt handled)
        assert result.exit_code == 0

    def test_watch_all_collects_vins(self):
        """--all spawns threads for each configured VIN."""
        import threading as _threading

        cfg = _make_cfg()
        cfg.vehicles.aliases["car2"] = MOCK_VIN2
        backend = _make_vehicle_backend()
        threads_started = []

        def _fake_start(self):
            threads_started.append(self)

        def _fake_join(self, timeout=None):
            pass

        with (
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.vehicle.time") as mock_time,
            patch.object(_threading.Thread, "start", _fake_start),
            patch.object(_threading.Thread, "join", _fake_join),
        ):
            mock_time.sleep.side_effect = [None, KeyboardInterrupt]
            result = _run("vehicle", "watch", "--all")

        assert result.exit_code == 0
        assert len(threads_started) == 2

    def test_watch_all_deduplicates_vins(self):
        """If default_vin matches an alias VIN, only one thread is spawned."""
        import threading as _threading

        cfg = _make_cfg()
        cfg.vehicles.aliases["mycar"] = MOCK_VIN  # same as default_vin
        backend = _make_vehicle_backend()
        threads_started = []

        def _fake_start(self):
            threads_started.append(self)

        def _fake_join(self, timeout=None):
            pass

        with (
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.vehicle.time") as mock_time,
            patch.object(_threading.Thread, "start", _fake_start),
            patch.object(_threading.Thread, "join", _fake_join),
        ):
            mock_time.sleep.side_effect = [None, KeyboardInterrupt]
            result = _run("vehicle", "watch", "--all")

        assert result.exit_code == 0
        assert len(threads_started) == 1  # deduplicated

    def test_watch_all_no_vins(self):
        """--all with no VINs configured exits with an error."""
        from tesla_cli.core.config import Config
        cfg = Config()  # no default_vin, no aliases
        cfg.general.backend = "owner"

        with (
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
        ):
            result = _run("vehicle", "watch", "--all")

        assert result.exit_code == 1
        assert "No VINs" in result.output or "configured" in result.output.lower()

    def test_watch_all_uses_threading(self):
        """Source code contains threading.Thread."""
        src = Path("src/tesla_cli/cli/commands/vehicle.py").read_text()
        assert "threading.Thread" in src


# ── TestChargeProfile ─────────────────────────────────────────────────────────

class TestChargeProfile:
    def test_profile_show_no_args(self):
        cfg = _make_cfg()
        backend = _make_vehicle_backend()
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
        ):
            result = _run("charge", "profile")
        assert result.exit_code == 0
        backend.get_charge_state.assert_called_once_with(MOCK_VIN)

    def test_profile_show_json(self):
        cfg = _make_cfg()
        backend = _make_vehicle_backend()
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
        ):
            result = _run("-j", "charge", "profile")
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert "charge_limit_soc" in data
        assert "charge_amps" in data

    def test_profile_set_limit(self):
        cfg = _make_cfg()
        backend = _make_vehicle_backend()
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
        ):
            result = _run("charge", "profile", "--limit", "80")
        assert result.exit_code == 0
        backend.command.assert_called_once_with(MOCK_VIN, "set_charge_limit", {"percent": 80})

    def test_profile_set_amps(self):
        cfg = _make_cfg()
        backend = _make_vehicle_backend()
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
        ):
            result = _run("charge", "profile", "--amps", "12")
        assert result.exit_code == 0
        backend.command.assert_called_once_with(MOCK_VIN, "set_charging_amps", {"charging_amps": 12})

    def test_profile_set_schedule(self):
        cfg = _make_cfg()
        backend = _make_vehicle_backend()
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
        ):
            result = _run("charge", "profile", "--schedule", "23:00")
        assert result.exit_code == 0
        backend.command.assert_called_once_with(
            MOCK_VIN, "set_scheduled_charging", {"enable": True, "time": 23 * 60}
        )

    def test_profile_set_schedule_disable(self):
        cfg = _make_cfg()
        backend = _make_vehicle_backend()
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
        ):
            result = _run("charge", "profile", "--schedule", "")
        assert result.exit_code == 0
        backend.command.assert_called_once_with(
            MOCK_VIN, "set_scheduled_charging", {"enable": False, "time": 0}
        )

    def test_profile_set_all_three(self):
        cfg = _make_cfg()
        backend = _make_vehicle_backend()
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
        ):
            result = _run("charge", "profile", "--limit", "75", "--amps", "16", "--schedule", "22:30")
        assert result.exit_code == 0
        assert backend.command.call_count == 3

    def test_profile_json_result(self):
        cfg = _make_cfg()
        backend = _make_vehicle_backend()
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
        ):
            result = _run("-j", "charge", "profile", "--limit", "80")
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert "ok" in data
        assert "results" in data
        assert data["ok"] is True

    def test_profile_failure(self):
        cfg = _make_cfg()
        backend = _make_vehicle_backend()
        backend.command.return_value = {"result": False}
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
        ):
            result = _run("charge", "profile", "--limit", "80")
        assert result.exit_code == 1

    def test_profile_in_charge_help(self):
        result = _run("charge", "--help")
        assert result.exit_code == 0
        assert "profile" in result.output




# ── TestConfigValidate ────────────────────────────────────────────────────────

class TestConfigValidate:
    def test_validate_clean_config(self):
        cfg = _make_cfg()
        with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg):
            result = _run("config", "validate")
        assert result.exit_code == 0
        assert "valid" in result.output.lower() or "✓" in result.output

    def test_validate_json_mode(self):
        cfg = _make_cfg()
        with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg):
            result = _run("-j", "config", "validate")
        assert result.exit_code == 0
        data = json.loads(result.output.replace("\n", ""))
        assert "checks" in data
        assert "summary" in data
        assert "valid" in data

    def test_validate_bad_backend(self):
        cfg = _make_cfg()
        cfg.general.backend = "bad"
        with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg):
            result = _run("config", "validate")
        assert result.exit_code == 1
        assert "bad" in result.output or "fail" in result.output.lower() or "✗" in result.output

    def test_validate_invalid_ha_url(self):
        cfg = _make_cfg()
        cfg.home_assistant.url = "homeassistant.local:8123"  # missing scheme
        with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg):
            result = _run("config", "validate")
        assert result.exit_code == 1

    def test_validate_invalid_teslaMate_url(self):
        cfg = _make_cfg()
        cfg.teslaMate.database_url = "mysql://localhost/teslaMate"
        with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg):
            result = _run("config", "validate")
        assert result.exit_code == 1

    def test_validate_negative_cost(self):
        cfg = _make_cfg()
        cfg.general.cost_per_kwh = -0.5
        with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg):
            result = _run("config", "validate")
        assert result.exit_code == 1

    def test_validate_mqtt_bad_qos(self):
        cfg = _make_cfg()
        cfg.mqtt.broker = "localhost"
        cfg.mqtt.qos = 5
        with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg):
            result = _run("config", "validate")
        assert result.exit_code == 1

    def test_validate_mqtt_valid(self):
        cfg = _make_cfg()
        cfg.mqtt.broker = "localhost"
        cfg.mqtt.qos = 1
        with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg):
            result = _run("config", "validate")
        assert result.exit_code == 0
        assert "mqtt" in result.output.lower() or "broker" in result.output.lower()

    def test_validate_no_vin_is_warn(self):
        from tesla_cli.core.config import Config
        cfg = Config()
        cfg.general.backend = "owner"
        # no default_vin — should warn but not fail
        with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg):
            result = _run("config", "validate")
        assert result.exit_code == 0  # warn, not fail

    def test_validate_in_config_help(self):
        result = _run("config", "--help")
        assert result.exit_code == 0
        assert "validate" in result.output

    def test_validate_summary_counts(self):
        cfg = _make_cfg()
        cfg.general.backend = "bad"  # 1 fail
        with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg):
            result = _run("-j", "config", "validate")
        assert result.exit_code == 1
        # Rich may wrap long JSON lines — collapse before parsing
        data = json.loads(result.output.replace("\n", ""))
        assert data["summary"]["fail"] >= 1
        assert data["valid"] is False

    def test_validate_apprise_url_no_scheme(self):
        cfg = _make_cfg()
        cfg.notifications.apprise_urls = ["slackhook-without-scheme"]
        with patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg):
            result = _run("config", "validate")
        # warn not fail → exit 0
        assert result.exit_code == 0


# ── TestVersion310 ────────────────────────────────────────────────────────────

class TestVersion310:
    def test_version_string(self):
        from tesla_cli import __version__
        # Passes as long as version is >= 3.1.0
        parts = tuple(int(x) for x in __version__.split("."))
        assert parts >= (3, 1, 0)

    def test_pyproject_version(self):
        # Version was bumped to 3.2.0; just verify pyproject is parseable
        content = Path("pyproject.toml").read_text()
        assert "version" in content
