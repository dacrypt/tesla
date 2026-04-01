"""Tests for v2.6.0: TeslaMate API, Auth middleware, Daemon, Geofence SSE."""

from __future__ import annotations

import os
import signal
from unittest.mock import MagicMock, patch

import pytest

# Skip entire module if fastapi not installed
fastapi = pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from tesla_cli.cli.app import app as cli_app  # noqa: E402
from tesla_cli.api.app import create_app  # noqa: E402
from tests.conftest import MOCK_VIN  # noqa: E402

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


def _make_backend():
    m = MagicMock()
    m.get_vehicle_data.return_value = {
        "charge_state": {"battery_level": 80},
        "drive_state": {"latitude": 37.4219, "longitude": -122.0840},
    }
    return m


def _make_tm_backend():
    m = MagicMock()
    m.get_trips.return_value = [{"id": 1, "km": 42.0}]
    m.get_charging_sessions.return_value = [{"id": 1, "kWh": 30.0}]
    m.get_stats.return_value = {"total_km": 10000, "total_kwh": 2000}
    m.get_efficiency.return_value = [{"trip_id": 1, "wh_km": 150.0}]
    m.get_drive_days.return_value = [{"date": "2026-03-01", "km": 55.0}]
    m.get_vampire_drain.return_value = {"avg_drain_pct_hr": 0.12}
    m.get_daily_energy.return_value = [{"date": "2026-03-01", "kwh": 20.0}]
    m.get_monthly_report.return_value = {"month": "2026-03", "km": 500}
    return m


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def srv():
    """Standard server fixture — no auth, owner backend."""
    cfg = _make_cfg()
    backend = _make_backend()
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


@pytest.fixture
def srv_auth():
    """Server fixture with API key configured.
    NOTE: patches must be active BEFORE create_app() so the middleware
    picks up the configured api_key from load_config().
    """
    cfg = _make_cfg(**{"server.api_key": "test-secret-key"})
    backend = _make_backend()

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
    app = create_app(vin=None)  # ← AFTER patches so middleware gets real api_key
    client = TestClient(app, raise_server_exceptions=False)
    yield client, cfg
    for p in patches:
        p.stop()


@pytest.fixture
def srv_tm():
    """Server fixture with TeslaMate backend available."""
    cfg = _make_cfg(**{"teslaMate.database_url": "postgresql://localhost/tm"})
    tm_backend = _make_tm_backend()

    patches = [
        patch("tesla_cli.api.app.load_config", return_value=cfg),
        patch("tesla_cli.api.routes.teslaMate.load_config", return_value=cfg),
        # TelemetryBackend is imported inline inside _backend(), so patch source
        patch("tesla_cli.api.routes.teslaMate._backend", return_value=tm_backend),
    ]
    for p in patches:
        p.start()
    app = create_app(vin=None)
    client = TestClient(app, raise_server_exceptions=False)
    yield client, tm_backend
    for p in patches:
        p.stop()


# ── Tests: TeslaMate API routes ───────────────────────────────────────────────

class TestTeslaMateRoutes:
    def test_trips(self, srv_tm):
        client, tm = srv_tm
        r = client.get("/api/teslaMate/trips")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_trips_with_limit(self, srv_tm):
        client, tm = srv_tm
        r = client.get("/api/teslaMate/trips?limit=5")
        assert r.status_code == 200
        tm.get_trips.assert_called_with(limit=5)

    def test_charges(self, srv_tm):
        client, tm = srv_tm
        r = client.get("/api/teslaMate/charges")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_stats(self, srv_tm):
        client, tm = srv_tm
        r = client.get("/api/teslaMate/stats")
        assert r.status_code == 200
        assert "total_km" in r.json()

    def test_efficiency(self, srv_tm):
        client, tm = srv_tm
        r = client.get("/api/teslaMate/efficiency")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_heatmap(self, srv_tm):
        client, tm = srv_tm
        r = client.get("/api/teslaMate/heatmap?days=30")
        assert r.status_code == 200
        tm.get_drive_days.assert_called_with(days=30)

    def test_vampire(self, srv_tm):
        client, tm = srv_tm
        r = client.get("/api/teslaMate/vampire")
        assert r.status_code == 200
        assert "avg_drain_pct_hr" in r.json()

    def test_daily_energy(self, srv_tm):
        client, tm = srv_tm
        r = client.get("/api/teslaMate/daily-energy")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_report(self, srv_tm):
        client, tm = srv_tm
        r = client.get("/api/teslaMate/report/2026-03")
        assert r.status_code == 200
        assert r.json()["month"] == "2026-03"

    def test_no_teslaMate_returns_503(self):
        from fastapi import HTTPException
        cfg = _make_cfg()  # no database_url / db_path
        patches = [
            patch("tesla_cli.api.app.load_config", return_value=cfg),
            patch("tesla_cli.api.routes.teslaMate.load_config", return_value=cfg),
            patch("tesla_cli.api.routes.teslaMate._backend",
                  side_effect=HTTPException(status_code=503, detail="Telemetry database not found.")),
        ]
        for p in patches:
            p.start()
        app = create_app(vin=None)
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/teslaMate/trips")
        for p in patches:
            p.stop()
        assert r.status_code == 503


# ── Tests: Auth middleware ────────────────────────────────────────────────────

class TestAuthMiddleware:
    def test_no_key_configured_allows_all(self, srv):
        """When no API key configured, all requests pass through."""
        client, _, _ = srv
        r = client.get("/api/status")
        assert r.status_code == 200

    def test_valid_key_header_passes(self, srv_auth):
        """Correct X-API-Key header allows request."""
        client, _ = srv_auth
        r = client.get("/api/status", headers={"X-API-Key": "test-secret-key"})
        assert r.status_code == 200

    def test_valid_key_query_param_passes(self, srv_auth):
        """Correct api_key query param allows request."""
        client, _ = srv_auth
        r = client.get("/api/status?api_key=test-secret-key")
        assert r.status_code == 200

    def test_missing_key_returns_401(self, srv_auth):
        """Missing API key returns 401."""
        client, _ = srv_auth
        r = client.get("/api/status")
        assert r.status_code == 401
        assert "API key" in r.json()["detail"]

    def test_wrong_key_returns_401(self, srv_auth):
        """Wrong API key returns 401."""
        client, _ = srv_auth
        r = client.get("/api/status", headers={"X-API-Key": "wrong-key"})
        assert r.status_code == 401

    def test_root_serves_ui_or_redirects(self, srv_auth):
        """/ serves the React SPA or redirects to docs."""
        client, _ = srv_auth
        r = client.get("/", follow_redirects=False)
        # 200 if ui/dist/ built, redirect if not
        assert r.status_code in (200, 301, 302, 303, 307, 308)

    def test_env_var_overrides_config(self):
        """TESLA_API_KEY env var takes precedence over config."""
        cfg = _make_cfg(**{"server.api_key": "config-key"})
        app = create_app(vin=None)
        patches = [patch("tesla_cli.api.app.load_config", return_value=cfg)]
        for p in patches:
            p.start()
        client = TestClient(app, raise_server_exceptions=False)

        with patch.dict(os.environ, {"TESLA_API_KEY": "env-key"}):
            r_wrong = client.get("/api/status", headers={"X-API-Key": "config-key"})
            r_right = client.get("/api/status", headers={"X-API-Key": "env-key"})

        for p in patches:
            p.stop()

        assert r_wrong.status_code == 401
        assert r_right.status_code == 200


# ── Tests: Geofences endpoint ─────────────────────────────────────────────────

class TestGeofencesEndpoint:
    def test_empty_geofences(self, srv):
        client, _, _ = srv
        r = client.get("/api/geofences")
        assert r.status_code == 200
        assert r.json() == []

    def test_returns_configured_zones(self):
        cfg = _make_cfg()
        cfg.geofences.zones = {
            "home": {"lat": 37.4219, "lon": -122.0840, "radius_km": 0.5},
            "work": {"lat": 37.3382, "lon": -121.8863, "radius_km": 0.3},
        }
        app = create_app(vin=None)
        patches = [patch("tesla_cli.api.app.load_config", return_value=cfg)]
        for p in patches:
            p.start()
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/geofences")
        for p in patches:
            p.stop()

        assert r.status_code == 200
        zones = r.json()
        assert len(zones) == 2
        names = {z["name"] for z in zones}
        assert names == {"home", "work"}

    def test_zone_has_expected_fields(self):
        cfg = _make_cfg()
        cfg.geofences.zones = {"home": {"lat": 1.0, "lon": 2.0, "radius_km": 0.5}}
        app = create_app(vin=None)
        patches = [patch("tesla_cli.api.app.load_config", return_value=cfg)]
        for p in patches:
            p.start()
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/geofences")
        for p in patches:
            p.stop()

        zone = r.json()[0]
        assert zone["name"] == "home"
        assert zone["lat"] == 1.0
        assert zone["lon"] == 2.0
        assert zone["radius_km"] == 0.5


# ── Tests: Haversine helper ───────────────────────────────────────────────────

class TestHaversine:
    def test_same_point_is_zero(self):
        from tesla_cli.api.app import _haversine_km
        assert _haversine_km(0, 0, 0, 0) == pytest.approx(0.0)

    def test_known_distance(self):
        from tesla_cli.api.app import _haversine_km
        # NYC (40.7128, -74.0060) to LA (34.0522, -118.2437) ≈ 3940 km
        d = _haversine_km(40.7128, -74.0060, 34.0522, -118.2437)
        assert 3900 < d < 4000

    def test_small_distance(self):
        from tesla_cli.api.app import _haversine_km
        d = _haversine_km(37.4219, -122.0840, 37.4220, -122.0841)
        assert d < 0.1  # less than 100m


# ── Tests: Auth middleware unit tests ─────────────────────────────────────────

class TestApiKeyMiddlewareUnit:
    def test_enabled_when_key_set(self):
        from tesla_cli.api.auth import ApiKeyMiddleware
        m = ApiKeyMiddleware(app=MagicMock(), api_key="mykey")
        assert m.enabled is True

    def test_disabled_when_no_key(self):
        from tesla_cli.api.auth import ApiKeyMiddleware
        m = ApiKeyMiddleware(app=MagicMock(), api_key="")
        assert m.enabled is False

    def test_env_var_overrides_empty_config(self):
        from tesla_cli.api.auth import ApiKeyMiddleware
        with patch.dict(os.environ, {"TESLA_API_KEY": "fromenv"}):
            m = ApiKeyMiddleware(app=MagicMock(), api_key="")
        assert m.enabled is True
        assert m._key == "fromenv"


# ── Tests: Config api_key field ───────────────────────────────────────────────

class TestServerConfig:
    def test_default_api_key_is_empty(self):
        from tesla_cli.core.config import ServerConfig
        sc = ServerConfig()
        assert sc.api_key == ""

    def test_default_pid_file_in_tesla_dir(self):
        from tesla_cli.core.config import ServerConfig
        sc = ServerConfig()
        assert ".tesla-cli" in sc.pid_file

    def test_config_has_server_field(self):
        from tesla_cli.core.config import Config
        cfg = Config()
        assert hasattr(cfg, "server")
        assert cfg.server.api_key == ""

    def test_auth_enabled_in_api_config(self):
        cfg = _make_cfg(**{"server.api_key": "k"})
        app = create_app(vin=None)
        patches = [patch("tesla_cli.api.app.load_config", return_value=cfg)]
        for p in patches:
            p.start()
        client = TestClient(app, raise_server_exceptions=False)
        r = client.get("/api/config", headers={"X-API-Key": "k"})
        for p in patches:
            p.stop()
        assert r.json()["auth_enabled"] is True


# ── Tests: Daemon helpers ─────────────────────────────────────────────────────

class TestDaemonHelpers:
    def test_read_pid_no_file(self, tmp_path):
        from tesla_cli.cli.commands.serve import _read_pid
        with patch("tesla_cli.cli.commands.serve._pid_file_path", return_value=tmp_path / "server.pid"):
            assert _read_pid() is None

    def test_write_and_read_pid(self, tmp_path):
        from tesla_cli.cli.commands.serve import _read_pid, _write_pid
        pf = tmp_path / "server.pid"
        with patch("tesla_cli.cli.commands.serve._pid_file_path", return_value=pf):
            _write_pid(12345)
            assert _read_pid() == 12345

    def test_clear_pid(self, tmp_path):
        from tesla_cli.cli.commands.serve import _clear_pid, _read_pid, _write_pid
        pf = tmp_path / "server.pid"
        with patch("tesla_cli.cli.commands.serve._pid_file_path", return_value=pf):
            _write_pid(99)
            _clear_pid()
            assert _read_pid() is None

    def test_is_running_own_process(self):
        from tesla_cli.cli.commands.serve import _is_running
        assert _is_running(os.getpid()) is True

    def test_is_running_dead_pid(self):
        from tesla_cli.cli.commands.serve import _is_running
        # PID 0 cannot be signalled by regular users → ProcessLookupError or PermissionError
        # Use a very high PID unlikely to exist
        assert _is_running(9999999) is False


# ── Tests: serve CLI subcommands ──────────────────────────────────────────────

class TestServeCli:
    def test_serve_status_not_running(self, tmp_path):
        pf = tmp_path / "server.pid"
        with patch("tesla_cli.cli.commands.serve._pid_file_path", return_value=pf):
            result = _runner.invoke(cli_app, ["serve", "status"])
        assert result.exit_code == 0
        assert "not running" in result.output.lower()

    def test_serve_status_running(self, tmp_path):
        pf = tmp_path / "server.pid"
        own_pid = os.getpid()
        pf.write_text(str(own_pid))
        with patch("tesla_cli.cli.commands.serve._pid_file_path", return_value=pf):
            result = _runner.invoke(cli_app, ["serve", "status"])
        assert result.exit_code == 0
        assert str(own_pid) in result.output

    def test_serve_status_json(self, tmp_path):
        import json
        pf = tmp_path / "server.pid"
        with patch("tesla_cli.cli.commands.serve._pid_file_path", return_value=pf):
            result = _runner.invoke(cli_app, ["serve", "status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["running"] is False

    def test_serve_stop_no_pid(self, tmp_path):
        pf = tmp_path / "server.pid"
        with patch("tesla_cli.cli.commands.serve._pid_file_path", return_value=pf):
            result = _runner.invoke(cli_app, ["serve", "stop"])
        assert result.exit_code != 0
        assert "no running" in result.output.lower()

    def test_serve_stop_kills_process(self, tmp_path):
        pf = tmp_path / "server.pid"
        own_pid = os.getpid()
        pf.write_text(str(own_pid))
        # Patch os.kill so we don't actually kill ourselves.
        # os.kill is called twice: once for _is_running (sig 0) and once for SIGTERM.
        with patch("tesla_cli.cli.commands.serve._pid_file_path", return_value=pf), \
             patch("os.kill") as mock_kill:
            result = _runner.invoke(cli_app, ["serve", "stop"])
        assert result.exit_code == 0
        mock_kill.assert_any_call(own_pid, signal.SIGTERM)

    def test_serve_daemon_already_running(self, tmp_path):
        pf = tmp_path / "server.pid"
        own_pid = os.getpid()
        pf.write_text(str(own_pid))
        with patch("tesla_cli.cli.commands.serve._pid_file_path", return_value=pf):
            result = _runner.invoke(cli_app, ["serve", "--daemon"])
        assert result.exit_code != 0
        assert "already running" in result.output.lower()

    def test_serve_daemon_launches_process(self, tmp_path):
        pf = tmp_path / "server.pid"
        mock_proc = MagicMock()
        mock_proc.pid = 54321
        with patch("tesla_cli.cli.commands.serve._pid_file_path", return_value=pf), \
             patch("tesla_cli.cli.commands.serve.subprocess.Popen", return_value=mock_proc), \
             patch("tesla_cli.cli.commands.serve._read_pid", return_value=None):
            result = _runner.invoke(cli_app, ["serve", "--daemon"])
        assert result.exit_code == 0
        assert "54321" in result.output
        assert pf.read_text().strip() == "54321"
