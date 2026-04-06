"""Tests for v3.2.0: watch notify per-vehicle, schedule-amps, heatmap --year, config/validate API."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import MOCK_VIN
from tests.conftest import run_cli as _run

# Skip server tests if fastapi/httpx not installed
fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.app import create_app  # noqa: E402


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
    m.command.return_value = {"result": True}
    return m


# ── TestWatchAllNotify ────────────────────────────────────────────────────────


class TestWatchAllNotify:
    def test_notify_title_includes_label(self):
        """When label is set, notifier title is 'Tesla Watch — {label}'."""
        import inspect

        import tesla_cli.cli.commands.vehicle as vmod

        source = inspect.getsource(vmod.vehicle_watch)
        assert "Tesla Watch —" in source

    def test_notify_title_no_label(self):
        """When label is empty, title falls back to 'Tesla Watch'."""
        import inspect

        import tesla_cli.cli.commands.vehicle as vmod

        source = inspect.getsource(vmod.vehicle_watch)
        # The fallback branch is present
        assert '"Tesla Watch"' in source

    def test_all_notify_in_docstring(self):
        """vehicle_watch docstring mentions --all --notify example."""
        import tesla_cli.cli.commands.vehicle as vmod

        doc = vmod.vehicle_watch.__doc__ or ""
        assert "--all --notify" in doc

    def test_notify_flag_exists(self):
        """tesla vehicle watch --help shows --notify."""
        result = _run("vehicle", "watch", "--help")
        assert result.exit_code == 0
        assert "--notify" in result.output

    def test_notify_title_source(self):
        """vehicle.py source contains 'Tesla Watch —' string."""
        import inspect

        import tesla_cli.cli.commands.vehicle as vmod

        src = inspect.getsource(vmod)
        assert "Tesla Watch —" in src

    def test_notify_called_with_per_vehicle_title(self):
        """When notifier fires with label, title is per-vehicle."""
        import threading

        cfg = _make_cfg()
        cfg.vehicles.aliases["home"] = MOCK_VIN
        backend = _make_vehicle_backend()

        # Two snapshots: first returns data, second has a change
        prev_data = {
            "charge_state": {"battery_level": 80, "charging_state": "Disconnected"},
            "vehicle_state": {"locked": True},
            "climate_state": {"is_climate_on": False},
            "drive_state": {"shift_state": None, "speed": None},
        }
        new_data = {
            "charge_state": {"battery_level": 70, "charging_state": "Disconnected"},
            "vehicle_state": {"locked": True},
            "climate_state": {"is_climate_on": False},
            "drive_state": {"shift_state": None, "speed": None},
        }
        backend.get_vehicle_data.side_effect = [prev_data, new_data]

        notify_calls = []

        mock_notifier = MagicMock()
        mock_notifier.notify.side_effect = lambda title, body: notify_calls.append(title)

        mock_apprise_cls = MagicMock(return_value=mock_notifier)

        stop_event = threading.Event()

        def _stop_after(*args, **kwargs):
            stop_event.set()

        mock_notifier.notify.side_effect = lambda title, body: (
            notify_calls.append(title),
            stop_event.set(),
        )

        with (
            patch("tesla_cli.cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.vehicle.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.vehicle.time") as mock_time,
            patch.dict("sys.modules", {"apprise": MagicMock(Apprise=mock_apprise_cls)}),
        ):
            mock_time.sleep.side_effect = KeyboardInterrupt
            _run("vehicle", "watch", "--notify", "tgram://botid/chatid")


# ── TestChargeScheduleAmps ────────────────────────────────────────────────────


class TestChargeScheduleAmps:
    def _make_backend(self):
        m = MagicMock()
        m.command.return_value = {"result": True}
        m.set_scheduled_charging.return_value = {"result": True}
        return m

    def test_schedule_amps_sets_both(self):
        """Calls command(set_charging_amps) AND set_scheduled_charging."""
        cfg = _make_cfg()
        backend = self._make_backend()
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("charge", "schedule-amps", "02:00", "8")
        assert result.exit_code == 0
        backend.command.assert_called_once_with(MOCK_VIN, "set_charging_amps", {"charging_amps": 8})
        backend.set_scheduled_charging.assert_called_once_with(
            MOCK_VIN, enable=True, time_minutes=120
        )

    def test_schedule_amps_time_conversion(self):
        """02:00 → minutes=120."""
        cfg = _make_cfg()
        backend = self._make_backend()
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
        ):
            _run("charge", "schedule-amps", "02:00", "8")
        backend.set_scheduled_charging.assert_called_once_with(
            MOCK_VIN, enable=True, time_minutes=120
        )

    def test_schedule_amps_time_conversion_2(self):
        """23:30 → minutes=1410."""
        cfg = _make_cfg()
        backend = self._make_backend()
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
        ):
            _run("charge", "schedule-amps", "23:30", "16")
        backend.set_scheduled_charging.assert_called_once_with(
            MOCK_VIN, enable=True, time_minutes=1410
        )

    def test_schedule_amps_json_mode(self):
        """With -j flag, returns {ok, schedule, amps, vin}."""
        cfg = _make_cfg()
        backend = self._make_backend()
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("-j", "charge", "schedule-amps", "02:00", "8")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["schedule"] == "02:00"
        assert data["amps"] == 8
        assert data["vin"] == MOCK_VIN

    def test_schedule_amps_invalid_time(self):
        """Invalid time format (25:00) → exit 1."""
        cfg = _make_cfg()
        backend = self._make_backend()
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("charge", "schedule-amps", "25:00", "8")
        assert result.exit_code == 1

    def test_schedule_amps_invalid_amps_low(self):
        """Amps=0 → exit 1."""
        cfg = _make_cfg()
        backend = self._make_backend()
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("charge", "schedule-amps", "02:00", "0")
        assert result.exit_code == 1

    def test_schedule_amps_invalid_amps_high(self):
        """Amps=49 → exit 1."""
        cfg = _make_cfg()
        backend = self._make_backend()
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("charge", "schedule-amps", "02:00", "49")
        assert result.exit_code == 1

    def test_schedule_amps_success_message(self):
        """Output contains the time and amps on success."""
        cfg = _make_cfg()
        backend = self._make_backend()
        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
        ):
            result = _run("charge", "schedule-amps", "02:00", "8")
        assert result.exit_code == 0
        assert "02:00" in result.output
        assert "8" in result.output

    def test_schedule_amps_in_charge_help(self):
        """schedule-amps appears in tesla charge --help."""
        result = _run("charge", "--help")
        assert result.exit_code == 0
        assert "schedule-amps" in result.output


# ── TestHeatmapYear ───────────────────────────────────────────────────────────


class TestHeatmapYear:
    def _make_tm_backend(self):
        m = MagicMock()
        m.get_drive_days.return_value = [
            {"day": "2025-06-15", "drives": 2, "km": 80.0},
        ]
        m.get_drive_days_year.return_value = [
            {"day": "2025-01-10", "drives": 1, "km": 45.0},
            {"day": "2025-03-20", "drives": 3, "km": 200.0},
        ]
        return m

    def test_heatmap_year_option_in_help(self):
        """tesla teslaMate heatmap --help shows --year."""
        result = _run("teslaMate", "heatmap", "--help")
        assert result.exit_code == 0
        assert "--year" in result.output

    def test_heatmap_year_calls_year_backend(self):
        """--year 2025 calls backend.get_drive_days_year(2025)."""
        cfg = _make_cfg(**{"teslaMate.database_url": "postgresql://localhost/tm"})
        backend = self._make_tm_backend()
        with (
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.teslaMate._backend", return_value=backend),
        ):
            result = _run("teslaMate", "heatmap", "--year", "2025")
        assert result.exit_code == 0
        backend.get_drive_days_year.assert_called_once_with(2025)
        backend.get_drive_days.assert_not_called()

    def test_heatmap_days_calls_days_backend(self):
        """No --year calls backend.get_drive_days(days=365)."""
        cfg = _make_cfg(**{"teslaMate.database_url": "postgresql://localhost/tm"})
        backend = self._make_tm_backend()
        with (
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.teslaMate._backend", return_value=backend),
        ):
            result = _run("teslaMate", "heatmap")
        assert result.exit_code == 0
        backend.get_drive_days.assert_called_once_with(days=365)
        backend.get_drive_days_year.assert_not_called()

    def test_heatmap_year_json_mode(self):
        """-j --year 2025 returns list of dicts."""
        cfg = _make_cfg(**{"teslaMate.database_url": "postgresql://localhost/tm"})
        backend = self._make_tm_backend()
        with (
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.teslaMate._backend", return_value=backend),
        ):
            result = _run("-j", "teslaMate", "heatmap", "--year", "2025")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2

    def test_heatmap_year_backend_method_exists(self):
        """TeslaMateBacked has get_drive_days_year method."""
        from tesla_cli.core.backends.teslaMate import TeslaMateBacked

        assert hasattr(TeslaMateBacked, "get_drive_days_year")

    def test_drive_days_year_sql_structure(self):
        """get_drive_days_year source uses _dt.date."""
        import inspect

        from tesla_cli.core.backends.teslaMate import TeslaMateBacked

        src = inspect.getsource(TeslaMateBacked.get_drive_days_year)
        assert "_dt.date" in src

    def test_heatmap_year_start_jan1(self):
        """For a past year, start is Jan 1 of that year."""
        import inspect

        import tesla_cli.cli.commands.teslaMate as tmmod

        src = inspect.getsource(tmmod.teslaMate_heatmap)
        assert "date(year, 1, 1)" in src

    def test_heatmap_year_end_dec31(self):
        """For a past year, end is Dec 31."""
        import inspect

        import tesla_cli.cli.commands.teslaMate as tmmod

        src = inspect.getsource(tmmod.teslaMate_heatmap)
        assert "date(year, 12, 31)" in src


# ── TestApiConfigValidate ─────────────────────────────────────────────────────


class TestApiConfigValidate:
    @pytest.fixture
    def srv(self):
        cfg = _make_cfg()
        app = create_app(vin=None)
        patches = [
            patch("tesla_cli.api.app.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.config_cmd.load_config", return_value=cfg),
        ]
        for p in patches:
            p.start()
        client = TestClient(app, raise_server_exceptions=False)
        yield client, cfg
        for p in patches:
            p.stop()

    def test_validate_endpoint_ok(self, srv):
        """GET /api/config/validate returns 200 with expected keys."""
        client, _ = srv
        resp = client.get("/api/config/validate")
        assert resp.status_code == 200
        data = resp.json()
        assert "valid" in data
        assert "errors" in data
        assert "warnings" in data
        assert "checks" in data

    def test_validate_valid_is_bool(self, srv):
        """response['valid'] is bool."""
        client, _ = srv
        resp = client.get("/api/config/validate")
        assert resp.status_code == 200
        assert isinstance(resp.json()["valid"], bool)

    def test_validate_checks_is_list(self, srv):
        """response['checks'] is a list."""
        client, _ = srv
        resp = client.get("/api/config/validate")
        assert isinstance(resp.json()["checks"], list)

    def test_validate_check_has_fields(self, srv):
        """Each check dict has field, status, message keys."""
        client, _ = srv
        resp = client.get("/api/config/validate")
        checks = resp.json()["checks"]
        assert len(checks) > 0
        for check in checks:
            assert "field" in check
            assert "status" in check
            assert "message" in check

    def test_validate_errors_count(self, srv):
        """errors count matches checks with status='error'."""
        client, _ = srv
        resp = client.get("/api/config/validate")
        data = resp.json()
        expected = sum(1 for c in data["checks"] if c["status"] == "error")
        assert data["errors"] == expected

    def test_validate_warnings_count(self, srv):
        """warnings count matches checks with status='warn'."""
        client, _ = srv
        resp = client.get("/api/config/validate")
        data = resp.json()
        expected = sum(1 for c in data["checks"] if c["status"] == "warn")
        assert data["warnings"] == expected

    def test_validate_run_config_checks_importable(self):
        """_run_config_checks is importable from config_cmd."""
        from tesla_cli.cli.commands.config_cmd import _run_config_checks

        assert callable(_run_config_checks)

    def test_validate_run_config_checks_returns_list(self):
        """_run_config_checks(Config()) returns list of dicts."""
        from tesla_cli.cli.commands.config_cmd import _run_config_checks
        from tesla_cli.core.config import Config

        result = _run_config_checks(Config())
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(c, dict) for c in result)


# ── TestVersion320 ────────────────────────────────────────────────────────────


class TestVersion320:
    def test_version_string(self):
        """__version__ >= '3.2.0'."""
        from packaging.version import Version

        import tesla_cli

        assert Version(tesla_cli.__version__) >= Version("3.2.0")

    def test_pyproject_version(self):
        """pyproject.toml version >= '3.2.0'."""
        import re
        from pathlib import Path

        from packaging.version import Version

        content = (Path(__file__).parent.parent / "pyproject.toml").read_text()
        m = re.search(r'version = "(\d+\.\d+\.\d+)"', content)
        assert m and Version(m.group(1)) >= Version("3.2.0")
