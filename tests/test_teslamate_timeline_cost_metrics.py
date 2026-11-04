"""Tests for v2.9.0: TeslaMate timeline, cost-report, Prometheus metrics, dashboard theme toggle."""

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


def _make_vehicle_backend(battery_level=80, range_miles=250.0, odometer=12345.0):
    m = MagicMock()
    m.get_vehicle_data.return_value = {
        "charge_state": {
            "battery_level": battery_level,
            "battery_range": range_miles,
            "charge_limit_soc": 90,
            "charger_power": 11,
            "charge_energy_added": 15.5,
        },
        "drive_state": {
            "speed": 0,
            "latitude": 37.4219,
            "longitude": -122.0840,
        },
        "vehicle_state": {
            "odometer": odometer,
            "locked": True,
            "sentry_mode": False,
        },
    }
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
            "value": 25.3,
            "detail": "Supercharger",
        },
        {
            "type": "ota",
            "start_date": "2026-03-03 02:00:00",
            "end_date": "2026-03-03 02:30:00",
            "value": None,
            "detail": "2024.26.1",
        },
    ]
    m.get_charging_sessions.return_value = [
        {
            "id": 1,
            "start_date": "2026-03-01 10:00:00",
            "end_date": "2026-03-01 11:00:00",
            "energy_added_kwh": 30.5,
            "cost": None,
            "start_battery_level": 20,
            "end_battery_level": 80,
            "location": "Home",
        },
        {
            "id": 2,
            "start_date": "2026-02-15 14:00:00",
            "end_date": "2026-02-15 14:30:00",
            "energy_added_kwh": 15.0,
            "cost": None,
            "start_battery_level": 40,
            "end_battery_level": 70,
            "location": "Supercharger",
        },
    ]
    return m


# ── Tests: TeslaMate Timeline ─────────────────────────────────────────────────


class TestTeslaMateTimeline:
    def _mock_backend(self, m):
        return patch("tesla_cli.cli.commands.teslaMate._backend", return_value=m)

    def test_timeline_rich_output(self):
        m = _make_tm_backend()
        with self._mock_backend(m):
            r = _run("teslaMate", "timeline")
        assert r.exit_code == 0
        assert "Timeline" in r.output or "trip" in r.output

    def test_timeline_json_mode(self):
        m = _make_tm_backend()
        with self._mock_backend(m):
            r = _run("-j", "teslaMate", "timeline")
        assert r.exit_code == 0
        data = json.loads(r.output)
        assert isinstance(data, list)
        assert len(data) == 3

    def test_timeline_json_has_type_field(self):
        m = _make_tm_backend()
        with self._mock_backend(m):
            r = _run("-j", "teslaMate", "timeline")
        data = json.loads(r.output)
        types = {ev["type"] for ev in data}
        assert "trip" in types
        assert "charge" in types
        assert "ota" in types

    def test_timeline_empty_result(self):
        m = _make_tm_backend()
        m.get_timeline.return_value = []
        with self._mock_backend(m):
            r = _run("teslaMate", "timeline")
        assert r.exit_code == 0
        assert "No events" in r.output

    def test_timeline_empty_json(self):
        m = _make_tm_backend()
        m.get_timeline.return_value = []
        with self._mock_backend(m):
            r = _run("-j", "teslaMate", "timeline")
        assert r.exit_code == 0
        data = json.loads(r.output)
        assert data == []

    def test_timeline_days_option(self):
        m = _make_tm_backend()
        with self._mock_backend(m):
            r = _run("teslaMate", "timeline", "--days", "7")
        assert r.exit_code == 0
        m.get_timeline.assert_called_once_with(days=7)

    def test_timeline_default_days(self):
        m = _make_tm_backend()
        with self._mock_backend(m):
            _run("teslaMate", "timeline")
        m.get_timeline.assert_called_once_with(days=30)

    def test_timeline_short_days_flag(self):
        m = _make_tm_backend()
        with self._mock_backend(m):
            _run("teslaMate", "timeline", "-d", "14")
        m.get_timeline.assert_called_once_with(days=14)

    def test_timeline_rich_shows_trip(self):
        m = _make_tm_backend()
        with self._mock_backend(m):
            r = _run("teslaMate", "timeline")
        assert "trip" in r.output

    def test_timeline_rich_shows_charge(self):
        m = _make_tm_backend()
        with self._mock_backend(m):
            r = _run("teslaMate", "timeline")
        assert "charge" in r.output

    def test_timeline_rich_shows_ota(self):
        m = _make_tm_backend()
        with self._mock_backend(m):
            r = _run("teslaMate", "timeline")
        assert "ota" in r.output

    def test_timeline_rich_shows_summary_counts(self):
        m = _make_tm_backend()
        with self._mock_backend(m):
            r = _run("teslaMate", "timeline")
        # Should show counts like "1 trips · 1 charges · 1 OTA updates"
        assert "trips" in r.output
        assert "charges" in r.output

    def test_timeline_duration_computed(self):
        """Duration column should show non-empty values for events with start+end."""
        m = _make_tm_backend()
        with self._mock_backend(m):
            r = _run("teslaMate", "timeline")
        # 45 minute trip should appear as "45m"
        assert "45m" in r.output

    def test_timeline_duration_hours(self):
        """90-minute charge should show as 1h 30m."""
        m = _make_tm_backend()
        with self._mock_backend(m):
            r = _run("teslaMate", "timeline")
        # 90 min = 1h 30m
        assert "1h 30m" in r.output

    def test_timeline_ota_value_dash(self):
        """OTA events should show '—' in value column."""
        m = _make_tm_backend()
        with self._mock_backend(m):
            r = _run("teslaMate", "timeline")
        assert "—" in r.output


# ── Tests: TeslaMate Cost Report ──────────────────────────────────────────────


class TestTeslaMateCostReport:
    def _mock_backend(self, m):
        return patch("tesla_cli.cli.commands.teslaMate._backend", return_value=m)

    def _make_cfg_with_cost(self, cost=0.25):
        cfg = _make_cfg(**{"general.cost_per_kwh": cost})
        return cfg

    def test_cost_report_rich_output(self):
        m = _make_tm_backend()
        cfg = self._make_cfg_with_cost(0.25)
        with (
            self._mock_backend(m),
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
        ):
            r = _run("teslaMate", "cost-report")
        assert r.exit_code == 0

    def test_cost_report_json_mode(self):
        m = _make_tm_backend()
        cfg = self._make_cfg_with_cost(0.25)
        with (
            self._mock_backend(m),
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
        ):
            r = _run("-j", "teslaMate", "cost-report")
        assert r.exit_code == 0
        data = json.loads(r.output)
        assert "cost_per_kwh" in data
        assert "months" in data
        assert "sessions" in data

    def test_cost_report_json_cost_per_kwh(self):
        m = _make_tm_backend()
        cfg = self._make_cfg_with_cost(0.30)
        with (
            self._mock_backend(m),
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
        ):
            r = _run("-j", "teslaMate", "cost-report")
        data = json.loads(r.output)
        assert data["cost_per_kwh"] == 0.30

    def test_cost_report_json_month_grouping(self):
        m = _make_tm_backend()
        cfg = self._make_cfg_with_cost(0.25)
        with (
            self._mock_backend(m),
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
        ):
            r = _run("-j", "teslaMate", "cost-report")
        data = json.loads(r.output)
        months = data["months"]
        # Two sessions in different months
        assert "2026-03" in months
        assert "2026-02" in months

    def test_cost_report_json_kwh_totals(self):
        m = _make_tm_backend()
        cfg = self._make_cfg_with_cost(0.25)
        with (
            self._mock_backend(m),
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
        ):
            r = _run("-j", "teslaMate", "cost-report")
        data = json.loads(r.output)
        assert data["months"]["2026-03"]["kwh"] == 30.5
        assert data["months"]["2026-02"]["kwh"] == 15.0

    def test_cost_report_json_cost_calculation(self):
        m = _make_tm_backend()
        cfg = self._make_cfg_with_cost(0.10)
        with (
            self._mock_backend(m),
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
        ):
            r = _run("-j", "teslaMate", "cost-report")
        data = json.loads(r.output)
        # 30.5 kWh * 0.10 = 3.05
        assert abs(data["months"]["2026-03"]["cost"] - 3.05) < 0.01

    def test_cost_report_json_sessions_count(self):
        m = _make_tm_backend()
        cfg = self._make_cfg_with_cost(0.25)
        with (
            self._mock_backend(m),
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
        ):
            r = _run("-j", "teslaMate", "cost-report")
        data = json.loads(r.output)
        assert data["sessions"] == 2

    def test_cost_report_month_filter(self):
        m = _make_tm_backend()
        cfg = self._make_cfg_with_cost(0.25)
        with (
            self._mock_backend(m),
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
        ):
            r = _run("-j", "teslaMate", "cost-report", "--month", "2026-03")
        data = json.loads(r.output)
        assert "2026-03" in data["months"]
        assert "2026-02" not in data["months"]
        assert data["sessions"] == 1

    def test_cost_report_no_sessions(self):
        m = _make_tm_backend()
        m.get_charging_sessions.return_value = []
        cfg = self._make_cfg_with_cost(0.25)
        with (
            self._mock_backend(m),
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
        ):
            r = _run("teslaMate", "cost-report")
        assert r.exit_code == 0
        assert "No charging sessions" in r.output

    def test_cost_report_limit_passed_to_backend(self):
        m = _make_tm_backend()
        cfg = self._make_cfg_with_cost(0.25)
        with (
            self._mock_backend(m),
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
        ):
            _run("teslaMate", "cost-report", "--limit", "50")
        m.get_charging_sessions.assert_called_once_with(limit=50)

    def test_cost_report_default_limit(self):
        m = _make_tm_backend()
        cfg = self._make_cfg_with_cost(0.25)
        with (
            self._mock_backend(m),
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
        ):
            _run("teslaMate", "cost-report")
        m.get_charging_sessions.assert_called_once_with(limit=100)

    def test_cost_report_zero_cost_per_kwh(self):
        m = _make_tm_backend()
        cfg = self._make_cfg_with_cost(0.0)
        with (
            self._mock_backend(m),
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
        ):
            r = _run("teslaMate", "cost-report")
        assert r.exit_code == 0

    def test_cost_report_rich_shows_total(self):
        m = _make_tm_backend()
        cfg = self._make_cfg_with_cost(0.25)
        with (
            self._mock_backend(m),
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
        ):
            r = _run("teslaMate", "cost-report")
        assert "Total" in r.output

    def test_cost_report_rich_shows_kwh(self):
        m = _make_tm_backend()
        cfg = self._make_cfg_with_cost(0.25)
        with (
            self._mock_backend(m),
            patch("tesla_cli.cli.commands.teslaMate.load_config", return_value=cfg),
        ):
            r = _run("teslaMate", "cost-report")
        assert "kWh" in r.output


# ── Tests: Prometheus /api/metrics endpoint ───────────────────────────────────


class TestApiMetrics:
    @pytest.fixture
    def srv(self):
        cfg = _make_cfg()
        backend = _make_vehicle_backend()
        app = create_app(vin=None)

        patches = [
            patch("tesla_cli.api.app.load_config", return_value=cfg),
            patch("tesla_cli.api.app.resolve_vin", return_value=MOCK_VIN),
            patch("tesla_cli.api.app.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.api.routes.vehicle.load_config", return_value=cfg),
            patch("tesla_cli.api.routes.vehicle.get_vehicle_backend", return_value=backend),
            patch("tesla_cli.api.routes.vehicle.resolve_vin", return_value=MOCK_VIN),
        ]
        for p in patches:
            p.start()
        client = TestClient(app, raise_server_exceptions=False)
        yield client, backend, cfg
        for p in patches:
            p.stop()

    def test_metrics_200(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/metrics")
        assert r.status_code == 200

    def test_metrics_content_type(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/metrics")
        assert "text/plain" in r.headers["content-type"]

    def test_metrics_prometheus_version(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/metrics")
        assert "0.0.4" in r.headers["content-type"]

    def test_metrics_battery_level_line(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/metrics")
        assert "tesla_battery_level" in r.text

    def test_metrics_battery_range_line(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/metrics")
        assert "tesla_battery_range" in r.text

    def test_metrics_odometer_line(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/metrics")
        assert "tesla_odometer" in r.text

    def test_metrics_vin_label_present(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/metrics")
        assert f'vin="{MOCK_VIN}"' in r.text

    def test_metrics_has_help_line(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/metrics")
        assert "# HELP tesla_battery_level" in r.text

    def test_metrics_has_type_line(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/metrics")
        assert "# TYPE tesla_battery_level gauge" in r.text

    def test_metrics_battery_value_correct(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/metrics")
        # battery_level is 80
        assert "tesla_battery_level" in r.text
        assert "80.0" in r.text

    def test_metrics_locked_value(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/metrics")
        assert "tesla_locked" in r.text

    def test_metrics_sentry_mode_value(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/metrics")
        assert "tesla_sentry_mode" in r.text

    def test_metrics_nan_for_missing_value(self, srv):
        """When vehicle data has missing fields, NaN is returned."""
        client, backend, cfg = srv
        backend.get_vehicle_data.return_value = {
            "charge_state": {},
            "drive_state": {},
            "vehicle_state": {},
        }
        r = client.get("/api/metrics")
        assert r.status_code == 200
        assert "NaN" in r.text

    def test_metrics_stale_on_error(self, srv):
        """When backend raises, endpoint still returns 200 with NaN values."""
        client, backend, cfg = srv
        backend.get_vehicle_data.side_effect = Exception("vehicle asleep")
        r = client.get("/api/metrics")
        assert r.status_code == 200
        assert "NaN" in r.text

    def test_metrics_charge_limit_line(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/metrics")
        assert "tesla_charge_limit" in r.text

    def test_metrics_charger_power_line(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/metrics")
        assert "tesla_charger_power" in r.text

    def test_metrics_speed_line(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/metrics")
        assert "tesla_speed" in r.text

    def test_metrics_lat_lon_lines(self, srv):
        client, backend, cfg = srv
        r = client.get("/api/metrics")
        assert "tesla_latitude" in r.text
        assert "tesla_longitude" in r.text


# ── Tests: Version ────────────────────────────────────────────────────────────


class TestVersion290:
    def test_version_string(self):
        from tesla_cli import __version__

        assert __version__ >= "2.9.0"

    def test_version_in_cli_output(self):
        r = _run("--version")
        assert "tesla-cli" in r.output.lower() or any(c.isdigit() for c in r.output)
