"""Security hardening of the self-hosted API server.

Covers: session cookies, read-only key role, CSRF (cross-site) blocking,
DNS-rebinding Host guard, public health probe, command allowlist,
``tesla serve`` refusing to expose an unauthenticated API, and 0600 config.
"""

from __future__ import annotations

import os
import stat
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from tesla_cli.api.app import create_app  # noqa: E402
from tesla_cli.api.auth import SESSION_COOKIE, session_token  # noqa: E402
from tesla_cli.api.command_policy import is_command_allowed  # noqa: E402
from tesla_cli.core.config import Config  # noqa: E402
from tests.conftest import MOCK_VIN, run_cli  # noqa: E402

CONTROL = "control-key-0123456789"
READ = "read-only-key-0123456789"


def _cfg(api_key: str = "", read_only_key: str = "", **server) -> Config:
    cfg = Config()
    cfg.general.default_vin = MOCK_VIN
    cfg.server.api_key = api_key
    cfg.server.read_only_key = read_only_key
    for k, v in server.items():
        setattr(cfg.server, k, v)
    return cfg


@pytest.fixture
def make_client(monkeypatch):
    monkeypatch.delenv("TESLA_API_KEY", raising=False)
    monkeypatch.delenv("TESLA_READ_ONLY_KEY", raising=False)
    started: list = []

    def _make(cfg: Config) -> tuple[TestClient, MagicMock]:
        backend = MagicMock()
        backend.command.return_value = {"result": True}
        backend.get_vehicle_data.return_value = {"vin": MOCK_VIN}
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
        started.extend(patches)
        app = create_app(vin=None)
        return TestClient(app, raise_server_exceptions=False), backend

    yield _make
    for p in started:
        p.stop()


# ── Public endpoints ──────────────────────────────────────────────────────────


def test_health_is_public_for_docker_healthcheck(make_client):
    client, _ = make_client(_cfg(CONTROL))
    assert client.get("/api/health").status_code == 200


def test_deep_health_requires_auth(make_client):
    client, _ = make_client(_cfg(CONTROL))
    assert client.get("/api/health?deep=true").status_code == 401


def test_openapi_docs_require_auth(make_client):
    client, _ = make_client(_cfg(CONTROL))
    assert client.get("/api/openapi.json").status_code == 401


# ── Session cookie ────────────────────────────────────────────────────────────


def test_session_status_reports_auth_required(make_client):
    client, _ = make_client(_cfg(CONTROL))
    body = client.get("/api/session").json()
    assert body == {"auth_required": True, "authenticated": False, "role": None}


def test_session_status_without_key(make_client):
    client, _ = make_client(_cfg())
    body = client.get("/api/session").json()
    assert body["auth_required"] is False and body["authenticated"] is True


def test_login_wrong_key_rejected(make_client):
    client, _ = make_client(_cfg(CONTROL))
    r = client.post("/api/session", json={"key": "nope"})
    assert r.status_code == 401
    assert SESSION_COOKIE not in r.cookies


def test_login_sets_httponly_cookie_not_raw_key(make_client):
    client, _ = make_client(_cfg(CONTROL))
    r = client.post("/api/session", json={"key": CONTROL})
    assert r.status_code == 200
    assert r.json()["role"] == "control"
    set_cookie = r.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "SameSite=strict" in set_cookie or "samesite=strict" in set_cookie.lower()
    assert CONTROL not in set_cookie
    assert session_token(CONTROL) in set_cookie


def test_cookie_authenticates_followup_requests(make_client):
    client, _ = make_client(_cfg(CONTROL))
    assert client.get("/api/status").status_code == 401
    client.post("/api/session", json={"key": CONTROL})
    assert client.get("/api/status").status_code == 200
    assert client.get("/api/session").json()["authenticated"] is True


def test_logout_clears_cookie(make_client):
    client, _ = make_client(_cfg(CONTROL))
    client.post("/api/session", json={"key": CONTROL})
    client.delete("/api/session")
    client.cookies.clear()
    assert client.get("/api/status").status_code == 401


def test_forged_cookie_rejected(make_client):
    client, _ = make_client(_cfg(CONTROL))
    client.cookies.set(SESSION_COOKIE, "deadbeef")
    assert client.get("/api/status").status_code == 401


def test_non_ascii_key_does_not_crash(make_client):
    client, _ = make_client(_cfg(CONTROL))
    r = client.post("/api/session", json={"key": "clave-ñ-🚗"})
    assert r.status_code == 401


# ── Read-only role ────────────────────────────────────────────────────────────


def test_read_only_key_can_read(make_client):
    client, _ = make_client(_cfg(CONTROL, READ))
    assert client.get("/api/status", headers={"X-API-Key": READ}).status_code == 200


def test_read_only_key_cannot_command(make_client):
    client, backend = make_client(_cfg(CONTROL, READ))
    r = client.post(
        "/api/vehicle/command",
        json={"command": "door_unlock"},
        headers={"X-API-Key": READ},
    )
    assert r.status_code == 403
    backend.command.assert_not_called()


def test_read_only_session_cookie_role(make_client):
    client, backend = make_client(_cfg(CONTROL, READ))
    assert client.post("/api/session", json={"key": READ}).json()["role"] == "read"
    assert client.post("/api/vehicle/command", json={"command": "honk_horn"}).status_code == 403
    backend.command.assert_not_called()


def test_control_key_can_command(make_client):
    client, backend = make_client(_cfg(CONTROL, READ))
    r = client.post(
        "/api/vehicle/command",
        json={"command": "honk_horn"},
        headers={"X-API-Key": CONTROL},
    )
    assert r.status_code == 200
    backend.command.assert_called_once_with(MOCK_VIN, "honk_horn")


# ── CSRF ──────────────────────────────────────────────────────────────────────


def test_cross_site_post_blocked_without_key(make_client):
    """A malicious page must not be able to unlock the car via localhost."""
    client, backend = make_client(_cfg())
    r = client.post(
        "/api/vehicle/command",
        json={"command": "door_unlock"},
        headers={"Origin": "https://evil.example"},
    )
    assert r.status_code == 403
    backend.command.assert_not_called()


def test_sec_fetch_site_cross_site_blocked(make_client):
    client, backend = make_client(_cfg())
    r = client.post(
        "/api/vehicle/command",
        json={"command": "door_unlock"},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert r.status_code == 403
    backend.command.assert_not_called()


def test_null_origin_blocked(make_client):
    client, _ = make_client(_cfg())
    r = client.post(
        "/api/vehicle/command", json={"command": "honk_horn"}, headers={"Origin": "null"}
    )
    assert r.status_code == 403


def test_same_origin_post_allowed(make_client):
    client, backend = make_client(_cfg())
    r = client.post(
        "/api/vehicle/command",
        json={"command": "honk_horn"},
        headers={"Origin": "http://testserver"},
    )
    assert r.status_code == 200


def test_configured_cors_origin_allowed(make_client):
    client, _ = make_client(_cfg(cors_origins=["https://dash.home.lan"]))
    r = client.post(
        "/api/vehicle/command",
        json={"command": "honk_horn"},
        headers={"Origin": "https://dash.home.lan", "Sec-Fetch-Site": "cross-site"},
    )
    assert r.status_code == 200


def test_cross_site_get_not_blocked_by_csrf(make_client):
    client, _ = make_client(_cfg())
    r = client.get("/api/status", headers={"Origin": "https://evil.example"})
    assert r.status_code == 200


# ── DNS rebinding ─────────────────────────────────────────────────────────────


def test_foreign_host_rejected_without_key(make_client):
    client, _ = make_client(_cfg())
    r = client.get("/api/status", headers={"Host": "attacker.example"})
    assert r.status_code == 403
    assert "Host not allowed" in r.json()["detail"]


@pytest.mark.parametrize("host", ["localhost:8080", "127.0.0.1:8080", "[::1]:8080"])
def test_loopback_hosts_allowed_without_key(make_client, host):
    client, _ = make_client(_cfg())
    assert client.get("/api/status", headers={"Host": host}).status_code == 200


def test_allowed_hosts_config(make_client):
    client, _ = make_client(_cfg(allowed_hosts=["tesla.home.lan"]))
    r = client.get("/api/status", headers={"Host": "tesla.home.lan:8080"})
    assert r.status_code == 200


def test_any_host_allowed_with_key(make_client):
    client, _ = make_client(_cfg(CONTROL))
    r = client.get("/api/status", headers={"Host": "192.168.1.20:8080", "X-API-Key": CONTROL})
    assert r.status_code == 200


# ── Command allowlist ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "command",
    ["erase_user_data", "set_pin_to_drive", "reset_valet_pin", "schedule_software_update"],
)
def test_dangerous_commands_blocked(make_client, command):
    client, backend = make_client(_cfg())
    r = client.post("/api/vehicle/command", json={"command": command})
    assert r.status_code == 403
    backend.command.assert_not_called()


@pytest.mark.parametrize("command", ["../../users/me", "door_lock/../x", "DOOR_LOCK", ""])
def test_malformed_command_names_blocked(command):
    assert not is_command_allowed(command)


def test_extra_allowed_commands(make_client):
    client, backend = make_client(_cfg(extra_allowed_commands=["set_vehicle_name"]))
    r = client.post(
        "/api/vehicle/command",
        json={"command": "set_vehicle_name", "params": {"vehicle_name": "Rayo"}},
    )
    assert r.status_code == 200
    backend.command.assert_called_once_with(MOCK_VIN, "set_vehicle_name", vehicle_name="Rayo")


def test_dashboard_commands_are_allowlisted():
    """Every raw command the React dashboard sends must stay allowed."""
    for cmd in [
        "actuate_trunk",
        "adjust_volume",
        "auto_conditioning_start",
        "auto_conditioning_stop",
        "charge_port_door_close",
        "charge_port_door_open",
        "door_lock",
        "door_unlock",
        "flash_lights",
        "guest_mode",
        "honk_horn",
        "media_next_track",
        "media_prev_track",
        "media_toggle_playback",
        "remote_seat_heater_request",
        "remote_start_drive",
        "remote_steering_wheel_heater_request",
        "set_bioweapon_mode",
        "set_climate_keeper_mode",
        "set_preconditioning_max",
        "set_scheduled_charging",
        "set_sentry_mode",
        "set_temps",
        "set_valet_mode",
        "share",
        "speed_limit_activate",
        "speed_limit_deactivate",
        "window_control",
    ]:
        assert is_command_allowed(cmd), cmd


# ── tesla serve guard ─────────────────────────────────────────────────────────


def test_is_loopback_host():
    from tesla_cli.cli.commands.serve import _is_loopback_host

    assert _is_loopback_host("127.0.0.1")
    assert _is_loopback_host("localhost")
    assert _is_loopback_host("::1")
    assert not _is_loopback_host("0.0.0.0")
    assert not _is_loopback_host("192.168.1.10")
    assert not _is_loopback_host("tesla.home.lan")


def test_ensure_api_key_generates_and_persists(monkeypatch):
    from tesla_cli.cli.commands import serve as serve_mod

    monkeypatch.delenv("TESLA_API_KEY", raising=False)
    cfg = _cfg()
    saved: list[Config] = []
    with (
        patch("tesla_cli.core.config.load_config", return_value=cfg),
        patch("tesla_cli.core.config.save_config", side_effect=saved.append),
    ):
        serve_mod._ensure_api_key()
    assert len(cfg.server.api_key) >= 32
    assert saved and saved[0].server.api_key == cfg.server.api_key


def test_ensure_api_key_keeps_existing(monkeypatch):
    from tesla_cli.cli.commands import serve as serve_mod

    monkeypatch.delenv("TESLA_API_KEY", raising=False)
    cfg = _cfg(CONTROL)
    with (
        patch("tesla_cli.core.config.load_config", return_value=cfg),
        patch("tesla_cli.core.config.save_config") as save,
    ):
        serve_mod._ensure_api_key()
    assert cfg.server.api_key == CONTROL
    save.assert_not_called()


def test_serve_lan_without_key_generates_key(monkeypatch):
    monkeypatch.delenv("TESLA_API_KEY", raising=False)
    cfg = _cfg()
    with (
        patch("tesla_cli.core.config.load_config", return_value=cfg),
        patch("tesla_cli.core.config.save_config"),
        patch("uvicorn.run") as run,
        patch("tesla_cli.api.app.create_app"),
    ):
        result = run_cli("serve", "--host", "0.0.0.0", "--no-open")
    assert result.exit_code == 0, result.output
    assert "API key generated" in result.output
    assert cfg.server.api_key
    run.assert_called_once()


def test_serve_lan_insecure_flag_skips_key(monkeypatch):
    monkeypatch.delenv("TESLA_API_KEY", raising=False)
    cfg = _cfg()
    with (
        patch("tesla_cli.core.config.load_config", return_value=cfg),
        patch("tesla_cli.core.config.save_config"),
        patch("uvicorn.run"),
        patch("tesla_cli.api.app.create_app"),
    ):
        result = run_cli("serve", "--host", "0.0.0.0", "--no-open", "--insecure-no-auth")
    assert result.exit_code == 0, result.output
    assert cfg.server.api_key == ""


def test_serve_api_key_rotate(monkeypatch):
    cfg = _cfg(CONTROL)
    with (
        patch("tesla_cli.core.config.load_config", return_value=cfg),
        patch("tesla_cli.core.config.save_config"),
    ):
        result = run_cli("serve", "api-key", "--rotate")
    assert result.exit_code == 0, result.output
    assert cfg.server.api_key != CONTROL
    assert cfg.server.api_key in result.output.replace("\n", "")


def test_serve_api_key_read_only_create_and_disable():
    cfg = _cfg(CONTROL)
    with (
        patch("tesla_cli.core.config.load_config", return_value=cfg),
        patch("tesla_cli.core.config.save_config"),
    ):
        assert run_cli("serve", "api-key", "--read-only", "--rotate").exit_code == 0
        assert cfg.server.read_only_key
        assert run_cli("serve", "api-key", "--read-only", "--disable").exit_code == 0
    assert cfg.server.read_only_key == ""
    assert cfg.server.api_key == CONTROL


# ── Config file permissions ───────────────────────────────────────────────────


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions")
def test_save_config_writes_owner_only(tmp_path, monkeypatch):
    from tesla_cli.core import config as config_mod

    cfg_file = tmp_path / "config.toml"
    monkeypatch.setattr(config_mod, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", cfg_file)
    cfg_file.write_text("")
    cfg_file.chmod(0o644)
    config_mod.save_config(_cfg(CONTROL))
    mode = stat.S_IMODE(cfg_file.stat().st_mode)
    assert mode == 0o600
    assert CONTROL in cfg_file.read_text()
    assert not (tmp_path / "config.toml.tmp").exists()


# ── Review follow-ups: guards, audit, static files ───────────────────────────


def test_single_flight_rejects_concurrent_run():
    from fastapi import HTTPException

    from tesla_cli.api.guards import single_flight

    with (
        single_flight("unit-test-op"),
        pytest.raises(HTTPException) as exc,
        single_flight("unit-test-op"),
    ):
        pass
    assert exc.value.status_code == 429
    with single_flight("unit-test-op"):  # released afterwards
        pass


def test_dossier_refresh_is_post_only(make_client):
    client, _ = make_client(_cfg())
    assert client.get("/api/dossier/refresh").status_code == 405


def test_audit_covers_config_routes_and_redacts(make_client, tmp_path):
    import json

    from tesla_cli.api import audit

    client, _ = make_client(_cfg())
    with (
        patch("tesla_cli.api.routes.notify.load_config", return_value=_cfg()),
        patch("tesla_cli.api.routes.notify.save_config"),
    ):
        client.post("/api/notify/add", json={"url": "tgram://SECRETTOKEN/123"})
    lines = audit.AUDIT_FILE.read_text().splitlines()
    entry = json.loads(lines[-1])
    assert entry["path"] == "/api/notify/add"
    assert entry["params"]["url"] == "***"
    assert "SECRETTOKEN" not in audit.AUDIT_FILE.read_text()


def test_audit_redacts_nested_pin(make_client):
    import json

    from tesla_cli.api import audit

    client, _ = make_client(_cfg())
    client.post(
        "/api/vehicle/command",
        json={"command": "speed_limit_activate", "params": {"pin": "1234"}},
    )
    entry = json.loads(audit.AUDIT_FILE.read_text().splitlines()[-1])
    assert entry["params"]["params"]["pin"] == "***"


def test_audit_skips_session_login(make_client):
    from tesla_cli.api import audit

    client, _ = make_client(_cfg(CONTROL))
    client.post("/api/session", json={"key": CONTROL})
    assert not audit.AUDIT_FILE.exists() or CONTROL not in audit.AUDIT_FILE.read_text()


def test_static_files_cannot_escape_ui_dist(tmp_path):
    """A sibling directory sharing the ui_dist prefix must not be served."""
    from tesla_cli.api import app as app_mod

    src = (app_mod.Path(app_mod.__file__).parent / "app.py").read_text()
    assert "is_relative_to(_ui_dist.resolve())" in src
    assert "startswith(str(_ui_dist" not in src


def test_browser_login_ignores_password_field(make_client):
    from tesla_cli.api.routes.auth import BrowserLoginRequest

    req = BrowserLoginRequest(email="a@b.c", password="hunter2", mfa_code="123456")
    assert not hasattr(req, "password")
    assert req.mfa_code == "123456"
