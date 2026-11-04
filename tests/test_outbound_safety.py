"""Automation command execution without a shell, webhook SSRF guard, URL masking."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tesla_cli.core.automation import AutomationEngine
from tesla_cli.core.models.automation import AutomationAction
from tesla_cli.core.url_safety import UnsafeUrlError, check_outbound_url, mask_secret_url

# ── command actions: no shell, per-argument substitution ─────────────────────


@pytest.fixture
def engine(tmp_path):
    return AutomationEngine(config_path=tmp_path / "automations.json")


def test_command_runs_without_shell(engine):
    action = AutomationAction(type="command", command="notify-send 'Battery {battery_level}%'")
    with patch("tesla_cli.core.automation.subprocess.run") as run:
        engine._execute_action(action, {"charge_state": {"battery_level": 42}})
    args, kwargs = run.call_args
    assert args[0] == ["notify-send", "Battery 42%"]
    assert kwargs["shell"] is False


def test_vehicle_data_cannot_inject_arguments(engine):
    """A hostile value (e.g. from a spoofed MQTT payload) stays a single argument."""
    action = AutomationAction(type="exec", command="logger {charging_state}")
    evil = "x; touch /tmp/pwned $(id)"
    with patch("tesla_cli.core.automation.subprocess.run") as run:
        engine._execute_action(action, {"charge_state": {"charging_state": evil}})
    argv = run.call_args.args[0]
    assert argv == ["logger", evil]


def test_unbalanced_quotes_do_nothing(engine):
    action = AutomationAction(type="command", command="echo 'oops")
    with patch("tesla_cli.core.automation.subprocess.run") as run:
        engine._execute_action(action, {})
    run.assert_not_called()


# ── webhook SSRF guard ───────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://[fe80::1]/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "file:///etc/passwd",
        "gopher://127.0.0.1:6379/_FLUSHALL",
        "http://0.0.0.0:8080/",
        "http:///nohost",
    ],
)
def test_blocked_webhook_urls(url):
    with pytest.raises(UnsafeUrlError):
        check_outbound_url(url, resolve=False)


@pytest.mark.parametrize(
    "url",
    [
        "http://192.168.1.10:8123/api/webhook/tesla",  # Home Assistant on the LAN
        "http://127.0.0.1:5000/hook",
        "https://hooks.example.com/abc",
    ],
)
def test_allowed_webhook_urls(url):
    assert check_outbound_url(url, resolve=False) == url


def test_hostname_resolving_to_link_local_blocked():
    fake = [(2, 1, 6, "", ("169.254.169.254", 443))]
    with (
        patch("tesla_cli.core.url_safety.socket.getaddrinfo", return_value=fake),
        pytest.raises(UnsafeUrlError),
    ):
        check_outbound_url("https://rebind.example/")


def test_engine_skips_unsafe_webhook(engine):
    action = AutomationAction(type="webhook", webhook_url="http://169.254.169.254/x")
    with patch("httpx.post") as post:
        engine._execute_action(action, {})
    post.assert_not_called()


def test_engine_posts_safe_webhook_without_redirects(engine):
    action = AutomationAction(type="webhook", webhook_url="http://192.168.1.10/hook")
    with patch("httpx.post") as post:
        engine._execute_action(action, {})
    assert post.call_args.kwargs["follow_redirects"] is False


# ── notification URL masking ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("url", "masked"),
    [
        ("tgram://123456:ABCdefSECRET/987654", "tgram://***"),
        ("ntfy://my-private-topic", "ntfy://***"),
        ("https://user:pw@hooks.example.com/abc?t=1", "https://hooks.example.com/***"),
        ("json://hass.local:8123/api/x", "json://hass.local:8123/***"),
        ("https://ntfy.sh", "https://ntfy.sh"),
    ],
)
def test_mask_secret_url(url, masked):
    out = mask_secret_url(url)
    assert out == masked
    assert "SECRET" not in out and "pw" not in out


def test_notify_list_masks_tokens():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from tesla_cli.api.app import create_app
    from tesla_cli.core.config import Config

    cfg = Config()
    cfg.notifications.apprise_urls = ["tgram://123456:ABCdefSECRET/987654"]
    cfg.notifications.enabled = True
    with (
        patch("tesla_cli.api.app.load_config", return_value=cfg),
        patch("tesla_cli.api.routes.notify.load_config", return_value=cfg),
    ):
        client = TestClient(create_app())
        r = client.get("/api/notify/list")
    assert r.status_code == 200
    assert r.json()["channels"] == ["tgram://***"]
    assert "SECRET" not in r.text


def test_api_rejects_unsafe_webhook_rule(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from tesla_cli.api.app import create_app
    from tesla_cli.core.config import Config

    cfg = Config()
    eng = AutomationEngine(config_path=tmp_path / "a.json")
    with (
        patch("tesla_cli.api.app.load_config", return_value=cfg),
        patch("tesla_cli.api.routes.automations._engine", return_value=eng),
    ):
        client = TestClient(create_app())
        r = client.post(
            "/api/automations/",
            json={
                "name": "steal",
                "trigger": {"type": "battery_below", "threshold": 20},
                "action": {"type": "webhook", "webhook_url": "http://169.254.169.254/"},
            },
        )
    assert r.status_code == 422
    assert "link-local" in r.json()["detail"]
    assert eng.rules == []
