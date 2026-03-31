"""Tests for v3.4.0: charging-locations, health-check, charging animation, trip-stats API."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tesla_cli.app import app as cli_app
from tests.conftest import MOCK_VIN

# Skip server tests if fastapi not installed
fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.server.app import create_app  # noqa: E402

_runner = CliRunner()

# ── Helpers ───────────────────────────────────────────────────────────────────


def _run(*args):
    return _runner.invoke(cli_app, list(args))


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


def _make_tm_backend():
    m = MagicMock()
    m.get_charging_locations.return_value = [
        {
            "location": "Home",
            "sessions": 45,
            "total_kwh": 360.5,
            "avg_kwh_per_session": 8.0,
            "last_visit": "2026-03-30 22:00:00",
        },
        {
            "location": "Supercharger - Downtown",
            "sessions": 12,
            "total_kwh": 480.0,
            "avg_kwh_per_session": 40.0,
            "last_visit": "2026-03-25 14:30:00",
        },
    ]
    m.get_trip_stats.return_value = {
        "summary": {
            "total_trips": 18,
            "total_km": 540.0,
            "avg_km": 30.0,
            "longest_km": 150.0,
            "shortest_km": 3.5,
            "avg_duration_min": 38,
        },
        "top_routes": [
            {"from_addr": "Home", "to_addr": "Office", "count": 10},
        ],
        "days": 30,
    }
    return m


def _make_vehicle_data(**cs_overrides):
    cs = {
        "battery_level": 72,
        "charge_limit_soc": 80,
        "charging_state": "Disconnected",
        "charger_power": 0,
    }
    cs.update(cs_overrides)
    return {
        "charge_state": cs,
        "vehicle_state": {
            "locked": True,
            "car_version": "2024.38.6",
            "software_update": {},
            "sentry_mode": True,
            "odometer": 12345.6,
            "tpms_pressure_fl": 2.9,
            "tpms_pressure_fr": 2.9,
            "tpms_pressure_rl": 2.8,
            "tpms_pressure_rr": 2.8,
        },
        "drive_state": {},
        "climate_state": {},
    }


@pytest.fixture
def srv_tm():
    """Server fixture with TeslaMate backend available."""
    cfg = _make_cfg(**{"teslaMate.database_url": "postgresql://localhost/tm"})
    tm_backend = _make_tm_backend()

    patches = [
        patch("tesla_cli.server.app.load_config", return_value=cfg),
        patch("tesla_cli.server.routes.teslaMate.load_config", return_value=cfg),
        patch("tesla_cli.backends.teslaMate.TeslaMateBacked", return_value=tm_backend),
    ]
    for p in patches:
        p.start()
    app = create_app(vin=None)
    client = TestClient(app, raise_server_exceptions=False)
    yield client, tm_backend, cfg
    for p in patches:
        p.stop()


@pytest.fixture
def srv_no_tm():
    """Server fixture with NO TeslaMate configured."""
    cfg = _make_cfg()

    patches = [
        patch("tesla_cli.server.app.load_config", return_value=cfg),
        patch("tesla_cli.server.routes.teslaMate.load_config", return_value=cfg),
    ]
    for p in patches:
        p.start()
    app = create_app(vin=None)
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    for p in patches:
        p.stop()


# ── TestChargingLocations ─────────────────────────────────────────────────────

class TestChargingLocations:
    def _run_cmd(self, tm_mock, extra_args=None):
        cfg = _make_cfg(**{"teslaMate.database_url": "postgresql://localhost/tm"})
        with patch("tesla_cli.commands.teslaMate.load_config", return_value=cfg), \
             patch("tesla_cli.backends.teslaMate.TeslaMateBacked", return_value=tm_mock):
            return _run("teslaMate", "charging-locations", *(extra_args or []))

    def test_charging_locations_output(self):
        tm = _make_tm_backend()
        result = self._run_cmd(tm)
        assert result.exit_code == 0
        assert "Home" in result.output
        assert "Sessions" in result.output or "sessions" in result.output.lower()
        assert "kWh" in result.output or "kwh" in result.output.lower()

    def test_charging_locations_json(self):
        tm = _make_tm_backend()
        cfg = _make_cfg(**{"teslaMate.database_url": "postgresql://localhost/tm"})
        with patch("tesla_cli.commands.teslaMate.load_config", return_value=cfg), \
             patch("tesla_cli.backends.teslaMate.TeslaMateBacked", return_value=tm):
            result = _run("-j", "teslaMate", "charging-locations")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 2
        assert "location" in data[0]
        assert "sessions" in data[0]
        assert "total_kwh" in data[0]
        assert "avg_kwh_per_session" in data[0]

    def test_charging_locations_days_param(self):
        tm = _make_tm_backend()
        self._run_cmd(tm, ["--days", "365"])
        tm.get_charging_locations.assert_called_with(days=365, limit=10)

    def test_charging_locations_limit_param(self):
        tm = _make_tm_backend()
        self._run_cmd(tm, ["--limit", "5"])
        tm.get_charging_locations.assert_called_with(days=90, limit=5)

    def test_charging_locations_empty(self):
        tm = _make_tm_backend()
        tm.get_charging_locations.return_value = []
        result = self._run_cmd(tm)
        assert result.exit_code == 0
        assert "No charging sessions" in result.output or "no" in result.output.lower()

    def test_charging_locations_in_help(self):
        result = _run("teslaMate", "--help")
        assert "charging-locations" in result.output

    def test_charging_locations_backend_method(self):
        from tesla_cli.backends.teslaMate import TeslaMateBacked
        assert hasattr(TeslaMateBacked, "get_charging_locations")

    def test_charging_locations_sql(self):
        src = Path(__file__).parent.parent / "src" / "tesla_cli" / "backends" / "teslaMate.py"
        text = src.read_text()
        assert "charge_energy_added" in text
        assert "GROUP BY" in text


# ── TestVehicleHealthCheck ─────────────────────────────────────────────────────

class TestVehicleHealthCheck:
    def _run_health(self, data_overrides=None, cs_overrides=None, extra_args=None):
        data = _make_vehicle_data(**(cs_overrides or {}))
        if data_overrides:
            for section, vals in data_overrides.items():
                if isinstance(vals, dict):
                    data.setdefault(section, {}).update(vals)
                else:
                    data[section] = vals
        cfg = _make_cfg()
        backend = MagicMock()
        backend.get_vehicle_data.return_value = data
        with patch("tesla_cli.commands.vehicle.load_config", return_value=cfg), \
             patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=backend), \
             patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN):
            return _run("vehicle", "health-check", *(extra_args or []))

    def test_health_check_output(self):
        result = self._run_health()
        assert result.exit_code == 0
        assert "Vehicle Health" in result.output
        assert "Battery" in result.output
        assert "Firmware" in result.output

    def test_health_check_json_mode(self):
        cfg = _make_cfg()
        backend = MagicMock()
        backend.get_vehicle_data.return_value = _make_vehicle_data()
        with patch("tesla_cli.commands.vehicle.load_config", return_value=cfg), \
             patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=backend), \
             patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN):
            result = _run("-j", "vehicle", "health-check")
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "vin" in data
        assert "checks" in data
        assert isinstance(data["checks"], list)
        check = data["checks"][0]
        assert "name" in check
        assert "status" in check
        assert "value" in check
        assert "detail" in check

    def test_health_check_battery_ok(self):
        cfg = _make_cfg()
        backend = MagicMock()
        data = _make_vehicle_data(battery_level=72)
        backend.get_vehicle_data.return_value = data
        with patch("tesla_cli.commands.vehicle.load_config", return_value=cfg), \
             patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=backend), \
             patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN):
            result = _run("-j", "vehicle", "health-check")
        data_out = json.loads(result.output)
        batt = next(c for c in data_out["checks"] if c["name"] == "Battery level")
        assert batt["status"] == "ok"

    def test_health_check_battery_warn(self):
        cfg = _make_cfg()
        backend = MagicMock()
        data = _make_vehicle_data(battery_level=15)
        backend.get_vehicle_data.return_value = data
        with patch("tesla_cli.commands.vehicle.load_config", return_value=cfg), \
             patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=backend), \
             patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN):
            result = _run("-j", "vehicle", "health-check")
        data_out = json.loads(result.output)
        batt = next(c for c in data_out["checks"] if c["name"] == "Battery level")
        assert batt["status"] == "warn"

    def test_health_check_battery_error(self):
        cfg = _make_cfg()
        backend = MagicMock()
        data = _make_vehicle_data(battery_level=5)
        backend.get_vehicle_data.return_value = data
        with patch("tesla_cli.commands.vehicle.load_config", return_value=cfg), \
             patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=backend), \
             patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN):
            result = _run("-j", "vehicle", "health-check")
        data_out = json.loads(result.output)
        batt = next(c for c in data_out["checks"] if c["name"] == "Battery level")
        assert batt["status"] == "error"

    def test_health_check_charge_limit_warn(self):
        cfg = _make_cfg()
        backend = MagicMock()
        data = _make_vehicle_data(charge_limit_soc=100)
        backend.get_vehicle_data.return_value = data
        with patch("tesla_cli.commands.vehicle.load_config", return_value=cfg), \
             patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=backend), \
             patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN):
            result = _run("-j", "vehicle", "health-check")
        data_out = json.loads(result.output)
        chk = next(c for c in data_out["checks"] if c["name"] == "Charge limit")
        assert chk["status"] == "warn"

    def test_health_check_firmware_ok(self):
        cfg = _make_cfg()
        backend = MagicMock()
        data = _make_vehicle_data()
        data["vehicle_state"]["software_update"] = {}
        backend.get_vehicle_data.return_value = data
        with patch("tesla_cli.commands.vehicle.load_config", return_value=cfg), \
             patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=backend), \
             patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN):
            result = _run("-j", "vehicle", "health-check")
        data_out = json.loads(result.output)
        fw = next(c for c in data_out["checks"] if c["name"] == "Firmware")
        assert fw["status"] == "ok"

    def test_health_check_locked_warn(self):
        cfg = _make_cfg()
        backend = MagicMock()
        data = _make_vehicle_data()
        data["vehicle_state"]["locked"] = False
        backend.get_vehicle_data.return_value = data
        with patch("tesla_cli.commands.vehicle.load_config", return_value=cfg), \
             patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=backend), \
             patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN):
            result = _run("-j", "vehicle", "health-check")
        data_out = json.loads(result.output)
        lock = next(c for c in data_out["checks"] if c["name"] == "Doors locked")
        assert lock["status"] == "warn"

    def test_health_check_tyre_low_warn(self):
        cfg = _make_cfg()
        backend = MagicMock()
        data = _make_vehicle_data()
        data["vehicle_state"]["tpms_pressure_fl"] = 2.1
        backend.get_vehicle_data.return_value = data
        with patch("tesla_cli.commands.vehicle.load_config", return_value=cfg), \
             patch("tesla_cli.commands.vehicle.get_vehicle_backend", return_value=backend), \
             patch("tesla_cli.commands.vehicle.resolve_vin", return_value=MOCK_VIN):
            result = _run("-j", "vehicle", "health-check")
        data_out = json.loads(result.output)
        tyre = next(c for c in data_out["checks"] if c["name"] == "Tyre pressure")
        assert tyre["status"] == "warn"
        assert "FL" in tyre["detail"]

    def test_health_check_in_vehicle_help(self):
        result = _run("vehicle", "--help")
        assert "health-check" in result.output


# ── TestDashboardChargingAnim ─────────────────────────────────────────────────

class TestDashboardChargingAnim:
    @pytest.fixture(autouse=True)
    def _load_html(self):
        html_path = Path(__file__).parent.parent / "src" / "tesla_cli" / "server" / "static" / "index.html"
        self.html = html_path.read_text()

    def test_charge_pulse_animation_css(self):
        assert "charge-pulse" in self.html

    def test_ring_fg_charging_class(self):
        assert "ring-fg.charging" in self.html

    def test_charge_rate_row_element(self):
        assert 'id="charge-rate-row"' in self.html

    def test_charge_eta_row_element(self):
        assert 'id="charge-eta-row"' in self.html

    def test_charging_class_added_in_js(self):
        assert "classList.add('charging')" in self.html

    def test_charging_class_removed_in_js(self):
        assert "classList.remove('charging')" in self.html


# ── TestApiTripStats ──────────────────────────────────────────────────────────

class TestApiTripStats:
    def test_trip_stats_endpoint_ok(self, srv_tm):
        client, tm_backend, cfg = srv_tm
        resp = client.get("/api/teslaMate/trip-stats")
        assert resp.status_code == 200

    def test_trip_stats_returns_dict(self, srv_tm):
        client, tm_backend, cfg = srv_tm
        resp = client.get("/api/teslaMate/trip-stats")
        data = resp.json()
        assert "summary" in data
        assert "top_routes" in data
        assert "days" in data

    def test_trip_stats_days_param(self, srv_tm):
        client, tm_backend, cfg = srv_tm
        resp = client.get("/api/teslaMate/trip-stats?days=7")
        assert resp.status_code == 200
        tm_backend.get_trip_stats.assert_called_with(days=7)

    def test_trip_stats_no_teslaMate_503(self, srv_no_tm):
        client = srv_no_tm
        resp = client.get("/api/teslaMate/trip-stats")
        assert resp.status_code == 503

    def test_trip_stats_backend_error_502(self, srv_tm):
        client, tm_backend, cfg = srv_tm
        tm_backend.get_trip_stats.side_effect = RuntimeError("DB gone")
        resp = client.get("/api/teslaMate/trip-stats")
        assert resp.status_code == 502

    def test_trip_stats_summary_has_fields(self, srv_tm):
        client, tm_backend, cfg = srv_tm
        resp = client.get("/api/teslaMate/trip-stats")
        summary = resp.json()["summary"]
        assert "total_trips" in summary
        assert "total_km" in summary
        assert "avg_km" in summary

    def test_trip_stats_top_routes_is_list(self, srv_tm):
        client, tm_backend, cfg = srv_tm
        resp = client.get("/api/teslaMate/trip-stats")
        assert isinstance(resp.json()["top_routes"], list)

    def test_trip_stats_default_days_30(self, srv_tm):
        client, tm_backend, cfg = srv_tm
        resp = client.get("/api/teslaMate/trip-stats")
        assert resp.status_code == 200
        tm_backend.get_trip_stats.assert_called_with(days=30)


# ── TestVersion340 ────────────────────────────────────────────────────────────

class TestVersion340:
    def test_version_string(self):
        from packaging.version import Version

        import tesla_cli
        assert Version(tesla_cli.__version__) >= Version("3.4.0")

    def test_pyproject_version(self):
        from packaging.version import Version
        pyproject = Path(__file__).parent.parent / "pyproject.toml"
        text = pyproject.read_text()
        for line in text.splitlines():
            if line.strip().startswith("version"):
                ver_str = line.split("=")[1].strip().strip('"')
                assert Version(ver_str) >= Version("3.4.0")
                break
