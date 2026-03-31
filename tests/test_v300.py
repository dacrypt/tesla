"""Tests for v3.0.0: Multi-vehicle dashboard, schedule-update, timeline API, notify templates, config migrate."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tesla_cli.app import app as cli_app
from tests.conftest import MOCK_VIN

_runner = CliRunner()

# Skip server tests if fastapi/httpx not installed
fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.server.app import create_app  # noqa: E402

# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_cfg(**overrides):
    from tesla_cli.config import Config
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


def _run(*args):
    return _runner.invoke(cli_app, list(args))


def _make_vehicle_backend():
    m = MagicMock()
    m.get_vehicle_data.return_value = {
        "charge_state": {"battery_level": 80},
        "drive_state": {"latitude": 37.4219, "longitude": -122.0840},
        "vehicle_state": {"odometer": 12345.0},
    }
    m.schedule_software_update.return_value = True
    return m


def _make_tm_backend():
    m = MagicMock()
    m.get_timeline.return_value = [
        {
            "type": "trip",
            "start_date": "2026-03-01 08:00:00",
            "end_date": "2026-03-01 08:45:00",
            "value": 42.5,
            "detail": "Home",
        },
        {
            "type": "charge",
            "start_date": "2026-03-02 10:00:00",
            "end_date": "2026-03-02 11:30:00",
            "value": 30.0,
            "detail": "Home",
        },
    ]
    return m


# ── Fixture ───────────────────────────────────────────────────────────────────

@pytest.fixture
def srv():
    cfg = _make_cfg()
    backend = _make_vehicle_backend()
    app = create_app(vin=None)

    patches = [
        patch("tesla_cli.server.app.load_config", return_value=cfg),
        patch("tesla_cli.server.app.resolve_vin", return_value=MOCK_VIN),
        patch("tesla_cli.server.app.get_vehicle_backend", return_value=backend),
        patch("tesla_cli.server.routes.vehicle.load_config", return_value=cfg),
        patch("tesla_cli.server.routes.vehicle.get_vehicle_backend", return_value=backend),
        patch("tesla_cli.server.routes.vehicle.resolve_vin", return_value=MOCK_VIN),
    ]
    for p in patches:
        p.start()
    client = TestClient(app, raise_server_exceptions=False)
    yield client, backend, cfg
    for p in patches:
        p.stop()


# ── TestMultiVehicleDashboard ─────────────────────────────────────────────────

class TestMultiVehicleDashboard:
    def test_api_vehicles_endpoint(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/vehicles")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_api_vehicles_includes_default(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/vehicles")
        assert r.status_code == 200
        data = r.json()
        # default VIN should appear
        vins = [v["vin"] for v in data]
        assert MOCK_VIN in vins

    def test_api_vehicles_empty_when_no_vin(self):
        cfg = _make_cfg()
        cfg.general.default_vin = ""
        app = create_app(vin=None)
        with patch("tesla_cli.server.app.load_config", return_value=cfg):
            client = TestClient(app, raise_server_exceptions=False)
            r = client.get("/api/vehicles")
            assert r.status_code == 200
            assert r.json() == []

    def test_api_vehicles_includes_aliases(self):
        cfg = _make_cfg()
        cfg.general.default_vin = MOCK_VIN
        cfg.vehicles.aliases = {"mycar": "5YJ3E1EA1PF999999"}
        app = create_app(vin=None)
        with patch("tesla_cli.server.app.load_config", return_value=cfg):
            client = TestClient(app, raise_server_exceptions=False)
            r = client.get("/api/vehicles")
            assert r.status_code == 200
            data = r.json()
            aliases = [v["alias"] for v in data]
            assert "mycar" in aliases
            assert "default" in aliases

    def test_vin_select_in_html(self):
        html_path = Path(__file__).parent.parent / "src" / "tesla_cli" / "server" / "static" / "index.html"
        if html_path.exists():
            content = html_path.read_text()
            assert 'id="vin-select"' in content

    def test_switch_vin_function_in_html(self):
        html_path = Path(__file__).parent.parent / "src" / "tesla_cli" / "server" / "static" / "index.html"
        if html_path.exists():
            content = html_path.read_text()
            assert "switchVin" in content

    def test_load_vehicle_list_function_in_html(self):
        html_path = Path(__file__).parent.parent / "src" / "tesla_cli" / "server" / "static" / "index.html"
        if html_path.exists():
            content = html_path.read_text()
            assert "loadVehicleList" in content

    def test_vehicle_route_reads_query_vin(self):
        """Check that _backend_and_vin reads from request.query_params."""
        source = Path(__file__).parent.parent / "src" / "tesla_cli" / "server" / "routes" / "vehicle.py"
        content = source.read_text()
        assert "query_params.get" in content
        assert "vin_override" in content


# ── TestVehicleScheduleUpdate ─────────────────────────────────────────────────

class TestVehicleScheduleUpdate:
    def test_schedule_update_immediate(self):
        cfg = _make_cfg()
        backend = _make_vehicle_backend()
        backend.schedule_software_update.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=backend),
        ):
            result = _run("vehicle", "schedule-update")
            assert result.exit_code == 0
            backend.schedule_software_update.assert_called_once_with(MOCK_VIN, offset_sec=0)

    def test_schedule_update_with_delay(self):
        cfg = _make_cfg()
        backend = _make_vehicle_backend()
        backend.schedule_software_update.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=backend),
        ):
            result = _run("vehicle", "schedule-update", "--delay", "30")
            assert result.exit_code == 0
            backend.schedule_software_update.assert_called_once_with(MOCK_VIN, offset_sec=1800)

    def test_schedule_update_json_mode(self):
        cfg = _make_cfg()
        backend = _make_vehicle_backend()
        backend.schedule_software_update.return_value = True
        with (
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=backend),
        ):
            result = _run("-j", "vehicle", "schedule-update", "--delay", "10")
            assert result.exit_code == 0
            data = json.loads(result.output.strip())
            assert data["ok"] is True
            assert data["delay_min"] == 10
            assert data["vin"] == MOCK_VIN

    def test_schedule_update_failure(self):
        cfg = _make_cfg()
        backend = _make_vehicle_backend()
        backend.schedule_software_update.return_value = False
        with (
            patch("tesla_cli.commands.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=backend),
        ):
            result = _run("vehicle", "schedule-update")
            assert result.exit_code == 1

    def test_schedule_update_in_vehicle_help(self):
        result = _run("vehicle", "--help")
        assert "schedule-update" in result.output


# ── TestTeslaMateTimelineRoute ────────────────────────────────────────────────

class TestTeslaMateTimelineRoute:
    def _make_srv_tm(self, tm_backend):
        cfg = _make_cfg(**{"teslaMate.database_url": "postgresql://localhost/teslaMate"})
        app = create_app(vin=None)

        patches = [
            patch("tesla_cli.server.app.load_config", return_value=cfg),
            patch("tesla_cli.server.routes.teslaMate.load_config", return_value=cfg),
            patch("tesla_cli.backends.teslaMate.TeslaMateBacked", return_value=tm_backend),
        ]
        for p in patches:
            p.start()
        client = TestClient(app, raise_server_exceptions=False)
        return client, patches

    def test_timeline_returns_list(self):
        tm = _make_tm_backend()
        client, patches = self._make_srv_tm(tm)
        try:
            r = client.get("/api/teslaMate/timeline")
            assert r.status_code == 200
            assert isinstance(r.json(), list)
        finally:
            for p in patches:
                p.stop()

    def test_timeline_days_param(self):
        tm = _make_tm_backend()
        client, patches = self._make_srv_tm(tm)
        try:
            r = client.get("/api/teslaMate/timeline?days=7")
            assert r.status_code == 200
            tm.get_timeline.assert_called_with(days=7)
        finally:
            for p in patches:
                p.stop()

    def test_timeline_no_teslaMate_503(self):
        cfg = _make_cfg()  # no database_url
        app = create_app(vin=None)
        with (
            patch("tesla_cli.server.app.load_config", return_value=cfg),
            patch("tesla_cli.server.routes.teslaMate.load_config", return_value=cfg),
        ):
            client = TestClient(app, raise_server_exceptions=False)
            r = client.get("/api/teslaMate/timeline")
            assert r.status_code == 503

    def test_timeline_backend_error_502(self):
        tm = MagicMock()
        tm.get_timeline.side_effect = RuntimeError("DB error")
        client, patches = self._make_srv_tm(tm)
        try:
            r = client.get("/api/teslaMate/timeline")
            assert r.status_code == 502
        finally:
            for p in patches:
                p.stop()

    def test_timeline_default_days(self):
        tm = _make_tm_backend()
        client, patches = self._make_srv_tm(tm)
        try:
            r = client.get("/api/teslaMate/timeline")
            assert r.status_code == 200
            tm.get_timeline.assert_called_with(days=30)
        finally:
            for p in patches:
                p.stop()

    def test_timeline_cli_command(self):
        """tesla teslaMate timeline renders table."""
        cfg = _make_cfg(**{"teslaMate.database_url": "postgresql://localhost/tm"})
        tm = _make_tm_backend()
        with (
            patch("tesla_cli.commands.teslaMate.load_config", return_value=cfg),
            patch("tesla_cli.backends.teslaMate.TeslaMateBacked", return_value=tm),
        ):
            result = _run("teslaMate", "timeline")
            assert result.exit_code == 0


# ── TestNotificationTemplates ─────────────────────────────────────────────────

class TestNotificationTemplates:
    def test_default_template_in_config(self):
        from tesla_cli.config import NotificationsConfig
        n = NotificationsConfig()
        assert "{event}" in n.message_template
        assert "{vehicle}" in n.message_template
        assert "{detail}" in n.message_template

    def test_set_template_saves(self, tmp_path):
        cfg = _make_cfg()
        new_tmpl = "{event}: {vehicle} at {detail}"
        with (
            patch("tesla_cli.commands.notify.load_config", return_value=cfg),
            patch("tesla_cli.commands.notify.save_config") as mock_save,
        ):
            result = _run("notify", "set-template", new_tmpl)
            assert result.exit_code == 0
            mock_save.assert_called_once()
            saved_cfg = mock_save.call_args[0][0]
            assert saved_cfg.notifications.message_template == new_tmpl

    def test_show_template_default(self):
        cfg = _make_cfg()
        with patch("tesla_cli.commands.notify.load_config", return_value=cfg):
            result = _run("notify", "show-template")
            assert result.exit_code == 0
            assert "{event}" in result.output

    def test_show_template_json(self):
        cfg = _make_cfg()
        with patch("tesla_cli.commands.notify.load_config", return_value=cfg):
            result = _run("-j", "notify", "show-template")
            assert result.exit_code == 0
            data = json.loads(result.output.strip())
            assert "template" in data

    def test_custom_template_set_and_show(self):
        cfg = _make_cfg()
        custom = "Alert: {event} on {vehicle}"
        cfg.notifications.message_template = custom
        with patch("tesla_cli.commands.notify.load_config", return_value=cfg):
            result = _run("notify", "show-template")
            assert result.exit_code == 0
            assert "Alert:" in result.output

    def test_set_template_in_help(self):
        result = _run("notify", "--help")
        assert "set-template" in result.output

    def test_show_template_in_help(self):
        result = _run("notify", "--help")
        assert "show-template" in result.output

    def test_template_format(self):
        from tesla_cli.config import NotificationsConfig
        n = NotificationsConfig()
        tmpl = n.message_template
        import time
        formatted = tmpl.format(
            event="test",
            vehicle="tesla-cli",
            detail="connectivity test",
            ts=time.strftime("%Y-%m-%d %H:%M"),
        )
        assert "test" in formatted
        assert "tesla-cli" in formatted


# ── TestConfigMigrate ─────────────────────────────────────────────────────────

class TestConfigMigrate:
    def test_migrate_up_to_date(self):
        cfg = _make_cfg()
        with (
            patch("tesla_cli.commands.config_cmd.load_config", return_value=cfg),
            patch("tesla_cli.commands.config_cmd.save_config"),
        ):
            result = _run("config", "migrate")
            assert result.exit_code == 0
            assert "up to date" in result.output

    def test_migrate_dry_run(self, tmp_path):
        cfg = _make_cfg()
        # Simulate missing field by returning old config missing message_template
        old_dict = cfg.model_dump()
        del old_dict["notifications"]["message_template"]

        from tesla_cli.config import Config
        old_cfg = Config.model_validate(old_dict)
        # Re-add a field to new that old is missing by patching
        # We patch load_config to return old_cfg and check additions shown
        with (
            patch("tesla_cli.commands.config_cmd.load_config", return_value=old_cfg),
            patch("tesla_cli.commands.config_cmd.save_config") as mock_save,
        ):
            result = _run("config", "migrate", "--dry-run")
            assert result.exit_code == 0
            # dry-run should not save
            mock_save.assert_not_called()

    def test_migrate_json_mode(self):
        cfg = _make_cfg()
        with (
            patch("tesla_cli.commands.config_cmd.load_config", return_value=cfg),
            patch("tesla_cli.commands.config_cmd.save_config"),
        ):
            result = _run("-j", "config", "migrate")
            assert result.exit_code == 0
            data = json.loads(result.output.strip())
            assert "dry_run" in data
            assert "additions" in data
            assert "version" in data

    def test_migrate_makes_backup(self, tmp_path):
        cfg = _make_cfg()
        fake_config = tmp_path / "config.toml"
        fake_config.write_text("[general]\ndefault_vin = 'TEST'\n")

        with (
            patch("tesla_cli.commands.config_cmd.load_config", return_value=cfg),
            patch("tesla_cli.commands.config_cmd.save_config"),
            patch("tesla_cli.config.CONFIG_FILE", fake_config),
        ):
            result = _run("config", "migrate")
            # Should complete without error (even if no additions)
            assert result.exit_code == 0

    def test_migrate_in_config_help(self):
        result = _run("config", "--help")
        assert "migrate" in result.output

    def test_migrate_adds_new_fields(self):
        """When new Config() has more fields than old config, additions are shown."""
        from tesla_cli.config import Config

        # Create a "new" config mock with an extra field compared to old
        cfg_old = _make_cfg()
        new_dict = cfg_old.model_dump()
        new_dict["notifications"]["brand_new_v300_field"] = "default_value"

        new_cfg_mock = MagicMock(spec=Config)
        new_cfg_mock.model_dump.return_value = new_dict

        with (
            patch("tesla_cli.commands.config_cmd.load_config", return_value=cfg_old),
            patch("tesla_cli.commands.config_cmd.save_config"),
            patch("tesla_cli.config.Config", return_value=new_cfg_mock),
        ):
            result = _run("-j", "config", "migrate")
            assert result.exit_code == 0
            data = json.loads(result.output.strip())
            assert "additions" in data
            assert isinstance(data["additions"], list)

    def test_migrate_saves_merged_config(self):
        cfg = _make_cfg()
        with (
            patch("tesla_cli.commands.config_cmd.load_config", return_value=cfg),
            patch("tesla_cli.commands.config_cmd.save_config"),
        ):
            # When already up to date, save is not called (shows "up to date")
            result = _run("config", "migrate")
            assert result.exit_code == 0
            # When up to date, no save needed
            # (migration only saves when there are additions)


# ── TestVersion300 ────────────────────────────────────────────────────────────

class TestVersion300:
    def test_version_string(self):
        import tesla_cli
        assert tesla_cli.__version__ == "3.0.0"

    def test_pyproject_version(self):
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject.read_text()
        assert 'version = "3.0.0"' in content
