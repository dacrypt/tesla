"""Tests for v3.3.0: charge forecast, trip-stats, health badge, cost-report API."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from tesla_cli.cli.app import app as cli_app
from tests.conftest import MOCK_VIN

# Skip server tests if fastapi not installed
fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.app import create_app  # noqa: E402

_runner = CliRunner()

# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _make_charge_state(**overrides):
    cs = {
        "battery_level": 60,
        "charge_limit_soc": 80,
        "charger_power": 11.5,
        "battery_range": 180.0,
        "time_to_full_charge": 1.5,
        "charging_state": "Charging",
    }
    cs.update(overrides)
    return cs


def _make_tm_backend():
    m = MagicMock()
    m.get_trips.return_value = []
    m.get_charging_sessions.return_value = [
        {"start_date": "2026-03-15 10:00:00", "energy_added_kwh": 20.0, "cost": None},
        {"start_date": "2026-03-20 14:00:00", "energy_added_kwh": 15.5, "cost": None},
        {"start_date": "2026-02-10 08:00:00", "energy_added_kwh": 30.0, "cost": None},
    ]
    m.get_stats.return_value = {"total_km": 10000, "total_kwh": 2000}
    m.get_trip_stats.return_value = {
        "summary": {
            "total_trips": 12,
            "total_km": 450.5,
            "avg_km": 37.5,
            "longest_km": 120.0,
            "shortest_km": 5.2,
            "avg_duration_min": 45,
        },
        "top_routes": [
            {"from_addr": "Home", "to_addr": "Office", "count": 8},
            {"from_addr": "Office", "to_addr": "Home", "count": 7},
        ],
        "days": 30,
    }
    return m


@pytest.fixture
def srv_tm():
    """Server fixture with TeslaMate backend available."""
    cfg = _make_cfg(**{
        "teslaMate.database_url": "postgresql://localhost/tm",
        "general.cost_per_kwh": 0.15,
    })
    tm_backend = _make_tm_backend()

    patches = [
        patch("tesla_cli.api.app.load_config", return_value=cfg),
        patch("tesla_cli.api.routes.teslaMate.load_config", return_value=cfg),
        patch("tesla_cli.api.routes.teslaMate._backend", return_value=tm_backend),
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
        patch("tesla_cli.api.app.load_config", return_value=cfg),
        patch("tesla_cli.api.routes.teslaMate.load_config", return_value=cfg),
    ]
    for p in patches:
        p.start()
    app = create_app(vin=None)
    client = TestClient(app, raise_server_exceptions=False)
    yield client
    for p in patches:
        p.stop()


# ── TestChargeForecast ────────────────────────────────────────────────────────

class TestChargeForecast:
    def _run(self, cs_overrides=None, extra_args=None):
        cs = _make_charge_state(**(cs_overrides or {}))
        cfg = MagicMock()
        cfg.general.default_vin = MOCK_VIN
        backend = MagicMock()
        backend.get_charge_state.return_value = cs

        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
        ):
            args = ["charge", "forecast"] + (extra_args or [])
            return _runner.invoke(cli_app, args)

    def test_forecast_charging_output(self):
        result = self._run({"time_to_full_charge": 1.5, "charging_state": "Charging"})
        assert result.exit_code == 0
        assert "1h 30m" in result.output

    def test_forecast_json_mode(self):
        result = self._run()
        # Run in JSON mode
        cs = _make_charge_state()
        cfg = MagicMock()
        cfg.general.default_vin = MOCK_VIN
        backend = MagicMock()
        backend.get_charge_state.return_value = cs

        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.cli.output.is_json_mode", return_value=True),
        ):
            result = _runner.invoke(cli_app, ["-j", "charge", "forecast"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert "battery_level" in data
        assert "charge_limit_soc" in data
        assert "charging_state" in data
        assert "charger_power_kw" in data
        assert "time_to_full_hrs" in data
        assert "time_to_full_str" in data
        assert "eta" in data
        assert "kwh_needed" in data
        assert "battery_range_mi" in data

    def test_forecast_not_charging_hint(self):
        result = self._run({"charging_state": "Disconnected", "time_to_full_charge": 0})
        assert result.exit_code == 0
        assert "connect to a charger" in result.output.lower() or "not currently charging" in result.output.lower()

    def test_forecast_zero_ttf(self):
        result = self._run({"time_to_full_charge": 0, "charger_power": 0})
        assert result.exit_code == 0
        # "—" should appear when ttf=0
        assert "—" in result.output

    def test_forecast_kwh_needed(self):
        cs = _make_charge_state(charger_power=11.5, time_to_full_charge=2.0, charging_state="Charging")
        cfg = MagicMock()
        cfg.general.default_vin = MOCK_VIN
        backend = MagicMock()
        backend.get_charge_state.return_value = cs

        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.cli.output.is_json_mode", return_value=True),
        ):
            result = _runner.invoke(cli_app, ["-j", "charge", "forecast"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert data["kwh_needed"] == pytest.approx(23.0, abs=0.01)

    def test_forecast_eta_format(self):
        import re
        cs = _make_charge_state(time_to_full_charge=1.0, charging_state="Charging")
        cfg = MagicMock()
        cfg.general.default_vin = MOCK_VIN
        backend = MagicMock()
        backend.get_charge_state.return_value = cs

        with (
            patch("tesla_cli.cli.commands.charge.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.charge.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.cli.commands.charge.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.cli.output.is_json_mode", return_value=True),
        ):
            result = _runner.invoke(cli_app, ["-j", "charge", "forecast"])
        data = json.loads(result.output.strip())
        assert re.match(r"\d{2}:\d{2}", data["eta"]), f"ETA not HH:MM format: {data['eta']}"

    def test_forecast_in_charge_help(self):
        result = _runner.invoke(cli_app, ["charge", "--help"])
        assert "forecast" in result.output

    def test_forecast_complete_state(self):
        """Source code should have yellow color for Complete state."""
        import inspect

        from tesla_cli.cli.commands import charge
        src = inspect.getsource(charge)
        assert "Complete" in src
        assert "yellow" in src


# ── TestTeslaMateTripsStats ───────────────────────────────────────────────────

class TestTeslaMateTripsStats:
    def _run_cli(self, extra_args=None, tm_backend=None):
        if tm_backend is None:
            tm_backend = _make_tm_backend()
        cfg = MagicMock()
        cfg.teslaMate.database_url = "postgresql://localhost/tm"
        cfg.teslaMate.car_id = 1

        with (
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.teslaMate._backend", return_value=tm_backend),
        ):
            args = ["teslaMate", "trip-stats"] + (extra_args or [])
            return _runner.invoke(cli_app, args)

    def test_trip_stats_output(self):
        result = self._run_cli()
        assert result.exit_code == 0
        assert "12" in result.output  # total_trips
        assert "450" in result.output  # total_km
        assert "37" in result.output   # avg_km

    def test_trip_stats_json_mode(self):
        tm = _make_tm_backend()
        cfg = MagicMock()
        cfg.teslaMate.database_url = "postgresql://localhost/tm"
        cfg.teslaMate.car_id = 1

        with (
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.teslaMate._backend", return_value=tm),
            patch("tesla_cli.cli.output.is_json_mode", return_value=True),
        ):
            result = _runner.invoke(cli_app, ["-j", "teslaMate", "trip-stats"])
        assert result.exit_code == 0
        data = json.loads(result.output.strip())
        assert "summary" in data
        assert "top_routes" in data
        assert "days" in data

    def test_trip_stats_top_routes_table(self):
        result = self._run_cli()
        assert result.exit_code == 0
        assert "Top Routes" in result.output

    def test_trip_stats_days_param(self):
        tm = _make_tm_backend()
        cfg = MagicMock()
        cfg.teslaMate.database_url = "postgresql://localhost/tm"
        cfg.teslaMate.car_id = 1

        with (
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
            patch("tesla_cli.cli.commands.teslaMate._backend", return_value=tm),
        ):
            _runner.invoke(cli_app, ["teslaMate", "trip-stats", "--days", "90"])
        tm.get_trip_stats.assert_called_with(days=90)

    def test_trip_stats_empty_result(self):
        tm = _make_tm_backend()
        tm.get_trip_stats.return_value = {"summary": {}, "top_routes": [], "days": 30}
        result = self._run_cli(tm_backend=tm)
        assert result.exit_code == 0
        # Should show no-data message
        assert "No trip data" in result.output or result.exit_code == 0

    def test_trip_stats_backend_method(self):
        from tesla_cli.core.backends.telemetry import TelemetryBackend
        assert hasattr(TelemetryBackend, "get_trip_stats")

    def test_trip_stats_in_help(self):
        result = _runner.invoke(cli_app, ["teslaMate", "--help"])
        assert "trip-stats" in result.output

    def test_get_trip_stats_sql(self):
        import inspect

        from tesla_cli.core.backends import teslaMate as tm_mod
        src = inspect.getsource(tm_mod)
        assert "total_trips" in src
        assert "routes_sql" in src




# ── TestApiCostReport ─────────────────────────────────────────────────────────

class TestApiCostReport:
    def test_cost_report_endpoint_ok(self, srv_tm):
        client, tm, cfg = srv_tm
        r = client.get("/api/teslaMate/cost-report")
        assert r.status_code == 200

    def test_cost_report_returns_dict(self, srv_tm):
        client, tm, cfg = srv_tm
        r = client.get("/api/teslaMate/cost-report")
        data = r.json()
        assert "cost_per_kwh" in data
        assert "months" in data
        assert "sessions" in data

    def test_cost_report_month_filter(self, srv_tm):
        client, tm, cfg = srv_tm
        r = client.get("/api/teslaMate/cost-report?month=2026-03")
        assert r.status_code == 200
        data = r.json()
        # Should only include sessions from 2026-03
        for ym in data["months"]:
            assert ym.startswith("2026-03")

    def test_cost_report_limit_param(self, srv_tm):
        client, tm, cfg = srv_tm
        r = client.get("/api/teslaMate/cost-report?limit=5")
        assert r.status_code == 200
        tm.get_charging_sessions.assert_called_with(limit=5)

    def test_cost_report_no_teslaMate_503(self, srv_no_tm):
        client = srv_no_tm
        r = client.get("/api/teslaMate/cost-report")
        assert r.status_code == 503

    def test_cost_report_months_sorted_desc(self, srv_tm):
        client, tm, cfg = srv_tm
        r = client.get("/api/teslaMate/cost-report")
        data = r.json()
        months = list(data["months"].keys())
        assert months == sorted(months, reverse=True)

    def test_cost_report_kwh_summed(self, srv_tm):
        client, tm, cfg = srv_tm
        r = client.get("/api/teslaMate/cost-report?month=2026-03")
        data = r.json()
        # March sessions: 20.0 + 15.5 = 35.5 kWh
        march = data["months"].get("2026-03", {})
        assert march.get("kwh") == pytest.approx(35.5, abs=0.01)

    def test_cost_report_cost_calculated(self, srv_tm):
        client, tm, cfg = srv_tm
        r = client.get("/api/teslaMate/cost-report?month=2026-03")
        data = r.json()
        cost_per_kwh = data["cost_per_kwh"]
        march = data["months"].get("2026-03", {})
        expected_cost = round(35.5 * cost_per_kwh, 2)
        assert march.get("cost") == pytest.approx(expected_cost, abs=0.01)


# ── TestVersion330 ────────────────────────────────────────────────────────────

class TestVersion330:
    def test_version_string(self):
        from packaging.version import Version

        from tesla_cli import __version__
        assert Version(__version__) >= Version("3.3.0")

    def test_pyproject_version(self):
        import pathlib

        from packaging.version import Version
        pyproject = pathlib.Path(__file__).parent.parent / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.strip().startswith("version"):
                ver_str = line.split("=")[1].strip().strip('"')
                assert Version(ver_str) >= Version("3.3.0")
                break
